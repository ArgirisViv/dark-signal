from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import AliasChoices, Field
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parents[2]
_ENV_ROOT = _BASE_DIR / ".env"
_ENV_BACKEND = _BASE_DIR / "backend" / ".env"

class Settings(BaseSettings):
    APP_NAME: str = "Dark Signal"
    APP_MODE: str = "EDUCATIONAL"
    LOG_LEVEL: str = "INFO"
    # Default is for local dev only; override via .env/ENV in real deployments.
    SECRET_KEY: str = "dev-insecure-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    SIMULATION_LINK_BASE_URL: str = "http://127.0.0.1:8000"
    DATABASE_URL: Optional[str] = None
    AUTO_CREATE_SCHEMA: bool = True
    bootstrap_token: Optional[str] = Field(default=None, validation_alias="BOOTSTRAP_TOKEN")
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_SANDBOX_MODE: bool = False
    SMTP_SANDBOX_RECIPIENT: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "LLM_API_KEY"),
    )
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-5.6"
    OPENAI_TIMEOUT_SECONDS: float = 45.0

    model_config = SettingsConfigDict(
        env_file=(str(_ENV_ROOT), str(_ENV_BACKEND)),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = Settings()
