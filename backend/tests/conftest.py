from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import create_app
from app.auth.password import hash_password
from app.auth.repositories import RoleRepository, UserRepository
from app.auth.seed import seed_permissions_and_roles
from app.storage import models  # noqa: F401
from app.storage.database import Base, get_session


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSession() as session:
        seed_permissions_and_roles(session)
        yield session


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()

    def override_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


def _make_user(
    session: Session, username: str, role_name: str, password: str = "Password1!"
) -> models.User:
    repo = UserRepository(session)
    role = RoleRepository(session).get_by_name(role_name)
    assert role is not None, f"role '{role_name}' not seeded"
    user = repo.create(
        username=username,
        display_name=username.capitalize(),
        password_hash=hash_password(password),
    )
    user.roles.append(role)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture()
def viewer_user(db_session: Session) -> models.User:
    return _make_user(db_session, "viewer1", "viewer")


@pytest.fixture()
def operator_user(db_session: Session) -> models.User:
    return _make_user(db_session, "operator1", "operator")


@pytest.fixture()
def approver_user(db_session: Session) -> models.User:
    return _make_user(db_session, "approver1", "approver")


@pytest.fixture()
def admin_user(db_session: Session) -> models.User:
    return _make_user(db_session, "admin1", "admin")


def get_token(client: TestClient, username: str, password: str = "Password1!") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def authed_client(client: TestClient, db_session: Session) -> TestClient:
    """Client pre-authenticated with an admin user."""
    _make_user(db_session, "authed_admin", "admin")
    token = get_token(client, "authed_admin")
    client.headers.update(auth_headers(token))
    return client
