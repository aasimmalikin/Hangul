from fastapi import APIRouter
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
from harness.cache.keys import answer_key
from harness.cache.memory_cache import MemoryCache
import json

router = APIRouter()
_registry = ToolRegistry()
_registry.registry(CALCULATOR_TOOL)
_registry.registry(SEARCH_DOCS_TOOL)
_cache = MemoryCache()



class AskRequest(BaseModel):
    question: str = Field(min_length=1, description = "The user's question.")


class AskResponse(BaseModel):
    answer: str
    run_id: str 
    prompt_version: str
    steps: int
    stopped_reason: str
    cached: bool

@router.post("/ask", response_model = AskResponse)
async def ask(req: AskRequest)-> AskResponse:
    prompt_version = get_prompt("system_agent")
    model = get_provider().model
    run = RunRecord(model = model, prompt_version = prompt_version.version)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id = run.run_id, prompt = prompt_version.version)

    log.info("Received question", question = req.question)
    key = answer_key(
        question = req.question,
        prompt_version = prompt_version.version,
        model = model,
        tool_names = [t.name for t in _registry.list()]
    )

    cached_raw = await _cache.get(key)
    if cached_raw is not None:
        data = json.loads(cached_raw)
        log.info("cache hit", key = key)
        return AskResponse(
            answer = data["answer"],
            run_id=run.run_id,
            prompt_version = prompt_version.version,
            steps = data["steps"],
            stopped_reason = data["stopped_reason"],
            cached = True
        )
    log.info("cache miss", key = key)


    result = await run_agent(
        question = req.question,
        prompt_text = prompt_version.text,
        registry = _registry,
        provider = get_provider()
    )
    await _cache.set(key, json.dumps({
        "answer": result.answer,
        "steps": result.steps,
        "stopped_reason": result.stopped_reason

    }))

    log.info("returning answer", steps = result.steps, stopped_reason = result.stopped_reason,
            input_tokens = result.input_tokens, output_tokens = result.output_tokens)

    return AskResponse(
        answer=result.answer,
        run_id=run.run_id,
        prompt_version = prompt_version.version,
        steps = result.steps,
        stopped_reason = result.stopped_reason,
        cached = False)