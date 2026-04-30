from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.devices.constants import DeviceStatus, DeviceTaskStatus
from app.storage.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    serial_number: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=DeviceStatus.PLANNED)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)

    connection: Mapped[DeviceConnectionConfig | None] = relationship(
        back_populates="device", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )

    last_discovery: Mapped[DeviceDiscoveryResult | None] = relationship(
        back_populates="device", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )

    config_snapshots: Mapped[list[DeviceConfigSnapshot]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by=lambda: (DeviceConfigSnapshot.collected_at.desc(), DeviceConfigSnapshot.id.desc()),
    )


class DeviceConnectionConfig(TimestampMixin, Base):
    __tablename__ = "device_connection_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, unique=True)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False, default="netconf")
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=830)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)

    device: Mapped[Device] = relationship(back_populates="connection")

    @property
    def has_credential(self) -> bool:
        return bool(self.credential_ref)


class CredentialRecord(TimestampMixin, Base):
    __tablename__ = "credential_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    credential_ref: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    credential_type: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_json: Mapped[dict[str, object]] = mapped_column("secret", JSON, default=dict)


class SystemConfig(TimestampMixin, Base):
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaskStatus(TimestampMixin, Base):
    __tablename__ = "task_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    task_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=DeviceTaskStatus.QUEUED)
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id"), nullable=True, index=True
    )
    result_summary: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_json: Mapped[dict[str, object]] = mapped_column("context", JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)

    device: Mapped[Device | None] = relationship()


class DeviceDiscoveryResult(TimestampMixin, Base):
    __tablename__ = "device_discovery_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, unique=True)
    source_task_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    system_info: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    device: Mapped[Device] = relationship(back_populates="last_discovery")


class DeviceConfigSnapshot(TimestampMixin, Base):
    __tablename__ = "device_config_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    source_task_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    datastore: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    diff_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    device: Mapped[Device] = relationship(back_populates="config_snapshots")
