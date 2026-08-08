import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler("logs/application.log"), logging.StreamHandler()],
)

import os

from dotenv import load_dotenv
from flask import Flask

from app.scheduler.scheduler_service import start_scheduler
from app.services.init_db import initialize_database
from app.services.settings_service import get_settings


def create_app():
    loaded = load_dotenv()
    if not loaded:
        print("Warning: .env file not found")

    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "secret_dashboard_key_123")

    initialize_database()

    @app.context_processor
    def inject_settings():
        return {"settings": get_settings()}

    from app.routes.public_routes import public_bp

    app.register_blueprint(public_bp)

    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_scheduler()

    return app
