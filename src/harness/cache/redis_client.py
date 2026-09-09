from redis.asyncio import Redis, from_url

from harness.config import get_settings


_client: Redis = from_url(
    get_settings().redis_url,
    decode_responses=True,
    max_connections=10,
)


def get_redis() -> Redis:
    return _client
