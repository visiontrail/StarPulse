from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, get_token


def test_viewer_cannot_submit(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.post(
        "/api/v1/change-requests",
        json={"device_id": 1, "datastore": "running", "change_summary": "test", "reason": "test"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_operator_submit_invalid_device(client: TestClient, operator_user):
    token = get_token(client, "operator1")
    resp = client.post(
        "/api/v1/change-requests",
        json={"device_id": 99999, "datastore": "running", "change_summary": "test", "reason": "testing"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


def test_direct_execute_requires_reason(client: TestClient, approver_user):
    token = get_token(client, "approver1")
    resp = client.post(
        "/api/v1/change-requests/direct-execute",
        json={"device_id": 1, "datastore": "running", "change_summary": "test", "reason": ""},
        headers=auth_headers(token),
    )
    assert resp.status_code in (400, 422)


def test_viewer_cannot_direct_execute(client: TestClient, viewer_user):
    token = get_token(client, "viewer1")
    resp = client.post(
        "/api/v1/change-requests/direct-execute",
        json={"device_id": 1, "datastore": "running", "change_summary": "test", "reason": "emergency"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_operator_cannot_approve(client: TestClient, operator_user):
    token = get_token(client, "operator1")
    resp = client.post(
        "/api/v1/change-requests/1/approve",
        json={"approval_note": None},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
