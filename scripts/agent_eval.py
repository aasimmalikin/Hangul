#!/usr/bin/env python3
"""End-to-end agent evaluation for agentic-qa.

Runs the REAL agent (run_agent) on a 50-item mixed golden set, then grades its
answers with the CALIBRATED judges:
  - correctness (vs a reference answer)   -- for doc + calculator items
  - faithfulness (vs retrieved_context)   -- for ALL items (reference-free)

Golden-set design (per 2026 agent/RAG eval guidance): 50 items, stratified by
tool/intent -- doc-grounded (RAG over the global index), calculator
(deterministic), and web-search (current info). Web items are graded on
faithfulness only, because their correct answer drifts over time (faithfulness
is reference-free; correctness needs a stable reference).

Metric thresholds use the calibrated cutoffs: correctness >= 0.6, faith >= 0.5.

Run from the project root (needs the global doc index at data/index.json):
    uv run python scripts/agent_eval.py
"""
import asyncio
import statistics
from pathlib import Path

# ---- mirror the /ask route's agent wiring --------------------------------
from harness.agent.loop import run_agent
from harness.providers import get_provider
from harness.prompts.registry import get_prompt
from harness.tools.registry import ToolRegistry
from harness.tools.builtin.calculator import CALCULATOR_TOOL
from harness.tools.builtin.web_search import WEB_SEARCH_TOOL
from harness.tools.builtin.search_docs_session import make_search_docs_tool
from harness.policy.policy import ToolPolicy
from harness.policy.tiers import Tier
from harness.policy.audit import AuditLog
from harness.checkpoint.store import CheckpointStore
from harness.obs.tracing import Trace

# calibrated judges
from harness.eval.openai_judge import OpenAIJudge
from harness.eval.graders import grade_correctness, grade_faithfulness

CORRECTNESS_THRESHOLD = 0.6   # from calibration
FAITHFULNESS_THRESHOLD = 0.5  # from calibration

_policy = ToolPolicy(tiers={
    "calculator": Tier.SAFE, "search_docs": Tier.SAFE, "web_search": Tier.SAFE,
})
_audit = AuditLog()
_store = CheckpointStore()


