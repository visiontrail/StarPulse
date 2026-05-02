from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.auth.constants import AuditOutcome
from app.auth.repositories import AuditLogRepository

logger = logging.getLogger(__name__)

_REDACTED_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "private_key",
        "secret",
        "credential",
        "config_body",
        "full_config",
    }
)


def _redact_audit_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in metadata.items():
        lower = key.lower()
        if any(part in lower for part in _REDACTED_KEYS):
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = _redact_audit_metadata(value)
        else:
            result[key] = value
    return result


def write_audit_event(
    *,
    session: Session,
    action: str,
    outcome: str,
    actor_user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    permission: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    safe_metadata = _redact_audit_metadata(metadata or {})
    try:
        AuditLogRepository(session).create(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            outcome=outcome,
            permission=permission,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=safe_metadata,
        )
    except Exception:
        logger.exception(
            "audit write failed: action=%s outcome=%s actor=%s",
            action,
            outcome,
            actor_user_id,
        )
        if outcome == AuditOutcome.SUCCESS and action not in (
            "auth.login.success",
            "auth.logout",
            "auth.login.failure",
            "auth.refresh.failure",
        ):
            raise
