import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession
from app.models import User
from app.schemas import Token, UserCreate, UserPublic
from app.security import DUMMY_HASH, create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: DbSession):
    # username and email were already lowercased by the schema
    if db.scalar(select(User.id).where(User.username == payload.username)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username is already taken")
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced past the checks above; the database constraint caught it.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username or email is already registered")
    db.refresh(user)
    logger.info("Registered user id=%s", user.id)
    return user


@router.post("/login", response_model=Token)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    # OAuth2PasswordRequestForm reads form fields, which also makes Swagger's
    # Authorize button work with this endpoint.
    username = form_data.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))

    # Always run one password verification, even for unknown users, so response
    # time does not reveal which usernames exist.
    password_ok = verify_password(form_data.password, user.hashed_password if user else DUMMY_HASH)

    if user is None or not password_ok:
        logger.warning("Failed login attempt")
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("User id=%s logged in", user.id)
    return Token(access_token=create_access_token(user.id))
