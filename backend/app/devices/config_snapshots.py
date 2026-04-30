from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.common.redaction import redact_sensitive
from app.devices.repository import DeviceRepository
from app.netconf.services import NetconfOperationResult
from app.storage.models import DeviceConfigSnapshot


@dataclass(frozen=True)
class ConfigSnapshotCreateResult:
    snapshot: DeviceConfigSnapshot
    previous_snapshot: DeviceConfigSnapshot | None


class ConfigSnapshotService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DeviceRepository(session)

    def save_read_result(
        self,
        *,
        device_id: int,
        source_task_id: str,
        datastore: str,
        result: NetconfOperationResult,
        collected_at: datetime | None = None,
    ) -> ConfigSnapshotCreateResult:
        if not result.ok or result.content_digest is None:
            raise ValueError("Only successful config read results can be saved")
        collected = collected_at or datetime.now(UTC)
        previous = self.repository.get_last_config_snapshot(
            device_id=device_id, datastore=datastore
        )
        diff_summary = build_diff_summary(previous, result.content_digest, collected)
        summary = build_snapshot_summary(
            datastore=datastore,
            content_digest=result.content_digest,
            collected_at=collected,
            read_summary=result.summary,
            diff_summary=diff_summary,
        )
        snapshot = self.repository.create_config_snapshot(
            device_id=device_id,
            source_task_id=source_task_id,
            datastore=datastore,
            content_digest=result.content_digest,
            collected_at=collected,
            diff_summary=diff_summary,
            summary=summary,
        )
        return ConfigSnapshotCreateResult(snapshot=snapshot, previous_snapshot=previous)


def build_diff_summary(
    previous: DeviceConfigSnapshot | None, current_digest: str, collected_at: datetime
) -> dict[str, object]:
    if previous is None:
        return {
            "changed": False,
            "previous_snapshot_id": None,
            "previous_content_digest": None,
            "current_content_digest": current_digest,
            "digest_changed": False,
            "collected_at_delta_seconds": None,
        }
    changed = previous.content_digest != current_digest
    return {
        "changed": changed,
        "previous_snapshot_id": previous.id,
        "previous_content_digest": previous.content_digest,
        "current_content_digest": current_digest,
        "digest_changed": changed,
        "collected_at_delta_seconds": int(
            (_as_aware(collected_at) - _as_aware(previous.collected_at)).total_seconds()
        ),
    }


def build_snapshot_summary(
    *,
    datastore: str,
    content_digest: str,
    collected_at: datetime,
    read_summary: dict[str, object],
    diff_summary: dict[str, object],
) -> dict[str, object]:
    safe_read_summary = redact_sensitive(read_summary)
    safe_read_summary.pop("config_content", None)
    safe_read_summary.pop("normalized_content", None)
    return {
        "datastore": datastore,
        "content_digest": content_digest,
        "collected_at": collected_at.isoformat(),
        "content_length": safe_read_summary.get("content_length"),
        "normalized_length": safe_read_summary.get("normalized_length"),
        "diff": diff_summary,
    }


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
