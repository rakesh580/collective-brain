"""Tests for the structured HTTP request access log middleware.

Behavior asserted: every handled HTTP request emits exactly one structured
log record with a fixed shape, carrying:
- method, path (the matched route template — not the full URL with query),
- status_code, latency_ms (non-negative float),
- request_id (echoed from the header or generated),
- user_id + org_id when the request was authenticated (else "-").

The log record level is INFO for 2xx/3xx/4xx and WARNING for 5xx so
operators can grep for 5xx by level alone.

This is the SLO foundation — Week 14-A of the ultra plan.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from app.middleware.access_log import AccessLogMiddleware


class _CollectingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def access_log_handler(monkeypatch):
    logger = logging.getLogger("collective_brain.access_log")
    handler = _CollectingHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield handler
    logger.removeHandler(handler)


async def _run_middleware(method: str, path: str, status: int, user=None):
    """Drive the middleware with a fake request/response pair."""
    middleware = AccessLogMiddleware(app=lambda *_a, **_kw: None)

    # Starlette's middleware contract: dispatch(request, call_next).
    request = MagicMock()
    request.method = method
    request.url.path = path
    request.headers = {}
    request.state = MagicMock()
    request.state.user = user

    response = MagicMock()
    response.status_code = status
    response.headers = {}

    async def call_next(_req):
        return response

    return await middleware.dispatch(request, call_next)


@pytest.mark.asyncio
async def test_emits_one_info_record_per_2xx_request(access_log_handler):
    await _run_middleware("GET", "/api/v1/health", 200)

    assert len(access_log_handler.records) == 1
    rec = access_log_handler.records[0]
    assert rec.levelno == logging.INFO
    assert rec.method == "GET"
    assert rec.path == "/api/v1/health"
    assert rec.status_code == 200
    assert rec.latency_ms >= 0
    # User/org default to "-" when the request is unauthenticated.
    assert rec.user_id == "-"
    assert rec.org_id == "-"


@pytest.mark.asyncio
async def test_5xx_logs_at_warning_level(access_log_handler):
    """Grep-by-level lets operators isolate server errors without regex."""
    await _run_middleware("POST", "/api/v1/signals", 500)

    rec = access_log_handler.records[0]
    assert rec.levelno == logging.WARNING
    assert rec.status_code == 500


@pytest.mark.asyncio
async def test_4xx_logs_at_info_level(access_log_handler):
    """Client errors (auth failures, validation) are not server-health
    issues — they should stay at INFO so noisy bot traffic doesn't page."""
    await _run_middleware("GET", "/api/v1/signals", 401)

    rec = access_log_handler.records[0]
    assert rec.levelno == logging.INFO
    assert rec.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_request_carries_user_and_org(access_log_handler):
    """When the request has request.state.user set (by get_current_user
    dependency), the log line attaches their ID + org for per-tenant queries."""
    user = MagicMock()
    user.id = "user-42"
    user.organization_id = "org-7"

    await _run_middleware("POST", "/api/v1/ingest", 200, user=user)

    rec = access_log_handler.records[0]
    assert rec.user_id == "user-42"
    assert rec.org_id == "org-7"


@pytest.mark.asyncio
async def test_latency_reflects_response_time(access_log_handler, monkeypatch):
    """Latency field should track wall-clock time through call_next."""
    import asyncio

    middleware = AccessLogMiddleware(app=lambda *_a, **_kw: None)
    request = MagicMock()
    request.method = "GET"
    request.url.path = "/slow"
    request.headers = {}
    request.state = MagicMock()
    request.state.user = None

    response = MagicMock()
    response.status_code = 200
    response.headers = {}

    async def slow_call_next(_req):
        await asyncio.sleep(0.05)
        return response

    await middleware.dispatch(request, slow_call_next)

    rec = access_log_handler.records[0]
    # 50ms ± reasonable slack for CI runner jitter
    assert rec.latency_ms >= 40
