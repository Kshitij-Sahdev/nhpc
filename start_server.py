"""
NHPC Weather Warning System — HTTP Server & REST API.

Serves the web dashboard (static files) and provides REST API endpoints
for weather forecasts, plant data, alert history, health checks,
metrics, and API documentation.

Features:
- ThreadingTCPServer for concurrent request handling
- Input validation and HTML sanitization
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- IP-based rate limiting (defense-in-depth)
- Kubernetes-compatible health probes (/liveness, /readiness)
- Prometheus metrics endpoint (/metrics)
- Redoc API documentation (/api/docs)

Usage:
    python start_server.py
"""

import http.server
import socketserver
import webbrowser
import threading
import time
import sys
import os
import json
import html
import shutil
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import database
from log import setup_logging, get_logger
from config import get_settings
from metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUEST_TOTAL,
    HTTP_ERROR_TOTAL,
    generate_latest,
    CONTENT_TYPE_LATEST,
    PROMETHEUS_AVAILABLE,
)

# --- Initialize logging and config ---
settings = get_settings()
setup_logging(
    level=settings.LOG_LEVEL,
    fmt=settings.LOG_FORMAT,
    log_file=settings.LOG_FILE,
)
logger = get_logger("nhpc.server")

# --- Process start time for uptime tracking ---
_START_TIME = time.monotonic()

# --- Rate Limiter (in-memory, per-IP) ---
_rate_lock = threading.Lock()
_rate_map: Dict[str, list] = {}  # IP -> list of request timestamps


def _check_rate_limit(ip: str) -> bool:
    """Check if an IP has exceeded the rate limit.

    Args:
        ip: Client IP address.

    Returns:
        True if rate limit exceeded, False if within limits.
    """
    rpm = settings.RATE_LIMIT_RPM
    if rpm <= 0:
        return False  # Rate limiting disabled

    now = time.time()
    window = 60.0  # 1 minute window

    with _rate_lock:
        if ip not in _rate_map:
            _rate_map[ip] = []

        # Purge old entries
        _rate_map[ip] = [t for t in _rate_map[ip] if now - t < window]

        if len(_rate_map[ip]) >= rpm:
            return True  # Rate limit exceeded

        _rate_map[ip].append(now)
        return False


def _cleanup_rate_map() -> None:
    """Periodically clean up stale rate limit entries."""
    now = time.time()
    with _rate_lock:
        stale_ips = [ip for ip, times in _rate_map.items()
                     if not times or now - max(times) > 120]
        for ip in stale_ips:
            del _rate_map[ip]


# --- Input Validation ---

def sanitize_name(raw_name: Optional[str]) -> str:
    """Sanitize user-provided name: strip HTML, limit length.

    Args:
        raw_name: Raw user input string.

    Returns:
        Cleaned, HTML-escaped, length-limited string.
    """
    if not raw_name:
        return ""
    # Strip HTML tags
    cleaned = html.escape(raw_name.strip())
    # Limit length
    if len(cleaned) > settings.NAME_MAX_LENGTH:
        cleaned = cleaned[:settings.NAME_MAX_LENGTH]
    return cleaned


def validate_coordinates(lat_str: str, lon_str: str) -> tuple:
    """Validate and parse lat/lon strings.

    Args:
        lat_str: Latitude as string.
        lon_str: Longitude as string.

    Returns:
        Tuple of (lat, lon) as floats.

    Raises:
        ValueError: If coordinates are invalid or out of range.
    """
    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except (ValueError, TypeError):
        raise ValueError("Latitude and longitude must be valid numbers.")

    if not (settings.LAT_MIN <= lat <= settings.LAT_MAX):
        raise ValueError(f"Latitude must be between {settings.LAT_MIN} and {settings.LAT_MAX} for Indian region.")
    if not (settings.LON_MIN <= lon <= settings.LON_MAX):
        raise ValueError(f"Longitude must be between {settings.LON_MIN} and {settings.LON_MAX} for Indian region.")

    return lat, lon


# --- Response Helpers ---

def send_json_response(
    handler: http.server.BaseHTTPRequestHandler,
    status_code: int,
    data: Any,
    cache_seconds: int = 60,
) -> None:
    """Send a JSON response with proper security & caching headers.

    Args:
        handler: HTTP request handler instance.
        status_code: HTTP status code.
        data: Data to serialize as JSON.
        cache_seconds: Cache-Control max-age (0 = no-cache).
    """
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', handler.headers.get('Origin', '*'))
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-Frame-Options', 'DENY')
    handler.send_header('X-XSS-Protection', '1; mode=block')
    handler.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
    handler.send_header('Content-Security-Policy', "default-src 'self'")
    if settings.is_production:
        handler.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    if cache_seconds > 0:
        handler.send_header('Cache-Control', f'public, max-age={cache_seconds}')
    else:
        handler.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode('utf-8'))


