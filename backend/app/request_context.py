"""Shared request-scoped context variables.

These were originally defined in ``main.py`` but are now shared so
middleware modules can set them without circular imports through main.

- ``request_id_var`` — short 8-char hex, attached to the response as
  ``X-Request-ID`` and included in every log record for correlation.
- ``org_id_var`` — the authenticated caller's organization_id, attached
  to log records for per-tenant log queries.

The ``RequestContextFilter`` in ``main.py`` reads these and writes them
onto every ``LogRecord`` as ``record.request_id`` and ``record.org_id``.
Middleware that knows these values (``RequestIDMiddleware``,
``AccessLogMiddleware``) sets them via ``var.set(...)`` at the start of
each request.
"""

from __future__ import annotations

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
org_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("org_id", default="-")
