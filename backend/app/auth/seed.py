from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.constants import ALL_PERMISSIONS, ROLE_PERMISSIONS
from app.auth.repositories import PermissionRepository, RoleRepository

logger = logging.getLogger(__name__)


def seed_permissions_and_roles(session: Session) -> None:
    perm_repo = PermissionRepository(session)
    role_repo = RoleRepository(session)

    perm_map: dict[str, object] = {}
    for perm_name in ALL_PERMISSIONS:
        perm = perm_repo.get_by_name(perm_name)
        if perm is None:
            perm = perm_repo.create(perm_name)
            logger.info("seeded permission: %s", perm_name)
        perm_map[perm_name] = perm

    for role_name, perm_names in ROLE_PERMISSIONS.items():
        role = role_repo.get_by_name(role_name)
        if role is None:
            role = role_repo.create(role_name, description=f"Seeded role: {role_name}")
            logger.info("seeded role: %s", role_name)

        existing_perm_names = {p.name for p in role.permissions}
        for perm_name in perm_names:
            if perm_name not in existing_perm_names:
                perm = perm_map[perm_name]
                role.permissions.append(perm)  # type: ignore[arg-type]

    session.commit()
    logger.info("permission/role seed complete")
