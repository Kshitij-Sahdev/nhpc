"""
NHPC Weather Warning System — Forecast Processor & Alert Engine.

Main orchestrator that:
1. Parses KML/SHP boundary files for power plant catchment areas
2. Fetches 120-hour IMD NWP forecasts for each station
3. Analyzes weather thresholds (rainfall, wind, temperature)
4. Detects alert state transitions (GREEN/YELLOW/RED)
5. Dispatches multi-channel notifications (Telegram, Slack, Email)
6. Persists results to the production database
7. Generates web dashboard data files

Usage:
    python update_forecasts.py
"""

import os
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

import imd_ping
import database
from log import setup_logging, get_logger
from config import get_settings
from metrics import (
    FORECAST_UPDATE_DURATION,
    FORECAST_UPDATE_TOTAL,
    FORECAST_STATION_COUNT,
    ACTIVE_ALERTS,
    ALERT_TRANSITIONS_TOTAL,
    NOTIFICATION_TOTAL,
)
from exceptions import KMLParseError

logger = get_logger("nhpc.forecasts")


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def safe_float(val: Any) -> float:
    """Convert a value to float, returning 0.0 on failure.

    Args:
        val: Any value that might be a number, NaN string, or None.

    Returns:
        Float value, or 0.0 if conversion fails.
    """
    if val is None or val == 'NaN' or val == 'nan':
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def clean_name(pm_name: Optional[str], doc_name: str) -> str:
    """Clean and normalize power plant names from KML metadata.

    Applies a mapping table for known abbreviations and appends
    disambiguation suffixes for duplicate names.

    Args:
        pm_name: Placemark name from KML (may be None or 'Unnamed').
        doc_name: Document name from KML (used as fallback).

    Returns:
        Cleaned, human-readable plant name.
    """
    raw_name = pm_name or ""
    doc_clean = doc_name.replace(".shp", "").replace(".kml", "").replace("_catchment", "").strip()

    if not raw_name or raw_name.lower() in ["unnamed", "export_output", ""]:
        raw_name = doc_clean

    mapping = {
        "TanakpurCorrected": "Tanakpur HEP",
        "Tanakpur": "Tanakpur HEP",
        "SubLowdam": "Subansiri Lower HEP",
        "Subansiri Lower": "Subansiri Lower HEP",
        "tld4": "Teesta Low Dam IV HEP",
        "Teesta Low Dam IV": "Teesta Low Dam IV HEP",
        "nbpdam": "Nimoo Bazgo HEP",
        "Nimoo Bazgo": "Nimoo Bazgo HEP",
        "ChutakPS": "Chutak Power Station",
        "Chutak": "Chutak Power Station",
        "Uri_I": "Uri-I Power Station",
        "Uri I": "Uri-I Power Station",
        "Uri_II": "Uri-II Power Station",
        "Uri II": "Uri-II Power Station",
        "Baira": "Baira Siul Power Station",
        "Salal": "Salal Power Station",
        "Chamera-I": "Chamera-I HEP",
        "Chamera-II": "Chamera-II HEP",
        "Chamera-III": "Chamera-III HEP",
        "Parbati-II": "Parbati-II HEP",
        "Parbati-III": "Parbati-III HEP",
        "Kishanganga": "Kishanganga HEP",
        "Dibang": "Dibang Multipurpose Project",
        "Ranjit Sagar": "Ranjit Sagar Hydro Project"
    }

    if raw_name in mapping:
        raw_name = mapping[raw_name]

    if doc_clean in mapping:
        doc_clean = mapping[doc_clean]

    if raw_name.lower() in ["unnamed", "export_output", ""]:
        raw_name = doc_clean

    raw_name = raw_name.replace("_", " ")
    return raw_name.strip()


def downsample_coordinates(
    coords: List[List[float]],
    max_points: int = 100,
) -> List[List[float]]:
    """Downsample polygon coordinates to reduce payload size.

    Args:
        coords: List of [lat, lon] coordinate pairs.
        max_points: Maximum number of points to keep.

    Returns:
        Downsampled coordinate list, preserving closure if original was closed.
    """
    if len(coords) <= max_points:
        return coords
    step = len(coords) // max_points
    if step < 1:
        step = 1
    downsampled = coords[::step]
    # Ensure it's closed if the original was closed
    if coords[0] == coords[-1] and downsampled[-1] != downsampled[0]:
        downsampled.append(downsampled[0])
    return downsampled


