"""
APScheduler Background Scheduler Service.

Runs periodic ingestion cycles for IMD weather forecasts and NDMA Sachet disaster alerts.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.imd_service import run_forecast_cycle

logger = logging.getLogger("nhpc.scheduler")
scheduler = BackgroundScheduler()


def start_scheduler():
    """Starts the background scheduler for automated weather and alert updates."""
    if not scheduler.running:
        scheduler.add_job(
            func=run_forecast_cycle,
            trigger="interval",
            minutes=15,
            id="imd_ndma_ingestion_job",
            replace_existing=True
        )
        scheduler.start()
        logger.info("Started APScheduler background ingestion runner (15-minute interval)")
