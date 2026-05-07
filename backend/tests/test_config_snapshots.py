from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.common.redaction import REDACTED
from app.devices.config_snapshots import ConfigSnapshotService, build_config_object_tree
from app.netconf.services import NetconfOperationResult
from app.storage.models import Device, TaskStatus


def test_snapshot_service_saves_first_snapshot_without_previous(db_session: Session) -> None:
    device = _device(db_session)
    result = _read_result("sha256:first", password="secret")

    saved = ConfigSnapshotService(db_session).save_read_result(
        device_id=device.id,
        source_task_id="task-config-1",
        datastore="running",
        result=result,
        collected_at=datetime(2026, 4, 30, 10, 0, tzinfo=UTC),
    )

    assert saved.previous_snapshot is None
    assert saved.snapshot.diff_summary["previous_snapshot_id"] is None
    assert saved.snapshot.diff_summary["changed"] is False
    assert saved.snapshot.summary["content_digest"] == "sha256:first"
    assert "secret" not in str(saved.snapshot.summary)


def test_snapshot_service_detects_unchanged_snapshot(db_session: Session) -> None:
    device = _device(db_session)
    service = ConfigSnapshotService(db_session)
    service.save_read_result(
        device_id=device.id,
        source_task_id="task-config-1",
        datastore="running",
        result=_read_result("sha256:same"),
        collected_at=datetime(2026, 4, 30, 10, 0, tzinfo=UTC),
    )

    saved = service.save_read_result(
        device_id=device.id,
        source_task_id="task-config-2",
        datastore="running",
        result=_read_result("sha256:same"),
        collected_at=datetime(2026, 4, 30, 10, 5, tzinfo=UTC),
    )

    assert saved.previous_snapshot is not None
    assert saved.snapshot.diff_summary["previous_snapshot_id"] == saved.previous_snapshot.id
    assert saved.snapshot.diff_summary["changed"] is False
    assert saved.snapshot.diff_summary["digest_changed"] is False


def test_snapshot_service_detects_changed_snapshot(db_session: Session) -> None:
    device = _device(db_session)
    service = ConfigSnapshotService(db_session)
    first_at = datetime(2026, 4, 30, 10, 0, tzinfo=UTC)
    service.save_read_result(
        device_id=device.id,
        source_task_id="task-config-1",
        datastore="running",
        result=_read_result("sha256:first"),
        collected_at=first_at,
    )

    saved = service.save_read_result(
        device_id=device.id,
        source_task_id="task-config-2",
        datastore="running",
        result=_read_result("sha256:second"),
        collected_at=first_at + timedelta(minutes=7),
    )

    assert saved.snapshot.diff_summary["changed"] is True
    assert saved.snapshot.diff_summary["digest_changed"] is True
    assert saved.snapshot.diff_summary["previous_content_digest"] == "sha256:first"
    assert saved.snapshot.diff_summary["collected_at_delta_seconds"] == 420


def test_rollback_eligibility_requires_successful_source_task(db_session: Session) -> None:
    device = _device(db_session)
    service = ConfigSnapshotService(db_session)
    saved = service.save_read_result(
        device_id=device.id,
        source_task_id="task-config-restorable",
        datastore="running",
        result=_read_result("sha256:restorable"),
        collected_at=datetime(2026, 4, 30, 10, 0, tzinfo=UTC),
    )

    assert service.assess_rollback_eligibility(saved.snapshot).eligible is False

    task = TaskStatus(
        task_id="task-config-restorable",
        task_type="device.config_snapshot",
        status="failed",
        device_id=device.id,
    )
    db_session.add(task)
    db_session.commit()
    assert service.assess_rollback_eligibility(saved.snapshot).eligible is False

    task.status = "succeeded"
    db_session.commit()
    assert service.assess_rollback_eligibility(saved.snapshot).eligible is True


def test_config_object_tree_parses_netconf_data_and_redacts_sensitive_leaves() -> None:
    tree = build_config_object_tree(
        """
        <data xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
          <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
              <name>eth0</name>
              <enabled>true</enabled>
            </interface>
            <interface>
              <name>eth1</name>
              <enabled>false</enabled>
            </interface>
          </interfaces>
          <keystore xmlns="urn:ietf:params:xml:ns:yang:ietf-keystore">
            <cleartext-private-key>super-secret-key</cleartext-private-key>
          </keystore>
        </data>
        """
    )

    assert tree is not None
    data = tree["data"]
    assert isinstance(data, dict)
    interfaces = data["interfaces"]
    assert isinstance(interfaces, dict)
    assert interfaces["_namespace"] == "urn:ietf:params:xml:ns:yang:ietf-interfaces"
    assert isinstance(interfaces["interface"], list)
    assert interfaces["interface"][0]["name"] == "eth0"
    assert interfaces["interface"][1]["enabled"] == "false"
    assert data["keystore"]["cleartext-private-key"] == REDACTED


def test_config_object_tree_parses_existing_ncclient_clark_notation_snapshot() -> None:
    tree = build_config_object_tree(
        '<{urn:ietf:params:xml:ns:netconf:base:1.0}rpc-reply message-id="1">'
        "<{urn:ietf:params:xml:ns:netconf:base:1.0}data>"
        "<{urn:ietf:params:xml:ns:yang:ietf-interfaces}interfaces>"
        "<{urn:ietf:params:xml:ns:yang:ietf-interfaces}interface>"
        "<{urn:ietf:params:xml:ns:yang:ietf-interfaces}name>eth0"
        "</{urn:ietf:params:xml:ns:yang:ietf-interfaces}name>"
        "</{urn:ietf:params:xml:ns:yang:ietf-interfaces}interface>"
        "</{urn:ietf:params:xml:ns:yang:ietf-interfaces}interfaces>"
        "</{urn:ietf:params:xml:ns:netconf:base:1.0}data>"
        "</{urn:ietf:params:xml:ns:netconf:base:1.0}rpc-reply>"
    )

    assert tree is not None
    data = tree["rpc-reply"]["data"]
    assert data["interfaces"]["interface"]["name"] == "eth0"


def _device(db_session: Session) -> Device:
    device = Device(name="sat-router-config", status="ready")
    db_session.add(device)
    db_session.flush()
    return device


def _read_result(content_digest: str, **extra: object) -> NetconfOperationResult:
    return NetconfOperationResult(
        ok=True,
        summary={
            "datastore": "running",
            "content_digest": content_digest,
            "content_length": 42,
            "normalized_length": 24,
            **extra,
        },
        config_content="<config>secret</config>",
        normalized_content="<config>secret</config>",
        datastore="running",
        content_digest=content_digest,
    )
