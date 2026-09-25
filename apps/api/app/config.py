from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    promptdiff_mode: str = "local"
    database_url: str = "sqlite:///./promptdiff.db"
    cors_origins: str = "http://localhost:3000"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

