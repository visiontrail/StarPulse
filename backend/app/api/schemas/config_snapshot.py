from __future__ import annotations

from datetime import datetime

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


class ConfigSnapshotListResponse(BaseModel):
    items: list[ConfigSnapshotSummaryRead]
    limit: int
    offset: int
