"""Per-request session identity. A session is an opaque ID that scopes a
visitor's uploaded documents. No accounts, no auth — ephemeral by design.
Production would swap this for real auth."""

import uuid
from fastapi import Header

def get_session_id(x_session_id: str | None = Header(default = None))->str:
    return x_session_id or "sess-" + uuid.uuid4().hex[:16]