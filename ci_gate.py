import asyncio
import json
import sys
from pathlib import Path

from harness.eval.gate import evaluate_gate
from harness.eval.dataset import load_case
from harness.eval.runner import run_eval
from harness.eval.openai_judge import OpenAIJudge
from harness.prompts.registry import get_prompt
from harness.providers import get_provider
from run_evals import run_fn

async def build_report()->dict:
    idx = Path("data/index_version.txt")
    report = await run_eval(
        cases = load_case("data/evalset.jsonl"),
        run_fn = run_fn, 
        judge = OpenAIJudge(), 
        prompt_version = get_prompt("system_agent").version,
        index_version=idx.read_text().strip() if idx.exists() else "unknown",
        model = get_provider().model,
    )
    return report.model_dump()

def main()->int:
    report = asyncio.run(build_report())
    baseline_path = Path("data/eval_baseline.json")
    baseline = json.loads(baseline_path.read_text()) if baseline_path.exists() else None

    result = evaluate_gate(report, baseline)
    print("=" * 50)
    print(f"CI EVAL GATE - {'PASS' if result.passed else 'FAIL'}")
    print(f"  correctness={report.get('avg_correctness'):.2f} "
          f"faithfulness={report.get('avg_faithfulness'):.2f} "
          f"pass_rate={report.get('pass_rate'):.2f}")
    for note in result.advisory_notes:
        print(f"  [advisory] {note}")
    for fail in result.blocking_failures:
        print(f"  [BLOCKING] {fail}")
    print("=" * 50)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())

