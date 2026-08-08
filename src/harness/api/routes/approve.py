"""POST /approve — resume a paused run after a human decision."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from harness.agent.loop import run_agent
from harness.logging import log
from harness.providers import get_provider
from harness.prompts.registry import get_prompt
from harness.api.session import get_session_id
from harness.obs.tracing import Trace, cost_usd
from harness.policy.guarded import guarded_dispatch

from harness.api.routes.ask import (
    _store, _audit, _policy, _trace_store, _registry, AskResponse,
)
from harness.tools.registry import ToolRegistry
from harness.tools.builtin.calculator import CALCULATOR_TOOL
from harness.tools.builtin.web_search import WEB_SEARCH_TOOL
from harness.tools.builtin.search_docs_session import make_search_docs_tool
from harness.tools.builtin.filesystem_session import wrap_filesystem_tool

router = APIRouter()


class ApproveRequest(BaseModel):
    approval_id: str
    decision: str

#764c6b934c9c4176b91fcbe5195da93b
def _build_session_registry(session_id: str) -> ToolRegistry:
    reg = ToolRegistry()
    reg.registry(make_search_docs_tool(session_id))
    reg.registry(CALCULATOR_TOOL)
    reg.registry(WEB_SEARCH_TOOL)
    for t in _registry.list():
        if t.name.startswith("filesystem__"):
            reg.registry(wrap_filesystem_tool(t, session_id))
    return reg


def _replace_placeholder(messages: list[dict], tool_call_id: str, content: str) -> None:
    """Overwrite the [awaiting human approval] placeholder with the real result."""
    for m in messages:
        if m.get("role") == "tool" and m.get("tool_call_id") == tool_call_id:
            m["content"] = content
            return
    # if not found (shouldn't happen), append it
    messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})


@router.post("/approve", response_model=AskResponse)
async def approve(req: ApproveRequest, session_id: str = Depends(get_session_id)) -> AskResponse:
    cp = _store.load(req.approval_id)
    if cp is None or cp.pending_tool is None:
        raise HTTPException(status_code=404, detail="No pending action for that approval id.")

    pending = cp.pending_tool
    model = get_provider().model
    prompt_version = get_prompt("system_agent")
    session_registry = _build_session_registry(session_id)

    if req.decision == "reject":
        content = (f"The user REJECTED the action '{pending['name']}'. "
                   f"Do not attempt it. Continue and answer without it.")
        log.info("action rejected", tool=pending["name"])
    else:
        try:
            args = dict(pending["arguments"])
            # FORCE the path inside this session's folder, whatever the agent proposed
            if "path" in args and pending["name"].startswith("filesystem__"):
                from pathlib import Path
                session_dir = (Path("data/sessions") / session_id).resolve()
                session_dir.mkdir(parents=True, exist_ok=True)
                filename = Path(args["path"]).name        # keep only the filename part
                args["path"] = str(session_dir / filename)
                log.info("forced path", original=pending["arguments"].get("path"), forced=args["path"])

            tool = session_registry.get(pending["name"])
            result = await guarded_dispatch(tool, args, _policy, _audit, approved=True)
            content = result.content
            log.info("action approved and executed", tool=pending["name"], result=content[:150])
        except Exception as e:  # noqa: BLE001
            content = f"Error executing approved action: {e}"
            log.warning("approved action failed", error=str(e))

    # replace the placeholder response with the real outcome, clear pending
    _replace_placeholder(cp.message, pending["tool_call_id"], content)
    cp.pending_tool = None
    cp.status = "running"
    _store.save(cp)

    trace = Trace(trace_id=req.approval_id)
    result = await run_agent(
        question="",
        prompt_text=prompt_version.text,
        registry=session_registry,
        provider=get_provider(),
        policy=_policy,
        audit=_audit,
        store=_store,
        thread_id=req.approval_id,
        trace=trace,
    )

    _trace_store.add(trace, model)
    summary = trace.summary()
    run_cost = cost_usd(model, summary["input_tokens"], summary["output_tokens"])

    return AskResponse(
        answer=result.answer,
        run_id=req.approval_id,
        prompt_version=prompt_version.version,
        steps=result.steps,
        stopped_reason=result.stopped_reason,
        cached=False,
        tools_used=result.tools_used,
        safety_blocked=result.safety_blocked,
        budget_used=result.budget_used,
        cost_usd=run_cost,
        resumed_from_step=result.resumed_from_step,
        pending_tool=result.pending_tool,
    )