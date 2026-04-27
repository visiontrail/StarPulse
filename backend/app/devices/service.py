from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate
from app.devices.repository import DeviceRepository
from app.storage.models import Device, DeviceConnectionConfig


class DeviceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DeviceRepository(session)

    def create_device(self, payload: DeviceCreate) -> Device:
        device = Device(
            name=payload.name,
            serial_number=payload.serial_number,
            group=payload.group,
            status=payload.status,
            metadata_json=payload.metadata,
        )
        if payload.connection is not None:
            device.connection = DeviceConnectionConfig(
                host=payload.connection.host,
                port=payload.connection.port,
                username=payload.connection.username,
                password_secret=payload.connection.password,
            )
        self.repository.add(device)
        self.repository.commit()
        return device

    def list_devices(self) -> list[Device]:
        return self.repository.list()

    def get_device(self, device_id: int) -> Device | None:
        return self.repository.get_with_connection(device_id)
