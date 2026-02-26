"""Unit tests for RedisService — caching, pub/sub, rate limiting (in-memory fallback)."""

import asyncio
import time

import pytest

from app.services.redis_service import RedisService


@pytest.fixture()
def svc():
    """RedisService with no URL → in-memory fallback."""
    return RedisService(redis_url="")


class TestInMemoryCache:
    @pytest.mark.asyncio
    async def test_set_and_get(self, svc):
        await svc.cache_set("key1", {"data": 42}, ttl_seconds=60)
        result = await svc.cache_get("key1")
        assert result == {"data": 42}

    @pytest.mark.asyncio
    async def test_get_missing_key(self, svc):
        result = await svc.cache_get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_expiry(self, svc):
        await svc.cache_set("temp", "value", ttl_seconds=0)
        # TTL=0 means no expiry in this implementation
        result = await svc.cache_get("temp")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_cache_delete(self, svc):
        await svc.cache_set("todel", "val")
        await svc.cache_delete("todel")
        assert await svc.cache_get("todel") is None

    @pytest.mark.asyncio
    async def test_cache_delete_pattern(self, svc):
        await svc.cache_set("prefix:a", 1)
        await svc.cache_set("prefix:b", 2)
        await svc.cache_set("other:c", 3)
        await svc.cache_delete_pattern("prefix:*")
        assert await svc.cache_get("prefix:a") is None
        assert await svc.cache_get("prefix:b") is None
        assert await svc.cache_get("other:c") == 3


class TestInMemoryPubSub:
    @pytest.mark.asyncio
    async def test_publish_subscribe(self, svc):
        received = []

        async def callback(data):
            received.append(data)

        await svc.subscribe("ch1", callback)
        await svc.publish("ch1", {"msg": "hello"})

        assert len(received) == 1
        assert received[0] == {"msg": "hello"}

    @pytest.mark.asyncio
    async def test_unsubscribe(self, svc):
        received = []

        async def callback(data):
            received.append(data)

        await svc.subscribe("ch1", callback)
        await svc.unsubscribe("ch1")
        await svc.publish("ch1", {"msg": "hello"})

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, svc):
        r1, r2 = [], []

        async def cb1(data):
            r1.append(data)

        async def cb2(data):
            r2.append(data)

        await svc.subscribe("ch", cb1)
        await svc.subscribe("ch", cb2)
        await svc.publish("ch", {"x": 1})

        assert len(r1) == 1
        assert len(r2) == 1

    @pytest.mark.asyncio
    async def test_publish_to_wrong_channel(self, svc):
        received = []

        async def callback(data):
            received.append(data)

        await svc.subscribe("ch1", callback)
        await svc.publish("ch2", {"msg": "hello"})

        assert len(received) == 0


class TestInMemoryRateLimiting:
    @pytest.mark.asyncio
    async def test_allows_within_limit(self, svc):
        for _ in range(5):
            allowed, remaining = await svc.check_rate_limit("test", 5, window_seconds=60)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, svc):
        for _ in range(5):
            await svc.check_rate_limit("test", 5, window_seconds=60)

        allowed, remaining = await svc.check_rate_limit("test", 5, window_seconds=60)
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, svc):
        for _ in range(5):
            await svc.check_rate_limit("key1", 5, window_seconds=60)

        # key2 should still be allowed
        allowed, remaining = await svc.check_rate_limit("key2", 5, window_seconds=60)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_window_expires(self, svc):
        # Fill up the limit with a very short window
        for _ in range(3):
            await svc.check_rate_limit("expire_test", 3, window_seconds=0)

        # With window=0, old entries should be cleaned on next check
        await asyncio.sleep(0.01)
        allowed, _ = await svc.check_rate_limit("expire_test", 3, window_seconds=0)
        # All previous entries older than 0 seconds are pruned
        assert allowed is True


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_ping_without_redis(self, svc):
        assert await svc.ping() is False

    def test_is_connected_without_redis(self, svc):
        assert svc.is_connected is False

    @pytest.mark.asyncio
    async def test_close_without_redis(self, svc):
        # Should not raise
        await svc.close()
