from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import delete, select

from app.models import User
from app.security import create_access_token
from tests.helpers import PASSWORD, auth_header, login, register

SECRET = "test-only-secret-" + "0123456789abcdef" * 2


# ---------- registration ----------
def test_register_success_returns_public_fields_only(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "writer" and body["email"] == "writer@example.com"
    assert set(body) == {"id", "username", "email", "created_at"}


def test_password_is_stored_hashed_not_plaintext(client, db_session):
    register(client)
    user = db_session.scalar(select(User).where(User.username == "writer"))
    assert user.hashed_password != PASSWORD
    assert PASSWORD not in user.hashed_password
    assert user.hashed_password.startswith("$argon2")


def test_username_and_email_are_normalized_to_lowercase(client):
    body = register(client, "MixedCase", "Mixed@Example.COM").json()
    assert body["username"] == "mixedcase"
    assert body["email"] == "mixed@example.com"


def test_duplicate_username_is_rejected(client):
    register(client, "writer", "one@example.com")
    response = register(client, "WRITER", "two@example.com")
    assert response.status_code == 409
    assert "Username" in response.json()["detail"]


def test_duplicate_email_is_rejected(client):
    register(client, "writer_one", "same@example.com")
    response = register(client, "writer_two", "SAME@example.com")
    assert response.status_code == 409
    assert "Email" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "email": "a@example.com", "password": PASSWORD},  # too short
        {"username": "bad name!", "email": "a@example.com", "password": PASSWORD},  # bad chars
        {"username": "valid_name", "email": "not-an-email", "password": PASSWORD},
        {"username": "valid_name", "email": "a@example.com", "password": "short"},
        {"username": "valid_name", "password": PASSWORD},  # email missing
        {},
    ],
)
def test_invalid_registration_data_is_rejected(client, payload):
    assert client.post("/auth/register", json=payload).status_code == 422


# ---------- login ----------
def test_login_success_returns_bearer_token(client):
    register(client)
    response = client.post("/auth/login", data={"username": "writer", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_username_is_case_insensitive(client):
    register(client, "writer")
    response = client.post("/auth/login", data={"username": "WRITER", "password": PASSWORD})
    assert response.status_code == 200


def test_login_wrong_password_and_unknown_user_give_same_error(client):
    register(client)
    wrong = client.post("/auth/login", data={"username": "writer", "password": "wrong-password"})
    unknown = client.post("/auth/login", data={"username": "nobody", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_requires_both_fields(client):
    assert client.post("/auth/login", data={"username": "writer"}).status_code == 422


def test_token_contains_subject_and_expiry(client):
    register(client)
    token = login(client)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert "sub" in payload and "exp" in payload


# ---------- token verification on a protected route ----------
def protected_call(client, headers=None):
    return client.post("/posts", json={"title": "t", "content": "c"}, headers=headers)


def test_missing_token_is_401(client):
    assert protected_call(client).status_code == 401


def test_garbage_token_is_401(client):
    assert protected_call(client, auth_header("not.a.jwt")).status_code == 401


def test_expired_token_is_401(client):
    register(client)
    expired = create_access_token(1, expires_delta=timedelta(minutes=-5))
    response = protected_call(client, auth_header(expired))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_token_signed_with_wrong_secret_is_401(client):
    register(client)
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "some-other-secret-" + "x" * 32,
        algorithm="HS256",
    )
    assert protected_call(client, auth_header(forged)).status_code == 401


def test_token_without_subject_is_401(client):
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, SECRET, algorithm="HS256"
    )
    assert protected_call(client, auth_header(token)).status_code == 401


def test_token_of_deleted_user_is_401(client, db_session):
    register(client)
    token = login(client)
    db_session.execute(delete(User))
    db_session.commit()
    assert protected_call(client, auth_header(token)).status_code == 401
