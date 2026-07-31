"""
NHPC Weather Warning System — Prometheus Metrics Definitions.

Exposes application-level metrics for monitoring via Prometheus.
Metrics are registered globally and instrumented from the relevant
modules (server, scraper, database).

The ``/metrics`` endpoint in start_server.py serves these metrics
in Prometheus text exposition format.

If prometheus_client is not installed, this module provides no-op
stubs so the rest of the codebase can instrument freely without
import errors or conditional logic.
"""

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # --- No-op stubs so instrumentation code doesn't need conditionals ---
    class _NoOp:
        """No-op metric stub when prometheus_client is not installed."""

        def __init__(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

        def observe(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def dec(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def time(self):
            """Context manager that does nothing."""
            import contextlib
            return contextlib.nullcontext()

    Counter = _NoOp  # type: ignore[assignment, misc]
    Gauge = _NoOp  # type: ignore[assignment, misc]
    Histogram = _NoOp  # type: ignore[assignment, misc]
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

    def generate_latest(registry=None) -> bytes:  # type: ignore[misc]
        return b"# prometheus_client not installed\n"


# ---------------------------------------------------------------------------
# HTTP / API Metrics
# ---------------------------------------------------------------------------

HTTP_REQUEST_DURATION = Histogram(
    "nhpc_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_TOTAL = Counter(
    "nhpc_http_requests_total",
    "Total number of HTTP requests processed",
    ["method", "endpoint", "status_code"],
)

HTTP_ERROR_TOTAL = Counter(
    "nhpc_http_errors_total",
    "Total number of HTTP error responses (4xx/5xx)",
    ["method", "endpoint", "status_code"],
)

# ---------------------------------------------------------------------------
# Forecast Scraper Metrics
# ---------------------------------------------------------------------------

FORECAST_UPDATE_DURATION = Histogram(
    "nhpc_forecast_update_duration_seconds",
    "Duration of a complete forecast scrape cycle",
)

FORECAST_UPDATE_TOTAL = Counter(
    "nhpc_forecast_updates_total",
    "Total number of forecast update cycles",
    ["status"],
)

FORECAST_STATION_COUNT = Gauge(
    "nhpc_forecast_stations_total",
    "Number of stations processed in last forecast run",
)

# ---------------------------------------------------------------------------
# IMD API Metrics
# ---------------------------------------------------------------------------

IMD_REQUEST_DURATION = Histogram(
    "nhpc_imd_request_duration_seconds",
    "IMD API request latency in seconds",
    ["endpoint"],
)

IMD_REQUEST_TOTAL = Counter(
    "nhpc_imd_requests_total",
    "Total IMD API requests",
    ["endpoint", "status"],
)

IMD_CACHE_HITS = Counter(
    "nhpc_imd_cache_hits_total",
    "Total IMD forecast cache hits",
)

# ---------------------------------------------------------------------------
# Database Metrics
# ---------------------------------------------------------------------------

DB_QUERY_DURATION = Histogram(
    "nhpc_db_query_duration_seconds",
    "Database query latency in seconds",
    ["operation"],
)

DB_ERROR_TOTAL = Counter(
    "nhpc_db_errors_total",
    "Total database errors",
    ["operation"],
)

# ---------------------------------------------------------------------------
# Alert Metrics
# ---------------------------------------------------------------------------

ACTIVE_ALERTS = Gauge(
    "nhpc_active_alerts",
    "Current active alert count by level",
    ["level"],
)

ALERT_TRANSITIONS_TOTAL = Counter(
    "nhpc_alert_transitions_total",
    "Total alert state transitions",
    ["old_status", "new_status"],
)

# ---------------------------------------------------------------------------
# Notification Metrics
# ---------------------------------------------------------------------------

NOTIFICATION_TOTAL = Counter(
    "nhpc_notifications_total",
    "Total alert notifications sent",
    ["channel", "status"],
)
