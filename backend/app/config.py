"""
SENTINEL Backend — Application Settings
Reads from .env file via pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AssemblyAI
    assemblyai_api_key: str = ""
    sentinel_agent_id: str = ""

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Phase 5 — Incident persistence & supervisor notification
    sentinel_db_path: str = "sentinel.db"
    supervisor_webhook_url: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Environment
    environment: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
