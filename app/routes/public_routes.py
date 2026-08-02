"""
Public Web Routes & AI API Endpoints Blueprint.
"""

from flask import Blueprint, jsonify, render_template, request
from app.services import database, warning_service, site_service, catchment_service
import imd_ping
import update_forecasts

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
@public_bp.route("/index.html")
def home():
    catchment_data = catchment_service.get_all_catchments_status()
    latest_run = database.get_latest_forecast_run()
    ndma_alerts = database.get_active_ndma_alerts()
    project_sites = database.get_all_plants()
    warnings = database.get_active_project_warnings()
    settings = database.get_system_settings()

    return render_template(
        "public/index.html",
        catchment_summary=catchment_data["summary"],
        catchments=catchment_data["catchments"],
        latest_run=latest_run,
        ndma_alerts=ndma_alerts,
        project_sites=project_sites,
        warnings=warnings,
        settings=settings
    )



@public_bp.route("/about")
def about():
    return render_template("public/about.html")


@public_bp.route("/api/docs")
def api_docs():
    return render_template("public/api-docs.html")


# --- AI API v1 Endpoints ---

@public_bp.route("/api/v1/ai-summary", methods=["GET"])
def ai_summary():
    """Aggregated JSON payload specifically formatted for AI Agents."""
    try:
        summary = warning_service.generate_ai_warning_summary()
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@public_bp.route("/api/v1/warnings", methods=["GET"])
def get_warnings():
    """Active integrated warnings (IMD rainfall + NDMA disaster proximity)."""
    try:
        warnings = database.get_active_project_warnings()
        return jsonify({"status": "success", "count": len(warnings), "warnings": warnings}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@public_bp.route("/api/v1/ndma-alerts", methods=["GET"])
def get_ndma_alerts():
    """Active NDMA Sachet CAP disaster alerts."""
    try:
        alerts = database.get_active_ndma_alerts()
        return jsonify({"status": "success", "count": len(alerts), "alerts": alerts}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@public_bp.route("/api/v1/forecasts", methods=["GET"])
def get_latest_forecasts():
    """Latest IMD station weather forecasts."""
    try:
        latest = database.get_latest_forecast_run()
        return jsonify(latest or {}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@public_bp.route("/api/v1/catchments", methods=["GET"])
def get_catchments():
    """NHPC catchment polygon boundaries."""
    try:
        catchments = site_service.get_catchment_data()
        return jsonify({"status": "success", "count": len(catchments), "catchments": catchments}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@public_bp.route("/api/v1/catchments/status", methods=["GET"])
def get_catchments_status():
    """Catchment-centric summary, risk levels, telemetry, and alerts for all catchments."""
    try:
        data = catchment_service.get_all_catchments_status()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@public_bp.route("/api/v1/geojson/catchments", methods=["GET"])
def get_geojson_catchments():
    """GeoJSON FeatureCollection of simplified catchment boundaries."""
    try:
        from app.services.spatial_engine import spatial_engine
        return jsonify(spatial_engine.get_geojson()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@public_bp.route("/api/v1/rivers", methods=["GET"])
def get_rivers():
    """GeoJSON FeatureCollection of major Indian river channel vectors."""
    try:
        from app.services.river_service import get_river_geojson
        return jsonify(get_river_geojson()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Legacy API Compatibility Endpoints ---

@public_bp.route("/api/forecast", methods=["GET"])
def api_forecast():
    lat_str = request.args.get("lat")
    lon_str = request.args.get("lon")
    name = request.args.get("name", "Custom Dam Site")

    if not lat_str or not lon_str:
        return jsonify({"error": "Missing lat or lon parameter"}), 400

    try:
        lat, lon = float(lat_str), float(lon_str)
        start_ist = imd_ping.get_latest_model_run_time()
        imd_data = imd_ping.fetch_imd_mausamgram(lat, lon)
        forecast_analysis = update_forecasts.analyze_forecast(name, imd_data, start_ist)
        return jsonify(forecast_analysis), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@public_bp.route("/api/plants", methods=["GET"])
def api_plants():
    return jsonify(database.get_all_plants()), 200


@public_bp.route("/api/alerts", methods=["GET"])
@public_bp.route("/api/history", methods=["GET"])
def api_alerts():
    return jsonify(database.get_alert_history(limit=50)), 200


@public_bp.route("/api/latest", methods=["GET"])
def api_latest():
    latest = database.get_latest_forecast_run()
    return jsonify(latest or {}), 200