# ---------------------------------------------------------------------------
# KML Parsing
# ---------------------------------------------------------------------------

def parse_kml(kml_path: str) -> List[Dict[str, Any]]:
    """Parse KML file to extract power plant catchment boundaries and centroids.

    Args:
        kml_path: Absolute path to the KML file.

    Returns:
        List of plant dicts with id, name, document, lat, lon, boundaries.

    Raises:
        KMLParseError: If the KML file is missing or unparseable.
    """
    logger.info("Parsing KML file: %s", kml_path)

    if not os.path.exists(kml_path):
        raise KMLParseError(f"KML file not found at {kml_path}")

    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    try:
        tree = ET.parse(kml_path)
    except ET.ParseError as e:
        raise KMLParseError(f"Failed to parse KML file: {e}") from e

    root = tree.getroot()

    power_plants: List[Dict[str, Any]] = []

    documents = root.findall('.//kml:Document', ns)
    for doc in documents:
        doc_name_el = doc.find('kml:name', ns)
        doc_name = doc_name_el.text if doc_name_el is not None else "Unnamed Document"

        placemarks = doc.findall('.//kml:Placemark', ns)
        for pm in placemarks:
            name_el = pm.find('kml:name', ns)
            pm_name = name_el.text if name_el is not None else None

            # SimpleData Name check
            simple_name = None
            extended_data = pm.find('kml:ExtendedData', ns)
            if extended_data is not None:
                for sd in extended_data.findall('.//kml:SimpleData', ns):
                    if sd.attrib.get('name') == 'Name':
                        simple_name = sd.text
                        break

            resolved_name = pm_name or simple_name
            cleaned = clean_name(resolved_name, doc_name)

            # Extract coordinates
            coord_elements = pm.findall('.//kml:coordinates', ns)
            polygons: List[List[List[float]]] = []
            all_points: List[Tuple[float, float]] = []

            for elem in coord_elements:
                text = elem.text or ""
                parts = text.strip().split()
                poly_coords: List[List[float]] = []
                for p in parts:
                    if not p:
                        continue
                    c_parts = p.split(',')
                    if len(c_parts) >= 2:
                        try:
                            lon = float(c_parts[0])
                            lat = float(c_parts[1])
                            poly_coords.append([lat, lon])  # Leaflet standard is [lat, lon]
                            all_points.append((lat, lon))
                        except ValueError:
                            pass
                if poly_coords:
                    polygons.append(downsample_coordinates(poly_coords, 80))

            if not all_points:
                continue

            lats = [pt[0] for pt in all_points]
            lons = [pt[1] for pt in all_points]
            centroid_lat = sum(lats) / len(lats)
            centroid_lon = sum(lons) / len(lons)

            grid_points_set = set()
            for pt in all_points:
                import imd_ping
                grid_points_set.add((imd_ping.snap_grid(pt[0]), imd_ping.snap_grid(pt[1])))
            grid_points = list(grid_points_set)

            # Verified Real-World Hydro Plant & Dam Centroids (CEA/NHPC GPS Coordinates)
            VERIFIED_COORDS = {
                "Tanakpur HEP": (29.0725, 80.1189),
                "Subansiri Lower HEP": (27.5536, 94.2586),
                "Teesta Low Dam IV HEP": (26.9642, 88.4722),
                "Kishanganga HEP (Project)": (34.6111, 74.6733),
                "Dibang Multipurpose Project (Project)": (28.2250, 95.7720),
                "Nimoo Bazgo HEP": (34.2153, 77.1853),
                "Chamera-I HEP": (32.5966, 75.9857),
                "Ranjit Sagar Hydro Project": (32.4410, 75.7280),
                "Chamera-III HEP": (32.4598, 76.2443),
                "Chamera-II HEP": (32.4734, 76.2552),
                "Churi G&D": (32.4596, 76.3626),
                "Baloo G&D": (32.5450, 76.2108),
                "Baira Siul Power Station": (32.8063, 76.1418),
                "Bhaledh": (32.7114, 76.3283),
                "Siul": (32.8242, 75.9232),
                "Surangani G&D": (32.7255, 76.1137),
                "Chutak Power Station": (34.4591, 76.0746),
                "Dibang Catchment area": (28.5233, 95.8253),
                "Kishanganga HEP (Catchment)": (34.6107, 74.8847),
                "Uri-I Power Station": (34.1450, 74.0450),
                "Uri-II Power Station": (34.0921, 74.0318),
                "Salal Power Station": (33.1378, 74.8044),
                "Parbati-III HEP": (31.7398, 77.2576),
                "Parbati-II HEP": (31.7836, 77.3275),
                "Jiwa": (31.8653, 77.4779),
                "Jigrai": (31.9458, 77.4617),
                "Hurla": (31.8980, 77.3876)
            }

            final_lat = round(centroid_lat, 5)
            final_lon = round(centroid_lon, 5)

            if cleaned in VERIFIED_COORDS:
                final_lat, final_lon = VERIFIED_COORDS[cleaned]

            power_plants.append({
                "id": len(power_plants) + 1,
                "name": cleaned,
                "document": doc_name,
                "lat": final_lat,
                "lon": final_lon,
                "boundaries": polygons,
                "grid_points": grid_points
            })

    logger.info("Parsed %d power plant catchments from KML with verified GPS coordinates", len(power_plants))
    return power_plants


