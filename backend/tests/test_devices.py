from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate
from app.devices.constants import SUPPORTED_CONFIG_DATASTORES, DeviceTaskType
from app.devices.repository import DeviceRepository
from app.devices.service import DeviceService
from app.storage.models import Device, DeviceConfigSnapshot, DeviceConnectionConfig, TaskStatus


def test_create_and_fetch_device(authed_client: TestClient) -> None:
    response = authed_client.post(
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

    list_response = authed_client.get("/api/v1/devices")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert "secret" not in str(list_response.json()).lower()

    detail_response = authed_client.get(f"/api/v1/devices/{body['id']}")
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


def test_config_snapshot_task_type_and_datastore_allowlist() -> None:
    assert DeviceTaskType.CONFIG_SNAPSHOT == "device.config_snapshot"
    assert SUPPORTED_CONFIG_DATASTORES == ("running", "candidate", "startup")


def test_device_repository_persists_and_queries_config_snapshots(db_session: Session) -> None:
    device = Device(name="sat-router-snapshot", status="ready")
    repository = DeviceRepository(db_session)
    repository.add(device)
    first_collected_at = datetime(2026, 4, 30, 10, 0, tzinfo=UTC)
    second_collected_at = first_collected_at + timedelta(minutes=5)

    first = repository.create_config_snapshot(
        device_id=device.id,
        source_task_id="task-config-1",
        datastore="running",
        content_digest="sha256:first",
        collected_at=first_collected_at,
        diff_summary={"changed": False, "previous_snapshot_id": None},
        summary={"digest": "sha256:first", "datastore": "running"},
    )
    second = repository.create_config_snapshot(
        device_id=device.id,
        source_task_id="task-config-2",
        datastore="running",
        content_digest="sha256:second",
        collected_at=second_collected_at,
        diff_summary={"changed": True, "previous_snapshot_id": first.id},
        summary={"digest": "sha256:second", "datastore": "running"},
    )
    repository.create_config_snapshot(
        device_id=device.id,
        source_task_id="task-config-3",
        datastore="startup",
        content_digest="sha256:startup",
        collected_at=second_collected_at + timedelta(minutes=5),
        diff_summary={"changed": False, "previous_snapshot_id": None},
        summary={"digest": "sha256:startup", "datastore": "startup"},
    )
    db_session.commit()
    db_session.expire_all()

    stored = db_session.query(DeviceConfigSnapshot).filter_by(source_task_id="task-config-2").one()
    previous = repository.get_previous_config_snapshot(
        device_id=device.id,
        datastore="running",
        before_snapshot_id=stored.id,
    )
    last_running = repository.get_last_config_snapshot(device_id=device.id, datastore="running")
    all_snapshots = repository.list_config_snapshots(device_id=device.id, limit=2)

    assert stored.content_digest == "sha256:second"
    assert stored.diff_summary == {"changed": True, "previous_snapshot_id": first.id}
    assert previous is not None
    assert previous.id == first.id
    assert last_running is not None
    assert last_running.id == second.id
    assert [snapshot.datastore for snapshot in all_snapshots] == ["startup", "running"]


def test_config_snapshot_list_and_profile_api_are_safe(
    authed_client: TestClient, db_session: Session
) -> None:
    device = DeviceService(db_session).create_device(
        DeviceCreate(
            name="sat-router-profile",
            connection={
                "host": "192.0.2.40",
                "username": "netconf",
                "password": "profile-secret",
            },
        )
    )
    repository = DeviceRepository(db_session)
    task = TaskStatus(
        task_id="task-config-profile",
        task_type="device.config_snapshot",
        status="succeeded",
        device_id=device.id,
        result_summary={"snapshot_id": 1},
        metadata_json={"device_id": device.id, "datastore": "running"},
        context_json={"device_id": device.id, "datastore": "running"},
    )
    db_session.add(task)
    db_session.flush()
    repository.upsert_discovery_result(
        device_id=device.id,
        source_task_id="task-discovery-profile",
        capabilities=["urn:test:capability"],
        system_info={"hostname": "sat-router-profile"},
        discovered_at=datetime(2026, 4, 30, 10, 0, tzinfo=UTC),
        summary={"capability_count": 1},
    )
    repository.create_config_snapshot(
        device_id=device.id,
        source_task_id=task.task_id,
        datastore="running",
        content_digest="sha256:profile",
        collected_at=datetime(2026, 4, 30, 10, 5, tzinfo=UTC),
        diff_summary={"changed": False, "previous_snapshot_id": None},
        summary={"content_digest": "sha256:profile", "datastore": "running"},
    )
    db_session.commit()

    snapshots_response = authed_client.get(f"/api/v1/devices/{device.id}/config-snapshots?limit=5")
    profile_response = authed_client.get(f"/api/v1/devices/{device.id}/profile")
    detail_response = authed_client.get(f"/api/v1/devices/{device.id}")

    assert snapshots_response.status_code == 200
    assert snapshots_response.json()["items"][0]["content_digest"] == "sha256:profile"
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["capabilities"] == ["urn:test:capability"]
    assert profile["last_config_snapshot"]["content_digest"] == "sha256:profile"
    assert profile["recent_tasks"][0]["task_id"] == "task-config-profile"
    assert profile["safety_summary"]["exposes_full_config"] is False
    assert detail_response.json()["last_config_snapshot"]["content_digest"] == "sha256:profile"
    assert "profile-secret" not in str(profile_response.json())


def test_config_snapshot_list_rejects_missing_device(authed_client: TestClient) -> None:
    response = authed_client.get("/api/v1/devices/999/config-snapshots")

    assert response.status_code == 404


def test_unauthenticated_cannot_access_snapshots(client: TestClient, db_session: Session) -> None:
    resp = client.get("/api/v1/devices/1/config-snapshots")
    assert resp.status_code == 401


def test_viewer_cannot_collect_snapshot(client: TestClient, viewer_user) -> None:
    from tests.conftest import auth_headers, get_token
    token = get_token(client, "viewer1")
    resp = client.post(
        "/api/v1/devices/1/config-snapshots",
        json={"datastore": "running"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
