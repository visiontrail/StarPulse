from __future__ import annotations

from fastapi.testclient import TestClient

from app.ai.services import AiCapabilityService
from app.tasks.jobs import sample_health


def test_sample_task_can_run_directly() -> None:
    assert sample_health.run("task-1", {"kind": "health"}) == {
        "task_id": "task-1",
        "status": "ok",
        "payload": {"kind": "health"},
    }


def test_task_api_records_and_dispatches_task(client: TestClient, monkeypatch) -> None:
    dispatched: list[tuple[str, dict[str, object]]] = []

    def fake_delay(task_id: str, payload: dict[str, object]) -> None:
        dispatched.append((task_id, payload))

    monkeypatch.setattr("app.tasks.service.sample_health.delay", fake_delay)

    response = client.post(
        "/api/v1/tasks",
        json={"task_type": "sample.health", "payload": {"kind": "health"}},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert dispatched == [(body["task_id"], {"kind": "health"})]

    detail = client.get(f"/api/v1/tasks/{body['task_id']}")
    assert detail.status_code == 200
    assert detail.json()["metadata"] == {"payload": {"kind": "health"}}


def test_ai_placeholder_is_inert() -> None:
    summary = AiCapabilityService().summary()

    assert summary.enabled is False
    assert summary.phase == "foundation-placeholder"
    assert summary.supported_actions == ()