# ---------------------------------------------------------------------------
# Forecast Analysis
# ---------------------------------------------------------------------------

def analyze_forecast(
    forecast_data: Dict[str, Any],
    start_time_ist: datetime,
) -> Dict[str, Any]:
    """Analyze raw IMD forecast data and determine alert level.

    Evaluates rainfall, wind, temperature, humidity and cloud cover
    against configurable thresholds to produce GREEN/YELLOW/RED alerts.

    Args:
        forecast_data: Raw forecast dict from IMD API with keys:
                       apcp, temp, wspd, gust, rh, tcdc.
        start_time_ist: Forecast start time in IST.

    Returns:
        Dict with alert_level, reasons, summary, and details.
    """
    settings = get_settings()

    def safe_float_or_none(val: Any, treat_zero_as_none: bool = False) -> Optional[float]:
        if val is None or val == 'NaN' or val == 'nan' or str(val).strip().lower() in ['nan', 'null', 'none', '']:
            return None
        try:
            f = float(val)
            if treat_zero_as_none and f == 0.0:
                return None
            return f
        except (ValueError, TypeError):
            return None

    def fill_none_list(raw_list: List[Optional[float]], default_val: float = 0.0) -> List[float]:
        filled: List[float] = []
        first_valid: Optional[float] = None
        for val in raw_list:
            if val is not None:
                first_valid = val
                break
        if first_valid is None:
            first_valid = default_val

        last_valid: Optional[float] = None
        for val in raw_list:
            if val is None:
                filled.append(last_valid if last_valid is not None else first_valid)
            else:
                filled.append(val)
                last_valid = val
        return filled

    rain_list = fill_none_list([safe_float_or_none(r) for r in forecast_data.get("apcp", [])], 0.0)
    temp_list = fill_none_list([safe_float_or_none(t, treat_zero_as_none=True) for t in forecast_data.get("temp", [])], 15.0)
    wind_list = fill_none_list([safe_float_or_none(w) for w in forecast_data.get("wspd", [])], 0.0)
    gust_list = fill_none_list([safe_float_or_none(g) for g in forecast_data.get("gust", [])], 0.0)
    rh_list = fill_none_list([safe_float_or_none(h) for h in forecast_data.get("rh", [])], 50.0)
    cloud_list = fill_none_list([safe_float_or_none(c) for c in forecast_data.get("tcdc", [])], 0.0)

    num_steps = min(41, len(rain_list), len(temp_list), len(wind_list))

    times_ist: List[str] = []
    for i in range(num_steps):
        time_val = start_time_ist + timedelta(hours=i * 3)
        times_ist.append(time_val.strftime("%Y-%m-%d %H:%M"))

    alert_level = "GREEN"

    # 1. Check max 3h rain
    max_3h_rain = max(rain_list) if rain_list else 0.0
    max_3h_rain_idx = rain_list.index(max_3h_rain) if rain_list else 0
    max_3h_rain_time = times_ist[max_3h_rain_idx] if times_ist else ""

    # 2. Cumulative rain
    rain_24h = sum(rain_list[:8]) if len(rain_list) >= 8 else sum(rain_list)
    rain_48h = sum(rain_list[:16]) if len(rain_list) >= 16 else sum(rain_list)
    rain_72h = sum(rain_list[:24]) if len(rain_list) >= 24 else sum(rain_list)

    # 3. Wind speed and Gusts
    max_wind = max(wind_list) if wind_list else 0.0
    max_gust = max(gust_list) if gust_list else 0.0

    # Determine alert thresholds (from configuration)
    reasons: List[str] = []
    if max_3h_rain > settings.ALERT_RAIN_3H_RED:
        alert_level = "RED"
        reasons.append(f"Extreme peak rainfall of {max_3h_rain:.1f} mm in 3h expected at {max_3h_rain_time}")
    elif max_3h_rain > settings.ALERT_RAIN_3H_ORANGE and alert_level != "RED":
        alert_level = "ORANGE"
        reasons.append(f"Very heavy peak rainfall of {max_3h_rain:.1f} mm in 3h expected at {max_3h_rain_time}")
    elif max_3h_rain > settings.ALERT_RAIN_3H_YELLOW and alert_level not in ["RED", "ORANGE"]:
        alert_level = "YELLOW"
        reasons.append(f"Heavy peak rainfall of {max_3h_rain:.1f} mm in 3h expected at {max_3h_rain_time}")

    if rain_24h > settings.ALERT_RAIN_24H_RED:
        alert_level = "RED"
        reasons.append(f"Extremely heavy 24-hour cumulative rainfall of {rain_24h:.1f} mm expected")
    elif rain_24h > settings.ALERT_RAIN_24H_ORANGE and alert_level != "RED":
        alert_level = "ORANGE"
        reasons.append(f"Very heavy 24-hour cumulative rainfall of {rain_24h:.1f} mm expected")
    elif rain_24h > settings.ALERT_RAIN_24H_YELLOW and alert_level not in ["RED", "ORANGE"]:
        alert_level = "YELLOW"
        reasons.append(f"Heavy 24-hour cumulative rainfall of {rain_24h:.1f} mm expected")

    if max_gust > settings.ALERT_GUST_RED:
        alert_level = "RED"
        reasons.append(f"Extreme wind gust of {max_gust:.1f} m/s expected")
    elif max_gust > settings.ALERT_GUST_ORANGE and alert_level != "RED":
        alert_level = "ORANGE"
        reasons.append(f"Very strong wind gust of {max_gust:.1f} m/s expected")
    elif max_gust > settings.ALERT_GUST_YELLOW and alert_level not in ["RED", "ORANGE"]:
        alert_level = "YELLOW"
        reasons.append(f"Strong wind gust of {max_gust:.1f} m/s expected")

    cleaned_forecast = {
        "times": times_ist,
        "rain": [round(r, 2) for r in rain_list[:num_steps]],
        "temp": [round(t, 1) for t in temp_list[:num_steps]],
        "wind_speed": [round(w, 1) for w in wind_list[:num_steps]],
        "wind_gust": [round(g, 1) for g in gust_list[:num_steps]],
        "rh": [round(h, 1) for h in rh_list[:num_steps]],
        "cloud_cover": [round(c, 1) for c in cloud_list[:num_steps]]
    }

    return {
        "alert_level": alert_level,
        "reasons": reasons,
        "summary": {
            "max_temp": round(max(temp_list), 1) if temp_list else 0.0,
            "min_temp": round(min(temp_list), 1) if temp_list else 0.0,
            "max_3h_rain": round(max_3h_rain, 1),
            "rain_24h": round(rain_24h, 1),
            "rain_48h": round(rain_48h, 1),
            "rain_72h": round(rain_72h, 1),
            "max_wind": round(max_wind, 1),
            "max_gust": round(max_gust, 1)
        },
        "details": cleaned_forecast
    }


