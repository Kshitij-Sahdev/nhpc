import os
from functools import wraps

from flask import Blueprint, jsonify, render_template, request

from app.services.alert_service import get_alert_by_id, get_all_alerts, get_polygon_data
from app.services.settings_service import get_settings
from app.services.site_service import get_gnd_sites, get_project_sites
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


@public_bp.route("/")
def home():
    alerts = get_all_alerts()
    polygon_data = get_polygon_data()
    project_sites = get_project_sites()
    gnd_sites = get_gnd_sites()
    projects = get_all_warnings()
    settings = get_settings()

    return render_template(
        "public/index.html",
        alerts=alerts,
        polygon_data=polygon_data,
        project_sites=project_sites,
        gnd_sites=gnd_sites,
        projects=projects,
        severity_colors={
            "Extreme": settings["severity_extreme"],
            "Moderate": settings["severity_moderate"],
            "Severe": settings["severity_severe"],
            "Minor": settings["severity_minor"],
        },
    )


@public_bp.route("/about")
def about():
    return render_template("public/about.html")


@public_bp.route("/api/docs")
def api_docs():
    return render_template("public/api-docs.html")


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
