import json
from pydantic import BaseModel
from harness.providers.base import Provider
from harness.tools.dispatch import dispatch
from harness.tools.openai_spec import to_openai_tool
from harness.tools.registry import ToolRegistry
from harness.logging import log

class AgentResult(BaseModel):
    answer: str
    steps: int
    stopped_reason: str
    input_tokens: int
    output_tokens: int

async def run_agent(
    *, 
    question:str,
    prompt_text:str,
    registry: ToolRegistry,
    provider: Provider,
    max_steps: int = 12
) -> AgentResult:
    messages: list[dict] = [
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": question},
    ]

    tools = [to_openai_tool(t) for t in registry.list()]
    total_in = total_out = 0

    for step in range(1, max_steps+1):
        turn = await provider.chat(messages, tools)
        total_in += turn.input_tokens
        total_out += turn.output_tokens

        if not turn.tool_calls:
            return AgentResult(answer = turn.text or "", steps = step, stopped_reason = "answered", input_tokens = total_in, output_tokens = total_out)
        
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
            try:
                result = await dispatch(registry.get(tc.name), tc.arguments)
                content = result.content
            except KeyError:
                content = f"Error Unknown tool {tc.name}"
            
            log.info("tool call", step=step, tool=tc.name, args=tc.arguments, result=content[:150])

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
    
    return AgentResult(
        answer = "Stopped before finishing: reached the step limit.",
        steps = max_steps, 
        stopped_reason = "max_steps",
        input_tokens = total_in,
        output_tokens = total_out
    )



