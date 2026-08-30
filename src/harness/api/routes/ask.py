import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from pathlib import Path
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
from harness.tools.builtin.filesystem_session import wrap_filesystem_tool
from harness.cache.keys import answer_key
from harness.cache.redis_cache import RedisCache
from harness.policy.policy import ToolPolicy
from harness.policy.tiers import Tier
from harness.policy.audit import AuditLog
from harness.checkpoint.store import CheckpointStore
from harness.obs.tracing import Trace, cost_usd
from harness.obs.trace_store import TraceStore

from harness.api.auth import get_current_user
from harness.db.ledger import record_transaction
from decimal import Decimal

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

_cache = RedisCache()

DOCS_ONLY_INSTRUCTION = ("\\n\\nYou are in DOCUMENTS-ONLY mode. You have exactly one tool: search_docs. "
    "For EVERY question you MUST immediately call the search_docs tool with a query "
    "derived from the question. Do NOT reply with text like 'let me check' or "
    "'I will look at the documents' first. Your VERY FIRST action must be to call "
    "search_docs. After you receive the search results, answer using ONLY those "
    "results. If the results do not contain the answer, reply exactly: "
    "'I couldn't find that in your document.' Never answer from your own knowledge.")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, description="The user's question.")
    thread_id: str | None = None
    docs_only: bool = False


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
    input_tokens: int = 0
    output_tokens: int = 0
    resumed_from_step: int = 0
    pending_tool: dict | None = None


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, user: dict = Depends(get_current_user)) -> AskResponse:
    prompt_version = get_prompt("system_agent")
    model = get_provider().model
    run = RunRecord(model=model, prompt_version=prompt_version.version)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run.run_id, prompt=prompt_version.version)

    log.info("Received question", question=req.question, docs_only=req.docs_only)


    session_registry = ToolRegistry()

    # search_docs is ALWAYS available — it is the one tool docs-only mode needs
    session_registry.registry(make_search_docs_tool(user["user_id"]))

    # the other tools are only added when NOT in docs-only mode
    if not req.docs_only:
        session_registry.registry(CALCULATOR_TOOL)
        session_registry.registry(WEB_SEARCH_TOOL)
        for t in _registry.list():
            if t.name.startswith("filesystem__"):
                session_registry.registry(wrap_filesystem_tool(t, user["user_id"]))
    
    session_dir = (Path("data/sessions") / user["user_id"]).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    

    session_folder_note = (
         "\\n\\n=== CRITICAL FILE-PATH RULE (follow exactly) ===\\n"
        f"The user's folder is EXACTLY this absolute path: {session_dir}\\n"
        "This folder ALREADY EXISTS. For ANY file operation on the user's files "
        "(write, read, list, edit), you MUST use this exact absolute path.\\n"
        f"To create a file named notes.txt, call write_file with path='{session_dir}/notes.txt'.\\n"
        "You are FORBIDDEN from using a bare filename like 'notes.txt' or an invented "
        f"path like '/mnt/session/'. Always prefix with '{session_dir}/'.\\n"
        "Do NOT call create_directory — the folder already exists.\\n"
        "=== END RULE ==="
    )
    prompt_text = prompt_version.text + session_folder_note

    if req.docs_only:
        prompt_text = prompt_text + DOCS_ONLY_INSTRUCTION

    key = answer_key(
        question=req.question,
        prompt_version=prompt_version.version,
        model=model,
        tool_names=[t.name for t in session_registry.list()],
        session_id = user["user_id"],
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
        prompt_text=prompt_text,
        registry=session_registry,
        provider=get_provider(),
        policy=_policy,
        audit=_audit,
        store=_store,
        thread_id=run.run_id,
        trace=trace,
        force_tool_use=req.docs_only,
    )


    _trace_store.add(trace, model)

    summary = trace.summary()
    run_cost = cost_usd(model, summary["input_tokens"], summary["output_tokens"])

    cost = Decimal(str(run_cost))
    if cost>0:
        record_transaction(
        user_id = user["user_id"], 
        amount = -cost,
        kind = "run_cost",
        thread_id = run.run_id,
        )

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
        input_tokens = result.input_tokens,
        output_tokens = result.output_tokens,
        resumed_from_step = result.resumed_from_step,
        pending_tool = result.pending_tool,
    )