def send_error_response(
    handler: http.server.BaseHTTPRequestHandler,
    status_code: int,
    user_message: str,
) -> None:
    """Send a safe error response that doesn't leak internals.

    Args:
        handler: HTTP request handler instance.
        status_code: HTTP error status code.
        user_message: User-facing error message.
    """
    send_json_response(handler, status_code, {"error": user_message}, cache_seconds=0)


# --- HTTP Request Handler ---

class Handler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for the NHPC API and web dashboard."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Serve from the web subfolder
        super().__init__(*args, directory=settings.WEB_DIR, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use structured logging instead of stderr."""
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:
        """Handle GET requests for API endpoints and static files."""
        request_start = time.monotonic()
        path = self.path.split("?")[0]  # Clean path for metrics

        # --- Rate Limiting ---
        client_ip = self.address_string()
        if path.startswith('/api/') and _check_rate_limit(client_ip):
            logger.warning("Rate limit exceeded for %s", client_ip)
            send_error_response(self, 429, "Too many requests. Please slow down.")
            HTTP_ERROR_TOTAL.labels(method="GET", endpoint=path, status_code="429").inc()
            return

        # --- Path Traversal Protection ---
        if '..' in self.path:
            send_error_response(self, 400, "Invalid request path.")
            return

        # ---------------------------------------------------------------
        # 1. Liveness Probe (lightweight, no dependencies)
        # ---------------------------------------------------------------
        if self.path == '/api/liveness':
            send_json_response(self, 200, {"status": "alive"}, cache_seconds=0)
            self._record_metrics("GET", "/api/liveness", 200, request_start)
            return

        # ---------------------------------------------------------------
        # 2. Readiness Probe (checks database + data freshness)
        # ---------------------------------------------------------------
        if self.path == '/api/readiness':
            try:
                db_ok = False
                try:
                    conn = database.get_connection()
                    conn.execute("SELECT 1")
                    conn.close()
                    db_ok = True
                except Exception as e:
                    logger.warning("Readiness: database check failed: %s", e)

                forecast_fresh = False
                try:
                    run_data = database.get_latest_forecast_run()
                    if run_data and run_data.get("run"):
                        fetched_at = run_data["run"].get("fetched_at", "")
                        if fetched_at:
                            last_fetch = datetime.strptime(fetched_at, "%Y-%m-%d %H:%M:%S")
                            forecast_fresh = (datetime.now() - last_fetch) < timedelta(hours=12)
                except Exception as e:
                    logger.warning("Readiness: forecast freshness check failed: %s", e)

                ready = db_ok and forecast_fresh
                status_code = 200 if ready else 503
                data = {
                    "status": "ready" if ready else "not_ready",
                    "database": "connected" if db_ok else "disconnected",
                    "forecast_fresh": forecast_fresh,
                }
                send_json_response(self, status_code, data, cache_seconds=0)
                self._record_metrics("GET", "/api/readiness", status_code, request_start)
            except Exception as e:
                logger.error("Readiness probe failed: %s", e, exc_info=True)
                send_error_response(self, 503, "Readiness check failed.")
                self._record_metrics("GET", "/api/readiness", 503, request_start)
            return

        # ---------------------------------------------------------------
        # 3. Health Check (comprehensive)
        # ---------------------------------------------------------------
        if self.path == '/api/health':
            try:
                # Check database connectivity
                db_ok = False
                try:
                    conn = database.get_connection()
                    conn.execute("SELECT 1")
                    conn.close()
                    db_ok = True
                except Exception as e:
                    logger.warning("Health: database check failed: %s", e)

                # Check last forecast run
                last_run = None
                try:
                    run_data = database.get_latest_forecast_run()
                    if run_data and run_data.get("run"):
                        last_run = run_data["run"].get("fetched_at")
                except Exception as e:
                    logger.warning("Health: forecast run check failed: %s", e)

                # Disk usage
                disk_info: Dict[str, Any] = {}
                try:
                    usage = shutil.disk_usage(settings.DATA_DIR)
                    disk_info = {
                        "total_gb": round(usage.total / (1024 ** 3), 2),
                        "free_gb": round(usage.free / (1024 ** 3), 2),
                        "used_percent": round((usage.used / usage.total) * 100, 1),
                    }
                except Exception:
                    pass

                # Uptime
                uptime_seconds = round(time.monotonic() - _START_TIME, 1)

                health_data = {
                    "status": "healthy" if db_ok else "degraded",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
                    "database": "connected" if db_ok else "disconnected",
                    "last_forecast_run": last_run,
                    "uptime_seconds": uptime_seconds,
                    "disk": disk_info,
                    "uptime": "active"
                }

                status_code = 200 if db_ok else 503
                send_json_response(self, status_code, health_data, cache_seconds=0)
                self._record_metrics("GET", "/api/health", status_code, request_start)
            except Exception as e:
                logger.error("Health check failed: %s", e, exc_info=True)
                send_error_response(self, 503, "Service health check failed.")
                self._record_metrics("GET", "/api/health", 503, request_start)
            return

        # ---------------------------------------------------------------
        # 4. Prometheus Metrics
        # ---------------------------------------------------------------
        if self.path == '/metrics':
            try:
                output = generate_latest()
                self.send_response(200)
                self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(output)
            except Exception as e:
                logger.error("Metrics endpoint failed: %s", e)
                send_error_response(self, 500, "Metrics generation failed.")
            return

        # ---------------------------------------------------------------
        # 5. API Documentation (Redoc)
        # ---------------------------------------------------------------
        if self.path == '/api/docs':
            redoc_html = """<!DOCTYPE html>
<html><head>
<title>NHPC API Documentation</title>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
<style>body{margin:0;padding:0;}</style>
</head><body>
<redoc spec-url='/api/openapi.yaml'></redoc>
<script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body></html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(redoc_html.encode('utf-8'))
            return

        if self.path == '/api/openapi.yaml':
            spec_path = os.path.join(settings.WORKSPACE_DIR, "openapi.yaml")
            if os.path.exists(spec_path):
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-yaml')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(spec_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                send_error_response(self, 404, "OpenAPI spec not found.")
            return

        # ---------------------------------------------------------------
        # 6. On-Demand Forecast API
        # ---------------------------------------------------------------
        if self.path.startswith('/api/forecast'):
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            lat_param = query_params.get('lat')
            lon_param = query_params.get('lon')
            name_param = query_params.get('name')

            if not lat_param or not lon_param:
                send_error_response(self, 400, "Latitude and longitude parameters are required.")
                self._record_metrics("GET", "/api/forecast", 400, request_start)
                return

            try:
                # Validate coordinates
                lat, lon = validate_coordinates(lat_param[0], lon_param[0])

                # Sanitize name
                raw_name = name_param[0] if name_param else f"Coordinates ({lat:.4f}, {lon:.4f})"
                name = sanitize_name(raw_name)

                # Import libraries dynamically
                import imd_ping
                import update_forecasts

                try:
                    model_str = imd_ping.get_model()
                    start_utc = datetime.strptime(model_str, "%Y%m%d%H")
                    start_ist = start_utc + timedelta(hours=5, minutes=30)
                except Exception as e:
                    logger.warning("Error fetching model date: %s", e)
                    start_ist = datetime.now()

                logger.info("Fetching on-demand forecast for: %s (%s, %s)", name, lat, lon)
                forecast_raw = imd_ping.get_forecast(lat, lon)
                analysis = update_forecasts.analyze_forecast(forecast_raw["forecast"], start_ist)

                plant_result = {
                    "id": "custom-" + f"{lat:.4f}-{lon:.4f}".replace(".", "-").replace("-", "_"),
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "boundaries": [],
                    "alert_level": analysis["alert_level"],
                    "reasons": analysis["reasons"],
                    "summary": analysis["summary"],
                    "forecast": analysis["details"]
                }

                # Log on-demand forecast request into database
                database.record_on_demand_query(
                    query_id=plant_result["id"],
                    name=name,
                    lat=lat,
                    lon=lon,
                    alert_level=analysis["alert_level"],
                    summary=analysis["summary"],
                    forecast=analysis["details"]
                )

                send_json_response(self, 200, plant_result)
                self._record_metrics("GET", "/api/forecast", 200, request_start)

            except ValueError as e:
                # Input validation errors — safe to show to client
                send_error_response(self, 400, str(e))
                self._record_metrics("GET", "/api/forecast", 400, request_start)
            except Exception as e:
                logger.error("Error processing forecast API request: %s", e, exc_info=True)
                send_error_response(self, 500, "Failed to fetch forecast data. Please try again later.")
                self._record_metrics("GET", "/api/forecast", 500, request_start)
            return

        # ---------------------------------------------------------------
        # 7. Plants API
        # ---------------------------------------------------------------
        elif self.path == '/api/plants':
            try:
                plants = database.get_all_plants()
                send_json_response(self, 200, plants)
                self._record_metrics("GET", "/api/plants", 200, request_start)
            except Exception as e:
                logger.error("Error fetching plants: %s", e, exc_info=True)
                send_error_response(self, 500, "Failed to retrieve plant data.")
                self._record_metrics("GET", "/api/plants", 500, request_start)
            return

        # ---------------------------------------------------------------
        # 8. Alert History API
        # ---------------------------------------------------------------
        elif self.path == '/api/alerts' or self.path == '/api/history':
            try:
                history = database.get_alert_history(limit=50)
                send_json_response(self, 200, history)
                self._record_metrics("GET", "/api/alerts", 200, request_start)
            except Exception as e:
                logger.error("Error fetching alert history: %s", e, exc_info=True)
                send_error_response(self, 500, "Failed to retrieve alert history.")
                self._record_metrics("GET", "/api/alerts", 500, request_start)
            return

        # ---------------------------------------------------------------
        # 9. Latest Forecast Run API
        # ---------------------------------------------------------------
        elif self.path == '/api/latest':
            try:
                run_data = database.get_latest_forecast_run()
                send_json_response(self, 200, run_data or {})
                self._record_metrics("GET", "/api/latest", 200, request_start)
            except Exception as e:
                logger.error("Error fetching latest forecast run: %s", e, exc_info=True)
                send_error_response(self, 500, "Failed to retrieve latest forecast data.")
                self._record_metrics("GET", "/api/latest", 500, request_start)
            return

        # ---------------------------------------------------------------
        # 10. Static File Serving (web dashboard)
        # ---------------------------------------------------------------
        super().do_GET()

    def _record_metrics(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        request_start: float,
    ) -> None:
        """Record HTTP request metrics for Prometheus.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            status_code: HTTP response status code.
            request_start: Monotonic timestamp when request started.
        """
        elapsed = time.monotonic() - request_start
        status_str = str(status_code)
        HTTP_REQUEST_DURATION.labels(
            method=method, endpoint=endpoint, status_code=status_str,
        ).observe(elapsed)
        HTTP_REQUEST_TOTAL.labels(
            method=method, endpoint=endpoint, status_code=status_str,
        ).inc()
        if status_code >= 400:
            HTTP_ERROR_TOTAL.labels(
                method=method, endpoint=endpoint, status_code=status_str,
            ).inc()


# --- Server Startup ---

def run_server() -> None:
    """Start the HTTP server."""
    port = settings.APP_PORT
    # Use ThreadingTCPServer so concurrent requests don't block each other
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.ThreadingTCPServer(("", port), Handler) as httpd:
            logger.info("=" * 55)
            logger.info("  NHPC Weather Warning Dashboard — Web Server")
            logger.info("=" * 55)
            logger.info("  Serving at:  http://localhost:%d/index.html", port)
            logger.info("  Health:      http://localhost:%d/api/health", port)
            logger.info("  Liveness:    http://localhost:%d/api/liveness", port)
            logger.info("  Readiness:   http://localhost:%d/api/readiness", port)
            logger.info("  API Docs:    http://localhost:%d/api/docs", port)
            if PROMETHEUS_AVAILABLE:
                logger.info("  Metrics:     http://localhost:%d/metrics", port)
            logger.info("  Directory:   %s", settings.WEB_DIR)
            logger.info("  Environment: %s", settings.APP_ENV)
            logger.info("  Log Level:   %s", settings.LOG_LEVEL)
            logger.info("  Press Ctrl+C to stop the server.")
            logger.info("=" * 55)

            # Start rate limiter cleanup thread
            def _rate_cleanup_loop():
                while True:
                    time.sleep(120)
                    _cleanup_rate_map()

            cleanup_thread = threading.Thread(target=_rate_cleanup_loop, daemon=True)
            cleanup_thread.start()

            httpd.serve_forever()
    except Exception as e:
        logger.critical("Error starting server: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Start server in a background daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to bind port
    time.sleep(0.8)

    # Open dashboard in default web browser (only in development)
    if not settings.is_production:
        dashboard_url = f"http://localhost:{settings.APP_PORT}/index.html"
        logger.info("Launching dashboard in your default browser...")
        webbrowser.open(dashboard_url)
    else:
        logger.info("Production mode — skipping browser launch.")

    # Keep main process alive to maintain the server
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping local web server. Goodbye!")
        sys.exit(0)
