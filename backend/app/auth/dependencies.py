from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.audit import write_audit_event
from app.auth.constants import AuditAction, AuditOutcome
from app.auth.repositories import UserRepository
from app.auth.tokens import decode_access_token
from app.storage.database import get_session
from app.storage.models import User

logger = logging.getLogger(__name__)

SessionDep = Annotated[Session, Depends(get_session)]

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def get_current_user(
    request: Request,
    session: SessionDep,
) -> User:
    token = _extract_bearer(request)
    if not token:
        raise _CREDENTIALS_EXCEPTION
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise _CREDENTIALS_EXCEPTION from None
    except jwt.PyJWTError:
        raise _CREDENTIALS_EXCEPTION from None

    user_id_str: str = payload.get("sub", "")
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise _CREDENTIALS_EXCEPTION from None

    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_permission(permission: str):
    def checker(
        request: Request,
        session: SessionDep,
        user: CurrentUserDep,
    ) -> User:
        user_perms = {p.name for role in user.roles for p in role.permissions}
        if permission not in user_perms:
            logger.info(
                "permission denied",
                extra={
                    "action": "authz.permission_denied",
                    "user_id": user.id,
                    "permission": permission,
                    "path": request.url.path,
                },
            )
            write_audit_event(
                session=session,
                action=AuditAction.PERMISSION_DENIED,
                outcome=AuditOutcome.DENIED,
                actor_user_id=user.id,
                permission=permission,
                target_type="endpoint",
                target_id=request.url.path,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return user

    return Depends(checker)
