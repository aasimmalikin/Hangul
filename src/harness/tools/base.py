from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from pydantic import BaseModel

class ToolResult(BaseModel):
    ok: bool
    content: str

@dataclass
class Tool:
    name: str
    description: str
    parameter: dict[str, Any]
    handler: Callable[..., Awaitable[str]]
