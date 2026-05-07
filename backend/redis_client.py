"""
Shared Redis client module.
Tries real Redis first; falls back to in-process fakeredis automatically.
One shared fakeredis server so pub/sub works between the pipeline and WebSocket.
"""
import os
import logging
import threading

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("APP_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

_fake_server = None
_using_fake = False
_lock = threading.Lock()


def _init_fake():
    global _fake_server, _using_fake
    with _lock:
        if not _using_fake:
            import fakeredis
            _fake_server = fakeredis.FakeServer()
            _using_fake = True
            logger.warning("Real Redis not available — using in-process fakeredis")


def get_sync_redis():
    """Return a sync redis.Redis client (real or fake)."""
    if _using_fake:
        import fakeredis
        return fakeredis.FakeRedis(server=_fake_server, decode_responses=True)
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        return client
    except Exception:
        _init_fake()
        import fakeredis
        return fakeredis.FakeRedis(server=_fake_server, decode_responses=True)


async def get_async_client():
    """Return an async Redis client (real aioredis or async fakeredis)."""
    if _using_fake:
        import fakeredis.aioredis
        return fakeredis.aioredis.FakeRedis(server=_fake_server, decode_responses=True)
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        return client
    except Exception:
        _init_fake()
        import fakeredis.aioredis
        return fakeredis.aioredis.FakeRedis(server=_fake_server, decode_responses=True)
