import json
from pathlib import Path
from harness.checkpoint.checkpoint import Checkpoint
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert
from harness.db.base import SessionLocal
from harness.db.models import Thread


class CheckpointStore:

    def load(self, thread_id: str)->Checkpoint | None:
        with SessionLocal() as session:
            row = session.get(Thread, thread_id)
            if row is None:
                return None
            return Checkpoint(
                thread_id=row.thread_id,
                message=row.message or [],
                step=row.step,
                status = row.status,
                completed_calls=row.completed_calls or {},
                pending_tool=row.pending_tool,
            )
    
    def save(self, cp: Checkpoint)-> None:
        values = {
            "thread_id": cp.thread_id, 
            "message": cp.message,
            "step": cp.step,
            "status": cp.status,
            "completed_calls":cp.completed_calls,
            "pending_tool": cp.pending_tool,
        }
        stmt = insert(Thread).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements = [Thread.thread_id], 
            set_ = {
                "message": stmt.excluded.message,
                "step": stmt.excluded.step,
                "status": stmt.excluded.status,
                "completed_calls": stmt.excluded.completed_calls,
                "pending_tool":stmt.excluded.pending_tool,
            },
        )
        with SessionLocal() as session:
            session.execute(stmt)
            session.commit()
    
    def delete(self, thread_id: str)->None:
        with SessionLocal() as session:
            row = session.get(Thread, thread_id)
            if row is not None:
                session.delete(row)
                session.commit()


