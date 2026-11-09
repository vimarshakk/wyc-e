"""Centralized config loaded from env."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


class Settings:
    MONGO_URL: str = os.environ["MONGO_URL"]
    DB_NAME: str = os.environ["DB_NAME"]
    CORS_ORIGINS: str = os.environ["CORS_ORIGINS"]
    EMERGENT_LLM_KEY: str = os.environ.get("EMERGENT_LLM_KEY", "")
    JWT_SECRET: str = os.environ["JWT_SECRET"]
    TOKEN_ENCRYPTION_KEY: str = os.environ["TOKEN_ENCRYPTION_KEY"]
    JWT_ALGO: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24 * 7
    APP_NAME: str = os.environ.get("APP_NAME", "wyshcare")
    STORAGE_URL: str = "https://integrations.emergentagent.com/objstore/api/v1/storage"
    EMERGENT_AUTH_URL: str = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


settings = Settings()
