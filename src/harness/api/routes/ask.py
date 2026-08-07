import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
import structlog
from harness.agent.loop import run_agent
from harness.logging import log
from harness.schemas.run import RunRecord
from harness.providers import get_provider
from harness.prompts.registry import get_prompt
from harness.tools.registry import ToolRegistry
from harness.tools.builtin.calculator import CALCULATOR_TOOL
from harness.tools.builtin.search_docs import SEARCH_DOCS_TOOL
from harness.tools.builtin.web_search import WEB_SEARCH_TOOL
from harness.tools.builtin.search_docs_session import make_search_docs_tool
from harness.cache.keys import answer_key
from harness.cache.memory_cache import MemoryCache
from harness.policy.policy import ToolPolicy
from harness.policy.tiers import Tier
from harness.policy.audit import AuditLog
from harness.checkpoint.store import CheckpointStore
from harness.obs.tracing import Trace, cost_usd
from harness.obs.trace_store import TraceStore
from harness.api.session import get_session_id

_audit = AuditLog()
_store = CheckpointStore()
_trace_store = TraceStore()
_policy = ToolPolicy(tiers={
    "calculator": Tier.SAFE,
    "search_docs": Tier.SAFE,
    "web_search": Tier.SAFE,
    "filesystem__read_file": Tier.SAFE,
    "filesystem__read_text_file": Tier.SAFE,
    "filesystem__read_media_file": Tier.SAFE,
    "filesystem__read_multiple_files": Tier.SAFE,
    "filesystem__list_directory": Tier.SAFE,
    "filesystem__list_directory_with_sizes": Tier.SAFE,
    "filesystem__directory_tree": Tier.SAFE,
    "filesystem__get_file_info": Tier.SAFE,
    "filesystem__search_files": Tier.SAFE,
    "filesystem__list_allowed_directories": Tier.SAFE,
    "filesystem__write_file": Tier.DESTRUCTIVE,
    "filesystem__edit_file": Tier.DESTRUCTIVE,
    "filesystem__create_directory": Tier.DESTRUCTIVE,
    "filesystem__move_file": Tier.DESTRUCTIVE,
})


router = APIRouter()
_registry = ToolRegistry()
_registry.registry(CALCULATOR_TOOL)
_registry.registry(SEARCH_DOCS_TOOL)
_registry.registry(WEB_SEARCH_TOOL)

_cache = MemoryCache()


class AskRequest(BaseModel):
    question: str = Field(min_length=1, description="The user's question.")
    thread_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    run_id: str
    prompt_version: str
    steps: int
    stopped_reason: str
    cached: bool
    tools_used: list[str] = []
    safety_blocked: list[str] = []
    budget_used: dict = {}
    cost_usd: float = 0.0
    resumed_from_step: int = 0


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, session_id: str = Depends(get_session_id)) -> AskResponse:
    prompt_version = get_prompt("system_agent")
    model = get_provider().model
    run = RunRecord(model=model, prompt_version=prompt_version.version)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run.run_id, prompt=prompt_version.version)

    log.info("Received question", question=req.question)

    session_registry = ToolRegistry()
    session_registry.registry(CALCULATOR_TOOL)
    session_registry.registry(WEB_SEARCH_TOOL)
    session_registry.registry(make_search_docs_tool(session_id))
    for t in _registry.list():
        if t.name.startswith("filesystem__"):
            session_registry.registry(t)

    key = answer_key(
        question=req.question,
        prompt_version=prompt_version.version,
        model=model,
        tool_names=[t.name for t in session_registry.list()],
        session_id = session_id,
    )

    cached_raw = await _cache.get(key)
    if cached_raw is not None:
        data = json.loads(cached_raw)
        log.info("cache hit", key=key)
        return AskResponse(
            answer=data["answer"],
            run_id=run.run_id,
            prompt_version=prompt_version.version,
            steps=data["steps"],
            stopped_reason=data["stopped_reason"],
            cached=True,
            tools_used = data.get("tools_used", []),
            safety_blocked = data.get("safety_blocked", []),
            budget_used = data.get("budget_used", {}),
            cost_usd = 0.0,
            resumed_from_step = 0

        )
    log.info("cache miss", key=key)

    trace = Trace(trace_id=run.run_id)

    result = await run_agent(
        question=req.question,
        prompt_text=prompt_version.text,
        registry=session_registry,
        provider=get_provider(),
        policy=_policy,
        audit=_audit,
        store=_store,
        thread_id=run.run_id,
        trace=trace,
    )

    _trace_store.add(trace, model)

    summary = trace.summary()
    run_cost = cost_usd(model, summary["input_tokens"], summary["output_tokens"])

    await _cache.set(key, json.dumps({
        "answer": result.answer,
        "steps": result.steps,
        "stopped_reason": result.stopped_reason,
        "tools_used": result.tools_used,
        "safety_blocked": result.safety_blocked,
        "budget_used": result.budget_used,
    }))

    log.info("returning answer", steps=result.steps, stopped_reason=result.stopped_reason,
             input_tokens=result.input_tokens, output_tokens=result.output_tokens)

    return AskResponse(
        answer=result.answer,
        run_id=run.run_id,
        prompt_version=prompt_version.version,
        steps=result.steps,
        stopped_reason=result.stopped_reason,
        cached=False,
        tools_used = result.tools_used,
        safety_blocked = result.safety_blocked,
        budget_used = result.budget_used,
        cost_usd = run_cost, 
        resumed_from_step = result.resumed_from_step,
    )
