import json
from pydantic import BaseModel
from harness.providers.base import Provider
from harness.tools.dispatch import dispatch
from harness.tools.openai_spec import to_openai_tool
from harness.tools.registry import ToolRegistry
from harness.logging import log
from harness.policy.guarded import guarded_dispatch
from harness.policy.policy import ToolPolicy
from harness.policy.audit import AuditLog
from harness.policy.budget import Budget
from harness.checkpoint.checkpoint import Checkpoint
from harness.checkpoint.store import CheckpointStore
from harness.checkpoint.idempotency import call_key

RETRIEVAL_TOOLS = {"search_docs", "filesystem__read_text_file", "filesystem__read_file"}

class AgentResult(BaseModel):
    answer: str
    steps: int
    stopped_reason: str
    input_tokens: int
    output_tokens: int
    retrieved_context: str = ""

async def run_agent(
    *, 
    question:str,
    prompt_text:str,
    registry: ToolRegistry,
    provider: Provider,
    max_steps: int = 12,
    max_tokens: int = 50_000,
    policy: ToolPolicy,
    audit: AuditLog,
    store: CheckpointStore,
    thread_id: str

) -> AgentResult:
    cp = store.load(thread_id) or Checkpoint(
        thread_id = thread_id,
        
        message = [
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": question},
    ])

    messages = cp.message

    budget = Budget(max_steps = max_steps, max_tokens = 50_000)

    tools = [to_openai_tool(t) for t in registry.list()]
    total_in = total_out = 0
    retrieved: list[str] = []

    for step in range(cp.step+1, max_steps+1):
        reason = budget.exceeded()
        if reason:
            cp.status = "done"
            store.save(cp)
            return AgentResult(
                answer = f"Stopped: {reason}",
                steps = step-1,
                stopped_reason = "budget_exceeded",
                input_tokens = total_in,
                output_tokens = total_out,
                retrieved_context = "\n\n".join(retrieved),
            )
        turn = await provider.chat(messages, tools)
        total_in += turn.input_tokens
        total_out += turn.output_tokens
        budget.add(steps = 1, tokens = turn.input_tokens + turn.output_tokens)

        if not turn.tool_calls:
            cp.status = "done"
            cp.step = step
            store.save(cp)
            return AgentResult(answer = turn.text or "", steps = step, stopped_reason = "answered", input_tokens = total_in, output_tokens = total_out, retrieved_context = "\n\n".join(retrieved))
        
        messages.append({
            "role": "assistant", "content": turn.text or "",
            "tool_calls": [
                {
                    "id": tc.id, "type": "function",
                    "function": {"name":tc.name, "arguments": json.dumps(tc.arguments)}
                } for tc in turn.tool_calls
            ]
        })

        for tc in turn.tool_calls:
            key = call_key(thread_id, tc.name, tc.arguments)

            try:
                result = await guarded_dispatch(registry.get(tc.name), tc.arguments, policy, audit)
                content = result.content
            except KeyError:
                content = f"Error Unknown tool {tc.name}"
            cp.completed_calls[key] = content
            if tc.name in RETRIEVAL_TOOLS and not content.startswith(("Invalid", "Error", "Tool")):
                retrieved.append(content)
            
            log.info("tool call", step=step, tool=tc.name, args=tc.arguments, result=content[:150])

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})

        cp.message = messages
        cp.step = step
        store.save(cp)
    
    cp.status = "done"
    store.save(cp)
    
    return AgentResult(
        answer = "Stopped before finishing: reached the step limit.",
        steps = max_steps, 
        stopped_reason = "max_steps",
        input_tokens = total_in,
        output_tokens = total_out,
        retrieved_context = "\n\n".join(retrieved),
    )



