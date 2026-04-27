from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate, DeviceRead
from app.devices.service import DeviceService
from app.storage.database import get_session

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
