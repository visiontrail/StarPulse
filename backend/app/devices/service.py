from __future__ import annotations

from sqlalchemy import delete as sql_delete, select, update as sql_update
from sqlalchemy.orm import Session

from app.api.schemas.device import DeviceCreate
from app.devices.constants import DeviceStatus
from app.devices.credentials import CredentialService, CredentialUnavailableError
from app.devices.repository import DeviceRepository
from app.storage.models import (
    Device,
    DeviceConfigChangePayload,
    DeviceConfigChangeRequest,
    DeviceConnectionConfig,
    TaskStatus,
)


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

    def delete_device(self, device_id: int) -> bool:
        device = self.repository.get_with_connection(device_id)
        if device is None:
            return False

        # Remove all task statuses for this device first (change_request_id refs cleaned up here too)
        self.session.execute(sql_delete(TaskStatus).where(TaskStatus.device_id == device_id))

        # Collect change request IDs, then delete payloads and requests
        change_request_ids = list(
            self.session.scalars(
                select(DeviceConfigChangeRequest.id).where(
                    DeviceConfigChangeRequest.device_id == device_id
                )
            )
        )
        if change_request_ids:
            self.session.execute(
                sql_delete(DeviceConfigChangePayload).where(
                    DeviceConfigChangePayload.change_request_id.in_(change_request_ids)
                )
            )
            # Null out self-referential FK before bulk delete
            self.session.execute(
                sql_update(DeviceConfigChangeRequest)
                .where(DeviceConfigChangeRequest.device_id == device_id)
                .values(rollback_of_change_id=None)
            )
            self.session.execute(
                sql_delete(DeviceConfigChangeRequest).where(
                    DeviceConfigChangeRequest.device_id == device_id
                )
            )

        self.session.flush()
        self.session.delete(device)
        self.session.flush()
        return True

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
