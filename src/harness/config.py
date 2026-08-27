from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application configuration settings."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "agentic-qa"
    environment: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"
    openai_api_key: str | None = None
    model: str = "gpt-4o-mini"
    tavily_api_key: str | None = None
    database_url: str = "postgresql+psycopg://agentic:agentic@localhost:5432/agentic_qa"
    redis_url: str = "redis://localhost:6379/0"

def get_settings() -> Settings:
    """ Retrieve the application settings, cached for performance. """
    return Settings()
