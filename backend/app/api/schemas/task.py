from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    task_type: str = Field(default="sample.health", min_length=1, max_length=128)
    payload: dict[str, object] = Field(default_factory=dict)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    task_id: str
    task_type: str
    status: str
    device_id: int | None = None
    result_summary: dict[str, object] | None = None
    error_code: str | None = None
    error_message: str | None = None
    context: dict[str, object] = Field(default_factory=dict, validation_alias="context_json")
    completed_at: datetime | None = None
    metadata: dict[str, object] = Field(validation_alias="metadata_json")
    created_at: datetime
    updated_at: datetime
