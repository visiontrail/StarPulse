from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Table, Text, func
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
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    change_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_config_change_requests.id"), nullable=True, index=True
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


# ── Auth / RBAC many-to-many association tables ────────────────────────────

from sqlalchemy import Column  # noqa: E402

user_roles_table = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)

role_permissions_table = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles_table, back_populates="users", lazy="selectin"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    users: Mapped[list[User]] = relationship(secondary=user_roles_table, back_populates="roles")
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions_table, back_populates="roles", lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions_table, back_populates="permissions"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    @property
    def is_valid(self) -> bool:
        from app.common.time import utc_now

        return self.revoked_at is None and self.expires_at > utc_now()


class DeviceConfigChangeRequest(TimestampMixin, Base):
    __tablename__ = "device_config_change_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    datastore: Mapped[str] = mapped_column(String(64), nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    change_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending_approval", index=True)

    submitter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    direct_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    direct_execute_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    execution_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    device: Mapped[Device] = relationship()
    submitter: Mapped[User] = relationship(foreign_keys=[submitter_id])
    approver: Mapped[User | None] = relationship(foreign_keys=[approver_id])
    executor: Mapped[User | None] = relationship(foreign_keys=[executor_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    permission: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_user_id])
