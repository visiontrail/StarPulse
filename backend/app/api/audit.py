from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.schemas.auth import AuditLogListResponse, AuditLogRead
from app.auth.constants import PERM_AUDIT_READ_FULL, PERM_AUDIT_READ_SUMMARY
from app.auth.dependencies import CurrentUserDep, SessionDep
from app.auth.repositories import AuditLogRepository

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
)
def list_audit_logs(
    session: SessionDep,
    user: CurrentUserDep,
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    since: datetime | None = Query(default=None),  # noqa: B008
    until: datetime | None = Query(default=None),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    user_perms = {p.name for role in user.roles for p in role.permissions}
    has_full = PERM_AUDIT_READ_FULL in user_perms

    _require_any_audit_perm(user_perms)

    logs = AuditLogRepository(session).list_paginated(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    items = [
        AuditLogRead.from_orm_full(log) if has_full else AuditLogRead.from_orm_summary(log)
        for log in logs
    ]
    return AuditLogListResponse(items=items, limit=limit, offset=offset)


def _require_any_audit_perm(user_perms: set[str]) -> None:
    from fastapi import HTTPException, status

    if PERM_AUDIT_READ_SUMMARY not in user_perms and PERM_AUDIT_READ_FULL not in user_perms:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
