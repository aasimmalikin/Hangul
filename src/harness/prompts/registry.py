import hashlib
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel

PROMPTS_DIR = Path(__file__).parent / "templates"

class Prompt(BaseModel):
    name: str
    text: str
    version: str

@lru_cache
def get_prompt(name:str)->Prompt:
    path = PROMPTS_DIR / f"{name}.txt"
    text = path.read_text(encoding="utf-8").strip()
    version = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return Prompt(name = name, text = text, version = version)
    