# ==========================================================================
# GOLDEN SET (50 items). category: doc / calc / web
#   doc  -> graded on correctness (vs reference) AND faithfulness (vs context)
#   calc -> graded on correctness (vs reference)
#   web  -> graded on faithfulness only (answer drifts; reference-free)
# References for doc/calc are drawn from the real global index (data/index.json).
# ==========================================================================
GOLDEN = [
    # ---------- DOC-GROUNDED (RAG over data/index.json) : 20 ----------
    {"cat":"doc","q":"How many examination rooms does Brightpath Medical Clinic have?","ref":"6 examination rooms"},
    {"cat":"doc","q":"How long are standard appointment slots at Brightpath?","ref":"20 minutes"},
    {"cat":"doc","q":"How many physicians and nurses does Brightpath employ?","ref":"8 physicians and 14 nurses"},
    {"cat":"doc","q":"How long are patient records retained at Brightpath?","ref":"7 years"},
    {"cat":"doc","q":"What was Nimbus Analytics' total revenue in FY2025?","ref":"48 million dollars"},
    {"cat":"doc","q":"Where is Nimbus Analytics headquartered?","ref":"Austin, Texas"},
    {"cat":"doc","q":"How many full-time employees does Nimbus have and across how many offices?","ref":"320 full-time employees across 4 offices"},
    {"cat":"doc","q":"How many standard pallets are in Meridian Logistics' Riverside inventory and what is each valued at?","ref":"1850 pallets, valued at 34 dollars each"},
    {"cat":"doc","q":"How many forklift battery packs does Meridian have and their unit value?","ref":"12 packs at 2200 dollars each"},
    {"cat":"doc","q":"How many delivery trucks does Harbor Freight Logistics operate?","ref":"54 delivery trucks"},
    {"cat":"doc","q":"What is the size of Harbor Freight's central warehouse and how many loading docks?","ref":"85,000 square feet with 14 loading docks"},
    {"cat":"doc","q":"How many products are in the Verdant Home Goods catalog and across how many categories?","ref":"240 products across 6 categories"},
    {"cat":"doc","q":"What is Verdant's best-selling category and how many products does it have?","ref":"kitchenware, with 68 products"},
    {"cat":"doc","q":"What energy density does the Project Aurora prototype currently achieve, and what is the 2027 target?","ref":"320 watt-hours per kilogram now; 500 target for 2027"},
    {"cat":"doc","q":"Who is the lead researcher on Project Aurora and what is the budget?","ref":"Dr. Sofia Andersson; 8 million dollars over 3 years"},
    {"cat":"doc","q":"At what elevation is Riverstone Mountain Resort and how many guest rooms does it have?","ref":"6,200 feet; 180 guest rooms"},
    {"cat":"doc","q":"What are the names of the three lodges at Riverstone?","ref":"Pinecrest, Summit, and Lakeside"},
    {"cat":"doc","q":"What are the check-in and check-out times at Riverstone?","ref":"check-in 4:00 PM, check-out 11:00 AM"},
    {"cat":"doc","q":"In which lodge are pets allowed at Riverstone and at what extra cost?","ref":"Lakeside Lodge only, extra 50 dollars per night"},
    {"cat":"doc","q":"How many storage aisles are in Meridian's Riverside warehouse and how many pallet racks per aisle?","ref":"12 aisles, 45 pallet racks each"},

    # ---------- DOC + REASONING (multi-fact / cross-doc) : 5 ----------
    {"cat":"doc","q":"What is the total pallet storage capacity of Meridian's Riverside warehouse (aisles x racks x pallets per rack)?","ref":"12 x 45 x 8 = 4320 pallets"},
    {"cat":"doc","q":"What is the total value of Meridian's standard pallet inventory (1850 pallets at 34 dollars)?","ref":"1850 x 34 = 62,900 dollars"},
    {"cat":"doc","q":"Across how many total rooms does Brightpath operate (exam plus procedure)?","ref":"6 + 2 = 8 rooms"},
    {"cat":"doc","q":"What was Nimbus's gross profit in FY2025 (revenue minus COGS)?","ref":"48M - 18M = 30 million dollars"},
    {"cat":"doc","q":"How many total deliveries does Harbor Freight's fleet make per day (54 trucks x 12 deliveries)?","ref":"54 x 12 = 648 deliveries per day"},

    # ---------- CALCULATOR (deterministic) : 12 ----------
    {"cat":"calc","q":"What is 15% of 84000?","ref":"12600"},
    {"cat":"calc","q":"What is 2340 multiplied by 18?","ref":"42120"},
    {"cat":"calc","q":"What is 96500 divided by 23?","ref":"approximately 4195.65"},
    {"cat":"calc","q":"What is 1850 multiplied by 34?","ref":"62900"},
    {"cat":"calc","q":"What is the sum of 4820, 1975, and 6340?","ref":"13135"},
    {"cat":"calc","q":"What is 12 multiplied by 45 multiplied by 8?","ref":"4320"},
    {"cat":"calc","q":"What is 7 factorial?","ref":"5040"},
    {"cat":"calc","q":"What is the square root of 2025?","ref":"45"},
    {"cat":"calc","q":"What is 340 kilograms multiplied by 54?","ref":"18360"},
    {"cat":"calc","q":"What is 890 minus 34, then multiplied by 2?","ref":"1712"},
    {"cat":"calc","q":"What is 22% of 5000?","ref":"1100"},
    {"cat":"calc","q":"If a pallet weighs 27 kg empty and 340 kg loaded, what is the weight of the goods alone?","ref":"340 - 27 = 313 kilograms"},

    # ---------- WEB SEARCH (faithfulness only; answer drifts) : 13 ----------
    {"cat":"web","q":"What is the current USD to INR exchange rate?"},
    {"cat":"web","q":"What is the current price of gold per ounce?"},
    {"cat":"web","q":"Who is the current president of France?"},
    {"cat":"web","q":"What is the latest stable version of Python?"},
    {"cat":"web","q":"What is the current price of Bitcoin in USD?"},
    {"cat":"web","q":"What is the current population of Japan?"},
    {"cat":"web","q":"Who is the current CEO of Microsoft?"},
    {"cat":"web","q":"What is the current price of silver per ounce?"},
    {"cat":"web","q":"What is the current USD to EUR exchange rate?"},
    {"cat":"web","q":"What is the current price of Ethereum in USD?"},
    {"cat":"web","q":"What is the latest iPhone model released?"},
    {"cat":"web","q":"What is the current price of crude oil per barrel?"},
    {"cat":"web","q":"Who is the current prime minister of the United Kingdom?"},
]


