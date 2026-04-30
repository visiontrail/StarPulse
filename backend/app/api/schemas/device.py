from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceConnectionCreate(BaseModel):
    protocol: str = Field(default="netconf", max_length=32)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=830, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=1024)


class DeviceConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    host: str
    port: int
    protocol: str
    username: str
    credential_ref: str | None = None
    has_credential: bool = False


class DeviceDiscoveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_task_id: str
    capabilities: list[str]
    system_info: dict[str, object]
    discovered_at: datetime
    summary: dict[str, object]


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
    last_discovery: DeviceDiscoveryRead | None = None
