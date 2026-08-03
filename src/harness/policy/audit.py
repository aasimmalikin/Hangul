import json
import time
from pathlib import Path

class AuditLog:
    def __init__(self, path:str = "data/audit.jsonl"):
        self._path = Path(path)
        self._path.parent.mkdir(parents = True, exist_ok = True)
    
    def record(self, *, tool:str, args: dict, decision:str, tier: str)->None:
        entry = {
            "ts": time.time(),
            "tool": tool, 
            "args": args, 
            "decision": decision,
            "tier": tier
        }
        with self._path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
