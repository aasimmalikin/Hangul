from fastapi import APIRouter
from pydantic import BaseModel, Field
import structlog
from harness.logging import log
from harness.schemas.run import RunRecord
from harness.providers import get_provider
from harness.prompts.registry import get_prompt

router = APIRouter()




class AskRequest(BaseModel):
    question: str = Field(min_length=1, description = "The user's question.")


class AskResponse(BaseModel):
    answer: str
    run_id: str 
    prompt: str

@router.post("/ask", response_model = AskResponse)
async def ask(req: AskRequest)-> AskResponse:
    prompt_version = get_prompt("system_agent")
    run = RunRecord(model = get_provider().model, prompt_version = prompt_version.version)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id = run.run_id, prompt = prompt_version.version)

    log.info("Received question", question = req.question)
    provider = get_provider()
    completion = await provider.complete(system = prompt_version.text, question = req.question )
    log.info("Returning Answer",
    model = completion.model,
    token_in = completion.token_in,
    token_out = completion.token_out,
    )

    return AskResponse(
        answer=completion.text,
        run_id=run.run_id,
        prompt = prompt_version.version)