from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate
from app.devices.service import DeviceService
from app.storage.models import DeviceConfigChangeRequest, TaskStatus
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
            "reason": "restore service",
        },
        headers=auth_headers(token),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["direct_execute"] is True
    assert body["execution_task_id"] is not None
    assert dispatched == [body["execution_task_id"]]


def test_config_change_task_updates_change_request_status(db_session: Session, monkeypatch):
    from app.netconf.services import NetconfOperationResult
    from app.tasks.jobs import run_config_change
    from tests.test_tasks_and_ai import _session_factory

    device = _create_ready_device(db_session)
    cr = DeviceConfigChangeRequest(
        device_id=device.id,
        datastore="running",
        change_summary="test",
        reason="test",
        status="queued",
        submitter_id=1,
        approver_id=1,
        executor_id=1,
    )
    db_session.add(cr)
    db_session.flush()
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

    class FakeService:
        def write_config(self, params, datastore, config_body):
            return NetconfOperationResult(ok=True, summary={"write": "success"})

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_config_change.run(task.task_id)
    db_session.expire_all()
    stored = db_session.get(DeviceConfigChangeRequest, cr.id)

    assert result["status"] == "succeeded"
    assert stored is not None
    assert stored.status == "executed"
    assert stored.executed_at is not None


def _create_ready_device(db_session: Session):
    return DeviceService(db_session).create_device(
        DeviceCreate(
            name="change-request-device",
            connection={
                "host": "192.0.2.60",
                "username": "netconf",
                "password": "device-secret",
            },
        )
    )
