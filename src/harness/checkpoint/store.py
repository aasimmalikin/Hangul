import json
from pathlib import Path
from harness.checkpoint.checkpoint import Checkpoint

class CheckpointStore:
    def __init__(self, path: str = "data/checkpoints.json")->None:
        self.path = Path(path)
        self._all: dict[str, dict] = {}
        if self.path.exists():
            self._all = json.loads(self.path.read_text())
    
    def save(self, cp: Checkpoint)->None:
        self._all[cp.thread_id] = cp.model_dump()
        self.path.parent.mkdir(parents = True, exist_ok = True)
        self.path.write_text(json.dumps(self._all, indent = 2))
    
    def load(self, thread_id: str)->Checkpoint | None:
        raw = self._all.get(thread_id)
        return Checkpoint(**raw) if raw else None

