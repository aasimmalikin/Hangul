import json
# fe4559c1bcf54fdfa04028453ff7f779
from pydantic import BaseModel, Field

from harness.providers.base import Provider
from harness.tools.openai_spec import to_openai_tool
from harness.tools.registry import ToolRegistry
from harness.logging import log

from harness.policy.guarded import guarded_dispatch
from harness.policy.policy import ToolPolicy
from harness.policy.audit import AuditLog
from harness.policy.budget import Budget
from harness.policy.tiers import Decision

from harness.checkpoint.checkpoint import Checkpoint
from harness.checkpoint.store import CheckpointStore
from harness.checkpoint.idempotency import call_key

from harness.obs.tracing import Trace


RETRIEVAL_TOOLS = {"search_docs", "filesystem__read_text_file", "filesystem__read_file"}


class AgentResult(BaseModel):
    answer: str
    steps: int
    stopped_reason: str
    input_tokens: int
    output_tokens: int
    retrieved_context: str = ""
    tools_used: list[str] = Field(default_factory=list)
    safety_blocked: list[str] = Field(default_factory=list)
    budget_used: dict = Field(default_factory=dict)
    resumed_from_step: int = 0
    pending_tool: dict | None = None


async def run_agent(
    *,
    question: str,
    prompt_text: str,
    registry: ToolRegistry,
    provider: Provider,
    policy: ToolPolicy,
    audit: AuditLog,
    store: CheckpointStore,
    thread_id: str,
    trace: Trace,
    approved_action: dict | None = None,
    max_steps: int = 20,
    max_tokens: int = 50_000,
) -> AgentResult:
    cp = store.load(thread_id) or Checkpoint(
        thread_id=thread_id,
        message=[
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": question},
        ],
    )
    messages = cp.message

    tools = [to_openai_tool(t) for t in registry.list()]
    total_in = total_out = 0
    retrieved: list[str] = []
    tools_used: list[str] = []
    safety_blocked: list[str] = []
    resumed_from = cp.step

    budget = Budget(max_steps=max_steps, max_tokens=max_tokens)

    def _budget_snapshot() -> dict:
        return {
            "steps": budget.steps,
            "max_steps": max_steps,
            "tokens": budget.tokens,
            "max_tokens": max_tokens,
        }

    async def _run_one_tool(tc) -> str:
        """Dispatch a single tool call and return its result content."""
        key = call_key(thread_id, tc.name, tc.arguments)
        if key in cp.completed_calls:
            return cp.completed_calls[key]
        with trace.span("gen_ai.tool.execute", **{"gen_ai.tool.name": tc.name}):
            try:
                result = await guarded_dispatch(registry.get(tc.name), tc.arguments, policy, audit)
                content = result.content
            except KeyError:
                content = f"Error: unknown tool {tc.name}"
        cp.completed_calls[key] = content
        return content

    with trace.span("agent.run", question=question):
        for step in range(cp.step + 1, max_steps + 1):
            reason = budget.exceeded()
            if reason:
                cp.status = "done"
                store.save(cp)
                return AgentResult(
                    answer=f"Stopped: {reason}.", steps=step - 1,
                    stopped_reason="budget_exceeded",
                    input_tokens=total_in, output_tokens=total_out,
                    retrieved_context="\n\n".join(retrieved),
                    tools_used=tools_used, safety_blocked=safety_blocked,
                    budget_used=_budget_snapshot(), resumed_from_step=resumed_from,
                )

            with trace.span("gen_ai.chat",
                            **{"gen_ai.request.model": provider.model}) as sp:
                turn = await provider.chat(messages, tools)
            sp.attributes["gen_ai.usage.input_tokens"] = turn.input_tokens
            sp.attributes["gen_ai.usage.output_tokens"] = turn.output_tokens

            total_in += turn.input_tokens
            total_out += turn.output_tokens
            budget.add(steps=1, tokens=turn.input_tokens + turn.output_tokens)

            if not turn.tool_calls:
                cp.status = "done"
                cp.step = step
                store.save(cp)
                return AgentResult(
                    answer=turn.text or "", steps=step, stopped_reason="answered",
                    input_tokens=total_in, output_tokens=total_out,
                    retrieved_context="\n\n".join(retrieved),
                    tools_used=tools_used, safety_blocked=safety_blocked,
                    budget_used=_budget_snapshot(), resumed_from_step=resumed_from,
                )

            messages.append({
                "role": "assistant",
                "content": turn.text or "",
                "tool_calls": [
                    {
                        "id": tc.id, "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    } for tc in turn.tool_calls
                ],
            })

            for tc in turn.tool_calls:
                if tc.name not in tools_used:
                    tools_used.append(tc.name)

            # find the first tool call that needs approval (and isn't pre-approved)
            pending_idx = None
            for i, tc in enumerate(turn.tool_calls):
                is_approved = (approved_action is not None
                               and approved_action.get("tool_call_id") == tc.id)
                if policy.decide(tc.name) == Decision.NEEDS_APPROVAL and not is_approved:
                    pending_idx = i
                    break

            if pending_idx is not None:
                # execute tool calls BEFORE the pending one (real responses)
                for tc in turn.tool_calls[:pending_idx]:
                    content = await _run_one_tool(tc)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})

                # the pending tool: save it + a placeholder response (keeps history valid)
                p = turn.tool_calls[pending_idx]
                cp.pending_tool = {"name": p.name, "arguments": p.arguments, "tool_call_id": p.id}
                messages.append({"role": "tool", "tool_call_id": p.id,
                                 "content": "[awaiting human approval]"})

                # placeholder responses for any tool calls AFTER the pending one
                for tc in turn.tool_calls[pending_idx + 1:]:
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": "[not executed — pending earlier approval]"})

                cp.message = messages
                cp.step = step
                cp.status = "pending_approval"
                store.save(cp)
                log.info("paused for approval", tool=p.name, args=p.arguments)
                return AgentResult(
                    answer=f"The agent wants to run '{p.name}'. Your approval is needed.",
                    steps=step, stopped_reason="pending_approval",
                    input_tokens=total_in, output_tokens=total_out,
                    retrieved_context="\n\n".join(retrieved),
                    tools_used=tools_used, safety_blocked=[p.name],
                    budget_used=_budget_snapshot(), resumed_from_step=resumed_from,
                    pending_tool=cp.pending_tool,
                )

            # no approval needed this turn — run every tool normally
            for tc in turn.tool_calls:
                is_approved = (approved_action is not None
                               and approved_action.get("tool_call_id") == tc.id)
                key = call_key(thread_id, tc.name, tc.arguments)
                if key in cp.completed_calls:
                    content = cp.completed_calls[key]
                else:
                    with trace.span("gen_ai.tool.execute", **{"gen_ai.tool.name": tc.name}):
                        try:
                            result = await guarded_dispatch(
                                registry.get(tc.name), tc.arguments, policy, audit,
                                approved=is_approved)
                            content = result.content
                        except KeyError:
                            content = f"Error: unknown tool {tc.name}"
                    cp.completed_calls[key] = content

                if "approval" in content.lower() or "not executed" in content.lower():
                    if tc.name not in safety_blocked:
                        safety_blocked.append(tc.name)
                if tc.name in RETRIEVAL_TOOLS and not content.startswith(("Invalid", "Error", "Tool")):
                    retrieved.append(content)
                log.info("tool call", step=step, tool=tc.name, args=tc.arguments, result=content[:150])
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})

            approved_action = None
            cp.message = messages
            cp.step = step
            cp.pending_tool = None
            store.save(cp)

    cp.status = "done"
    store.save(cp)
    return AgentResult(
        answer="Stopped before finishing: reached the step limit.",
        steps=max_steps, stopped_reason="max_steps",
        input_tokens=total_in, output_tokens=total_out,
        retrieved_context="\n\n".join(retrieved),
        tools_used=tools_used, safety_blocked=safety_blocked,
        budget_used=_budget_snapshot(), resumed_from_step=resumed_from,
    )