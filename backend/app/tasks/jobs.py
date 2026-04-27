from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(name="star_pulse.sample_health")
def sample_health(task_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return {"task_id": task_id, "status": "ok", "payload": payload or {}}