# ---------------------------------------------------------------------------
# Alert Notifications
# ---------------------------------------------------------------------------

def send_telegram_alert(
    plant_name: str,
    old_status: str,
    new_status: str,
    reasons: List[str],
) -> None:
    """Send alert notification via Telegram Bot API.

    Silently returns if Telegram credentials are not configured.
    """
    settings = get_settings()
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id or token.startswith("your_"):
        logger.debug("Telegram not configured — skipping alert for %s", plant_name)
        return

    emoji = "🔴" if new_status == "RED" else ("🟡" if new_status == "YELLOW" else "🟢")
    text = (
        f"{emoji} <b>NHPC WEATHER WARNING ALERT</b>\n"
        f"<b>Station:</b> {plant_name}\n"
        f"<b>Alert Level Changed:</b> {old_status} -> {new_status}\n"
        f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}\n"
    )
    if reasons:
        text += "\n<b>Active Hazard Details:</b>\n"
        for r in reasons:
            text += f"• {r}\n"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        logger.info("Telegram alert sent for %s", plant_name)
        NOTIFICATION_TOTAL.labels(channel="telegram", status="success").inc()
    except Exception as ex:
        logger.error("Telegram alert failed for %s: %s", plant_name, ex)
        NOTIFICATION_TOTAL.labels(channel="telegram", status="error").inc()


