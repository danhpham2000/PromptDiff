from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    promptdiff_mode: str = "local"
    database_url: str = "sqlite:///./promptdiff.db"
    database_url_unpooled: str | None = None
    cors_origins: str = "http://localhost:3000"
    groq_api_key: str | None = None
    neon_auth_base_url: str | None = None
    neon_auth_jwks_url: str | None = None
    neon_auth_audience: str | None = None
    upstash_redis_rest_url: str | None = None
    upstash_redis_rest_token: str | None = None
    promptdiff_jwt_issuer: str = "https://app.promptdiff.dev"
    promptdiff_jwt_audience: str = "promptdiff-api"
    promptdiff_jwt_private_key: str | None = None
    promptdiff_jwt_public_key: str | None = None
    promptdiff_jwt_key_id: str = "promptdiff-2026-01"
    promptdiff_secret_encryption_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
