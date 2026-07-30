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

router = APIRouter()
_registry = ToolRegistry()
_registry.registry(CALCULATOR_TOOL)



class AskRequest(BaseModel):
    question: str = Field(min_length=1, description = "The user's question.")


class AskResponse(BaseModel):
    answer: str
    run_id: str 
    prompt_version: str
    steps: int
    stopped_reason: str

@router.post("/ask", response_model = AskResponse)
async def ask(req: AskRequest)-> AskResponse:
    prompt_version = get_prompt("system_agent")
    run = RunRecord(model = get_provider().model, prompt_version = prompt_version.version)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id = run.run_id, prompt = prompt_version.version)

    log.info("Received question", question = req.question)
    result = await run_agent(
        question = req.question,
        prompt_text = prompt_version.text,
        registry = _registry,
        provider = get_provider()
    )
    log.info("returning answer", steps = result.steps, stopped_reason = result.stopped_reason,
            input_tokens = result.input_tokens, output_tokens = result.output_tokens)

    return AskResponse(
        answer=result.answer,
        run_id=run.run_id,
        prompt_version = prompt_version.version,
        steps = result.steps,
        stopped_reason = result.stopped_reason)