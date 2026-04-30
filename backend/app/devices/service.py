from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate
from app.devices.constants import DeviceStatus
from app.devices.credentials import CredentialService, CredentialUnavailableError
from app.devices.repository import DeviceRepository
from app.storage.models import Device, DeviceConnectionConfig


class DeviceConnectionConfigMissingError(RuntimeError):
    pass


class DeviceCredentialUnavailableError(RuntimeError):
    pass


class DeviceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DeviceRepository(session)
        self.credentials = CredentialService(session)

    def create_device(self, payload: DeviceCreate) -> Device:
        device = Device(
            name=payload.name,
            serial_number=payload.serial_number,
            group=payload.group,
            status=payload.status,
            metadata_json=payload.metadata,
        )
        if payload.connection is not None:
            credential_ref = self.credentials.save_password(payload.connection.password)
            device.connection = DeviceConnectionConfig(
                protocol=payload.connection.protocol,
                host=payload.connection.host,
                port=payload.connection.port,
                username=payload.connection.username,
                credential_ref=credential_ref,
            )
            if payload.status == DeviceStatus.PLANNED:
                device.status = DeviceStatus.READY
        self.repository.add(device)
        self.repository.commit()
        return device

    def list_devices(self) -> list[Device]:
        return self.repository.list()

    def get_device(self, device_id: int) -> Device | None:
        return self.repository.get_with_connection(device_id)

    def ensure_ready_for_device_task(self, device_id: int) -> Device:
        device = self.repository.get_with_connection(device_id)
        if device is None:
            raise LookupError("Device not found")
        if device.connection is None:
            raise DeviceConnectionConfigMissingError("Device connection config is missing")
        try:
            self.credentials.resolve(device.connection.credential_ref)
        except CredentialUnavailableError as exc:
            raise DeviceCredentialUnavailableError("Device credential is unavailable") from exc
        return device
