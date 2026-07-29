from typing import Protocol
from pydantic import BaseModel

class Completion(BaseModel):
    """Represents a single completion from a model."""
    text: str
    model: str
    token_in: int = 0
    token_out: int = 0

class Provider(Protocol):
    """Abstract class for a provider that can generate completions."""
    async def complete(self, *, system: str, question:str)->Completion: ...

