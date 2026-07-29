from openai import AsyncOpenAI
from harness.providers.base import Completion

class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def complete(self, *, system:str, question:str)->Completion:
        """Generate a completion using the OpenAI API."""
        response = await self.client.chat.completions.create(
            model = self.model,
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": question}
            ]
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        return Completion(
            text = text,
            model = self.model,
            token_in = getattr(usage, "prompt_tokens", 0),
            token_out = getattr(usage, "completion_tokens", 0)
        )
