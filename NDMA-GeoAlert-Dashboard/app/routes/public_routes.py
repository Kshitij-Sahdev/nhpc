import os
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app.scheduler.scheduler_service import reload_scheduler
from app.services.alert_service import get_alert_by_id, get_all_alerts, get_polygon_data
from app.services.imd_service import evaluate_imd_catchment_alert, get_all_catchment_imd_warnings
from app.services.settings_service import get_settings, update_settings
from app.services.site_service import get_gnd_sites, get_project_sites
from app.services.state_service import get_all_states, update_selected_states
from app.services.warning_service import get_all_warnings, get_project_warnings

public_bp = Blueprint("public", __name__)

API_TOKEN = os.getenv("PUBLIC_API_TOKEN")


def api_token_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return (
                jsonify({"error": "Missing Authorization header"}),
                401,
            )

        try:
            scheme, token = auth_header.split(" ", 1)
        except ValueError:
            return (
                jsonify({"error": "Invalid Authorization header"}),
                401,
            )

        if scheme != "Bearer" or token != API_TOKEN:
            return (
                jsonify({"error": "Invalid token"}),
                401,
            )

        return func(*args, **kwargs)

    return wrapper


@public_bp.route("/health")
def health_check():
    return jsonify({"status": "healthy"}), 200


@public_bp.route("/")
def home():
    alerts = get_all_alerts()
    polygon_data = get_polygon_data()
    project_sites = get_project_sites()
    gnd_sites = get_gnd_sites()
    projects = get_all_warnings()
    settings = get_settings()
    states = get_all_states()

    # Retrieve all MySQL database 12km catchment forecast warnings
    imd_catchments = get_all_catchment_imd_warnings()

    # Attach IMD 12km catchment grid forecast to every project
    for project in projects:
        pname = project.get("project_name", "")
        project["imd_forecast"] = evaluate_imd_catchment_alert(pname, settings)

    return render_template(
        "public/index.html",
        alerts=alerts,
        polygon_data=polygon_data,
        project_sites=project_sites,
        gnd_sites=gnd_sites,
        projects=projects,
        states=states,
        settings=settings,
        imd_catchments=imd_catchments,
        severity_colors={
            "Extreme": settings.get("severity_extreme", "#d20f39"),
            "Moderate": settings.get("severity_moderate", "#df8e1d"),
            "Severe": settings.get("severity_severe", "#fe640b"),
            "Minor": settings.get("severity_minor", "#40a02b"),
        },
    )


@public_bp.route("/api/docs")
def api_docs():
    return render_template("public/api-docs.html")


@public_bp.route("/settings", methods=["POST"])
def update_settings_public():
    update_settings(
        {
            "scheduler_minutes": request.form.get("scheduler_minutes", "15"),
            "request_delay_seconds": request.form.get("request_delay_seconds", "1"),
            "max_retries": request.form.get("max_retries", "3"),
            "retry_delay_seconds": request.form.get("retry_delay_seconds", "5"),
            "warning_distance_km": request.form.get("warning_distance_km", "50"),
            "severity_extreme": request.form.get("severity_extreme", "#d20f39"),
            "severity_severe": request.form.get("severity_severe", "#fe640b"),
            "severity_moderate": request.form.get("severity_moderate", "#df8e1d"),
            "severity_minor": request.form.get("severity_minor", "#40a02b"),
            "alert_rain_3h_red": request.form.get("alert_rain_3h_red", "30.0"),
            "alert_rain_3h_yellow": request.form.get("alert_rain_3h_yellow", "15.0"),
            "alert_rain_24h_red": request.form.get("alert_rain_24h_red", "100.0"),
            "alert_rain_24h_yellow": request.form.get("alert_rain_24h_yellow", "50.0"),
            "alert_gust_red": request.form.get("alert_gust_red", "25.0"),
            "alert_gust_yellow": request.form.get("alert_gust_yellow", "15.0"),
        }
    )
    reload_scheduler()
    return redirect(url_for("public.home"))


@public_bp.route("/states", methods=["POST"])
def update_states_public():
    selected_states = request.form.getlist("selected_states")
    selected_states = [int(state_id) for state_id in selected_states]
    update_selected_states(selected_states)
    return redirect(url_for("public.home"))


@public_bp.route("/api/alert/<int:alert_id>")
@api_token_required
def alert_by_id(alert_id):
    alert = get_alert_by_id(alert_id)
    if not alert:
        return jsonify({"error": "Alert not found"}), 404
    return jsonify(alert)


@public_bp.route("/api/warnings")
@api_token_required
def warnings():
    return jsonify(get_all_warnings())


@public_bp.route("/api/project/<int:project_id>")
@api_token_required
def project_warnings(project_id):
    warnings = get_project_warnings(project_id)
    if not warnings["project_exists"]:
        return jsonify(warnings), 404
    return jsonify(warnings)


@public_bp.route("/api/ai-summary")
@public_bp.route("/api/v1/ai-summary")
def ai_summary():
    from app.services.ai_summary_service import generate_ai_summary
    return jsonify(generate_ai_summary())
