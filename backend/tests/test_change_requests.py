from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate
from app.devices.repository import DeviceRepository
from app.devices.service import DeviceService
from app.storage.models import (
    DeviceConfigChangePayload,
    DeviceConfigChangeRequest,
    TaskStatus,
)
from tests.conftest import auth_headers, get_token


def test_viewer_cannot_submit(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.post(
        "/api/v1/change-requests",
        json={"device_id": 1, "datastore": "running", "change_summary": "test", "reason": "test"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_operator_submit_invalid_device(client: TestClient, operator_user):
    token = get_token(client, "operator1")
    resp = client.post(
        "/api/v1/change-requests",
        json={
            "device_id": 99999,
            "datastore": "running",
            "change_summary": "test",
            "config_body": "<config/>",
            "reason": "testing",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


def test_direct_execute_requires_reason(client: TestClient, approver_user):
    token = get_token(client, "approver1")
    resp = client.post(
        "/api/v1/change-requests/direct-execute",
        json={"device_id": 1, "datastore": "running", "change_summary": "test", "reason": ""},
        headers=auth_headers(token),
    )
    assert resp.status_code in (400, 422)


def test_viewer_cannot_direct_execute(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.post(
        "/api/v1/change-requests/direct-execute",
        json={
            "device_id": 1,
            "datastore": "running",
            "change_summary": "test",
            "reason": "emergency",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_operator_cannot_approve(client: TestClient, operator_user):
    token = get_token(client, "operator1")
    resp = client.post(
        "/api/v1/change-requests/1/approve",
        json={"approval_note": None},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_approval_queues_execution_task(
    client: TestClient,
    db_session: Session,
    operator_user,
    approver_user,
    monkeypatch,
):
    dispatched: list[str] = []
    monkeypatch.setattr("app.tasks.service.run_config_change.delay", dispatched.append)
    device = _create_ready_device(db_session)
    operator_token = get_token(client, "operator1")
    submit_resp = client.post(
        "/api/v1/change-requests",
        json={
            "device_id": device.id,
            "datastore": "running",
            "change_summary": "set interface description",
            "config_body": "<config><interfaces/></config>",
            "reason": "planned maintenance",
        },
        headers=auth_headers(operator_token),
    )
    assert submit_resp.status_code == 201

    approver_token = get_token(client, "approver1")
    approve_resp = client.post(
        f"/api/v1/change-requests/{submit_resp.json()['id']}/approve",
        json={"approval_note": "approved"},
        headers=auth_headers(approver_token),
    )

    assert approve_resp.status_code == 200
    body = approve_resp.json()
    assert body["status"] == "queued"
    assert body["execution_task_id"] is not None
    assert dispatched == [body["execution_task_id"]]

    task = db_session.query(TaskStatus).filter_by(task_id=body["execution_task_id"]).one()
    assert task.change_request_id == body["id"]
    assert task.actor_user_id == approver_user.id
    assert "config_body" not in task.metadata_json
    assert body["preflight_status"] == "passed"
    assert body["baseline_snapshot_id"] is not None


def test_direct_execute_creates_queued_change_request(
    client: TestClient,
    db_session: Session,
    approver_user,
    monkeypatch,
):
    dispatched: list[str] = []
    monkeypatch.setattr("app.tasks.service.run_config_change.delay", dispatched.append)
    device = _create_ready_device(db_session)
    token = get_token(client, "approver1")

    resp = client.post(
        "/api/v1/change-requests/direct-execute",
        json={
            "device_id": device.id,
            "datastore": "running",
            "change_summary": "emergency change",
            "config_body": "<config><emergency/></config>",
            "reason": "restore service",
        },
        headers=auth_headers(token),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["direct_execute"] is True
    assert body["execution_task_id"] is not None
    assert body["preflight_status"] == "passed"
    assert body["risk_summary"]["baseline_snapshot_id"] is not None
    assert dispatched == [body["execution_task_id"]]
    assert "config_body" not in str(body)


def test_submit_change_request_requires_config_body(
    client: TestClient, db_session: Session, operator_user
):
    device = _create_ready_device(db_session)
    token = get_token(client, "operator1")

    resp = client.post(
        "/api/v1/change-requests",
        json={
            "device_id": device.id,
            "datastore": "running",
            "change_summary": "missing body",
            "reason": "planned maintenance",
        },
        headers=auth_headers(token),
    )

    assert resp.status_code == 400


def test_preflight_preview_succeeds_without_creating_records(
    client: TestClient, db_session: Session, operator_user
):
    device = _create_ready_device(db_session)
    token = get_token(client, "operator1")

    resp = client.post(
        "/api/v1/change-requests/preflight",
        json={
            "device_id": device.id,
            "datastore": "running",
            "change_summary": "set interface description",
            "config_body": "<config><interfaces/></config>",
            "reason": "planned maintenance",
        },
        headers=auth_headers(token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True
    assert body["baseline_snapshot"]["content_digest"] == "sha256:baseline"
    assert body["risk_summary"]["payload"]["length"] > 0
    assert db_session.query(DeviceConfigChangeRequest).count() == 0
    assert db_session.query(TaskStatus).filter_by(task_type="device.config_change").count() == 0
    assert "interfaces" not in str(body)


def test_preflight_reports_missing_baseline_and_submit_rejects(
    client: TestClient, db_session: Session, operator_user
):
    device = DeviceService(db_session).create_device(
        DeviceCreate(
            name="change-request-no-baseline",
            connection={
                "host": "192.0.2.61",
                "username": "netconf",
                "password": "device-secret",
            },
        )
    )
    db_session.add(
        TaskStatus(
            task_id="connection-no-baseline",
            task_type="device.connection_test",
            status="succeeded",
            device_id=device.id,
        )
    )
    DeviceRepository(db_session).upsert_discovery_result(
        device_id=device.id,
        source_task_id="discovery-no-baseline",
        capabilities=["urn:test"],
        system_info={},
        discovered_at=datetime.now(UTC),
        summary={},
    )
    db_session.commit()
    token = get_token(client, "operator1")
    payload = {
        "device_id": device.id,
        "datastore": "running",
        "change_summary": "change",
        "config_body": "<config/>",
        "reason": "planned maintenance",
    }

    preview = client.post(
        "/api/v1/change-requests/preflight",
        json=payload,
        headers=auth_headers(token),
    )
    submit = client.post("/api/v1/change-requests", json=payload, headers=auth_headers(token))

    assert preview.status_code == 200
    assert preview.json()["passed"] is False
    assert "baseline_snapshot_required" in preview.json()["blockers"]
    assert submit.status_code == 400
    assert db_session.query(DeviceConfigChangeRequest).count() == 0


def test_preflight_reports_stale_baseline(client: TestClient, db_session: Session, operator_user):
    device = _create_ready_device(
        db_session,
        collected_at=datetime.now(UTC) - timedelta(hours=2),
    )
    token = get_token(client, "operator1")

    resp = client.post(
        "/api/v1/change-requests/preflight",
        json={
            "device_id": device.id,
            "datastore": "running",
            "change_summary": "change",
            "config_body": "<config/>",
            "reason": "planned maintenance",
        },
        headers=auth_headers(token),
    )

    assert resp.status_code == 200
    assert resp.json()["passed"] is False
    assert "baseline_snapshot_stale" in resp.json()["blockers"]
    assert resp.json()["recommended_action"] == "refresh_baseline_snapshot"


def test_preflight_rejects_invalid_datastore_empty_payload_and_viewer_permission(
    client: TestClient, db_session: Session, operator_user, viewer_user
):
    device = _create_ready_device(db_session)
    operator_token = get_token(client, "operator1")
    viewer_token = get_token(client, "viewer1")
    payload = {
        "device_id": device.id,
        "datastore": "invalid",
        "change_summary": "change",
        "config_body": " ",
        "reason": "planned maintenance",
    }

    operator_resp = client.post(
        "/api/v1/change-requests/preflight",
        json=payload,
        headers=auth_headers(operator_token),
    )
    viewer_resp = client.post(
        "/api/v1/change-requests/preflight",
        json=payload | {"datastore": "running", "config_body": "<config/>"},
        headers=auth_headers(viewer_token),
    )

    assert operator_resp.status_code in (200, 422)
    if operator_resp.status_code == 200:
        blockers = operator_resp.json()["blockers"]
        assert "unsupported_datastore" in blockers
        assert "config_body_missing" in blockers
    assert viewer_resp.status_code == 403


def test_preflight_redacts_sensitive_payload_content(
    client: TestClient, db_session: Session, operator_user
):
    device = _create_ready_device(db_session)
    token = get_token(client, "operator1")

    resp = client.post(
        "/api/v1/change-requests/preflight",
        json={
            "device_id": device.id,
            "datastore": "running",
            "change_summary": "rotate secret",
            "config_body": "<config><password>super-secret</password></config>",
            "reason": "planned maintenance",
        },
        headers=auth_headers(token),
    )

    assert resp.status_code == 200
    assert "super-secret" not in str(resp.json())
    assert "password" not in str(resp.json()).lower()


def test_operator_cannot_preview_rollback_preflight(client: TestClient, operator_user):
    token = get_token(client, "operator1")

    resp = client.post(
        "/api/v1/change-requests/preflight",
        json={
            "device_id": 1,
            "datastore": "running",
            "reason": "restore",
            "mode": "rollback",
            "rollback_target_snapshot_id": 1,
        },
        headers=auth_headers(token),
    )

    assert resp.status_code == 403


def test_rollback_preflight_reports_success_and_blockers(
    client: TestClient, db_session: Session, approver_user
):
    now = datetime.now(UTC)
    device = _create_ready_device(db_session, collected_at=now - timedelta(minutes=30))
    target = _create_restorable_snapshot(
        db_session,
        device_id=device.id,
        source_task_id="rollback-target",
        content_digest="sha256:rollback-target",
        normalized_content="<config><target/></config>",
        collected_at=now - timedelta(minutes=20),
    )
    current = _create_restorable_snapshot(
        db_session,
        device_id=device.id,
        source_task_id="rollback-current",
        content_digest="sha256:rollback-current",
        normalized_content="<config><current/></config>",
        collected_at=now - timedelta(minutes=10),
    )
    missing_content = _create_snapshot_without_normalized_content(
        db_session,
        device_id=device.id,
        source_task_id="rollback-missing-content",
        content_digest="sha256:missing-content",
        collected_at=now - timedelta(minutes=15),
    )
    db_session.add(
        DeviceConfigChangeRequest(
            device_id=device.id,
            datastore="running",
            change_summary="origin not recoverable",
            reason="test",
            status="pending_approval",
            submitter_id=approver_user.id,
        )
    )
    db_session.commit()
    origin = db_session.query(DeviceConfigChangeRequest).one()

    token = get_token(client, "approver1")
    payload = {
        "device_id": device.id,
        "datastore": "running",
        "reason": "restore",
        "mode": "rollback",
        "rollback_target_snapshot_id": target.id,
    }

    success = client.post(
        "/api/v1/change-requests/preflight",
        json=payload,
        headers=auth_headers(token),
    )
    no_divergence = client.post(
        "/api/v1/change-requests/preflight",
        json=payload | {"rollback_target_snapshot_id": current.id},
        headers=auth_headers(token),
    )
    not_restorable = client.post(
        "/api/v1/change-requests/preflight",
        json=payload | {"rollback_target_snapshot_id": missing_content.id},
        headers=auth_headers(token),
    )
    bad_origin = client.post(
        "/api/v1/change-requests/preflight",
        json=payload | {"rollback_of_change_id": origin.id},
        headers=auth_headers(token),
    )

    assert success.status_code == 200
    assert success.json()["passed"] is True
    assert success.json()["mode"] == "rollback"
    assert success.json()["rollback_target_snapshot"]["id"] == target.id
    assert success.json()["baseline_snapshot"]["id"] == current.id
    assert success.json()["payload"]["digest"].startswith("sha256:")
    assert no_divergence.status_code == 200
    assert "ROLLBACK_NO_DIVERGENCE" in no_divergence.json()["blockers"]
    assert not_restorable.status_code == 200
    assert "ROLLBACK_TARGET_NOT_RESTORABLE" in not_restorable.json()["blockers"]
    assert bad_origin.status_code == 200
    assert "ROLLBACK_ORIGIN_NOT_RECOVERABLE" in bad_origin.json()["blockers"]

    inflight = DeviceConfigChangeRequest(
        device_id=device.id,
        datastore="running",
        change_summary="in flight",
        reason="test",
        status="queued",
        submitter_id=approver_user.id,
    )
    db_session.add(inflight)
    db_session.commit()
    blocked = client.post(
        "/api/v1/change-requests/preflight",
        json=payload,
        headers=auth_headers(token),
    )
    assert "CHANGE_IN_FLIGHT" in blocked.json()["blockers"]


def test_submit_rollback_persists_server_derived_payload(
    client: TestClient, db_session: Session, approver_user
):
    now = datetime.now(UTC)
    device = _create_ready_device(db_session, collected_at=now - timedelta(minutes=30))
    target = _create_restorable_snapshot(
        db_session,
        device_id=device.id,
        source_task_id="submit-rollback-target",
        content_digest="sha256:submit-rollback-target",
        normalized_content="<config><target>secret</target></config>",
        collected_at=now - timedelta(minutes=20),
    )
    _create_restorable_snapshot(
        db_session,
        device_id=device.id,
        source_task_id="submit-rollback-current",
        content_digest="sha256:submit-rollback-current",
        normalized_content="<config><current/></config>",
        collected_at=now - timedelta(minutes=10),
    )

    token = get_token(client, "approver1")
    resp = client.post(
        "/api/v1/change-requests/rollback",
        json={
            "device_id": device.id,
            "datastore": "running",
            "change_summary": "restore target",
            "reason": "restore service",
            "rollback_target_snapshot_id": target.id,
        },
        headers=auth_headers(token),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_rollback"] is True
    assert body["preflight_summary"]["mode"] == "rollback"
    assert "secret" not in str(body)
    payload = (
        db_session.query(DeviceConfigChangePayload)
        .filter_by(change_request_id=body["id"])
        .one()
    )
    assert payload.summary_source == f"rollback_from_snapshot:{target.id}"
    assert payload.body_digest == body["preflight_summary"]["payload"]["digest"]
    assert payload.config_body == "<config><target>secret</target></config>"


def test_rollback_approval_reruns_preflight_and_blocks_inflight(
    client: TestClient, db_session: Session, approver_user, monkeypatch
):
    dispatched: list[str] = []
    monkeypatch.setattr("app.tasks.service.run_config_change.delay", dispatched.append)
    now = datetime.now(UTC)
    device = _create_ready_device(db_session, collected_at=now - timedelta(minutes=30))
    target = _create_restorable_snapshot(
        db_session,
        device_id=device.id,
        source_task_id="approve-rollback-target",
        content_digest="sha256:approve-rollback-target",
        normalized_content="<config><target/></config>",
        collected_at=now - timedelta(minutes=20),
    )
    _create_restorable_snapshot(
        db_session,
        device_id=device.id,
        source_task_id="approve-rollback-current",
        content_digest="sha256:approve-rollback-current",
        normalized_content="<config><current/></config>",
        collected_at=now - timedelta(minutes=10),
    )
    token = get_token(client, "approver1")
    submit_resp = client.post(
        "/api/v1/change-requests/rollback",
        json={
            "device_id": device.id,
            "datastore": "running",
            "change_summary": "restore target",
            "reason": "restore service",
            "rollback_target_snapshot_id": target.id,
        },
        headers=auth_headers(token),
    )
    assert submit_resp.status_code == 201
    rollback_id = submit_resp.json()["id"]
    db_session.add(
        DeviceConfigChangeRequest(
            device_id=device.id,
            datastore="running",
            change_summary="parallel change",
            reason="test",
            status="queued",
            submitter_id=approver_user.id,
        )
    )
    db_session.commit()

    approve_resp = client.post(
        f"/api/v1/change-requests/{rollback_id}/approve",
        json={"approval_note": "go"},
        headers=auth_headers(token),
    )

    assert approve_resp.status_code == 400
    assert "CHANGE_IN_FLIGHT" in approve_resp.json()["detail"]
    assert dispatched == []


def test_config_change_task_updates_change_request_status(db_session: Session, monkeypatch):
    from app.netconf.services import NetconfOperationResult
    from app.tasks.jobs import run_config_change
    from tests.test_tasks_and_ai import _session_factory

    device = _create_ready_device(db_session)
    baseline = DeviceRepository(db_session).get_latest_successful_snapshot(
        device_id=device.id, datastore="running"
    )
    assert baseline is not None
    cr = DeviceConfigChangeRequest(
        device_id=device.id,
        datastore="running",
        change_summary="test",
        reason="test",
        status="queued",
        submitter_id=1,
        approver_id=1,
        executor_id=1,
        baseline_snapshot_id=baseline.id,
        preflight_status="passed",
    )
    db_session.add(cr)
    db_session.flush()
    db_session.add(
        DeviceConfigChangePayload(
            change_request_id=cr.id,
            config_body="<config><interfaces/></config>",
        )
    )
    task = TaskStatus(
        task_id="change-task-success",
        task_type="device.config_change",
        status="queued",
        device_id=device.id,
        actor_user_id=1,
        change_request_id=cr.id,
        metadata_json={"device_id": device.id, "datastore": "running"},
        context_json={"device_id": device.id, "datastore": "running"},
    )
    db_session.add(task)
    db_session.commit()
    monkeypatch.setattr("app.tasks.jobs.SessionLocal", _session_factory(db_session))

    captured: dict[str, str] = {}

    class FakeService:
        def write_config(self, params, datastore, config_body):
            captured["datastore"] = datastore
            captured["config_body"] = config_body
            return NetconfOperationResult(ok=True, summary={"write": "success"})

        def read_config(self, params, datastore):
            return NetconfOperationResult(
                ok=True,
                summary={
                    "datastore": datastore,
                    "content_digest": "sha256:post",
                    "content_length": 32,
                    "normalized_length": 32,
                },
                config_content="<config><interfaces/></config>",
                normalized_content="<config><interfaces/></config>",
                datastore=datastore,
                content_digest="sha256:post",
            )

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_config_change.run(task.task_id)
    db_session.expire_all()
    stored = db_session.get(DeviceConfigChangeRequest, cr.id)

    assert result["status"] == "succeeded"
    assert stored is not None
    assert stored.status == "executed"
    assert stored.executed_at is not None
    assert stored.verification_status == "passed"
    assert stored.verification_snapshot_id is not None
    assert stored.verified_at is not None
    assert captured == {
        "datastore": "running",
        "config_body": "<config><interfaces/></config>",
    }


def test_config_change_task_marks_verification_failure_after_write_success(
    db_session: Session, monkeypatch
):
    from app.devices.constants import DeviceAccessErrorCode
    from app.netconf.services import NetconfOperationResult
    from app.tasks.jobs import run_config_change
    from tests.test_tasks_and_ai import _session_factory

    device = _create_ready_device(db_session)
    baseline = DeviceRepository(db_session).get_latest_successful_snapshot(
        device_id=device.id, datastore="running"
    )
    assert baseline is not None
    cr, task = _create_change_task(
        db_session,
        device_id=device.id,
        baseline_snapshot_id=baseline.id,
        task_id="change-task-verification-failed",
    )
    monkeypatch.setattr("app.tasks.jobs.SessionLocal", _session_factory(db_session))

    class FakeService:
        def write_config(self, params, datastore, config_body):
            return NetconfOperationResult(ok=True, summary={"write": "success"})

        def read_config(self, params, datastore):
            return NetconfOperationResult(
                ok=False,
                error_code=DeviceAccessErrorCode.CONNECTION_TIMEOUT,
                error_message="NETCONF operation timed out",
                context={"password": "verify-secret", "datastore": datastore},
            )

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_config_change.run(task.task_id)
    db_session.expire_all()
    stored = db_session.get(DeviceConfigChangeRequest, cr.id)
    stored_task = db_session.query(TaskStatus).filter_by(task_id=task.task_id).one()

    assert result["status"] == "failed"
    assert stored is not None
    assert stored.status == "verification_failed"
    assert stored.verification_status == "failed"
    assert stored.executed_at is not None
    assert stored.verification_snapshot_id is None
    assert stored_task.result_summary["write"] == "success"
    assert stored_task.result_summary["verification"] == "failed"
    assert stored_task.context_json["password"] == "***REDACTED***"
    assert db_session.query(TaskStatus).filter_by(task_id=task.task_id).count() == 1


def test_verification_failure_auto_proposes_rollback_with_preflight(
    db_session: Session, monkeypatch
):
    from app.auth.constants import AuditAction
    from app.auth.repositories import AuditLogRepository
    from app.devices.constants import DeviceAccessErrorCode
    from app.netconf.services import NetconfOperationResult
    from app.tasks.jobs import run_config_change
    from tests.test_tasks_and_ai import _session_factory

    now = datetime.now(UTC)
    device = _create_ready_device(db_session, collected_at=now - timedelta(minutes=30))
    baseline = _create_restorable_snapshot(
        db_session,
        device_id=device.id,
        source_task_id="auto-proposal-baseline",
        content_digest="sha256:auto-proposal-baseline",
        normalized_content="<config><baseline/></config>",
        collected_at=now - timedelta(minutes=10),
    )
    cr, task = _create_change_task(
        db_session,
        device_id=device.id,
        baseline_snapshot_id=baseline.id,
        task_id="change-task-auto-rollback",
    )
    monkeypatch.setattr("app.tasks.jobs.SessionLocal", _session_factory(db_session))

    class FakeService:
        def write_config(self, params, datastore, config_body):
            return NetconfOperationResult(ok=True, summary={"write": "success"})

        def read_config(self, params, datastore):
            return NetconfOperationResult(
                ok=False,
                error_code=DeviceAccessErrorCode.CONNECTION_TIMEOUT,
                error_message="NETCONF operation timed out",
                context={"datastore": datastore},
            )

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_config_change.run(task.task_id)
    db_session.expire_all()
    rollback = (
        db_session.query(DeviceConfigChangeRequest)
        .filter_by(rollback_of_change_id=cr.id, is_rollback=True)
        .one()
    )
    payload = (
        db_session.query(DeviceConfigChangePayload)
        .filter_by(change_request_id=rollback.id)
        .one()
    )

    assert result["status"] == "failed"
    assert rollback.status == "pending_approval"
    assert rollback.rollback_target_snapshot_id == baseline.id
    assert rollback.execution_task_id is None
    assert rollback.preflight_summary["mode"] == "rollback"
    assert "blockers" in rollback.preflight_summary
    assert payload.summary_source == f"rollback_from_snapshot:{baseline.id}"
    logs = AuditLogRepository(db_session).list_paginated(
        action=AuditAction.CHANGE_ROLLBACK_PROPOSED
    )
    assert logs
    assert logs[0].metadata_json["preflight_status"] == rollback.preflight_status


def test_rollback_task_rejects_payload_digest_mismatch_before_write(
    db_session: Session, monkeypatch
):
    from app.netconf.services import NetconfOperationResult
    from app.tasks.jobs import run_config_change
    from tests.test_tasks_and_ai import _session_factory

    now = datetime.now(UTC)
    device = _create_ready_device(db_session, collected_at=now - timedelta(minutes=30))
    target = _create_restorable_snapshot(
        db_session,
        device_id=device.id,
        source_task_id="rollback-digest-target",
        content_digest="sha256:rollback-digest-target",
        normalized_content="<config><target/></config>",
        collected_at=now - timedelta(minutes=10),
    )
    cr = DeviceConfigChangeRequest(
        device_id=device.id,
        datastore="running",
        change_summary="rollback",
        reason="restore",
        status="queued",
        submitter_id=1,
        approver_id=1,
        executor_id=1,
        is_rollback=True,
        rollback_target_snapshot_id=target.id,
        preflight_status="passed",
    )
    db_session.add(cr)
    db_session.flush()
    db_session.add(
        DeviceConfigChangePayload(
            change_request_id=cr.id,
            config_body="<config><tampered/></config>",
        )
    )
    task = TaskStatus(
        task_id="rollback-digest-mismatch-task",
        task_type="device.config_change",
        status="queued",
        device_id=device.id,
        actor_user_id=1,
        change_request_id=cr.id,
        metadata_json={"device_id": device.id, "datastore": "running"},
        context_json={"device_id": device.id, "datastore": "running"},
    )
    db_session.add(task)
    db_session.commit()
    monkeypatch.setattr("app.tasks.jobs.SessionLocal", _session_factory(db_session))

    class FakeService:
        def write_config(self, params, datastore, config_body):
            raise AssertionError("write_config must not be called after digest mismatch")

        def read_config(self, params, datastore):
            return NetconfOperationResult(ok=True)

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_config_change.run(task.task_id)
    db_session.expire_all()
    stored = db_session.get(DeviceConfigChangeRequest, cr.id)
    stored_task = db_session.query(TaskStatus).filter_by(task_id=task.task_id).one()

    assert result["status"] == "failed"
    assert stored is not None
    assert stored.status == "failed"
    assert stored_task.error_code == "INVALID_PARAMETER"
    assert stored_task.error_message == "Rollback payload digest mismatch"


def test_config_change_task_write_failure_skips_verification(
    db_session: Session, monkeypatch
):
    from app.devices.constants import DeviceAccessErrorCode
    from app.netconf.services import NetconfOperationResult
    from app.tasks.jobs import run_config_change
    from tests.test_tasks_and_ai import _session_factory

    device = _create_ready_device(db_session)
    cr, task = _create_change_task(
        db_session,
        device_id=device.id,
        baseline_snapshot_id=None,
        task_id="change-task-write-failed",
    )
    monkeypatch.setattr("app.tasks.jobs.SessionLocal", _session_factory(db_session))

    class FakeService:
        def write_config(self, params, datastore, config_body):
            return NetconfOperationResult(
                ok=False,
                error_code=DeviceAccessErrorCode.AUTH_FAILED,
                error_message="NETCONF authentication failed",
                context={"password": "write-secret"},
            )

        def read_config(self, params, datastore):
            raise AssertionError("verification must not run after write failure")

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_config_change.run(task.task_id)
    db_session.expire_all()
    stored = db_session.get(DeviceConfigChangeRequest, cr.id)

    assert result["status"] == "failed"
    assert stored is not None
    assert stored.status == "failed"
    assert stored.verification_status is None
    stored_task = db_session.query(TaskStatus).filter_by(task_id=task.task_id).one()
    assert stored_task.error_code == "AUTH_FAILED"


def _create_change_task(
    db_session: Session,
    *,
    device_id: int,
    baseline_snapshot_id: int | None,
    task_id: str,
) -> tuple[DeviceConfigChangeRequest, TaskStatus]:
    cr = DeviceConfigChangeRequest(
        device_id=device_id,
        datastore="running",
        change_summary="test",
        reason="test",
        status="queued",
        submitter_id=1,
        approver_id=1,
        executor_id=1,
        baseline_snapshot_id=baseline_snapshot_id,
        preflight_status="passed" if baseline_snapshot_id is not None else None,
    )
    db_session.add(cr)
    db_session.flush()
    db_session.add(
        DeviceConfigChangePayload(
            change_request_id=cr.id,
            config_body="<config><interfaces/></config>",
        )
    )
    task = TaskStatus(
        task_id=task_id,
        task_type="device.config_change",
        status="queued",
        device_id=device_id,
        actor_user_id=1,
        change_request_id=cr.id,
        metadata_json={"device_id": device_id, "datastore": "running"},
        context_json={"device_id": device_id, "datastore": "running"},
    )
    db_session.add(task)
    db_session.commit()
    return cr, task


def _create_restorable_snapshot(
    db_session: Session,
    *,
    device_id: int,
    source_task_id: str,
    content_digest: str,
    normalized_content: str,
    collected_at: datetime,
):
    db_session.add(
        TaskStatus(
            task_id=source_task_id,
            task_type="device.config_snapshot",
            status="succeeded",
            device_id=device_id,
            completed_at=collected_at,
        )
    )
    snapshot = DeviceRepository(db_session).create_config_snapshot(
        device_id=device_id,
        source_task_id=source_task_id,
        datastore="running",
        content_digest=content_digest,
        collected_at=collected_at,
        diff_summary={"changed": True},
        summary={"content_digest": content_digest},
        normalized_content=normalized_content,
    )
    db_session.commit()
    return snapshot


def _create_snapshot_without_normalized_content(
    db_session: Session,
    *,
    device_id: int,
    source_task_id: str,
    content_digest: str,
    collected_at: datetime,
):
    db_session.add(
        TaskStatus(
            task_id=source_task_id,
            task_type="device.config_snapshot",
            status="succeeded",
            device_id=device_id,
            completed_at=collected_at,
        )
    )
    snapshot = DeviceRepository(db_session).create_config_snapshot(
        device_id=device_id,
        source_task_id=source_task_id,
        datastore="running",
        content_digest=content_digest,
        collected_at=collected_at,
        diff_summary={"changed": True},
        summary={"content_digest": content_digest},
        normalized_content=None,
    )
    db_session.commit()
    return snapshot


def _create_ready_device(
    db_session: Session,
    *,
    collected_at: datetime | None = None,
):
    device = DeviceService(db_session).create_device(
        DeviceCreate(
            name="change-request-device",
            connection={
                "host": "192.0.2.60",
                "username": "netconf",
                "password": "device-secret",
            },
        )
    )
    db_session.add(
        TaskStatus(
            task_id=f"connection-ready-{device.id}",
            task_type="device.connection_test",
            status="succeeded",
            device_id=device.id,
            completed_at=datetime.now(UTC),
        )
    )
    repository = DeviceRepository(db_session)
    repository.upsert_discovery_result(
        device_id=device.id,
        source_task_id=f"discovery-ready-{device.id}",
        capabilities=["urn:test"],
        system_info={},
        discovered_at=datetime.now(UTC),
        summary={"capability_count": 1},
    )
    repository.create_config_snapshot(
        device_id=device.id,
        source_task_id=f"snapshot-ready-{device.id}",
        datastore="running",
        content_digest="sha256:baseline",
        collected_at=collected_at or datetime.now(UTC),
        diff_summary={"changed": False},
        summary={"content_digest": "sha256:baseline"},
    )
    db_session.commit()
    return device
