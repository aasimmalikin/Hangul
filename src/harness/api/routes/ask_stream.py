import json
from fastapi import Request, APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from harness.api.auth import get_current_user
from harness.api.routes.ask import AskRequest, _build_and_run

router = APIRouter()

@router.post("/ask/stream")
async def ask_stream(req: AskRequest, request: Request, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]

    async def event_generator():
        try:
            outcome = await _build_and_run(req, user_id)

            if await request.is_disconnected():
                return 
            r = outcome.result

            for tool_name in r.tools_used:
                yield {"event": "tool_call", "data": json.dumps({"tool": tool_name})}
            
            yield {"event": "token", "data": json.dumps({"text": r.answer})}

            if r.pending_tool:
                yield {"event": "approval_required", "data": json.dumps(r.pending_tool)}
            
            yield {"event": "done", "data": json.dumps({
                "steps": r.steps,
                "run_id": outcome.run.run_id,
                "cost_usd": outcome.run_cost,
            })}
        
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)})}
    
    return EventSourceResponse(event_generator())
