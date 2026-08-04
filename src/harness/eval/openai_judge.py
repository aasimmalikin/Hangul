import json
from openai import AsyncOpenAI
from harness.config import get_settings

class OpenAIJudge:
    def __init__(self, model: str = "gpt-4o")->None:
        self._client = AsyncOpenAI(api_key = get_settings().openai_api_key)
        self._model = model
    
    async def score(self, rubric: str, payload: str)->tuple[float, str]:
        resp = await self._client.chat.completions.create(
            model = self._model,
            messages = [
                {"role": "system", "content": rubric + " Respond ONLY as JSON: {\"score\": <float>, \"reason\": <string>}."},
                {"role": "user", "content": payload},
            ],

        )
        raw = resp.choices[0].message.content or "{}"
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return float(data.get("score", 0.0)), data.get("reason", "")