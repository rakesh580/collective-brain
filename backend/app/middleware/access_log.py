"""Structured HTTP request access log middleware.

One log record per handled request at the ``collective_brain.access_log``
logger. Carries the fields needed for SLO calculation and per-tenant
debugging without any additional infrastructure.

Fields on every record (via stdlib logging's ``extra=`` kwarg):
- method, path, status_code, latency_ms, user_id

Fields via contextvars (read by the ``RequestContextFilter`` in main.py):
- request_id, trace_id, org_id

Why this split: main.py's ``_record_factory`` preemptively sets
``request_id``, ``trace_id``, and ``org_id`` as default attributes on
EVERY LogRecord. Python's ``logging.Logger.makeRecord`` then raises
``KeyError: "Attempt to overwrite 'X' in LogRecord"`` if we try to pass
those keys via ``extra=`` (documented 3.2+ behavior). So we feed the
contextvars and let the filter populate the record naturally.

Log levels:
- 5xx → WARNING (operator-actionable)
- everything else → INFO (includes 401/403/404 from bots, unauth probes)

Week 14-A of the ultra plan (Q2 observability quarter).
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.request_context import org_id_var

access_logger = logging.getLogger("collective_brain.access_log")


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000.0

        user = getattr(getattr(request, "state", None), "user", None)
        user_id = getattr(user, "id", None) or "-"
        resolved_org = getattr(user, "organization_id", None) or "-"

        # Feed org_id into the contextvar so the RequestContextFilter
        # picks it up and writes it onto the record. This avoids the
        # ``extra=`` overwrite collision with main.py's _record_factory.
        token = org_id_var.set(resolved_org)
        try:
            level = logging.WARNING if response.status_code >= 500 else logging.INFO
            access_logger.log(
                level,
                "%s %s -> %d in %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                latency_ms,
                extra={
                    # Only NEW keys here — reserved fields (request_id,
                    # trace_id, org_id, message, asctime) must not appear.
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": round(latency_ms, 2),
                    "user_id": user_id,
                },
            )
        finally:
            org_id_var.reset(token)

        return response
