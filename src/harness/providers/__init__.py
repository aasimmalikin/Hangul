from functools import lru_cache
from harness.providers.openai_provider import OpenAIProvider
from harness.config import get_settings
from harness.providers.base import Provider

@lru_cache
def get_provider()->Provider:
    s = get_settings()
    return OpenAIProvider(api_key = s.openai_api_key, model = s.model)