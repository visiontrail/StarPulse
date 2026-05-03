from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.constants import AuditAction
from app.auth.repositories import AuditLogRepository, RoleRepository
from tests.conftest import auth_headers, get_token


def test_login_success(client: TestClient, viewer_user):
    resp = client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "Password1!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["username"] == "viewer1"
    assert "password" not in str(data)


def test_login_wrong_password(client: TestClient, viewer_user):
    resp = client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client: TestClient):
    resp = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


def test_login_disabled_user(client: TestClient, db_session: Session, viewer_user):
    viewer_user.is_active = False
    db_session.commit()
    resp = client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "Password1!"})
    assert resp.status_code == 401


def test_get_me(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "viewer1"
    assert data["session_valid"] is True
    assert "password" not in str(data)
    assert "token" not in str(data)


def test_unauthenticated_returns_401(client: TestClient):
    resp = client.get("/api/v1/devices")
    assert resp.status_code == 401


def test_logout(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert resp.status_code == 204


def test_refresh_rotates_and_revokes_previous_token(client: TestClient, viewer_user):
    get_token(client, "viewer1")
    old_refresh = client.cookies.get("refresh_token")
    assert old_refresh

    refresh_resp = client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh
    assert new_refresh != old_refresh

    client.cookies.set("refresh_token", old_refresh)
    reused_resp = client.post("/api/v1/auth/refresh")
    assert reused_resp.status_code == 401


def test_logout_revokes_current_refresh_token(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token

    logout_resp = client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert logout_resp.status_code == 204

    client.cookies.set("refresh_token", refresh_token)
    refresh_resp = client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 401


def test_refresh_uses_latest_roles_after_role_change(
    client: TestClient, admin_user, viewer_user, db_session: Session
):
    viewer_token = get_token(client, "viewer1")
    viewer_refresh = client.cookies.get("refresh_token")
    assert viewer_refresh
    me_before = client.get("/api/v1/auth/me", headers=auth_headers(viewer_token)).json()
    assert "device:collect" not in me_before["permissions"]

    admin_token = get_token(client, "admin1")
    operator_role = RoleRepository(db_session).get_by_name("operator")
    assert operator_role is not None
    assign_resp = client.post(
        f"/api/v1/admin/users/{viewer_user.id}/roles",
        json={"role_id": operator_role.id},
        headers=auth_headers(admin_token),
    )
    assert assign_resp.status_code == 200

    client.cookies.set("refresh_token", viewer_refresh)
    refresh_resp = client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    refreshed_token = refresh_resp.json()["access_token"]
    me_after = client.get("/api/v1/auth/me", headers=auth_headers(refreshed_token)).json()
    assert "operator" in me_after["roles"]
    assert "device:collect" in me_after["permissions"]


def test_refresh_missing_cookie_records_audit(
    client: TestClient, db_session: Session
):
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401

    logs = AuditLogRepository(db_session).list_paginated(action=AuditAction.REFRESH_FAILURE)
    assert logs


def test_health_anonymous(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_api_v1_business_routes_have_default_auth_boundary(client: TestClient):
    public_routes = {
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/refresh"),
    }
    for route in client.app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/v1"):
            continue
        methods = {method for method in route.methods if method not in {"HEAD", "OPTIONS"}}
        if all((method, route.path) in public_routes for method in methods):
            continue
        dependency_names = {dependency.call.__name__ for dependency in route.dependant.dependencies}
        assert "get_current_user" in dependency_names or "checker" in dependency_names, route.path
