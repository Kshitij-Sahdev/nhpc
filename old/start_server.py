"""
NHPC Hydro Power Weather Warning & NDMA Emergency Alert System — Unified Flask Server.

Serves:
1. Public GIS Dashboard (static files & Leaflet map).
2. Standalone REST API v1 for AI Warning Systems (/api/v1/ai-summary, /api/v1/warnings, /api/v1/forecasts).
3. Admin Management Portal (/admin, /admin/login, /admin/settings).
4. Health Probes & Observability (/api/health, /api/liveness, /api/readiness, /metrics).
"""

import os
import time

from flask import Flask, Blueprint, request, jsonify, render_template_string, send_from_directory

import database
import warning_service
from spatial_engine import spatial_engine
from log import setup_logging, get_logger
from config import get_settings
from metrics import generate_latest, CONTENT_TYPE_LATEST, PROMETHEUS_AVAILABLE

settings = get_settings()
setup_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT, log_file=settings.LOG_FILE)
logger = get_logger("nhpc.server")

_START_TIME = time.monotonic()

# Initialize Database on launch
database.init_db()

# Create Flask App
app = Flask(__name__, static_folder="web", static_url_path="")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "nhpc-secret-key-2026-catppuccin")


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# ---------------------------------------------------------------------------
# Blueprints Definition
# ---------------------------------------------------------------------------

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
public_bp = Blueprint("public", __name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# API v1 Endpoints (AI-First Standalone API)
# ---------------------------------------------------------------------------

@api_bp.route("/ai-summary", methods=["GET"])
def get_ai_summary():
    """Returns aggregated high-level JSON for AI Agent consumption."""
    try:
        summary = warning_service.generate_ai_warning_summary()
        return jsonify(summary), 200
    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/warnings", methods=["GET"])
def get_warnings():
    """Returns active integrated warnings (IMD rainfall + NDMA disaster proximity)."""
    try:
        warnings = database.get_active_project_warnings()
        return jsonify({"status": "success", "count": len(warnings), "warnings": warnings}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/ndma-alerts", methods=["GET"])
def get_ndma_alerts():
    """Returns active NDMA Sachet CAP disaster alerts."""
    try:
        alerts = database.get_active_ndma_alerts()
        return jsonify({"status": "success", "count": len(alerts), "alerts": alerts}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/forecasts", methods=["GET"])
def get_latest_forecasts():
    """Returns latest IMD station weather forecasts."""
    try:
        latest = database.get_latest_forecast_run()
        if not latest:
            return jsonify({"error": "No forecast data available"}), 444
        return jsonify(latest), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/catchments", methods=["GET"])
def get_catchments():
    """Returns NHPC catchment polygon boundaries."""
    try:
        catchments = spatial_engine.load_catchments()
        return jsonify({"status": "success", "count": len(catchments), "catchments": catchments}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Public Web Routes & Legacy API compatibility
# ---------------------------------------------------------------------------

@public_bp.route("/")
@public_bp.route("/index.html")
def serve_index():
    return send_from_directory("web", "index.html")


@public_bp.route("/<path:path>")
def serve_static(path):
    if os.path.exists(os.path.join("web", path)):
        return send_from_directory("web", path)
    return jsonify({"error": "File not found"}), 404


@public_bp.route("/api/forecast", methods=["GET"])
def legacy_api_forecast():
    """Legacy on-demand forecast query for custom lat/lon."""
    lat_str = request.args.get("lat")
    lon_str = request.args.get("lon")
    name = request.args.get("name", "Custom Dam Site")

    if not lat_str or not lon_str:
        return jsonify({"error": "Missing lat or lon parameter"}), 400

    try:
        lat, lon = float(lat_str), float(lon_str)
        if not (5.0 <= lat <= 40.0 and 65.0 <= lon <= 100.0):
            return jsonify({"error": "Coordinates out of bounds"}), 400
    except ValueError:
        return jsonify({"error": "Invalid coordinates"}), 400

    try:
        import imd_ping
        import update_forecasts

        start_ist = imd_ping.get_model()
        imd_data = imd_ping.fetch_imd_mausamgram(lat, lon)
        forecast_analysis = update_forecasts.analyze_forecast(imd_data, start_ist)

        query_id = f"custom-{int(lat*1000)}-{int(lon*1000)}"
        database.record_on_demand_query(
            query_id=query_id,
            name=name,
            lat=lat,
            lon=lon,
            alert_level=forecast_analysis["alert_level"],
            summary=forecast_analysis["summary"],
            forecast=forecast_analysis["forecast"]
        )

        return jsonify(forecast_analysis), 200
    except Exception as e:
        logger.error(f"Error in on-demand forecast query: {e}")
        return jsonify({"error": str(e)}), 500


@public_bp.route("/api/plants", methods=["GET"])
def legacy_api_plants():
    return jsonify(database.get_all_plants()), 200


@public_bp.route("/api/alerts", methods=["GET"])
@public_bp.route("/api/history", methods=["GET"])
def legacy_api_alerts():
    return jsonify(database.get_alert_history(limit=50)), 200


@public_bp.route("/api/latest", methods=["GET"])
def legacy_api_latest():
    latest = database.get_latest_forecast_run()
    return jsonify(latest or {}), 200


@public_bp.route("/api/health", methods=["GET"])
def health_check():
    stats = database.get_database_stats()
    uptime = time.monotonic() - _START_TIME
    return jsonify({
        "status": "healthy",
        "uptime_seconds": round(uptime, 2),
        "database": stats
    }), 200


@public_bp.route("/api/liveness", methods=["GET"])
def liveness():
    return jsonify({"status": "alive"}), 200


@public_bp.route("/api/readiness", methods=["GET"])
def readiness():
    try:
        stats = database.get_database_stats()
        return jsonify({"status": "ready", "database": stats}), 200
    except Exception:
        return jsonify({"status": "degraded"}), 503


@public_bp.route("/metrics", methods=["GET"])
def metrics():
    if PROMETHEUS_AVAILABLE:
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}
    return "Prometheus metrics disabled", 404


# ---------------------------------------------------------------------------
# Admin Portal Blueprint
# ---------------------------------------------------------------------------

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>NHPC Admin Portal - System Controls</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1e1e2e; color: #cdd6f4; margin: 0; padding: 2rem; }
        .card { background: #181825; border: 1px solid #313244; padding: 1.5rem; border-radius: 8px; max-width: 700px; margin: 0 auto; }
        h2 { color: #89b4fa; border-bottom: 1px solid #313244; padding-bottom: 0.5rem; }
        .form-group { margin-bottom: 1.2rem; }
        label { display: block; margin-bottom: 0.4rem; color: #a6adc8; }
        input[type="text"], input[type="number"] { width: 100%; padding: 0.6rem; background: #313244; border: 1px solid #45475a; color: #cdd6f4; border-radius: 4px; }
        button { background: #89b4fa; color: #11111b; border: none; padding: 0.7rem 1.4rem; font-weight: bold; border-radius: 4px; cursor: pointer; }
        button:hover { background: #b4befe; }
        .badge { background: #a6e3a1; color: #11111b; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>⚡ NHPC System Controls & Proximity Settings</h2>
        {% if msg %}
            <p style="color: #a6e3a1;">{{ msg }}</p>
        {% endif %}
        <form method="POST" action="/admin/settings">
            <div class="form-group">
                <label>Catchment & NDMA Proximity Buffer Threshold (km):</label>
                <input type="number" name="warning_distance_km" value="{{ settings.get('warning_distance_km', '25') }}" min="1" max="500">
            </div>
            <div class="form-group">
                <label>System Mode:</label>
                <span class="badge">ACTIVE (Standalone AI API First)</span>
            </div>
            <button type="submit">Save Configuration</button>
        </form>
    </div>
</body>
</html>
"""

@admin_bp.route("/")
@admin_bp.route("/settings", methods=["GET", "POST"])
def admin_settings():
    msg = None
    if request.method == "POST":
        dist_val = request.form.get("warning_distance_km", "25")
        database.update_system_setting("warning_distance_km", dist_val)
        msg = f"Successfully updated Proximity Buffer Threshold to {dist_val} km!"

    curr_settings = database.get_system_settings()
    return render_template_string(ADMIN_HTML, settings=curr_settings, msg=msg)


# Register Blueprints
app.register_blueprint(api_bp)
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp)


def main():
    port = settings.APP_PORT
    logger.info(f"Starting NHPC Unified Flask Application on http://localhost:{port}")
    logger.info(f"AI API Summary Endpoint available at http://localhost:{port}/api/v1/ai-summary")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
