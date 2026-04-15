"""OpenTelemetry setup for Collective Brain.

Call setup_telemetry(settings) once at app startup.
Then use get_tracer() anywhere you need a span.

Trace IDs are injected into every log record via the RequestIDFilter
enhancement in main.py, so every log line carries:
  - request_id (existing)
  - trace_id   (new — links logs to distributed traces)
  - org_id     (new — enables per-tenant log filtering)

Exporter behaviour:
  - CB_OTEL_ENDPOINT is set → sends traces to that OTLP gRPC endpoint
    (Grafana Tempo, Jaeger, Honeycomb, etc.)
  - Otherwise → no-op exporter (zero overhead, traces not exported)
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

logger = logging.getLogger("collective_brain.telemetry")

_tracer_provider: TracerProvider | None = None


def setup_telemetry(service_name: str = "collective-brain", version: str = "0.3.0") -> None:
    """Initialize OpenTelemetry. Safe to call multiple times (idempotent)."""
    global _tracer_provider
    if _tracer_provider is not None:
        return

    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: version,
        "deployment.environment": "production" if os.getenv("CB_DEV_MODE") != "1" else "development",
    })

    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("CB_OTEL_ENDPOINT", "")

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OpenTelemetry: exporting traces to %s", otlp_endpoint)
        except ImportError:
            logger.warning("opentelemetry-exporter-otlp-proto-grpc not installed — traces not exported")
    else:
        # Dev mode: log a message but don't spam stdout with trace JSON
        logger.info(
            "OpenTelemetry: no CB_OTEL_ENDPOINT set — set it to export traces "
            "(e.g. Grafana Tempo at http://localhost:4317)"
        )

    # Auto-instrument FastAPI (adds span per request, propagates context)
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument()
        logger.info("OpenTelemetry: FastAPI instrumented")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-fastapi not installed")

    # Auto-instrument SQLAlchemy (adds span per query)
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
        logger.info("OpenTelemetry: SQLAlchemy instrumented")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-sqlalchemy not installed")

    # Auto-instrument httpx (adds span per outbound HTTP call — LLM APIs)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("OpenTelemetry: httpx instrumented")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-httpx not installed")

    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    logger.info("OpenTelemetry: tracer provider initialized")


def get_tracer(name: str = "collective_brain") -> trace.Tracer:
    """Return an OpenTelemetry tracer. Always safe to call — returns a no-op tracer if not set up."""
    return trace.get_tracer(name)


def current_trace_id() -> str:
    """Return the current trace ID as a hex string, or '-' if no active span."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.is_valid:
        return format(ctx.trace_id, "032x")
    return "-"
