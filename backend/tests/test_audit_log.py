from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.audit import write_audit_event
from app.auth.constants import AuditAction, AuditOutcome
from tests.conftest import auth_headers, get_token


def test_audit_event_created_on_login(client: TestClient, viewer_user, db_session: Session):
    client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "Password1!"})
    token = get_token(client, "viewer1")
    resp = client.get("/api/v1/audit/logs", headers=auth_headers(token))
    assert resp.status_code == 200
    actions = [item["action"] for item in resp.json()["items"]]
    assert AuditAction.LOGIN_SUCCESS in actions


def test_audit_event_created_on_login_failure(client: TestClient, viewer_user, db_session: Session):
    client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "WRONG"})
    token = get_token(client, "viewer1")
    resp = client.get("/api/v1/audit/logs", headers=auth_headers(token))
    assert resp.status_code == 200
    actions = [item["action"] for item in resp.json()["items"]]
    assert AuditAction.LOGIN_FAILURE in actions


def test_audit_metadata_redaction(db_session: Session):
    write_audit_event(
        session=db_session,
        action=AuditAction.LOGIN_FAILURE,
        outcome=AuditOutcome.FAILURE,
        metadata={"password": "secret123", "username": "test"},
    )
    db_session.commit()
    from app.auth.repositories import AuditLogRepository
    logs = AuditLogRepository(db_session).list_paginated(action=AuditAction.LOGIN_FAILURE)
    assert logs, "expected audit log"
    meta = logs[0].metadata_json
    assert meta.get("password") == "***REDACTED***"
    assert meta.get("username") == "test"


def test_permission_denied_audit(client: TestClient, viewer_user, db_session: Session):
    token = get_token(client, "viewer1")
    client.get("/api/v1/admin/users", headers=auth_headers(token))
    resp = client.get("/api/v1/audit/logs", headers=auth_headers(token))
    actions = [item["action"] for item in resp.json()["items"]]
    assert AuditAction.PERMISSION_DENIED in actions
