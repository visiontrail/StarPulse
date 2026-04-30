from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.storage.models import CredentialRecord


class CredentialUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeCredential:
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None


class CredentialService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_password(self, password: str | None) -> str:
        credential_ref = f"cred_{uuid4().hex}"
        record = CredentialRecord(
            credential_ref=credential_ref,
            credential_type="password",
            secret_json={"password": password},
        )
        self.session.add(record)
        self.session.flush()
        return credential_ref

    def resolve(self, credential_ref: str | None) -> RuntimeCredential:
        if not credential_ref:
            raise CredentialUnavailableError("Credential reference is missing")
        record = self.session.scalar(
            select(CredentialRecord).where(CredentialRecord.credential_ref == credential_ref)
        )
        if record is None:
            raise CredentialUnavailableError("Credential reference is unavailable")
        return RuntimeCredential(
            password=_optional_str(record.secret_json.get("password")),
            private_key=_optional_str(record.secret_json.get("private_key")),
            passphrase=_optional_str(record.secret_json.get("passphrase")),
        )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
