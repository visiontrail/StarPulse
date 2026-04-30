from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai.services import AiCapabilityService
from app.api.schemas.device import DeviceCreate
from app.devices.constants import DeviceAccessErrorCode
from app.devices.service import DeviceService
from app.netconf.services import NetconfOperationResult
from app.storage.models import Device, TaskStatus
from app.tasks.jobs import run_capability_discovery, run_connection_test, sample_health


def test_sample_task_can_run_directly() -> None:
    assert sample_health.run("task-1", {"kind": "health"}) == {
        "task_id": "task-1",
        "status": "ok",
        "payload": {"kind": "health"},
    }


def test_task_api_records_and_dispatches_task(client: TestClient, monkeypatch) -> None:
    dispatched: list[tuple[str, dict[str, object]]] = []

    def fake_delay(task_id: str, payload: dict[str, object]) -> None:
        dispatched.append((task_id, payload))

    monkeypatch.setattr("app.tasks.service.sample_health.delay", fake_delay)

    response = client.post(
        "/api/v1/tasks",
        json={"task_type": "sample.health", "payload": {"kind": "health"}},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert dispatched == [(body["task_id"], {"kind": "health"})]

    detail = client.get(f"/api/v1/tasks/{body['task_id']}")
    assert detail.status_code == 200
    assert detail.json()["metadata"] == {"payload": {"kind": "health"}}


def test_ai_placeholder_is_inert() -> None:
    summary = AiCapabilityService().summary()

    assert summary.enabled is False
    assert summary.phase == "foundation-placeholder"
    assert summary.supported_actions == ()


def test_device_task_api_dispatches_without_leaking_secret(
    client: TestClient, monkeypatch
) -> None:
    dispatched: list[str] = []

    def fake_delay(task_id: str) -> None:
        dispatched.append(task_id)

    monkeypatch.setattr("app.tasks.service.run_connection_test.delay", fake_delay)

    device_response = client.post(
        "/api/v1/devices",
        json={
            "name": "sat-router-task-api",
            "connection": {
                "host": "192.0.2.30",
                "username": "netconf",
                "password": "api-secret",
            },
        },
    )
    device_id = device_response.json()["id"]

    response = client.post(f"/api/v1/devices/{device_id}/connection-test")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["device_id"] == device_id
    assert dispatched == [body["task_id"]]
    assert "api-secret" not in str(body)


def test_device_task_api_rejects_missing_device_without_dispatch(
    client: TestClient, monkeypatch
) -> None:
    dispatched: list[str] = []
    monkeypatch.setattr("app.tasks.service.run_connection_test.delay", dispatched.append)

    response = client.post("/api/v1/devices/999/connection-test")

    assert response.status_code == 404
    assert dispatched == []


def test_connection_test_task_records_success(
    db_session: Session, monkeypatch
) -> None:
    task_id, device_id = _create_device_task_fixture(db_session)
    monkeypatch.setattr("app.tasks.jobs.SessionLocal", _session_factory(db_session))

    class FakeService:
        def test_connection(self, params):
            return NetconfOperationResult(ok=True, summary={"connected": True})

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_connection_test.run(task_id)
    db_session.expire_all()
    task = db_session.query(TaskStatus).one()

    assert result["status"] == "succeeded"
    assert task.status == "succeeded"
    assert task.device_id == device_id
    assert task.result_summary == {"connected": True}
    assert task.error_code is None


def test_capability_discovery_task_records_result(
    db_session: Session, monkeypatch
) -> None:
    task_id, device_id = _create_device_task_fixture(
        db_session, task_type="device.capability_discovery"
    )
    monkeypatch.setattr("app.tasks.jobs.SessionLocal", _session_factory(db_session))

    class FakeService:
        def discover_capabilities(self, params):
            return NetconfOperationResult(
                ok=True,
                summary={"capability_count": 1},
                capabilities=["urn:ietf:params:netconf:base:1.0"],
                system_info={"hostname": "sat-router"},
            )

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_capability_discovery.run(task_id)
    db_session.expire_all()
    device = db_session.get(Device, device_id)

    assert result["status"] == "succeeded"
    assert device is not None
    assert device.status == "online"
    assert device.last_discovery is not None
    assert device.last_discovery.capabilities == ["urn:ietf:params:netconf:base:1.0"]


def test_connection_test_task_records_standard_error_and_redacted_context(
    db_session: Session, monkeypatch, caplog
) -> None:
    task_id, _ = _create_device_task_fixture(db_session)
    monkeypatch.setattr("app.tasks.jobs.SessionLocal", _session_factory(db_session))

    class FakeService:
        def test_connection(self, params):
            return NetconfOperationResult(
                ok=False,
                error_code=DeviceAccessErrorCode.AUTH_FAILED,
                error_message="NETCONF authentication failed",
                context={"password": "task-secret", "host": params.host},
            )

    monkeypatch.setattr("app.tasks.jobs.create_netconf_service", lambda: FakeService())

    result = run_connection_test.run(task_id)
    db_session.expire_all()
    task = db_session.query(TaskStatus).one()

    assert result["status"] == "failed"
    assert task.error_code == "AUTH_FAILED"
    assert task.context_json["password"] == "***REDACTED***"
    assert "task-secret" not in caplog.text


def _create_device_task_fixture(
    db_session: Session, *, task_type: str = "device.connection_test"
) -> tuple[str, int]:
    device = DeviceService(db_session).create_device(
        DeviceCreate(
            name=f"sat-router-{task_type}",
            connection={
                "host": "192.0.2.31",
                "username": "netconf",
                "password": "task-secret",
            },
        )
    )
    task = TaskStatus(
        task_id=f"task-{task_type}",
        task_type=task_type,
        status="queued",
        device_id=device.id,
        metadata_json={"device_id": device.id},
        context_json={"device_id": device.id},
    )
    db_session.add(task)
    db_session.commit()
    return task.task_id, device.id


def _session_factory(db_session: Session):
    return sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
