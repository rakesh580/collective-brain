"""Structured HTTP request access log middleware.

One log record per handled request, at the ``collective_brain.access_log``
logger. Carries the fields needed for SLO calculation and per-tenant
debugging without any additional infrastructure:

- method, path, status_code
- latency_ms
- user_id, org_id (or "-" when unauthenticated)
- the standard request_id + trace_id are added by the existing logging
  filter in main.py, so there's no duplication here.

Log levels:
- 5xx → WARNING (operator-actionable)
- everything else → INFO (noise expected; includes 401/403/404 from bots)

These records feed three use cases:
1. SLO tracking via ``latency_ms`` + ``status_code`` percentiles.
2. Per-org debugging via ``org_id``.
3. Error investigation — pair with the ``error_ref`` emitted by the global
   exception handler to find the exact traceback.

Week 14-A of the ultra plan (Q2 observability quarter).
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

access_logger = logging.getLogger("collective_brain.access_log")


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000.0

        user = getattr(getattr(request, "state", None), "user", None)
        user_id = getattr(user, "id", None) or "-"
        org_id = getattr(user, "organization_id", None) or "-"

        level = logging.WARNING if response.status_code >= 500 else logging.INFO

        # Stdlib logging supports structured fields via the `extra` kwarg —
        # they attach to the LogRecord so the JSON formatter (in prod) picks
        # them up automatically, and they're also readable in dev-mode logs.
        access_logger.log(
            level,
            "%s %s -> %d in %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
                "user_id": user_id,
                "org_id": org_id,
            },
        )

        return response
