from fastapi import APIRouter
from pydantic import BaseModel, Field
import structlog
from harness.logging import log
from harness.schemas.run import RunRecord

router = APIRouter()

class AskRequest(BaseModel):
    question: str = Field(min_length=1, description = "The user's question.")


class AskResponse(BaseModel):
    answer: str
    run_id: str 

@router.post("/ask", response_model = AskResponse)
async def ask(req: AskRequest)-> AskResponse:
    run = RunRecord()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id = run.run_id)
    log.info("Received question", question = req.question)
    answer = f"This is a hardcoded answer. you asked: {req.question!r}"

    return AskResponse(
        answer=answer,
        run_id=run.run_id)