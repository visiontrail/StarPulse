from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.schemas.auth import (
    PermissionRead,
    RolePermissionUpdateRequest,
    RoleRead,
    UserCreateRequest,
    UserRead,
    UserRoleAssignRequest,
)
from app.auth.audit import write_audit_event
from app.auth.constants import PERM_ROLE_MANAGE, PERM_USER_MANAGE, AuditAction, AuditOutcome
from app.auth.dependencies import CurrentUserDep, SessionDep, require_permission
from app.auth.password import hash_password
from app.auth.repositories import PermissionRepository, RoleRepository, UserRepository
from app.common.time import utc_now
from app.storage.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permission(PERM_USER_MANAGE)],
)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> UserRead:
    repo = UserRepository(session)
    if repo.get_by_username(payload.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    user = repo.create(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    write_audit_event(
        session=session,
        action=AuditAction.USER_CREATED,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        target_type="user",
        target_id=str(user.id),
        permission=PERM_USER_MANAGE,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"username": payload.username},
    )
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user)


@router.get(
    "/users",
    response_model=list[UserRead],
    dependencies=[require_permission(PERM_USER_MANAGE)],
)
def list_users(session: SessionDep) -> list[UserRead]:
    users = UserRepository(session).list_all()
    return [UserRead.model_validate(u) for u in users]


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    dependencies=[require_permission(PERM_USER_MANAGE)],
)
def get_user(user_id: int, session: SessionDep) -> UserRead:
    user = _get_user_or_404(session, user_id)
    return UserRead.model_validate(user)


@router.post(
    "/users/{user_id}/disable",
    response_model=UserRead,
    dependencies=[require_permission(PERM_USER_MANAGE)],
)
def disable_user(
    user_id: int,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> UserRead:
    user = _get_user_or_404(session, user_id)
    user.is_active = False
    user.updated_at = utc_now()
    write_audit_event(
        session=session,
        action=AuditAction.USER_DISABLED,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        target_type="user",
        target_id=str(user.id),
        permission=PERM_USER_MANAGE,
        ip_address=request.client.host if request.client else None,
    )
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user)


@router.post(
    "/users/{user_id}/enable",
    response_model=UserRead,
    dependencies=[require_permission(PERM_USER_MANAGE)],
)
def enable_user(
    user_id: int,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> UserRead:
    user = _get_user_or_404(session, user_id)
    user.is_active = True
    user.updated_at = utc_now()
    write_audit_event(
        session=session,
        action=AuditAction.USER_ENABLED,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        target_type="user",
        target_id=str(user.id),
        permission=PERM_USER_MANAGE,
        ip_address=request.client.host if request.client else None,
    )
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user)


@router.post(
    "/users/{user_id}/roles",
    response_model=UserRead,
    dependencies=[require_permission(PERM_ROLE_MANAGE)],
)
def assign_role(
    user_id: int,
    payload: UserRoleAssignRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> UserRead:
    user = _get_user_or_404(session, user_id)
    role = RoleRepository(session).get_by_id(payload.role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    roles_before = _role_names(user)
    if role not in user.roles:
        user.roles.append(role)
    roles_after = _role_names(user)
    write_audit_event(
        session=session,
        action=AuditAction.ROLE_ASSIGNED,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        target_type="user",
        target_id=str(user.id),
        permission=PERM_ROLE_MANAGE,
        ip_address=request.client.host if request.client else None,
        metadata={
            "role_name": role.name,
            "role_id": role.id,
            "roles_before": roles_before,
            "roles_after": roles_after,
        },
    )
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user)


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    response_model=UserRead,
    dependencies=[require_permission(PERM_ROLE_MANAGE)],
)
def remove_role(
    user_id: int,
    role_id: int,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> UserRead:
    user = _get_user_or_404(session, user_id)
    role = next((r for r in user.roles if r.id == role_id), None)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not assigned")
    roles_before = _role_names(user)
    user.roles.remove(role)
    roles_after = _role_names(user)
    write_audit_event(
        session=session,
        action=AuditAction.ROLE_REMOVED,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        target_type="user",
        target_id=str(user.id),
        permission=PERM_ROLE_MANAGE,
        ip_address=request.client.host if request.client else None,
        metadata={
            "role_name": role.name,
            "role_id": role.id,
            "roles_before": roles_before,
            "roles_after": roles_after,
        },
    )
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user)


@router.get(
    "/roles",
    response_model=list[RoleRead],
    dependencies=[require_permission(PERM_ROLE_MANAGE)],
)
def list_roles(session: SessionDep) -> list[RoleRead]:
    roles = RoleRepository(session).list_all()
    return [RoleRead.model_validate(r) for r in roles]


@router.put(
    "/roles/{role_id}/permissions",
    response_model=RoleRead,
    dependencies=[require_permission(PERM_ROLE_MANAGE)],
)
def update_role_permissions(
    role_id: int,
    payload: RolePermissionUpdateRequest,
    request: Request,
    session: SessionDep,
    actor: CurrentUserDep,
) -> RoleRead:
    role = RoleRepository(session).get_by_id(role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    perm_repo = PermissionRepository(session)
    all_perms = {p.id: p for p in perm_repo.list_all()}
    new_perms = [all_perms[pid] for pid in payload.permission_ids if pid in all_perms]
    role.permissions = new_perms
    write_audit_event(
        session=session,
        action=AuditAction.ROLE_PERMISSION_CHANGED,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        target_type="role",
        target_id=str(role.id),
        permission=PERM_ROLE_MANAGE,
        ip_address=request.client.host if request.client else None,
        metadata={"permission_ids": payload.permission_ids},
    )
    session.commit()
    session.refresh(role)
    return RoleRead.model_validate(role)


@router.get(
    "/permissions",
    response_model=list[PermissionRead],
    dependencies=[require_permission(PERM_USER_MANAGE)],
)
def list_permissions(session: SessionDep) -> list[PermissionRead]:
    perms = PermissionRepository(session).list_all()
    return [PermissionRead.model_validate(p) for p in perms]


def _get_user_or_404(session: Session, user_id: int) -> User:
    user = UserRepository(session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _role_names(user: User) -> list[str]:
    return sorted(role.name for role in user.roles)
