from fastapi import APIRouter

from harness.api.routes.ask import _trace_store

router = APIRouter()


@router.get("/traces")
async def traces(n: int = 20):
    return {"traces": _trace_store.recent(n)}


@router.get("/metrics")
async def metrics():
    return _trace_store.metrics()
