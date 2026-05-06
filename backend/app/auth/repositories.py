from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.storage.models import (
    AuditLog,
    DeviceConfigChangePayload,
    DeviceConfigChangeRequest,
    Permission,
    RefreshToken,
    Role,
    User,
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def list_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        return list(
            self.session.scalars(select(User).order_by(User.id).limit(limit).offset(offset))
        )

    def create(self, username: str, display_name: str, password_hash: str) -> User:
        user = User(username=username, display_name=display_name, password_hash=password_hash)
        self.session.add(user)
        self.session.flush()
        self.session.refresh(user)
        return user

    def save(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        self.session.refresh(user)
        return user


class RoleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, role_id: int) -> Role | None:
        return self.session.get(Role, role_id)

    def get_by_name(self, name: str) -> Role | None:
        return self.session.scalar(select(Role).where(Role.name == name))

    def list_all(self) -> list[Role]:
        return list(self.session.scalars(select(Role).order_by(Role.id)))

    def create(self, name: str, description: str | None = None) -> Role:
        role = Role(name=name, description=description)
        self.session.add(role)
        self.session.flush()
        self.session.refresh(role)
        return role

    def save(self, role: Role) -> Role:
        self.session.add(role)
        self.session.flush()
        self.session.refresh(role)
        return role


class PermissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_name(self, name: str) -> Permission | None:
        return self.session.scalar(select(Permission).where(Permission.name == name))

    def list_all(self) -> list[Permission]:
        return list(self.session.scalars(select(Permission).order_by(Permission.id)))

    def create(self, name: str, description: str | None = None) -> Permission:
        perm = Permission(name=name, description=description)
        self.session.add(perm)
        self.session.flush()
        self.session.refresh(perm)
        return perm


class RefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )

    def create(self, user_id: int, token_hash: str, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.session.add(token)
        self.session.flush()
        self.session.refresh(token)
        return token

    def revoke(self, token: RefreshToken, revoked_at: datetime) -> None:
        token.revoked_at = revoked_at
        self.session.add(token)
        self.session.flush()

    def revoke_all_for_user(self, user_id: int, revoked_at: datetime) -> None:
        tokens = list(
            self.session.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        )
        for token in tokens:
            token.revoked_at = revoked_at
        self.session.flush()


class ChangeRequestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, cr_id: int) -> DeviceConfigChangeRequest | None:
        return self.session.get(DeviceConfigChangeRequest, cr_id)

    def list_all(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[DeviceConfigChangeRequest]:
        q = select(DeviceConfigChangeRequest).order_by(DeviceConfigChangeRequest.id.desc())
        if status:
            q = q.where(DeviceConfigChangeRequest.status == status)
        return list(self.session.scalars(q.limit(limit).offset(offset)))

    def create(self, **kwargs: object) -> DeviceConfigChangeRequest:
        cr = DeviceConfigChangeRequest(**kwargs)
        self.session.add(cr)
        self.session.flush()
        self.session.refresh(cr)
        return cr

    def save(self, cr: DeviceConfigChangeRequest) -> DeviceConfigChangeRequest:
        self.session.add(cr)
        self.session.flush()
        self.session.refresh(cr)
        return cr

    def update_preflight(
        self,
        cr: DeviceConfigChangeRequest,
        *,
        status: str,
        baseline_snapshot_id: int | None,
        preflight_summary: dict[str, object],
        risk_summary: dict[str, object],
        generated_at: datetime,
    ) -> DeviceConfigChangeRequest:
        cr.preflight_status = status
        cr.baseline_snapshot_id = baseline_snapshot_id
        cr.preflight_summary = preflight_summary
        cr.risk_summary = risk_summary
        cr.preflight_generated_at = generated_at
        return self.save(cr)

    def update_verification(
        self,
        cr: DeviceConfigChangeRequest,
        *,
        status: str,
        verification_snapshot_id: int | None,
        verification_summary: dict[str, object],
        verified_at: datetime | None,
    ) -> DeviceConfigChangeRequest:
        cr.verification_status = status
        cr.verification_snapshot_id = verification_snapshot_id
        cr.verification_summary = verification_summary
        cr.verified_at = verified_at
        return self.save(cr)

    def create_payload(
        self,
        change_request_id: int,
        config_body: str,
        *,
        body_digest: str | None = None,
        body_length: int | None = None,
        line_count: int | None = None,
        summary_source: str | None = None,
    ) -> DeviceConfigChangePayload:
        body_digest = body_digest or "sha256:" + sha256(config_body.encode("utf-8")).hexdigest()
        body_length = body_length if body_length is not None else len(config_body)
        line_count = line_count if line_count is not None else len(config_body.splitlines())
        payload = DeviceConfigChangePayload(
            change_request_id=change_request_id,
            config_body=config_body,
            body_digest=body_digest,
            body_length=body_length,
            line_count=line_count,
            summary_source=summary_source,
        )
        self.session.add(payload)
        self.session.flush()
        return payload

    def get_payload(self, change_request_id: int) -> DeviceConfigChangePayload | None:
        return self.session.scalar(
            select(DeviceConfigChangePayload).where(
                DeviceConfigChangePayload.change_request_id == change_request_id
            )
        )

    def find_pending_rollback_proposal(
        self, rollback_of_change_id: int
    ) -> DeviceConfigChangeRequest | None:
        return self.session.scalar(
            select(DeviceConfigChangeRequest).where(
                DeviceConfigChangeRequest.rollback_of_change_id == rollback_of_change_id,
                DeviceConfigChangeRequest.is_rollback.is_(True),
                DeviceConfigChangeRequest.status == "pending_approval",
            )
        )

    def find_latest_rollback_proposal(
        self, rollback_of_change_id: int
    ) -> DeviceConfigChangeRequest | None:
        return self.session.scalar(
            select(DeviceConfigChangeRequest)
            .where(
                DeviceConfigChangeRequest.rollback_of_change_id == rollback_of_change_id,
                DeviceConfigChangeRequest.is_rollback.is_(True),
            )
            .order_by(DeviceConfigChangeRequest.id.desc())
            .limit(1)
        )


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, **kwargs: object) -> AuditLog:
        log = AuditLog(**kwargs)
        self.session.add(log)
        self.session.flush()
        return log

    def list_paginated(
        self,
        *,
        actor_user_id: int | None = None,
        action: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        outcome: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        q = select(AuditLog).order_by(AuditLog.created_at.desc())
        if actor_user_id is not None:
            q = q.where(AuditLog.actor_user_id == actor_user_id)
        if action:
            q = q.where(AuditLog.action == action)
        if target_type:
            q = q.where(AuditLog.target_type == target_type)
        if target_id:
            q = q.where(AuditLog.target_id == target_id)
        if outcome:
            q = q.where(AuditLog.outcome == outcome)
        if since:
            q = q.where(AuditLog.created_at >= since)
        if until:
            q = q.where(AuditLog.created_at <= until)
        return list(self.session.scalars(q.limit(limit).offset(offset)))
