from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.auth.repositories import RefreshTokenRepository
from app.common.time import utc_now
from app.core.config import get_settings
from app.storage.models import RefreshToken


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_refresh_token(session: Session, user_id: int) -> str:
    raw = secrets.token_urlsafe(48)
    settings = get_settings()
    expires_at = utc_now() + timedelta(days=settings.refresh_token_ttl_days)
    RefreshTokenRepository(session).create(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=expires_at,
    )
    return raw


def validate_and_rotate_refresh_token(
    session: Session, raw_token: str
) -> tuple[RefreshToken, str]:
    repo = RefreshTokenRepository(session)
    token_hash = _hash_token(raw_token)
    token = repo.get_by_hash(token_hash)

    if token is None or not token.is_valid:
        raise ValueError("invalid or expired refresh token")

    now = utc_now()
    repo.revoke(token, revoked_at=now)

    new_raw = secrets.token_urlsafe(48)
    settings = get_settings()
    expires_at = now + timedelta(days=settings.refresh_token_ttl_days)
    repo.create(
        user_id=token.user_id,
        token_hash=_hash_token(new_raw),
        expires_at=expires_at,
    )
    return token, new_raw


def revoke_refresh_token(session: Session, raw_token: str) -> None:
    repo = RefreshTokenRepository(session)
    token_hash = _hash_token(raw_token)
    token = repo.get_by_hash(token_hash)
    if token and token.revoked_at is None:
        repo.revoke(token, revoked_at=utc_now())
