from redis.asyncio import Redis
from redis.exceptions import RedisError

from harness.cache.redis_client import get_redis
from harness.logging import log

DEFAULT_TTL_SECONDS = 24*60*60

class RedisCache:
    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS)->None:
        self._ttl = ttl
        self._redis: Redis = get_redis()
    
    async def get(self, key: str)->str | None:
        try:
            return await self._redis.get(key)
        except RedisError as e:
            log.warning("Cache unavailable on get", error = type(e).__name__)
            return None
        
    async def set(self, key:str, value: str)->None:
        try:
            await self._redis.set(key, value, ex = self._ttl)
        except RedisError as e:
            log.warning("Cache unavilable on set", error = type(e).__name__)
