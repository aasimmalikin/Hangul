"""GET /quality — surface the latest eval run and CI-gate verdict."""

import json
from pathlib import Path

from fastapi import APIRouter

from harness.eval.gate import evaluate_gate

router = APIRouter()

_EVAL_DIR = Path("data/eval_runs")
_BASELINE = Path("data/eval_baseline.json")

@router.get("/quality")
async def quality()->dict:
    if not _EVAL_DIR.exists():
        return {"available": False, "reason": "no eval runs found"}
    
    runs = sorted(_EVAL_DIR.glob("eval-*.json"), reverse = True)
    if not runs:
        return {"available": False, "reason": "no eval runs found"}
    
    report = json.loads(runs[0].read_text())
    baseline = json.loads(_BASELINE.read_text()) if _BASELINE.exists() else None

    gate = evaluate_gate(report, baseline)
    return {
        "available": True, 
        "avg_correctness": report.get("avg_correctness"),
        "avg_faithfulness": report.get("avg_faithfulness"),
        "pass_rate": report.get("pass_rate"),
        "cases": report.get("n"),
        "prompt_version": report.get("prompt_version"),
        "index_version": report.get("index_version"),
        "model": report.get("model"),
        "gate_passed": gate.passed,
        "blocking_failures": gate.blocking_failures,
        "advisory_notes": gate.advisory_notes,
        "run_file": runs[0].name,
    }