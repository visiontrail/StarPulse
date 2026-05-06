from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.devices.config_snapshots import ConfigSnapshotService
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
