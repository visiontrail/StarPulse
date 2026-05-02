from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.audit import write_audit_event
from app.auth.constants import AuditAction, AuditOutcome
from app.auth.repositories import AuditLogRepository
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
    logs = AuditLogRepository(db_session).list_paginated(action=AuditAction.LOGIN_FAILURE)
    assert logs, "expected audit log"
    meta = logs[0].metadata_json
    assert meta.get("password") == "***REDACTED***"
    assert meta.get("username") == "test"


def test_permission_denied_audit(client: TestClient, viewer_user, db_session: Session):
    token = get_token(client, "viewer1")
    client.get("/api/v1/admin/users", headers=auth_headers(token))
    db_session.rollback()
    resp = client.get("/api/v1/audit/logs", headers=auth_headers(token))
    actions = [item["action"] for item in resp.json()["items"]]
    assert AuditAction.PERMISSION_DENIED in actions


def test_config_snapshot_validation_failure_is_audited(
    client: TestClient, operator_user, db_session: Session
):
    token = get_token(client, "operator1")
    resp = client.post(
        "/api/v1/devices/999/config-snapshots",
        json={"datastore": "intended"},
        headers=auth_headers(token),
    )

    assert resp.status_code == 400
    logs = AuditLogRepository(db_session).list_paginated(action=AuditAction.VALIDATION_FAILED)
    assert logs
    assert logs[0].permission == "device:collect"
    assert logs[0].metadata_json["reason"] == "unsupported_datastore"
