"""Tests for the structured HTTP request access log middleware.

Behavior asserted: every handled HTTP request emits exactly one structured
log record with a fixed shape, carrying:
- method, path (the matched route template — not the full URL with query),
- status_code, latency_ms (non-negative float),
- user_id when the request was authenticated (else "-"),
- org_id via the shared ``org_id_var`` contextvar so the
  ``RequestContextFilter`` in main.py writes it onto the record WITHOUT
  colliding with ``extra=``.

The log record level is INFO for 2xx/3xx/4xx and WARNING for 5xx so
operators can grep for 5xx by level alone.

This is the SLO foundation — Week 14-A of the ultra plan.

Includes a "production logging chain" regression test that replays the
exact main.py JSON formatter + _record_factory + RequestContextFilter
pipeline, to catch the ``KeyError: "Attempt to overwrite 'org_id' in
LogRecord"`` that broke the original shipment (PR #14).
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
    # user_id travels via extra= (no collision with LogRecord defaults).
    assert rec.user_id == "-"
    # org_id is NOT on the raw record — it's fed through org_id_var and
    # materialized onto the record by main.py's RequestContextFilter, which
    # isn't attached to this test's plain handler. See
    # test_works_under_production_logging_chain for the full-pipeline check.


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
    dependency), user_id lands on the record via extra= and org_id is
    pushed into the contextvar for the RequestContextFilter to pick up.

    We verify user_id directly here; org_id propagation is covered by
    test_works_under_production_logging_chain, which runs the full filter
    pipeline end-to-end.
    """
    from app.request_context import org_id_var

    user = MagicMock()
    user.id = "user-42"
    user.organization_id = "org-7"

    # Sample the contextvar from INSIDE the middleware's log call by hooking
    # a filter that captures the current value.
    captured_org = {"value": None}

    class _ContextCapture(logging.Filter):
        def filter(self, record):
            captured_org["value"] = org_id_var.get("<unset>")
            return True

    access_log_handler.addFilter(_ContextCapture())

    await _run_middleware("POST", "/api/v1/ingest", 200, user=user)

    rec = access_log_handler.records[0]
    assert rec.user_id == "user-42"
    assert captured_org["value"] == "org-7"


@pytest.mark.asyncio
async def test_works_under_production_logging_chain():
    """Replay the EXACT main.py logging setup — factory, filter, JSON
    formatter — to prove the middleware doesn't KeyError when the record
    factory preemptively sets org_id / request_id / trace_id defaults.

    This is the test that PR #14 was missing. The plain-handler tests
    above pass even when the middleware is broken in production because
    they bypass both the factory and the filter.
    """
    from pythonjsonlogger import jsonlogger

    from app.request_context import org_id_var, request_id_var

    # Replicate main.py's record factory.
    old_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        r = old_factory(*args, **kwargs)
        if not hasattr(r, "request_id"):
            r.request_id = "-"
        if not hasattr(r, "trace_id"):
            r.trace_id = "-"
        if not hasattr(r, "org_id"):
            r.org_id = "-"
        return r

    logging.setLogRecordFactory(factory)
    try:
        import io

        # Replicate the JSON formatter + handler wiring.
        stream = io.StringIO()
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(request_id)s %(trace_id)s %(org_id)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)

        class ContextFilter(logging.Filter):
            def filter(self, r):
                r.request_id = request_id_var.get("-")
                r.trace_id = "-"
                r.org_id = org_id_var.get("-")
                return True

        handler.addFilter(ContextFilter())

        access_logger = logging.getLogger("collective_brain.access_log")
        access_logger.handlers = [handler]
        access_logger.propagate = False
        access_logger.setLevel(logging.INFO)

        # Now drive the middleware end-to-end.
        user = MagicMock()
        user.id = "user-7"
        user.organization_id = "org-42"
        await _run_middleware("GET", "/api/v1/health", 200, user=user)

        # No KeyError means the fix is real. Verify the JSON carries the
        # contextvar-sourced org_id AND the extra-sourced custom fields.
        import json

        line = stream.getvalue().strip()
        assert line, "middleware failed to emit a log line"
        record = json.loads(line)

        assert record["org_id"] == "org-42"  # From contextvar via filter
        assert record["status_code"] == 200  # From extra kwarg
        assert record["user_id"] == "user-7"
        assert record["method"] == "GET"
        assert record["path"] == "/api/v1/health"
    finally:
        logging.setLogRecordFactory(old_factory)


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
