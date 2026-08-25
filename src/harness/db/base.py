from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from harness.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping = True, 
    pool_size = 5,
    max_overflow = 10,
    future = True,
)

SessionLocal = sessionmaker(bind = engine, expire_on_commit = False, future = True)