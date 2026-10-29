"""Application settings, loaded from environment variables and the .env file.

Real environment variables win over .env. If JWT_SECRET is missing, too short
or still a placeholder, the app refuses to start (fail fast)."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./blogging_platform.db"
    jwt_secret: str  # no default on purpose: it must be provided
    access_token_expire_minutes: int = 30

    @field_validator("jwt_secret")
    @classmethod
    def secret_must_be_strong(cls, value: str) -> str:
        if len(value) < MIN_SECRET_LENGTH or value.lower().startswith(("replace", "change")):
            raise ValueError(
                f"JWT_SECRET must be at least {MIN_SECRET_LENGTH} characters and not a "
                "placeholder. Generate one with: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return value

    @field_validator("access_token_expire_minutes")
    @classmethod
    def expiry_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be at least 1")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
