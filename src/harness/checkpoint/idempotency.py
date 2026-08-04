import hashlib
import json

def call_key(thread_id:str, tool_name: str, args: dict)->str:
    payload = json.dumps({"t": thread_id, "n": tool_name, "a": args}, sort_keys = True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]