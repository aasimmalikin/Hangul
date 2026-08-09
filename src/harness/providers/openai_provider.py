from openai import AsyncOpenAI
from harness.providers.base import AssistantTurn, ToolCall
import json


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def chat(self, messages: list[dict], tools: list[dict],
                   tool_choice: str | None = None) -> AssistantTurn:
        """Generate a completion using the OpenAI API.

        tool_choice: pass "required" to force the model to call a tool this turn
        (used by docs-only mode so it MUST call search_docs, not narrate)."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "tools": tools or None,
        }
        if tool_choice is not None and tools:
            kwargs["tool_choice"] = tool_choice

        response = await self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        calls = [ToolCall(id=tc.id, name=tc.function.name,
                          arguments=json.loads(tc.function.arguments or "{}"))
                 for tc in (msg.tool_calls or [])]
        usage = response.usage
        return AssistantTurn(
            text=msg.content,
            tool_calls=calls,
            input_tokens=getattr(usage, "prompt_tokens", 0),
            output_tokens=getattr(usage, "completion_tokens", 0),
        )
