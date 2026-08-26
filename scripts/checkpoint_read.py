#!/usr/bin/env python3
"""Read the checkpoint written by checkpoint_write.py, then exit.

Half two of the persistence proof. This runs in a different process from the
writer, so anything it finds must have come from Postgres.
"""
import sys

from harness.checkpoint.store import CheckpointStore

THREAD_ID = "persistence-probe"

store = CheckpointStore()
cp = store.load(THREAD_ID)

if cp is None:
    print(f"FAIL: no checkpoint found for {THREAD_ID!r}")
    print("either the write did not commit, or the store is not persisting")
    sys.exit(1)

failures = []
if cp.step != 3:
    failures.append(f"step: expected 3, got {cp.step}")
if len(cp.message) != 2:
    failures.append(f"message: expected 2 entries, got {len(cp.message)}")
if cp.completed_calls.get("a3f8c21d") != "tool result from an earlier step":
    failures.append("completed_calls: value missing or wrong")
if cp.pending_tool is None or cp.pending_tool.get("name") != "filesystem__write_file":
    failures.append("pending_tool: missing or wrong")

if failures:
    print("FAIL: checkpoint loaded but fields do not match")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)

print("PASS: checkpoint survived a process restart")
print(f"  thread_id       {cp.thread_id}")
print(f"  step            {cp.step}")
print(f"  message         {len(cp.message)} entries")
print(f"  completed_calls {len(cp.completed_calls)} entries")
print(f"  pending_tool    {cp.pending_tool['name']}")

store.delete(THREAD_ID)
print("cleaned up")