from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.constants import AuditAction
from app.auth.repositories import AuditLogRepository
from tests.conftest import auth_headers, get_token


def test_admin_create_user(client: TestClient, admin_user):
    token = get_token(client, "admin1")
    resp = client.post(
        "/api/v1/admin/users",
        json={"username": "newuser", "display_name": "New User", "password": "Password1!"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert "password" not in str(data)
    assert "password_hash" not in str(data)


def test_admin_assign_role(client: TestClient, admin_user, viewer_user, db_session: Session):
    admin_token = get_token(client, "admin1")
    # Get operator role id
    roles_resp = client.get("/api/v1/admin/roles", headers=auth_headers(admin_token))
    roles = roles_resp.json()
    operator_role = next((r for r in roles if r["name"] == "operator"), None)
    assert operator_role is not None

    resp = client.post(
        f"/api/v1/admin/users/{viewer_user.id}/roles",
        json={"role_id": operator_role["id"]},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    role_names = [r["name"] for r in resp.json()["roles"]]
    assert "operator" in role_names

    logs = AuditLogRepository(db_session).list_paginated(action=AuditAction.ROLE_ASSIGNED)
    assert logs
    assert logs[0].metadata_json["roles_before"] == ["viewer"]
    assert logs[0].metadata_json["roles_after"] == ["operator", "viewer"]


def test_admin_disable_user(client: TestClient, admin_user, viewer_user):
    admin_token = get_token(client, "admin1")
    resp = client.post(
        f"/api/v1/admin/users/{viewer_user.id}/disable",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
