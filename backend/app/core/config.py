from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: Literal["dev", "staging", "prod", "test"] = "dev"
    DATABASE_URL: str = "postgresql+asyncpg://analyst:analyst@localhost:5432/analyst"
    REDIS_URL: str = "redis://localhost:6379/0"

    # S3 / MinIO
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_BUCKET: str = "analyst"
    S3_ACCESS_KEY: str = "minio"
    S3_SECRET_KEY: str = "minio12345"
    S3_REGION: str = "us-east-1"

    # Security & Tokens
    JWT_SECRET: str = "change-me-32-bytes-minimum-very-secure-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 14

    # LLM Settings
    LLM_ENABLED: bool = False
    LLM_PROVIDER: Literal["anthropic", "mock"] = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-3-5-sonnet-20241022"
    LLM_TOKEN_BUDGET_PER_DATASET: int = 200000

    @property
    def llm_enabled(self) -> bool:
        return self.LLM_ENABLED and bool(self.ANTHROPIC_API_KEY)

    @property
    def anthropic_api_key(self) -> str:
        return self.ANTHROPIC_API_KEY

    # Limits & Retention
    MAX_UPLOAD_MB: int = 200
    MAX_ROWS: int = 2000000
    MAX_COLS: int = 500
    RETENTION_DAYS: int = 30

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )


settings = Settings()
