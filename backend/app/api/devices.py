from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate, DeviceRead
from app.api.schemas.task import TaskRead
from app.devices.service import (
    DeviceConnectionConfigMissingError,
    DeviceCredentialUnavailableError,
    DeviceService,
)
from app.storage.database import get_session
from app.tasks.service import TaskService

router = APIRouter(prefix="/devices", tags=["devices"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, session: SessionDep) -> DeviceRead:
    device = DeviceService(session).create_device(payload)
    return DeviceRead.model_validate(device)


@router.get("", response_model=list[DeviceRead])
def list_devices(session: SessionDep) -> list[DeviceRead]:
    devices = DeviceService(session).list_devices()
    return [DeviceRead.model_validate(device) for device in devices]


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(device_id: int, session: SessionDep) -> DeviceRead:
    device = DeviceService(session).get_device(device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return DeviceRead.model_validate(device)


@router.post(
    "/{device_id}/connection-test",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_connection_test(device_id: int, session: SessionDep) -> TaskRead:
    _ensure_ready(device_id, session)
    task_status = TaskService(session).submit_connection_test(device_id)
    return TaskRead.model_validate(task_status)


@router.post(
    "/{device_id}/capability-discovery",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_capability_discovery(device_id: int, session: SessionDep) -> TaskRead:
    _ensure_ready(device_id, session)
    task_status = TaskService(session).submit_capability_discovery(device_id)
    return TaskRead.model_validate(task_status)


def _ensure_ready(device_id: int, session: Session) -> None:
    try:
        DeviceService(session).ensure_ready_for_device_task(device_id)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        ) from None
    except DeviceConnectionConfigMissingError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device connection config is missing",
        ) from None
    except DeviceCredentialUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device credential is unavailable",
        ) from None
