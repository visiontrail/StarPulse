from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.storage.models import Device
from app.storage.repositories import Repository


class DeviceRepository(Repository[Device]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Device)

    def list(self) -> list[Device]:
        return list(
            self.session.scalars(select(Device).options(selectinload(Device.connection))).all()
        )

    def get_with_connection(self, device_id: int) -> Device | None:
        return self.session.scalar(
            select(Device)
            .where(Device.id == device_id)
            .options(selectinload(Device.connection))
        )

