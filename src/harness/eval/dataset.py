import json
from pathlib import Path
from pydantic import BaseModel

class EvalCase(BaseModel):
    id: str
    question: str
    reference: str

def load_case(path:Path)->list[EvalCase]:
    lines = Path(path).read_text().strip().splitlines()
    return [EvalCase(**json.loads(line)) for line in lines]