from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.auth.repositories import RoleRepository, UserRepository

logger = logging.getLogger(__name__)


def bootstrap_admin(session: Session, username: str, password: str) -> None:
    """Create initial admin user if it does not already exist."""
    user_repo = UserRepository(session)
    role_repo = RoleRepository(session)

    if user_repo.get_by_username(username) is not None:
        logger.info("bootstrap: admin user '%s' already exists, skipping", username)
        return

    admin_role = role_repo.get_by_name("admin")
    if admin_role is None:
        logger.error("bootstrap: 'admin' role not found; run seed first")
        return

    user = user_repo.create(
        username=username,
        display_name="Administrator",
        password_hash=hash_password(password),
    )
    user.roles.append(admin_role)
    session.commit()
    logger.info("bootstrap: created admin user '%s'", username)
