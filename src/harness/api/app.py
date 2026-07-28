import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from harness.logging import configure_logging, log
from harness.config import get_settings
from harness.api.routes import ask, health

settings = get_settings()
configure_logging(settings.log_level)

@asynccontextmanager

async def lifespan(app: FastAPI):
    log.info("Starting up", app_name = settings.app_name, env = settings.environment)
    yield
    log.info("harness shutting down")

def create_app() -> FastAPI:
    app = FastAPI(title = settings.app_name, lifespan = lifespan)
    app.include_router(ask.router)
    app.include_router(health.router)
    return app

app = create_app()