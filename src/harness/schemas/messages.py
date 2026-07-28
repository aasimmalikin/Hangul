from typing import Literal
from pydantic import BaseModel

class Message(BaseModel):
    """One turn in a conversation"""
    role: Literal["system", "user", "assistant"]
    content: str