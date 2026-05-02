from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
    assert "password" not in str(data)
    assert "token" not in str(data)


def test_unauthenticated_returns_401(client: TestClient):
    resp = client.get("/api/v1/devices")
    assert resp.status_code == 401


def test_logout(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert resp.status_code == 204


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
