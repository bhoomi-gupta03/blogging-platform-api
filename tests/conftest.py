import os

# Set BEFORE the app is imported, so the tests can never use your real
# database or secret, even if your shell or .env contains real values.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-only-secret-" + "0123456789abcdef" * 2

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import PASSWORD, auth_header, login, register  # noqa: E402


@pytest.fixture
def engine():
    """A brand-new in-memory database for every test."""
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def db_session(session_factory):
    """Direct database access for assertions (e.g. is the password hashed?)."""
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # No "with" block on purpose: startup is skipped, so create_tables() never
    # touches the application's real engine.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(client):
    """Register and log in a user; returns that user's Authorization header."""

    def _make(username: str = "writer", email: str | None = None) -> dict[str, str]:
        register(client, username, email or f"{username}@example.com")
        return auth_header(login(client, username, PASSWORD))

    return _make
