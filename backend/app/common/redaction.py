from __future__ import annotations

SENSITIVE_KEY_PARTS = ("password", "secret", "private_key", "passphrase", "credential")
REDACTED = "***REDACTED***"


def redact_sensitive(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _is_sensitive_key(str(key)) else redact_sensitive(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(child) for child in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(child) for child in value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lower_key = key.lower()
    normalized_key = lower_key.replace("-", "_")
    return any(part in normalized_key for part in SENSITIVE_KEY_PARTS)
