from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, get_token


def test_viewer_can_read_devices(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.get("/api/v1/devices", headers=auth_headers(token))
    assert resp.status_code == 200


def test_viewer_cannot_collect(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.post(
        "/api/v1/devices/1/config-snapshots",
        json={"datastore": "running"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_operator_can_submit_change_request(client: TestClient, operator_user):
    token = get_token(client, "operator1")
    resp = client.post(
        "/api/v1/change-requests",
        json={
            "device_id": 999,
            "datastore": "running",
            "change_summary": "test change",
            "reason": "testing"
        },
        headers=auth_headers(token),
    )
    assert resp.status_code in (201, 400)


def test_viewer_cannot_submit_change_request(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.post(
        "/api/v1/change-requests",
        json={
            "device_id": 1,
            "datastore": "running",
            "change_summary": "test",
            "reason": "test"
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_admin_can_list_users(client: TestClient, admin_user):
    token = get_token(client, "admin1")
    resp = client.get("/api/v1/admin/users", headers=auth_headers(token))
    assert resp.status_code == 200


def test_viewer_cannot_manage_users(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.get("/api/v1/admin/users", headers=auth_headers(token))
    assert resp.status_code == 403


def test_audit_log_accessible_by_viewer(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.get("/api/v1/audit/logs", headers=auth_headers(token))
    assert resp.status_code == 200


def test_approver_cannot_manage_users(client: TestClient, approver_user):
    token = get_token(client, "approver1")
    resp = client.get("/api/v1/admin/users", headers=auth_headers(token))
    assert resp.status_code == 403
