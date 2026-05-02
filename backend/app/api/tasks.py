from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.task import TaskCreate, TaskRead
from app.auth.constants import PERM_TASK_READ
from app.auth.dependencies import SessionDep, require_permission
from app.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_permission(PERM_TASK_READ)],
)
def submit_task(payload: TaskCreate, session: SessionDep) -> TaskRead:
    task_status = TaskService(session).submit_sample_task(payload.task_type, payload.payload)
    return TaskRead.model_validate(task_status)


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    dependencies=[require_permission(PERM_TASK_READ)],
)
def get_task(task_id: str, session: SessionDep) -> TaskRead:
    task_status = TaskService(session).get_task(task_id)
    if task_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task_status)
