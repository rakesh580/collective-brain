"""Circuit Breaker pattern to prevent cascading failures.

States:
  CLOSED  → Normal operation, requests pass through
  OPEN    → Service is down, requests fail fast without calling the service
  HALF_OPEN → After timeout, allow one test request to check recovery

Prevents:
  - Thread exhaustion from hanging requests to a dead service
  - Cascading timeouts across dependent services
  - Resource starvation when LLM/embedding/external APIs go down
"""

import logging
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar

logger = logging.getLogger("collective_brain.circuit_breaker")

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Raised when the circuit is open and requests are being rejected."""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Service '{service_name}' is unavailable (circuit open). "
            f"Retry after {retry_after:.0f}s"
        )


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    Usage:
        breaker = CircuitBreaker("llm_service", failure_threshold=3, recovery_timeout=30)
        result = await breaker.call(llm.generate, messages)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._last_error: str | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info("Circuit %s: OPEN → HALF_OPEN (testing recovery)", self.name)
        return self._state

    @property
    def is_available(self) -> bool:
        return self.state != CircuitState.OPEN

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute a function through the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            retry_after = self.recovery_timeout - (time.time() - self._last_failure_time)
            raise CircuitBreakerError(self.name, max(0, retry_after))

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except CircuitBreakerError:
            raise  # Don't count circuit breaker errors as failures
        except Exception as e:
            self._on_failure(str(e))
            raise

    def _on_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._last_error = None
                logger.info("Circuit %s: HALF_OPEN → CLOSED (recovered)", self.name)
        else:
            # Reset failure count on success in closed state
            self._failure_count = 0

    def _on_failure(self, error: str):
        self._failure_count += 1
        self._last_failure_time = time.time()
        self._last_error = error

        if self._state == CircuitState.HALF_OPEN:
            # Failed during recovery test — go back to open
            self._state = CircuitState.OPEN
            logger.warning("Circuit %s: HALF_OPEN → OPEN (recovery failed: %s)", self.name, error)
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit %s: CLOSED → OPEN after %d failures (last: %s)",
                self.name, self._failure_count, error,
            )

    def get_status(self) -> dict:
        """Return circuit breaker status for health checks."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_error": self._last_error,
            "is_available": self.is_available,
        }

    def reset(self):
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_error = None
        logger.info("Circuit %s: manually reset to CLOSED", self.name)
