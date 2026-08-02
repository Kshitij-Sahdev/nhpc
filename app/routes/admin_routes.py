"""
Admin Management Portal Blueprint.
"""

from flask import Blueprint, jsonify, render_template, request, redirect, url_for, session
from app.services import database, imd_service

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@admin_bp.route("/dashboard")
def dashboard():
    settings = database.get_system_settings()
    latest_run = database.get_latest_forecast_run()
    alerts = database.get_active_ndma_alerts()
    history = database.get_alert_history(limit=20)
    return render_template(
        "admin/dashboard.html",
        settings=settings,
        latest_run=latest_run,
        alerts=alerts,
        history=history
    )


@admin_bp.route("/settings", methods=["POST"])
def update_settings():
    dist_val = request.form.get("warning_distance_km", "25")
    database.update_system_setting("warning_distance_km", dist_val)
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/refresh", methods=["POST"])
def manual_refresh():
    """Manually triggers an IMD and NDMA forecast ingestion cycle."""
    try:
        imd_service.run_forecast_cycle()
        return jsonify({"status": "success", "message": "Manual forecast ingestion cycle complete"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
