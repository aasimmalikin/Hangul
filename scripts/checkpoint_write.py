#!/usr/bin/env python3
"""Write a checkpoint, then exit.

Half one of the persistence proof. Run this, let the process die, then run
checkpoint_read.py in a fresh process. If the data comes back, the store is
genuinely persisting rather than holding state in memory.
"""
from harness.checkpoint.store import Checkpoint, CheckpointStore

THREAD_ID = "persistence-probe"

store = CheckpointStore()
store.save(Checkpoint(
    thread_id=THREAD_ID,
    message=[
        {"role": "user", "content": "does this survive a restart"},
        {"role": "assistant", "content": "we are about to find out"},
    ],
    step=3,
    completed_calls={"a3f8c21d": "tool result from an earlier step"},
    pending_tool={"name": "filesystem__write_file", "arguments": {"path": "notes.md"}},
))

print(f"wrote checkpoint for thread_id={THREAD_ID!r}")
print("now run: uv run python scripts/checkpoint_read.py")