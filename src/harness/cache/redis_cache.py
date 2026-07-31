import redis.asyncio as redis

class RedisCache:
    def __init__(self, url:str, ttl_seconds: int = 86400)->None:
        self._r = redis.from_url(url, decode_responses = True)
        self._ttl = ttl_seconds
    async def get(self, key:str)->str | None:
        return await self._r.get(key)
    async def set(self, key:str, value:str) -> None:
        await self._r.set(key, value, ex = self._ttl)