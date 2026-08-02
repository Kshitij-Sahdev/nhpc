from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.auth.auth_service import validate_admin_login
from app.scheduler.scheduler_service import reload_scheduler
from app.services.ingestion_service import ingest_alerts
from app.services.log_service import get_recent_logs
from app.services.settings_service import get_settings, update_settings
from app.services.state_service import get_all_states, update_selected_states

admin_bp = Blueprint("admin", __name__)


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.admin_login"))

        return view(*args, **kwargs)

    return wrapped_view


@admin_bp.route("/admin")
@admin_required
def admin_dashboard():
    states = get_all_states()
    settings = get_settings()
    logs = get_recent_logs()
    return render_template(
        "admin/dashboard.html", states=states, settings=settings, logs=logs
    )


@admin_bp.route("/admin/states", methods=["POST"])
@admin_required
def update_states():
    selected_states = request.form.getlist("selected_states")
    selected_states = [int(state_id) for state_id in selected_states]
    update_selected_states(selected_states)
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/ingest")
@admin_required
def admin_ingest():
    ingest_alerts()
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if validate_admin_login(username, password):
            session["admin_logged_in"] = True
            return redirect(url_for("admin.admin_dashboard"))

        flash("Invalid Credentials")
    return render_template("admin/login.html")


@admin_bp.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin.admin_login"))


@admin_bp.route("/settings", methods=["POST"])
@admin_required
def update_settings_route():
    update_settings(
        {
            "scheduler_minutes": request.form["scheduler_minutes"],
            "request_delay_seconds": request.form["request_delay_seconds"],
            "max_retries": request.form["max_retries"],
            "retry_delay_seconds": request.form["retry_delay_seconds"],
            "warning_distance_km": request.form["warning_distance_km"],
            "severity_extreme": request.form["severity_extreme"],
            "severity_severe": request.form["severity_severe"],
            "severity_moderate": request.form["severity_moderate"],
            "severity_minor": request.form["severity_minor"],
        }
    )

    reload_scheduler()

    flash("Settings updated successfully.")

    return redirect(url_for("admin.admin_dashboard"))
