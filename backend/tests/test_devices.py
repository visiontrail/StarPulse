from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_and_fetch_device(client: TestClient) -> None:
    response = client.post(
        "/api/v1/devices",
        json={
            "name": "sat-router-001",
            "serial_number": "SR-001",
            "group": "leo-alpha",
            "connection": {
                "host": "192.0.2.10",
                "port": 830,
                "username": "netconf",
                "password": "secret",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "sat-router-001"
    assert body["connection"]["host"] == "192.0.2.10"

    list_response = client.get("/api/v1/devices")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/api/v1/devices/{body['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["serial_number"] == "SR-001"

