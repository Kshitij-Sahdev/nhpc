from datetime import datetime, timezone
from typing import Any, Dict

from app.services.imd_service import evaluate_imd_catchment_alert, get_all_catchment_imd_warnings, get_canonical_name
from app.services.settings_service import get_settings
from app.services.site_service import get_project_sites
from app.services.warning_service import get_all_warnings


def generate_ai_summary() -> Dict[str, Any]:
    """Generates structured, highly detailed, unit-rich, comprehensive JSON data payload for AI ingestion."""
    settings = get_settings()
    projects_warnings = get_all_warnings()
    project_sites = get_project_sites()
    catchments_data = get_all_catchment_imd_warnings()

    site_map = {s["project_id"]: s for s in project_sites}

    detailed_projects = []
    projects_at_risk = 0
    total_red_projects = 0
    total_yellow_projects = 0
    total_ndma_alerts = 0

    for item in projects_warnings:
        pid = item.get("project_id")
        pname = item.get("project_name", "")
        site_info = site_map.get(pid, {})

        lat = site_info.get("lat", 0.0)
        lng = site_info.get("lng", 0.0)
        canonical_name = get_canonical_name(pname)

        # Evaluate IMD 12km catchment grid
        imd_eval = evaluate_imd_catchment_alert(pname, settings)

        ndma_alerts = item.get("warnings", [])
        ndma_count = len(ndma_alerts)
        total_ndma_alerts += ndma_count

        # Combined status evaluation
        combined_status = imd_eval["catchment_status"]
        if ndma_count > 0 and combined_status == "GREEN":
            combined_status = "YELLOW"

        if combined_status == "RED":
            total_red_projects += 1
            projects_at_risk += 1
        elif combined_status == "YELLOW":
            total_yellow_projects += 1
            projects_at_risk += 1

        project_summary = {
            "project_id": pid,
            "project_name": pname,
            "canonical_catchment_name": canonical_name,
            "coordinates": {
                "latitude": lat,
                "longitude": lng,
                "datum": "WGS84"
            },
            "status": combined_status,
            "catchment_grid_summary": {
                "catchment_name": imd_eval["catchment_name"],
                "total_12km_grid_boxes": imd_eval["grid_count"],
                "catchment_status": imd_eval["catchment_status"],
                "max_predicted_rain_3h_mm": imd_eval["max_rain_3h_mm"],
                "max_predicted_rain_24h_mm": imd_eval["max_rain_24h_mm"],
                "max_predicted_gust_m_s": imd_eval["max_gust_m_s"],
                "active_grid_warnings_count": len(imd_eval["grid_warnings"]),
                "grid_warnings": imd_eval["grid_warnings"],
            },
            "ndma_disaster_alerts": {
                "active_alerts_count": ndma_count,
                "alerts": [
                    {
                        "alert_id": w.get("alert_id"),
                        "event": w.get("event"),
                        "severity": w.get("severity"),
                        "urgency": w.get("urgency"),
                        "certainty": w.get("certainty", "Observed"),
                        "warning_type": w.get("warning_type"),
                        "headline": w.get("headline_en", ""),
                        "distance_km": round(float(w.get("distance_km", 0.0)), 2),
                        "created_at": str(w.get("created_at")),
                        "expires_at": str(w.get("expires", "")),
                    }
                    for w in ndma_alerts
                ],
            },
        }

        detailed_projects.append(project_summary)

    total_grid_boxes = sum(c["total_grids"] for c in catchments_data)
    total_grid_warnings = sum(len(c["grid_details"]) for c in catchments_data if c["status"] != "GREEN")

    overall_status = "NORMAL"
    if total_red_projects > 0:
        overall_status = "CRITICAL"
    elif total_yellow_projects > 0:
        overall_status = "WARNING"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system_metadata": {
            "application": "NHPC Catchment Alert Dashboard & IMD Mausamgram Integration",
            "version": "2.5.0",
            "telemetry_enabled": False,
            "data_sources": [
                "IMD Mausamgram 0.125° GFS/MME Grid NWP Forecasts (mausamgram.imd.gov.in)",
                "NDMA SACHET CAP Protocol Disaster Feed (sachet.ndma.gov.in)",
                "CWC Hydro-Meteorological Reservoir & River Basins Telemetry",
                "NHPC Hydro Electric Power Station Asset Geo-Registry"
            ],
            "spatial_resolution": "12km x 12km (0.125 degree grid step)",
            "unit_specifications": {
                "precipitation_3h": "mm (millimeters per 3 hours)",
                "precipitation_24h": "mm (millimeters per 24 hours)",
                "wind_gust": "m/s (meters per second)",
                "temperature": "°C (degrees Celsius)",
                "distance": "km (kilometers)",
                "coordinates": "WGS84 decimal degrees (Latitude, Longitude)"
            },
        },
        "summary": {
            "overall_system_status": overall_status,
            "total_monitored_projects": len(detailed_projects),
            "projects_at_risk_count": projects_at_risk,
            "red_alert_projects_count": total_red_projects,
            "yellow_alert_projects_count": total_yellow_projects,
            "total_active_ndma_disaster_alerts": total_ndma_alerts,
            "total_monitored_12km_grid_boxes": total_grid_boxes,
            "active_grid_warnings_count": total_grid_warnings,
        },
        "configured_thresholds": {
            "rain_3h_red_threshold_mm": float(settings.get("alert_rain_3h_red", 30.0)),
            "rain_3h_yellow_threshold_mm": float(settings.get("alert_rain_3h_yellow", 15.0)),
            "rain_24h_red_threshold_mm": float(settings.get("alert_rain_24h_red", 100.0)),
            "rain_24h_yellow_threshold_mm": float(settings.get("alert_rain_24h_yellow", 50.0)),
            "wind_gust_red_threshold_m_s": float(settings.get("alert_gust_red", 25.0)),
            "wind_gust_yellow_threshold_m_s": float(settings.get("alert_gust_yellow", 15.0)),
            "warning_proximity_distance_km": float(settings.get("warning_distance_km", 50.0)),
        },
        "all_catchments_database": catchments_data,
        "projects": detailed_projects,
    }
