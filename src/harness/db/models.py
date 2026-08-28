from datetime import datetime
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from harness.db.base import Base

class Thread(Base):
    __tablename__ = "threads"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key = True)
    message: Mapped[list] = mapped_column(JSONB, nullable = False, default = list)
    step: Mapped[int] = mapped_column(Integer, nullable = False, default = 0)
    status: Mapped[str] = mapped_column(String(32), nullable = False, default = "running")
    completed_calls: Mapped[dict] = mapped_column(JSONB, nullable = False, default = dict)
    pending_tool: Mapped[dict | None] = mapped_column(JSONB, nullable = True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone = True), server_default = func.now(), nullable = False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone = True), server_default = func.now(), onupdate = func.now(), nullable = False)

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key = True)
    google_sub: Mapped[str] = mapped_column(String(255), unique = True, nullable = False)
    email: Mapped[str] = mapped_column(String(255), nullable = False)
    role: Mapped[str] = mapped_column(String(32), nullable = False, default = "user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone = True), server_default = func.now(), nullable = False)
    

