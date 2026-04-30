from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate
from app.devices.repository import DeviceRepository
from app.devices.service import DeviceService
from app.storage.models import Device, DeviceConnectionConfig, TaskStatus


def test_create_and_fetch_device(client: TestClient) -> None:
    response = client.post(
        "/api/v1/devices",
        json={
            "name": "sat-router-001",
            "serial_number": "SR-001",
            "group": "leo-alpha",
            "connection": {
                "host": "192.0.2.10",
                "port": 830,
                "username": "netconf",
                "password": "secret",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "sat-router-001"
    assert body["connection"]["host"] == "192.0.2.10"
    assert body["connection"]["has_credential"] is True
    assert "password" not in body["connection"]

    list_response = client.get("/api/v1/devices")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert "secret" not in str(list_response.json()).lower()

    detail_response = client.get(f"/api/v1/devices/{body['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["serial_number"] == "SR-001"


def test_device_repository_persists_connection_credential_ref_and_discovery(
    db_session: Session,
) -> None:
    device = Device(name="sat-router-002", status="ready")
    device.connection = DeviceConnectionConfig(
        protocol="netconf",
        host="192.0.2.11",
        port=830,
        username="netconf",
        credential_ref="cred-test",
    )
    repository = DeviceRepository(db_session)
    repository.add(device)

    task = TaskStatus(
        task_id="task-discovery-1",
        task_type="device.capability_discovery",
        status="queued",
        device_id=device.id,
    )
    db_session.add(task)
    db_session.flush()
    repository.upsert_discovery_result(
        device_id=device.id,
        source_task_id=task.task_id,
        capabilities=["urn:ietf:params:netconf:base:1.0"],
        system_info={"hostname": "router-002"},
        discovered_at=task.created_at,
        summary={"capability_count": 1},
    )
    db_session.commit()
    db_session.expire_all()

    stored = repository.get_with_connection(device.id)

    assert stored is not None
    assert stored.connection is not None
    assert stored.connection.credential_ref == "cred-test"
    assert stored.last_discovery is not None
    assert stored.last_discovery.summary == {"capability_count": 1}


def test_device_service_stores_password_in_credential_boundary(db_session: Session) -> None:
    device = DeviceService(db_session).create_device(
        DeviceCreate(
            name="sat-router-003",
            connection={
                "host": "192.0.2.12",
                "username": "netconf",
                "password": "super-secret",
            },
        )
    )

    assert device.connection is not None
    assert device.connection.credential_ref
    assert "super-secret" not in str(device.connection.__dict__)
