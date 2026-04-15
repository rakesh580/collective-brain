"""Redis service for pub/sub, caching, and rate limiting.

Falls back gracefully to in-memory when Redis is unavailable,
so the app works in dev without Redis running.
"""

import asyncio
import contextlib
import json
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("collective_brain.redis")

# In-memory fallbacks
_memory_cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expire_time)
_memory_pubsub: dict[str, list[Callable]] = defaultdict(list)
_memory_rate: dict[str, list[float]] = defaultdict(list)


class RedisService:
    """Unified Redis interface with in-memory fallback."""

    def __init__(self, redis_url: str = ""):
        self._redis = None
        self._pubsub = None
        self._subscriptions: dict[str, Callable] = {}
        self._listener_task: asyncio.Task | None = None
        self._redis_url = redis_url

        if redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                )
                # Safely log Redis host without credentials
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(redis_url)
                    safe_host = f"{parsed.hostname}:{parsed.port}" if parsed.hostname else "unknown"
                except Exception:
                    safe_host = "configured"
                logger.info("Redis connected: %s", safe_host)
            except Exception as e:
                logger.warning("Redis unavailable, using in-memory fallback: %s", e)
                self._redis = None
        else:
            logger.info("No Redis URL configured, using in-memory fallback")

    @property
    def is_connected(self) -> bool:
        return self._redis is not None

    # ─── Health Check ──────────────────────────────────────────

    async def ping(self) -> bool:
        if not self._redis:
            return False
        try:
            return await self._redis.ping()
        except Exception:
            return False

    # ─── Caching ───────────────────────────────────────────────

    async def cache_get(self, key: str) -> Any | None:
        """Get cached value. Returns None if not found or expired."""
        if self._redis:
            try:
                val = await self._redis.get(f"cache:{key}")
                return json.loads(val) if val else None
            except Exception:
                pass

        # In-memory fallback
        if key in _memory_cache:
            value, expire = _memory_cache[key]
            if expire == 0 or time.time() < expire:
                return value
            del _memory_cache[key]
        return None

    async def cache_set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Cache a value with TTL."""
        if self._redis:
            try:
                await self._redis.setex(
                    f"cache:{key}", ttl_seconds, json.dumps(value, default=str)
                )
                return
            except Exception:
                pass

        # In-memory fallback
        expire = time.time() + ttl_seconds if ttl_seconds > 0 else 0
        _memory_cache[key] = (value, expire)

    async def cache_delete(self, key: str):
        """Invalidate a cache key."""
        if self._redis:
            try:
                await self._redis.delete(f"cache:{key}")
                return
            except Exception:
                pass

        _memory_cache.pop(key, None)

    async def cache_delete_pattern(self, pattern: str):
        """Delete all keys matching a pattern."""
        if self._redis:
            try:
                keys = []
                async for key in self._redis.scan_iter(f"cache:{pattern}"):
                    keys.append(key)
                if keys:
                    await self._redis.delete(*keys)
                return
            except Exception:
                pass

        # In-memory fallback — simple prefix match
        prefix = pattern.rstrip("*")
        to_delete = [k for k in _memory_cache if k.startswith(prefix)]
        for k in to_delete:
            del _memory_cache[k]

    # ─── Pub/Sub ───────────────────────────────────────────────

    async def publish(self, channel: str, message: dict):
        """Publish a message to a channel."""
        if self._redis:
            try:
                await self._redis.publish(channel, json.dumps(message, default=str))
                return
            except Exception:
                pass

        # In-memory fallback — call subscribers directly
        for callback in _memory_pubsub.get(channel, []):
            try:
                await callback(message)
            except Exception as e:
                logger.error("In-memory pubsub callback error: %s", e)

    async def subscribe(self, channel: str, callback: Callable[[dict], Awaitable[None]]):
        """Subscribe to a channel with an async callback."""
        if self._redis:
            try:
                if self._pubsub is None:
                    self._pubsub = self._redis.pubsub()

                await self._pubsub.subscribe(channel)
                self._subscriptions[channel] = callback

                # Start listener if not running
                if self._listener_task is None or self._listener_task.done():
                    self._listener_task = asyncio.create_task(self._listen_loop())
                return
            except Exception:
                pass

        # In-memory fallback
        _memory_pubsub[channel].append(callback)

    async def unsubscribe(self, channel: str):
        """Unsubscribe from a channel."""
        if self._redis and self._pubsub:
            with contextlib.suppress(Exception):
                await self._pubsub.unsubscribe(channel)

        self._subscriptions.pop(channel, None)
        _memory_pubsub.pop(channel, None)

    async def _listen_loop(self):
        """Background task that reads messages from Redis pub/sub."""
        if not self._pubsub:
            return
        try:
            while True:
                msg = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg and msg["type"] == "message":
                    channel = msg["channel"]
                    callback = self._subscriptions.get(channel)
                    if callback:
                        try:
                            data = json.loads(msg["data"])
                            await callback(data)
                        except Exception as e:
                            logger.error("Pub/sub callback error on %s: %s", channel, e)
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Pub/sub listener error: %s", e)

    # ─── Rate Limiting ─────────────────────────────────────────

    async def check_rate_limit(
        self, key: str, max_requests: int, window_seconds: int = 60
    ) -> tuple[bool, int]:
        """Check if a rate limit is exceeded.

        Returns (allowed: bool, remaining: int).
        """
        full_key = f"rate:{key}"

        if self._redis:
            try:
                now = time.time()
                pipe = self._redis.pipeline()
                pipe.zremrangebyscore(full_key, 0, now - window_seconds)
                pipe.zadd(full_key, {str(now): now})
                pipe.zcard(full_key)
                pipe.expire(full_key, window_seconds)
                results = await pipe.execute()
                count = results[2]
                remaining = max(0, max_requests - count)
                return count <= max_requests, remaining
            except Exception:
                pass

        # In-memory fallback
        now = time.time()
        _memory_rate[key] = [
            t for t in _memory_rate[key] if t > now - window_seconds
        ]
        _memory_rate[key].append(now)
        count = len(_memory_rate[key])
        remaining = max(0, max_requests - count)
        return count <= max_requests, remaining

    # ─── Cleanup ───────────────────────────────────────────────

    async def close(self):
        """Clean shutdown."""
        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task

        if self._pubsub:
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()

        logger.info("Redis service closed")
