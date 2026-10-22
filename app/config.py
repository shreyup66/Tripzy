from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = DEV_SECRET
    database_url: str = "sqlite:///./tripzy.db"
    places_provider: str = "mock"  # "mock" or "osm"
    places_api_key: str = ""
    places_timeout_seconds: float = 10.0
    places_user_agent: str = "Tripzy/1.0 (student coursework project)"
    session_max_age_seconds: int = 14 * 24 * 3600

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and (settings.secret_key == DEV_SECRET or len(settings.secret_key) < 32):
        raise RuntimeError("Set a long random SECRET_KEY before running in production.")
    return settings
