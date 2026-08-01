from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application configuration settings."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "agentic-qa"
    environment: str = Literal["dev", "prod"] 
    log_level: str = "INFO"
    openai_api_key: str | None = None
    model: str = "gpt-4o-mini"
    tavily_api_key: str | None = None

@lru_cache()
def get_settings() -> Settings:
    """ Retrieve the application settings, cached for performance. """
    return Settings()
