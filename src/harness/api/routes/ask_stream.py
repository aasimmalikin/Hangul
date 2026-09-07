import asyncio
import json

from fastapi import Request, APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from harness.api.auth import get_current_user
from harness.api.routes.ask import AskRequest, _build_and_run

router = APIRouter()


@router.post("/ask/stream")
async def ask_stream(req: AskRequest, request: Request,
                     user: dict = Depends(get_current_user)):
    user_id = user["user_id"]

    # Bridge between the agent (producing tokens) and the SSE generator
    # (sending them). The agent runs as a background task and pushes tokens
    # onto this queue via the on_token callback; the generator drains it live.
    queue: asyncio.Queue = asyncio.Queue()

    def on_token(text: str) -> None:
        queue.put_nowait(("token", text))

    async def run_and_signal():
        """Run the agent in the background; put the final outcome (or error)
        on the queue when done so the generator knows to stop."""
        try:
            outcome = await _build_and_run(req, user_id, on_token=on_token)
            await queue.put(("outcome", outcome))
        except Exception as e:  # noqa: BLE001
            await queue.put(("error", str(e)))

    async def event_generator():
        task = asyncio.create_task(run_and_signal())
        try:
            while True:
                if await request.is_disconnected():
                    task.cancel()
                    return

                kind, payload = await queue.get()

                if kind == "token":
                    # A live token from the streaming final turn.
                    yield {"event": "token", "data": json.dumps({"text": payload})}

                elif kind == "error":
                    yield {"event": "error", "data": json.dumps({"message": payload})}
                    return

                elif kind == "outcome":
                    # The run finished. Emit tool calls, approval (if paused),
                    # and done. Note: if tokens already streamed, the answer is
                    # on screen; we do NOT re-send it as a token here.
                    outcome = payload
                    r = outcome.result

                    for tool_name in r.tools_used:
                        yield {"event": "tool_call",
                               "data": json.dumps({"tool": tool_name})}

                    if r.pending_tool:
                        yield {"event": "approval_required", "data": json.dumps({
                            **r.pending_tool,
                            "run_id": outcome.run.run_id,
                        })}
                        # A paused run streamed no answer tokens; the card stands
                        # alone, so nothing else to send but done.
                    elif not _streamed_any(r):
                        # Fallback: if for some reason no tokens streamed (e.g.
                        # a cached path or non-streaming turn), send the answer
                        # once so the user still sees it.
                        yield {"event": "token",
                               "data": json.dumps({"text": r.answer})}

                    yield {"event": "done", "data": json.dumps({
                        "steps": r.steps,
                        "run_id": outcome.run.run_id,
                        "cost_usd": outcome.run_cost,
                    })}
                    return
        finally:
            if not task.done():
                task.cancel()

    return EventSourceResponse(event_generator())


def _streamed_any(result) -> bool:
    """Whether the run produced streamed tokens. Heuristic: a paused run or an
    empty answer means nothing streamed."""
    return bool(result.answer) and result.pending_tool is None
