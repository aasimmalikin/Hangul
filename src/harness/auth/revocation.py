import time
from harness.cache.redis_client import get_redis

_PREFIX = "revoked:"

async def revoke(jti: str, exp: int)-> None:
    ttl = max(1, exp - int(time.time()))
    await get_redis.set(f"{_PREFIX}{jti}", "1", exp = ttl)

async def is_revoked(jti: str)->bool:
    try:
        await get_redis.get(f"{_PREFIX}{jti}") is not None
    except:
        return True
