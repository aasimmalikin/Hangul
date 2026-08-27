from redis.asyncio import Redis, ConnectionPool
from harness.config import get_settings

_pool = ConnectionPool.from_url(
    get_settings().redis_url, 
    decode_responses = True,
    max_connections = 20,
)

def get_redis()->Redis:
    return Redis(connection_pool = _pool)