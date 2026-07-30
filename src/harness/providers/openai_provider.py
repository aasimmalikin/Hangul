from openai import AsyncOpenAI
from harness.providers.base import AssistantTurn, ToolCall
import json

class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def chat(self, messages: list[dict], tools: list[dict])->AssistantTurn:
        """Generate a completion using the OpenAI API."""
        response = await self.client.chat.completions.create(
            model = self.model,
            messages = messages,
            tools = tools or None
        )
        msg = response.choices[0].message
        calls = [ToolCall(id = tc.id, name = tc.function.name, arguments = json.loads(tc.function.arguments or "{}"))
        for tc in (msg.tool_calls or [])]
        usage = response.usage
        return AssistantTurn(
            text = msg.content,
            tool_calls = calls,
            input_tokens = getattr(usage, "prompt_tokens", 0),
            output_tokens = getattr(usage, "completion_tokens", 0)
        )
