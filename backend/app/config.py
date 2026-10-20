from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://arl:change-me@localhost:5432/arl"
    # If unset, the API is open (local development only). Set it for any shared deployment.
    api_key: SecretStr | None = None
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    mock_simulate_latency: bool = True
    max_import_bytes: int = 5_000_000

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_means_disabled(cls, v: object) -> object:
        return None if v in ("", None) else v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
