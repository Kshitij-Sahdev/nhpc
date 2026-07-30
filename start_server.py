import http.server
import socketserver
import webbrowser
import threading
import time
import sys
import os
import json
import html
import logging
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

import database

# --- Configuration ---
PORT = 8000
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(WORKSPACE_DIR, "web")

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("nhpc-server")

# --- Input Validation ---
# India geographic bounds (with generous margin)
LAT_MIN, LAT_MAX = 5.0, 40.0
LON_MIN, LON_MAX = 65.0, 100.0
NAME_MAX_LENGTH = 200


def sanitize_name(raw_name):
    """Sanitize user-provided name: strip HTML, limit length."""
    if not raw_name:
        return ""
    # Strip HTML tags
    cleaned = html.escape(raw_name.strip())
    # Limit length
    if len(cleaned) > NAME_MAX_LENGTH:
        cleaned = cleaned[:NAME_MAX_LENGTH]
    return cleaned


def validate_coordinates(lat_str, lon_str):
    """Validate and parse lat/lon strings. Returns (lat, lon) or raises ValueError."""
    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except (ValueError, TypeError):
        raise ValueError("Latitude and longitude must be valid numbers.")
    
    if not (LAT_MIN <= lat <= LAT_MAX):
        raise ValueError(f"Latitude must be between {LAT_MIN} and {LAT_MAX} for Indian region.")
    if not (LON_MIN <= lon <= LON_MAX):
        raise ValueError(f"Longitude must be between {LON_MIN} and {LON_MAX} for Indian region.")
    
    return lat, lon


def send_json_response(handler, status_code, data, cache_seconds=60):
    """Send a JSON response with proper security & caching headers."""
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', handler.headers.get('Origin', '*'))
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-Frame-Options', 'DENY')
    if cache_seconds > 0:
        handler.send_header('Cache-Control', f'public, max-age={cache_seconds}')
    else:
        handler.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode('utf-8'))


def send_error_response(handler, status_code, user_message):
    """Send a safe error response that doesn't leak internals."""
    send_json_response(handler, status_code, {"error": user_message})


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve from the web subfolder
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        """Override to use proper logging instead of stderr."""
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self):
        # 1. Health Check Endpoint
        if self.path == '/api/health':
            try:
                # Check database connectivity
                db_ok = False
                try:
                    conn = database.get_connection()
                    conn.execute("SELECT 1")
                    conn.close()
                    db_ok = True
                except Exception:
                    pass
                
                # Check last forecast run
                last_run = None
                try:
                    run_data = database.get_latest_forecast_run()
                    if run_data and run_data.get("run"):
                        last_run = run_data["run"].get("fetched_at")
                except Exception:
                    pass
                
                health_data = {
                    "status": "healthy" if db_ok else "degraded",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
                    "database": "connected" if db_ok else "disconnected",
                    "last_forecast_run": last_run,
                    "uptime": "active"
                }
                
                status_code = 200 if db_ok else 503
                send_json_response(self, status_code, health_data)
            except Exception as e:
                logger.error("Health check failed: %s", e)
                send_error_response(self, 503, "Service health check failed.")
            return

        # 2. API route: Custom location weather forecast
        if self.path.startswith('/api/forecast'):
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            lat_param = query_params.get('lat')
            lon_param = query_params.get('lon')
            name_param = query_params.get('name')
            
            if not lat_param or not lon_param:
                send_error_response(self, 400, "Latitude and longitude parameters are required.")
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
                
            except ValueError as e:
                # Input validation errors — safe to show to client
                send_error_response(self, 400, str(e))
            except Exception as e:
                logger.error("Error processing forecast API request: %s", e, exc_info=True)
                send_error_response(self, 500, "Failed to fetch forecast data. Please try again later.")
            return

        # 3. API route: Fetch all registered Hydro Power Plants
        elif self.path == '/api/plants':
            try:
                plants = database.get_all_plants()
                send_json_response(self, 200, plants)
            except Exception as e:
                logger.error("Error fetching plants: %s", e, exc_info=True)
                send_error_response(self, 500, "Failed to retrieve plant data.")
            return

        # 4. API route: Fetch Alert Transition History
        elif self.path == '/api/alerts' or self.path == '/api/history':
            try:
                history = database.get_alert_history(limit=50)
                send_json_response(self, 200, history)
            except Exception as e:
                logger.error("Error fetching alert history: %s", e, exc_info=True)
                send_error_response(self, 500, "Failed to retrieve alert history.")
            return

        # 5. API route: Fetch Latest DB Forecast Run
        elif self.path == '/api/latest':
            try:
                run_data = database.get_latest_forecast_run()
                send_json_response(self, 200, run_data or {})
            except Exception as e:
                logger.error("Error fetching latest forecast run: %s", e, exc_info=True)
                send_error_response(self, 500, "Failed to retrieve latest forecast data.")
            return

        super().do_GET()


def run_server():
    # Use ThreadingTCPServer so concurrent requests don't block each other
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
            logger.info("=" * 55)
            logger.info("  NHPC Weather Warning Dashboard — Web Server")
            logger.info("=" * 55)
            logger.info("  Serving at: http://localhost:%d/index.html", PORT)
            logger.info("  Health:     http://localhost:%d/api/health", PORT)
            logger.info("  Directory:  %s", WEB_DIR)
            logger.info("  Press Ctrl+C to stop the server.")
            logger.info("=" * 55)
            httpd.serve_forever()
    except Exception as e:
        logger.critical("Error starting server: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    # Start server in a background daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to bind port
    time.sleep(0.8)
    
    # Open dashboard in default web browser
    dashboard_url = f"http://localhost:{PORT}/index.html"
    logger.info("Launching dashboard in your default browser...")
    webbrowser.open(dashboard_url)
    
    # Keep main process alive to maintain the server
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping local web server. Goodbye!")
        sys.exit(0)