def send_slack_alert(
    plant_name: str,
    old_status: str,
    new_status: str,
    reasons: List[str],
) -> None:
    """Send alert notification via Slack Incoming Webhook.

    Silently returns if Slack webhook is not configured.
    """
    settings = get_settings()
    webhook_url = settings.SLACK_WEBHOOK_URL

    if not webhook_url or webhook_url.startswith("https://hooks.slack.com/services/T00000000"):
        logger.debug("Slack not configured — skipping alert for %s", plant_name)
        return

    color = "#ef4444" if new_status == "RED" else ("#f59e0b" if new_status == "YELLOW" else "#10b981")
    emoji = "🚨" if new_status == "RED" else ("⚠️" if new_status == "YELLOW" else "✅")

    reasons_text = "\n".join([f"• {r}" for r in reasons]) if reasons else "No warnings active."

    payload = {
        "attachments": [
            {
                "fallback": f"NHPC Weather Alert: {plant_name} is now {new_status}",
                "color": color,
                "title": f"{emoji} Weather Alert State Change: {plant_name}",
                "fields": [
                    {
                        "title": "Previous State",
                        "value": old_status,
                        "short": True
                    },
                    {
                        "title": "Current State",
                        "value": new_status,
                        "short": True
                    },
                    {
                        "title": "Alert Details",
                        "value": reasons_text,
                        "short": False
                    }
                ],
                "footer": "NHPC Weather Warning System",
                "ts": int(datetime.now().timestamp())
            }
        ]
    }
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        logger.info("Slack alert sent for %s", plant_name)
        NOTIFICATION_TOTAL.labels(channel="slack", status="success").inc()
    except Exception as ex:
        logger.error("Slack alert failed for %s: %s", plant_name, ex)
        NOTIFICATION_TOTAL.labels(channel="slack", status="error").inc()


