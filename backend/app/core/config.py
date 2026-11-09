from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WYC-e Care Platform"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "wyc_e"
    frontend_url: str = "http://localhost:3000"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    claude_api_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/v1/calendar/oauth/callback"
    abdm_base_url: str | None = None
    abdm_client_id: str | None = None
    abdm_client_secret: str | None = None
    abdm_callback_secret: str | None = None
    nhcx_participant_code: str | None = None
    nhcx_callback_secret: str | None = None
    storage_bucket: str = "wyc-e-documents"
    storage_endpoint: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
