from __future__ import annotations

from datetime import timedelta
from typing import Any

import jwt

from app.common.time import utc_now
from app.core.config import get_settings


def create_access_token(
    subject: str,
    roles: list[str],
    permissions: list[str],
    token_id: str,
) -> str:
    settings = get_settings()
    now = utc_now()
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": roles,
        "permissions": permissions,
        "jti": token_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
