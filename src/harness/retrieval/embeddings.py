from functools import lru_cache
from openai import AsyncOpenAI
from harness.config import get_settings

class OpenAIEmbedder:
    def __init__(self, api_key:str, model: str = "text-embedding-3-small")->None:
        self._client = AsyncOpenAI(api_key = api_key)
        self.model = model
    
    async def embed(self, text:str)-> list[float]:
        resp = await self._client.embeddings.create(model = self.model, input = text)
        return resp.data[0].embedding

@lru_cache
def get_embedder()->OpenAIEmbedder:
    return OpenAIEmbedder(api_key = get_settings().openai_api_key)
