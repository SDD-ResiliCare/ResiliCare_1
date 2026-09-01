"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "ResiliCare API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_url: str = "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json"
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in self.cors_origins_raw.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
