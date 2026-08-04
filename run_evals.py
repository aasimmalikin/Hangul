"""Run the eval harness against the agent and save a versioned report."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from harness.eval.dataset import load_case
from harness.eval.runner import run_eval
from harness.eval.openai_judge import OpenAIJudge
from harness.agent.loop import run_agent
from harness.prompts.registry import get_prompt
from harness.providers import get_provider
from harness.api.routes.ask import _registry, _policy, _audit, _store
import uuid

async def run_fn(question: str) -> tuple[str, str]:
    """Run the real agent on one question, return (answer, retrieved_context)."""
    result = await run_agent(
        question=question,
        prompt_text=get_prompt("system_agent").text,
        registry=_registry,
        provider=get_provider(),
        policy=_policy,
        audit=_audit,
        store=_store,
        thread_id="eval-" + uuid.uuid4().hex[:12],
    )
    
    return result.answer, result.retrieved_context

def current_index_version(path:Path = "data/index_version.txt")->str:
    p = Path("data/index_version.txt")
    return p.read_text().strip() if p.exists() else "unknown"


async def main() -> None:
    cases = load_case("data/evalset.jsonl")
    print(f"running eval over {len(cases)} cases...\n")

    report = await run_eval(
        cases=cases,
        run_fn=run_fn,
        judge=OpenAIJudge(),
        prompt_version=get_prompt("system_agent").version,
        index_version=current_index_version(),    
        model=get_provider().model,
    )

    # print a readable summary
    print(f"cases:            {report.n}")
    print(f"avg correctness:  {report.avg_correctness:.2f}")
    print(f"avg faithfulness: {report.avg_faithfulness:.2f}")
    print(f"pass rate:        {report.pass_rate:.0%}")
    print(f"prompt={report.prompt_version}  index={report.index_version}  model={report.model}")
    print("\nper-case:")
    for r in report.result:
        print(f"  {r.id}: correctness={r.correctness:.2f} faithfulness={r.faithfulness:.2f}")

    # save the full report, timestamped, so runs can be compared over time
    out_dir = Path("data/eval_runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"eval-{stamp}.json"
    out_path.write_text(json.dumps(report.model_dump(), indent=2))
    print(f"\nsaved report -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main())