def send_email_alert(
    plant_name: str,
    old_status: str,
    new_status: str,
    reasons: List[str],
) -> None:
    """Send alert notification via SMTP email.

    Silently returns if SMTP credentials are not configured.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    settings = get_settings()
    smtp_server = settings.SMTP_SERVER
    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER
    smtp_pass = settings.SMTP_PASSWORD
    sender = settings.SMTP_SENDER or smtp_user
    recipient = settings.ALERT_RECIPIENT_EMAIL

    if not all([smtp_server, smtp_user, smtp_pass, recipient]):
        logger.debug("Email (SMTP) not configured — skipping alert for %s", plant_name)
        return

    emoji = "🚨" if new_status == "RED" else ("⚠️" if new_status == "YELLOW" else "✅")
    subject = f"{emoji} [NHPC Weather Alert] {plant_name} Status Changed to {new_status}"

    reasons_li = "".join([f"<li>{r}</li>" for r in reasons]) if reasons else "<li>No alerts active</li>"

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 8px; border-top: 5px solid { '#ef4444' if new_status=='RED' else ('#f59e0b' if new_status=='YELLOW' else '#10b981') };">
            <h2 style="color: #333333; margin-top: 0;">NHPC Hydro Weather Warning System</h2>
            <p style="font-size: 16px; color: #555555;">
                An alert state change has been detected for the <strong>{plant_name}</strong> hydro powerplant.
            </p>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold; background-color: #f9f9f9; width: 40%;">Station Name</td>
                    <td style="padding: 10px; border: 1px solid #dddddd;">{plant_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold; background-color: #f9f9f9;">State Transition</td>
                    <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold; color: { '#ef4444' if new_status=='RED' else ('#f59e0b' if new_status=='YELLOW' else '#10b981') };">
                        {old_status} -> {new_status}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold; background-color: #f9f9f9;">Detection Time</td>
                    <td style="padding: 10px; border: 1px solid #dddddd;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}</td>
                </tr>
            </table>

            <h3 style="color: #333333;">Active Hazards / Details:</h3>
            <ul style="padding-left: 20px; line-height: 1.6; color: #555555;">
                {reasons_li}
            </ul>
            <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 30px 0;">
            <p style="font-size: 12px; color: #999999; text-align: center;">
                This is an automated notification from the NHPC Meteorological Warning Terminal.
            </p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    try:
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender, recipient, msg.as_string())
        server.close()
        logger.info("Email alert sent to %s for %s", recipient, plant_name)
        NOTIFICATION_TOTAL.labels(channel="email", status="success").inc()
    except Exception as ex:
        logger.error("Email alert failed for %s: %s", plant_name, ex)
        NOTIFICATION_TOTAL.labels(channel="email", status="error").inc()


# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------

def main() -> None:
    """Execute the complete forecast scrape, analysis, and alert cycle.

    This is the main entry point called by the scraper loop or manual execution.
    """
    run_start = time.monotonic()
    settings = get_settings()

    workspace_dir = settings.WORKSPACE_DIR
    web_dir = settings.WEB_DIR
    os.makedirs(web_dir, exist_ok=True)
    kml_path = settings.KML_PATH
    summary_txt_path = os.path.join(workspace_dir, "weather_forecast_summary.txt")
    js_data_path = os.path.join(web_dir, "forecast_data.js")
    json_data_path = os.path.join(web_dir, "forecasts.json")
    data_dir = settings.DATA_DIR
    os.makedirs(data_dir, exist_ok=True)
    state_path = os.path.join(data_dir, "alert_state.json")

    if not os.path.exists(kml_path):
        logger.error("KML file not found at %s", kml_path)
        FORECAST_UPDATE_TOTAL.labels(status="error").inc()
        return

    # Initialize production database schema
    database.init_db()

    # Load previous alert states to check transitions
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as sf:
                previous_states = json.load(sf)
        except Exception as e:
            logger.warning("Failed to load alert state file (%s). Starting fresh.", e)
            previous_states = {}
    else:
        previous_states = {}

    # 1. Parse KML & Upsert Plants in Database
    try:
        power_plants = parse_kml(kml_path)
    except KMLParseError as e:
        logger.error("KML parsing failed: %s", e)
        FORECAST_UPDATE_TOTAL.labels(status="error").inc()
        return

    database.upsert_plants(power_plants)

    # 2. Get model date
    try:
        model_str = imd_ping.get_model()
        start_utc = datetime.strptime(model_str, "%Y%m%d%H")
        start_ist = start_utc + timedelta(hours=5, minutes=30)
    except Exception as e:
        logger.warning("Failed to get or parse model date (%s). Using current time.", e)
        start_ist = datetime.now()
        model_str = start_ist.strftime("%Y%m%d00")

    logger.info("Weather forecast start time (IST): %s", start_ist.strftime("%Y-%m-%d %H:%M"))

    # 3. Fetch forecasts and analyze
    results: List[Dict[str, Any]] = []
    total = len(power_plants)

    for idx, plant in enumerate(power_plants):
        name = plant["name"]
        lat = plant["lat"]
        lon = plant["lon"]

        grid_points = plant.get("grid_points", [(lat, lon)])
        logger.info("[%d/%d] Fetching forecast for %s (across %d regions)", idx + 1, total, name, len(grid_points))
        try:
            worst_alert_level = "GREEN"
            all_reasons = []
            max_summary = {}
            first_forecast_details = None
            affected_regions = []

            import concurrent.futures
            
            def fetch_and_analyze(g_lat, g_lon):
                f_raw = imd_ping.get_forecast(g_lat, g_lon)
                return g_lat, g_lon, analyze_forecast(f_raw["forecast"], start_ist)

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_and_analyze, g_lat, g_lon) for g_lat, g_lon in grid_points]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        g_lat, g_lon, analysis = future.result()
                        
                        if first_forecast_details is None:
                            first_forecast_details = analysis["details"]

                        level = analysis["alert_level"]
                        if level == "RED":
                            worst_alert_level = "RED"
                        elif level == "YELLOW" and worst_alert_level != "RED":
                            worst_alert_level = "YELLOW"
                        elif level == "UNKNOWN" and worst_alert_level == "GREEN":
                            worst_alert_level = "UNKNOWN"
                        
                        if level in ["RED", "YELLOW"]:
                            affected_regions.append({"lat": g_lat, "lon": g_lon, "level": level})

                        for reason in analysis["reasons"]:
                            all_reasons.append(f"[Region: {g_lat}, {g_lon}] {reason}")
                        
                        for k, v in analysis["summary"].items():
                            if k not in max_summary:
                                max_summary[k] = v
                            else:
                                max_summary[k] = max(max_summary[k], v)
                    except Exception as e:
                        logger.error("Error fetching forecast for grid region: %s", e)
                        continue

            plant_result = {
                "id": plant["id"],
                "name": name,
                "lat": lat,
                "lon": lon,
                "boundaries": plant["boundaries"],
                "alert_level": worst_alert_level,
                "reasons": all_reasons,
                "summary": max_summary,
                "forecast": first_forecast_details,
                "affected_regions": affected_regions
            }
            results.append(plant_result)

            # State transition and notification checks
            old_status = previous_states.get(name, "GREEN")
            if old_status != plant_result["alert_level"]:
                logger.info(
                    "Alert state change: %s: %s -> %s",
                    name, old_status, plant_result["alert_level"],
                )
                ALERT_TRANSITIONS_TOTAL.labels(
                    old_status=old_status, new_status=plant_result["alert_level"]
                ).inc()

                # Record alert transition in Database
                database.record_alert_transition(
                    plant["id"], name, old_status,
                    plant_result["alert_level"], plant_result["reasons"],
                )
                # Send notifications
                send_telegram_alert(name, old_status, plant_result["alert_level"], plant_result["reasons"])
                send_slack_alert(name, old_status, plant_result["alert_level"], plant_result["reasons"])
                send_email_alert(name, old_status, plant_result["alert_level"], plant_result["reasons"])

            # Update state
            previous_states[name] = plant_result["alert_level"]

        except Exception as e:
            logger.error("Error fetching forecast for %s: %s", name, e, exc_info=True)
            results.append({
                "id": plant["id"],
                "name": name,
                "lat": lat,
                "lon": lon,
                "boundaries": plant["boundaries"],
                "alert_level": "UNKNOWN",
                "reasons": [f"API Error: {str(e)}"],
                "summary": {},
                "forecast": {}
            })

    # Save updated alert states
    with open(state_path, "w", encoding="utf-8") as sf:
        json.dump(previous_states, sf, indent=2)

    # 4. Generate summary report
    logger.info("Writing summary report to: %s", summary_txt_path)
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    red_count = sum(1 for r in results if r["alert_level"] == "RED")
    yellow_count = sum(1 for r in results if r["alert_level"] == "YELLOW")
    green_count = sum(1 for r in results if r["alert_level"] == "GREEN")
    unknown_count = sum(1 for r in results if r["alert_level"] == "UNKNOWN")

    # Update Prometheus gauges
    ACTIVE_ALERTS.labels(level="RED").set(red_count)
    ACTIVE_ALERTS.labels(level="YELLOW").set(yellow_count)
    ACTIVE_ALERTS.labels(level="GREEN").set(green_count)
    ACTIVE_ALERTS.labels(level="UNKNOWN").set(unknown_count)
    FORECAST_STATION_COUNT.set(total)

    with open(summary_txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("             HYDRO POWER PLANT WEATHER WARNING SYSTEM SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"Report Generated: {current_time_str}\n")
        f.write(f"IMD Model Run Base Time (IST): {start_ist.strftime('%Y-%m-%d %H:%M')}\n\n")

        f.write("SUMMARY STATISTICS:\n")
        f.write(f"  RED ALERT (High Risk)      : {red_count} plants\n")
        f.write(f"  YELLOW WATCH (Medium Risk) : {yellow_count} plants\n")
        f.write(f"  GREEN SAFE (Low Risk)      : {green_count} plants\n")
        if unknown_count > 0:
            f.write(f"  UNKNOWN (Fetch Error)      : {unknown_count} plants\n")
        f.write("\n" + "-" * 80 + "\n")

        f.write("ACTIVE WARNINGS & ALERTS:\n")
        f.write("-" * 80 + "\n")
        warning_found = False
        for r in results:
            if r["alert_level"] in ["RED", "YELLOW"]:
                warning_found = True
                f.write(f"[{r['alert_level']}] {r['name']} ({r['lat']}, {r['lon']})\n")
                for reason in r["reasons"]:
                    f.write(f"  - {reason}\n")
                f.write(f"  - 24h Rain: {r['summary'].get('rain_24h')} mm | 48h Rain: {r['summary'].get('rain_48h')} mm | Max Wind: {r['summary'].get('max_wind')} m/s\n\n")
        if not warning_found:
            f.write("  No active alerts. All systems are green/safe.\n\n")

        f.write("-" * 80 + "\n")
        f.write("ALL STATION FORECAST OVERVIEW:\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'No.':<3} | {'Power Plant Name':<28} | {'Lat':<8} | {'Lon':<8} | {'Status':<7} | {'24h Rain':<8} | {'Max Wind':<8}\n")
        f.write("-" * 80 + "\n")
        for idx, r in enumerate(results):
            rain_val = f"{r['summary'].get('rain_24h', 0.0):.1f} mm" if 'rain_24h' in r['summary'] else "N/A"
            wind_val = f"{r['summary'].get('max_wind', 0.0):.1f} m/s" if 'max_wind' in r['summary'] else "N/A"
            f.write(f"{idx+1:<3} | {r['name']:<28} | {r['lat']:<8.4f} | {r['lon']:<8.4f} | {r['alert_level']:<7} | {rain_val:<8} | {wind_val:<8}\n")
        f.write("=" * 80 + "\n")

    # 5. Generate forecasts.json and forecast_data.js
    logger.info("Writing JSON data to: %s", json_data_path)
    web_data = {
        "generated_at": current_time_str,
        "model_run": start_ist.strftime("%Y-%m-%d %H:%M"),
        "statistics": {
            "red": red_count,
            "yellow": yellow_count,
            "green": green_count,
            "unknown": unknown_count
        },
        "plants": results
    }

    # Persist forecast run and station metrics to Database
    database.record_forecast_run(
        model_run_time=start_ist.strftime("%Y-%m-%d %H:%M"),
        statistics=web_data["statistics"],
        plants_results=results
    )

    # Ingest NDMA Sachet alerts and evaluate spatial catchment geofencing warnings
    try:
        import warning_service
        warning_service.generate_integrated_warnings(buffer_km=25.0)
    except Exception as e:
        logger.warning(f"NDMA & Catchment spatial warning processing failed (non-fatal): {e}")

    with open(json_data_path, "w", encoding="utf-8") as f:
        json.dump(web_data, f, indent=2)

    logger.info("Writing JS wrapper to: %s", js_data_path)
    with open(js_data_path, "w", encoding="utf-8") as f:
        f.write("// Consolidates all weather forecasts and shapes for the UI\n")
        f.write("window.FORECAST_DATA = ")
        json.dump(web_data, f)
        f.write(";\n")

    # 6. Data cleanup (retention policy)
    try:
        database.cleanup_old_data(
            forecast_days=settings.DB_CLEANUP_DAYS,
        )
    except Exception as e:
        logger.warning("Data cleanup failed (non-fatal): %s", e)

    run_elapsed = time.monotonic() - run_start
    FORECAST_UPDATE_DURATION.observe(run_elapsed)
    FORECAST_UPDATE_TOTAL.labels(status="success").inc()
    logger.info(
        "Forecast cycle complete: %d stations processed in %.1fs "
        "(RED=%d, YELLOW=%d, GREEN=%d, UNKNOWN=%d)",
        total, run_elapsed, red_count, yellow_count, green_count, unknown_count,
    )


if __name__ == "__main__":
    setup_logging(level=get_settings().LOG_LEVEL, fmt=get_settings().LOG_FORMAT)
    main()
