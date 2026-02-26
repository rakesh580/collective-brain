"""Unit tests for CircuitBreaker — state transitions, failure tracking, recovery."""

import asyncio
import time

import pytest

from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


class TestCircuitBreakerStates:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True

    def test_status_report(self):
        cb = CircuitBreaker("test_svc")
        status = cb.get_status()
        assert status["name"] == "test_svc"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["is_available"] is True


class TestFailureTracking:
    @pytest.mark.asyncio
    async def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)

        async def failing():
            raise ValueError("boom")

        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(failing)

        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 2

    @pytest.mark.asyncio
    async def test_opens_at_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)

        async def failing():
            raise ValueError("boom")

        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(failing)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)

        async def failing():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call(failing)

        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerError) as exc_info:
            await cb.call(failing)
        assert exc_info.value.service_name == "test"

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3)

        async def failing():
            raise ValueError("boom")

        async def success():
            return "ok"

        # 2 failures
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(failing)

        # 1 success resets counter
        result = await cb.call(success)
        assert result == "ok"
        assert cb._failure_count == 0


class TestRecovery:
    @pytest.mark.asyncio
    async def test_transitions_to_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        async def failing():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call(failing)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        cb = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1, success_threshold=1
        )

        async def failing():
            raise ValueError("boom")

        async def success():
            return "ok"

        with pytest.raises(ValueError):
            await cb.call(failing)

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        result = await cb.call(success)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        async def failing():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call(failing)

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        with pytest.raises(ValueError):
            await cb.call(failing)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_manual_reset(self):
        cb = CircuitBreaker("test", failure_threshold=1)

        async def failing():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call(failing)

        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0


class TestCircuitBreakerError:
    def test_error_attributes(self):
        err = CircuitBreakerError("my_service", retry_after=30.0)
        assert err.service_name == "my_service"
        assert err.retry_after == 30.0
        assert "my_service" in str(err)
