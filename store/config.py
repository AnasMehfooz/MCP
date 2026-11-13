"""Settings shared by every entry point: API, MCP server, Alembic and scripts.

Values come from environment variables first, then from <project>/.env, then from the
defaults below. Claude Desktop launches the MCP server from an unpredictable working
directory, so the .env file is located from this file's path, never from the current
directory.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # `STORE_ID=` in .env means "not set"
        extra="ignore",  # .env also carries the docker-compose variables
    )

    # Default: the database from docker-compose.yml.
    database_url: str = Field(
        default="postgresql+psycopg://store:store@localhost:5432/store", validation_alias="STORE_DATABASE_URL"
    )
    # The store this process works on. Unset: the only store in the database, if there is exactly one.
    store_id: UUID | None = Field(default=None, validation_alias="STORE_ID")
    low_stock_threshold: int = Field(default=5, ge=0, validation_alias="STORE_LOW_STOCK_THRESHOLD")
    # `whsec_...`, printed by `stripe listen`. Unset: the webhook route rejects every request.
    stripe_webhook_secret: SecretStr | None = Field(default=None, validation_alias="STRIPE_WEBHOOK_SECRET")

    @field_validator("database_url")
    @classmethod
    def _postgres_with_psycopg(cls, url: str) -> str:
        scheme, _, rest = url.partition("://")
        if scheme in ("postgres", "postgresql"):  # no driver given: use the one this project installs
            return f"postgresql+psycopg://{rest}"
        if not scheme.startswith("postgresql+"):
            raise ValueError("must be a postgresql:// URL; the store needs Postgres with pgvector")
        return url


settings = Settings()
