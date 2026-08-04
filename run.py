"""
NHPC Hydro Power Weather Warning & NDMA Emergency Alert Platform — Application Entry Point.

Usage:
    python run.py
"""

import os
from log import setup_logging, get_logger
from config import get_settings
from app import create_app

settings = get_settings()
setup_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT, log_file=settings.LOG_FILE)
logger = get_logger("nhpc.run")

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", settings.APP_PORT))
    logger.info(f"Starting NHPC & NDMA GeoAlert Flask Server on http://0.0.0.0:{port}")
    logger.info(f"AI API Summary Endpoint: http://localhost:{port}/api/v1/ai-summary")
    logger.info(f"Public Dashboard: http://localhost:{port}/")
    logger.info(f"Admin Management Portal: http://localhost:{port}/admin")
    
    app.run(host="0.0.0.0", port=port, debug=False)
