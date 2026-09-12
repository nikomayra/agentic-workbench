from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )

    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://workbench:workbench@localhost:5432/workbench"
    )
    cors_origins: str = "http://localhost:5173"
    openai_api_key: str = ""


settings = Settings()
