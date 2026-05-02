from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.schemas.auth import (
    CurrentUserRead,
    LoginRequest,
    LoginResponse,
    TokenRefreshResponse,
)
from app.auth.audit import write_audit_event
from app.auth.constants import AuditAction, AuditOutcome
from app.auth.dependencies import CurrentUserDep, SessionDep
from app.auth.password import verify_password
from app.auth.refresh import (
    generate_refresh_token,
    revoke_refresh_token,
    validate_and_rotate_refresh_token,
)
from app.auth.repositories import UserRepository
from app.auth.tokens import create_access_token
from app.core.config import get_settings
from app.storage.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

_REFRESH_COOKIE = "refresh_token"


def _build_current_user(user: User) -> CurrentUserRead:
    roles = [r.name for r in user.roles]
    perms: list[str] = []
    seen: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            if perm.name not in seen:
                seen.add(perm.name)
                perms.append(perm.name)
    return CurrentUserRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=roles,
        permissions=perms,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_ttl_days * 86400,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, httponly=True)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response, session: SessionDep) -> LoginResponse:
    user = UserRepository(session).get_by_username(payload.username)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    if user is None or not verify_password(payload.password, user.password_hash) or not user.is_active:
        write_audit_event(
            session=session,
            action=AuditAction.LOGIN_FAILURE,
            outcome=AuditOutcome.FAILURE,
            target_type="user",
            target_id=payload.username,
            ip_address=ip,
            user_agent=ua,
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    current_user = _build_current_user(user)
    access_token = create_access_token(
        subject=str(user.id),
        roles=current_user.roles,
        permissions=current_user.permissions,
        token_id=str(uuid4()),
    )
    refresh_raw = generate_refresh_token(session, user.id)
    _set_refresh_cookie(response, refresh_raw)

    write_audit_event(
        session=session,
        action=AuditAction.LOGIN_SUCCESS,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        ip_address=ip,
        user_agent=ua,
    )
    session.commit()
    return LoginResponse(access_token=access_token, user=current_user)


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token(
    request: Request,
    response: Response,
    session: SessionDep,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> TokenRefreshResponse:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    if not refresh_token:
        _record_refresh_failure(session, ip, ua)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    try:
        old_token, new_raw = validate_and_rotate_refresh_token(session, refresh_token)
    except ValueError:
        _record_refresh_failure(session, ip, ua)
        session.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user = UserRepository(session).get_by_id(old_token.user_id)
    if user is None or not user.is_active:
        _record_refresh_failure(session, ip, ua)
        session.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable")

    current_user = _build_current_user(user)
    access_token = create_access_token(
        subject=str(user.id),
        roles=current_user.roles,
        permissions=current_user.permissions,
        token_id=str(uuid4()),
    )
    _set_refresh_cookie(response, new_raw)
    session.commit()
    return TokenRefreshResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUserDep,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
) -> None:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    if refresh_token:
        revoke_refresh_token(session, refresh_token)
    _clear_refresh_cookie(response)
    write_audit_event(
        session=session,
        action=AuditAction.LOGOUT,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        ip_address=ip,
        user_agent=ua,
    )
    session.commit()


@router.get("/me", response_model=CurrentUserRead)
def get_current_user_endpoint(user: CurrentUserDep) -> CurrentUserRead:
    return _build_current_user(user)


def _record_refresh_failure(session: Session, ip: str | None, ua: str | None) -> None:
    write_audit_event(
        session=session,
        action=AuditAction.REFRESH_FAILURE,
        outcome=AuditOutcome.FAILURE,
        ip_address=ip,
        user_agent=ua,
    )
