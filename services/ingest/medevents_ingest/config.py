"""Settings loaded from environment."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings; read once at startup."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql://medevents:medevents@localhost:5432/medevents",
        alias="DATABASE_URL",
    )


def get_settings() -> Settings:
    return Settings()
