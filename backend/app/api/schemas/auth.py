from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class PermissionRead(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class RoleRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    permissions: list[PermissionRead] = []

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    id: int
    username: str
    display_name: str

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: int
    username: str
    display_name: str
    is_active: bool
    roles: list[RoleRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @property
    def permissions(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for role in self.roles:
            for perm in role.permissions:
                if perm.name not in seen:
                    seen.add(perm.name)
                    result.append(perm.name)
        return result


class CurrentUserRead(BaseModel):
    id: int
    username: str
    display_name: str
    is_active: bool
    roles: list[str]
    permissions: list[str]

    model_config = {"from_attributes": False}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUserRead


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)


class UserRoleAssignRequest(BaseModel):
    role_id: int


class RolePermissionUpdateRequest(BaseModel):
    permission_ids: list[int]


class AuditLogRead(BaseModel):
    id: int
    actor_user_id: int | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    outcome: str
    permission: str | None = None
    ip_address: str | None = None
    created_at: datetime
    metadata: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_summary(cls, log: object) -> AuditLogRead:
        from app.storage.models import AuditLog

        assert isinstance(log, AuditLog)
        return cls(
            id=log.id,
            actor_user_id=log.actor_user_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            outcome=log.outcome,
            permission=log.permission,
            ip_address=log.ip_address,
            created_at=log.created_at,
            metadata={},
        )

    @classmethod
    def from_orm_full(cls, log: object) -> AuditLogRead:
        from app.storage.models import AuditLog

        assert isinstance(log, AuditLog)
        return cls(
            id=log.id,
            actor_user_id=log.actor_user_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            outcome=log.outcome,
            permission=log.permission,
            ip_address=log.ip_address,
            created_at=log.created_at,
            metadata=log.metadata_json or {},
        )


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    limit: int
    offset: int


class ChangeRequestSubmitRequest(BaseModel):
    device_id: int
    datastore: str
    change_summary: str = Field(min_length=1)
    change_ref: str | None = None
    reason: str = Field(min_length=1)


class ChangeRequestApproveRequest(BaseModel):
    approval_note: str | None = None


class ChangeRequestRejectRequest(BaseModel):
    rejection_note: str = Field(min_length=1)


class ChangeRequestDirectExecuteRequest(BaseModel):
    device_id: int
    datastore: str
    change_summary: str = Field(min_length=1)
    change_ref: str | None = None
    reason: str = Field(min_length=1)


class ChangeRequestRead(BaseModel):
    id: int
    device_id: int
    datastore: str
    change_summary: str
    change_ref: str | None = None
    reason: str
    status: str
    submitter: UserSummary | None = None
    approver: UserSummary | None = None
    approval_note: str | None = None
    approved_at: datetime | None = None
    direct_execute: bool
    direct_execute_reason: str | None = None
    execution_task_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChangeRequestListResponse(BaseModel):
    items: list[ChangeRequestRead]
    limit: int
    offset: int
