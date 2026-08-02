"""
IMD Weather Ingestion & Forecast Processor Service.

Queries IMD Mausamgram 0.125° grid 5-day NWP forecasts, analyzes 120h weather trajectories,
and evaluates weather warning levels (GREEN/YELLOW/RED).
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
import imd_ping
import update_forecasts
from app.services import database
from app.services.warning_service import generate_integrated_warnings

logger = logging.getLogger("nhpc.imd_service")


def run_forecast_cycle() -> Dict[str, Any]:
    """Runs a complete IMD weather scraping and analysis cycle."""
    logger.info("Starting automated IMD weather ingestion cycle...")
    
    # Run update_forecasts main logic
    update_forecasts.main()
    
    # Generate NDMA integrated spatial warnings
    generate_integrated_warnings(buffer_km=25.0)

    latest = database.get_latest_forecast_run()
    logger.info("IMD weather ingestion cycle completed successfully.")
    return latest or {}
