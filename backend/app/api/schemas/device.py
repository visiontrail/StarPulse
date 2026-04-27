from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceConnectionCreate(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=830, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=1024)


class DeviceConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    host: str
    port: int
    username: str


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    serial_number: str | None = Field(default=None, max_length=255)
    group: str | None = Field(default=None, max_length=255)
    status: str = Field(default="planned", max_length=64)
    metadata: dict[str, object] = Field(default_factory=dict)
    connection: DeviceConnectionCreate | None = None


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    serial_number: str | None
    group: str | None
    status: str
    metadata: dict[str, object] = Field(validation_alias="metadata_json")
    created_at: datetime
    updated_at: datetime
    connection: DeviceConnectionRead | None = None
