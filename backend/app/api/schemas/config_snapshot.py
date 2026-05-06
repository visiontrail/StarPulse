from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigSnapshotCollectRequest(BaseModel):
    datastore: str = Field(default="running", min_length=1, max_length=64)


class ConfigSnapshotSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_task_id: str
    datastore: str
    content_digest: str
    collected_at: datetime
    diff_summary: dict[str, object]
    summary: dict[str, object]
    rollback_eligible: bool = False
    rollback_blocker: str | None = None

    @classmethod
    def from_snapshot(
        cls, snapshot: Any, *, source_task_succeeded: bool = True
    ) -> ConfigSnapshotSummaryRead:
        eligible = bool(getattr(snapshot, "normalized_content", None)) and source_task_succeeded
        return cls(
            id=snapshot.id,
            source_task_id=snapshot.source_task_id,
            datastore=snapshot.datastore,
            content_digest=snapshot.content_digest,
            collected_at=snapshot.collected_at,
            diff_summary=snapshot.diff_summary,
            summary=snapshot.summary,
            rollback_eligible=eligible,
            rollback_blocker=None if eligible else "ROLLBACK_TARGET_NOT_RESTORABLE",
        )


class ConfigSnapshotListResponse(BaseModel):
    items: list[ConfigSnapshotSummaryRead]
    limit: int
    offset: int
