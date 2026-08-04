from pydantic import BaseModel
from typing import Awaitable, Callable
from harness.eval.dataset import EvalCase
from harness.eval.graders import Judge, grade_correctness, grade_faithfulness

class CaseResult(BaseModel):
    id: str
    correctness: float
    faithfulness: float
    answer: str

class EvalReport(BaseModel):
    n: int
    avg_correctness: float
    avg_faithfulness: float
    pass_rate: float
    prompt_version: str
    index_version: str
    model: str
    result: list[CaseResult]

async def run_eval(cases: list[EvalCase],run_fn: Callable[[str], Awaitable[tuple[str, str]]],
                judge: Judge,*,prompt_version: str,index_version: str, model: str, pass_threshold: float = 0.7,) -> EvalReport:
    results = []
    for case in cases:
        answer, context = await run_fn(case.question)
        c, _ = await grade_correctness(judge, case.question, answer, case.reference)
        f, _ = await grade_faithfulness(judge, answer, context)
        results.append(CaseResult(id = case.id, correctness = c, faithfulness = f, answer = answer))
    
    n = len(results)
    return EvalReport(
        n = n,
        avg_correctness = sum(r.correctness for r in results) /n, 
        avg_faithfulness = sum(r.faithfulness for r in results) /n,
        pass_rate = sum(1 for r in results if r.correctness>pass_threshold)/n, 
        prompt_version = prompt_version, 
        index_version = index_version, 
        model = model, 
        result = results,

    )