def build_registry(session_id):
    reg = ToolRegistry()
    reg.registry(make_search_docs_tool(session_id))
    reg.registry(CALCULATOR_TOOL)
    reg.registry(WEB_SEARCH_TOOL)
    return reg


async def run_one(item, idx, judge):
    prompt_version = get_prompt("system_agent")
    reg = build_registry(f"eval-{idx}")
    trace = Trace(trace_id=f"eval-{idx}")
    result = await run_agent(
        question=item["q"],
        prompt_text=prompt_version.text,
        registry=reg,
        provider=get_provider(),
        policy=_policy,
        audit=_audit,
        store=_store,
        thread_id=f"eval-{idx}",
        trace=trace,
    )
    answer = result.answer
    context = result.retrieved_context or ""

    out = {"cat": item["cat"], "q": item["q"], "answer": answer}

    # correctness (doc + calc, vs reference)
    if item["cat"] in ("doc", "calc") and item.get("ref"):
        cscore, _ = await grade_correctness(
            judge, question=item["q"], answer=answer, reference=item["ref"])
        out["correctness"] = float(cscore)
        out["correct"] = float(cscore) >= CORRECTNESS_THRESHOLD

    # faithfulness (all items with retrieved context, vs context)
    # web + doc have context; calc usually has none (pure computation)
    if context.strip():
        fscore, _ = await grade_faithfulness(judge, answer=answer, context=context)
        out["faithfulness"] = float(fscore)
        out["faithful"] = float(fscore) >= FAITHFULNESS_THRESHOLD

    return out


async def main():
    judge = build_judge = OpenAIJudge(model="gpt-4o")
    print(f"Running agent on {len(GOLDEN)} eval items...\n")

    results = []
    for i, item in enumerate(GOLDEN):
        try:
            r = await run_one(item, i, judge)
            results.append(r)
            c = f"corr={r['correctness']:.2f}" if "correctness" in r else "corr=  - "
            f = f"faith={r['faithfulness']:.2f}" if "faithfulness" in r else "faith=  - "
            print(f"  [{i+1:2}/{len(GOLDEN)}] {r['cat']:>4} | {c} | {f} | {item['q'][:44]}")
        except Exception as e:
            print(f"  [{i+1:2}/{len(GOLDEN)}] ERROR: {type(e).__name__}: {e}")

    # aggregate
    def rate(items, key):
        vals = [r[key] for r in items if key in r]
        return (sum(vals) / len(vals) * 100, len(vals)) if vals else (0, 0)

    print("\n" + "=" * 60)
    print("AGENT EVALUATION RESULTS")
    print("=" * 60)

    for cat in ("doc", "calc", "web"):
        sub = [r for r in results if r["cat"] == cat]
        if not sub:
            continue
        corr_pct, corr_n = rate(sub, "correct")
        faith_pct, faith_n = rate(sub, "faithful")
        print(f"\n  {cat.upper()} ({len(sub)} items):")
        if corr_n:
            print(f"    correctness : {corr_pct:.0f}%  ({corr_n} graded)")
        if faith_n:
            print(f"    faithfulness: {faith_pct:.0f}%  ({faith_n} graded)")

    # overall
    print("\n" + "-" * 60)
    all_corr, corr_n = rate(results, "correct")
    all_faith, faith_n = rate(results, "faithful")
    print(f"  OVERALL correctness : {all_corr:.0f}%  ({corr_n} items graded)")
    print(f"  OVERALL faithfulness: {all_faith:.0f}%  ({faith_n} items graded)")
    # mean scores too
    corr_scores = [r["correctness"] for r in results if "correctness" in r]
    faith_scores = [r["faithfulness"] for r in results if "faithfulness" in r]
    if corr_scores:
        print(f"  mean correctness score : {statistics.mean(corr_scores):.2f}")
    if faith_scores:
        print(f"  mean faithfulness score: {statistics.mean(faith_scores):.2f}")

    print("\n" + "=" * 60)
    print("RESUME LINE")
    print("=" * 60)
    print(f'  "Evaluated the agent on a 50-item stratified golden set '
          f'(doc-RAG, calculator, web-search) using calibrated LLM-as-judges: '
          f'{all_corr:.0f}% correctness, {all_faith:.0f}% faithfulness."')


if __name__ == "__main__":
    asyncio.run(main())