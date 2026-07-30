from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field

class RunRecord(BaseModel):
    """ Identifies one answer, for tracing and reproducibility"""
    run_id: str =  Field(default_factory = lambda: uuid4().hex)
    model: str = "unknown"
    prompt_version: str = "unknown"
    timestamp: datetime = Field(default_factory = lambda: datetime.now(timezone.utc))
