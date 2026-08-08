"""
NHPC Hydro Power Weather Warning & NDMA GeoAlert — Flask App Initializer.
"""

import os
import logging
from flask import Flask
from dotenv import load_dotenv

from app.services import database
from app.scheduler.scheduler_service import start_scheduler

logger = logging.getLogger("nhpc.app")


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "nhpc-secret-key-2026-catppuccin")

    # Initialize Database Schema
    database.init_db()

    # Register Blueprints
    from app.routes.public_routes import public_bp
    from app.routes.admin_routes import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    # Start background APScheduler (only in main worker process)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_scheduler()

    return app
