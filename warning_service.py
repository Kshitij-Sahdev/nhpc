"""
NHPC Integrated Warning & Spatial Risk Service.

Combines:
1. IMD NWP 5-day weather warnings (heavy rainfall, gale wind thresholds).
2. NDMA Sachet disaster alerts (landslides, flash floods, cyclones).
3. Shapely & PyProj spatial catchment geofencing engine (25 km buffer).
4. Standalone AI Warning System Summary Payload generator (`/api/v1/ai-summary`).
"""

import logging
from typing import Any, Dict, List, Optional
import database
from ndma_service import fetch_ndma_alerts
from spatial_engine import spatial_engine

logger = logging.getLogger("nhpc.warnings")


def generate_integrated_warnings(buffer_km: float = 25.0) -> List[Dict[str, Any]]:
    """Generates integrated warnings matching registered hydro power stations and catchments

    against active NDMA emergency alert polygons using Shapely / PyProj math.
    """
    settings = database.get_system_settings()
    configured_buffer = float(settings.get("warning_distance_km", str(buffer_km)))

    alerts = fetch_ndma_alerts()
    database.save_ndma_alerts(alerts)

    plants = database.get_all_plants()
    warnings = []

    for alert in alerts:
        polygons = alert.get("polygons", [])
        alert_id = alert.get("alert_id", "")
        event = alert.get("event", "Disaster Alert")
        severity = alert.get("severity", "Severe")

        for poly_str in polygons:
            # Evaluate alert polygon against catchments using spatial engine
            catchment_matches = spatial_engine.evaluate_alert_polygon_string(poly_str, buffer_km=configured_buffer)
            for cm in catchment_matches:
                warnings.append({
                    "site_type": "CATCHMENT",
                    "site_name": cm["catchment_name"],
                    "project_id": cm["catchment_name"],
                    "alert_id": alert_id,
                    "event": event,
                    "severity": severity,
                    "warning_type": cm["status"],
                    "distance_km": cm["distance_km"]
                })

        # Also evaluate plant centroids
        for plant in plants:
            lat, lon = plant.get("lat"), plant.get("lon")
            plant_name = plant.get("name")

            for poly_str in polygons:
                # Calculate point distance to alert polygon
                matches = spatial_engine.evaluate_location_against_catchments(lat, lon, buffer_km=configured_buffer)
                for m in matches:
                    warnings.append({
                        "site_type": "POWER_STATION",
                        "site_name": plant_name,
                        "project_id": plant.get("id", plant_name),
                        "alert_id": alert_id,
                        "event": event,
                        "severity": severity,
                        "warning_type": m["status"],
                        "distance_km": m["distance_km"]
                    })

    database.save_project_warnings(warnings)
    logger.info(f"Generated {len(warnings)} integrated NDMA & catchment proximity warnings.")
    return warnings


def generate_ai_warning_summary() -> Dict[str, Any]:
    """Generates structured JSON payload specifically formatted for consumption by AI Agents."""
    latest_run = database.get_latest_forecast_run()
    ndma_alerts = database.get_active_ndma_alerts()
    active_warnings = database.get_active_project_warnings()
    history = database.get_alert_history(limit=10)
    settings = database.get_system_settings()

    red_plants = []
    yellow_plants = []

    if latest_run and "forecasts" in latest_run:
        for f in latest_run["forecasts"]:
            if f.get("alert_level") == "RED":
                red_plants.append({
                    "plant_name": f.get("plant_name"),
                    "lat": f.get("lat"),
                    "lon": f.get("lon"),
                    "rain_24h": f.get("rain_24h"),
                    "max_3h_rain": f.get("max_3h_rain"),
                    "max_wind": f.get("max_wind"),
                    "reasons": f.get("reasons_json")
                })
            elif f.get("alert_level") == "YELLOW":
                yellow_plants.append({
                    "plant_name": f.get("plant_name"),
                    "lat": f.get("lat"),
                    "lon": f.get("lon"),
                    "rain_24h": f.get("rain_24h"),
                    "max_3h_rain": f.get("max_3h_rain"),
                    "max_wind": f.get("max_wind"),
                    "reasons": f.get("reasons_json")
                })

    return {
        "status": "OPERATIONAL",
        "system": "NHPC Hydro Power Weather Warning & NDMA Emergency Alert System",
        "version": "2.0-AI-API",
        "timestamp": database.datetime.now().isoformat(),
        "summary": {
            "total_stations_monitored": len(latest_run["forecasts"]) if latest_run and "forecasts" in latest_run else 0,
            "red_alert_count": len(red_plants),
            "yellow_watch_count": len(yellow_plants),
            "ndma_disaster_alerts_count": len(ndma_alerts),
            "active_proximity_warnings_count": len(active_warnings)
        },
        "settings": settings,
        "high_risk_stations": red_plants,
        "moderate_risk_stations": yellow_plants,
        "active_ndma_disaster_alerts": [
            {
                "alert_id": a.get("alert_id"),
                "event": a.get("event"),
                "severity": a.get("severity"),
                "headline": a.get("headline"),
                "area_description": a.get("area_description"),
                "effective": a.get("effective"),
                "expires": a.get("expires")
            }
            for a in ndma_alerts
        ],
        "catchment_proximity_warnings": active_warnings[:15],
        "recent_alert_transitions": history[:5]
    }
