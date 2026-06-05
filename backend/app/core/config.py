from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BACKEND_DIR / "app.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env")

    APP_NAME: str = "Campus AI Match"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600

    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_PRO_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_FLASH_MODEL: str = "deepseek-v4-flash"

    QWEN_EMBED_PATH: str = "model_cache/Qwen3-Embedding-0.6B"
    QWEN_RERANK_PATH: str = "model_cache/Qwen3-Reranker-0.6B"
    QWEN_EMBED_MRL_DIM: int = 0

    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    SENTRY_DSN: str = ""

    # SMTP (optional — email verification & password reset)
    SMTP_HOST: str = ""
    SMTP_PORT: str = "587"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@campus-match.com"

    # Site domain
    DOMAIN: str = "http://localhost"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value


def is_postgres() -> bool:
    return "postgresql" in settings.DATABASE_URL


def is_sqlite() -> bool:
    return "sqlite" in settings.DATABASE_URL


settings = Settings()
