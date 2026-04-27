from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.storage.models import TaskStatus
from app.tasks.jobs import sample_health


class TaskService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def submit_sample_task(self, task_type: str, payload: dict[str, object]) -> TaskStatus:
        task_id = str(uuid4())
        task_status = TaskStatus(
            task_id=task_id,
            task_type=task_type,
            status="queued",
            metadata_json={"payload": payload},
        )
        self.session.add(task_status)
        self.session.commit()
        self.session.refresh(task_status)
        sample_health.delay(task_id, payload)
        return task_status

    def get_task(self, task_id: str) -> TaskStatus | None:
        return self.session.scalar(select(TaskStatus).where(TaskStatus.task_id == task_id))
