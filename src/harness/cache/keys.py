"""The cache key. The rule: everything that can change the answer goes in the
hash, and nothing that can't (like the per-request run_id) may."""


import json
import hashlib

def answer_key(*, question: str, prompt_version: str, model: str, tool_names: list[str]) -> str:
    payload = json.dumps(
        {
            "q": question, "pv": prompt_version, "m": model, "t": sorted(tool_names)
        }, sort_keys = True,
    )
    return "answer" + hashlib.sha256(payload.encode()).hexdigest()[:16]