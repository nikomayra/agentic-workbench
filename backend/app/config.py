from pathlib import Path

from agents import set_default_openai_key
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
    redis_url: str = "redis://:workbench@localhost:6379/0"
    managed_workspace_root: Path = (
        Path(__file__).resolve().parents[1] / ".agent_workspaces"
    )


settings = Settings()


def configure_agents() -> None:
    set_default_openai_key(settings.openai_api_key)
