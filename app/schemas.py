from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

# Strings are stripped first, then length-checked, so "   " is rejected as empty.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", "email")
    @classmethod
    def normalize_to_lowercase(cls, value: str) -> str:
        return value.lower()  # usernames and emails are case-insensitive


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PostCreate(BaseModel):
    title: Title
    content: Content


class PostUpdate(BaseModel):
    """PUT replaces the whole post, so both fields are required."""
    title: Title
    content: Content


class PostPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    owner_id: int
