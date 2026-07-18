import os
import sys
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests

# Import weather fetching functions from imd_ping.py
# Add current directory to path just in case
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import imd_ping

# Simple custom .env parser to avoid external dependencies
def load_env(filepath=".env"):
    if os.path.exists(filepath):
        print(f"Loading configurations from {filepath}...")
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

# Load env variables at startup
load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Monkey-patch imd_ping to cache the model name and avoid 27 redundant network requests!
_cached_model = None
_original_get_model = imd_ping.get_model

def cached_get_model():
    global _cached_model
    if _cached_model is None:
        print("Fetching model date from IMD (once)...")
        _cached_model = _original_get_model()
        print(f"Model Date: {_cached_model}")
    return _cached_model

imd_ping.get_model = cached_get_model

def safe_float(val):
    if val is None or val == 'NaN' or val == 'nan':
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def clean_name(pm_name, doc_name):
    raw_name = pm_name or ""
    doc_clean = doc_name.replace(".shp", "").replace(".kml", "").replace("_catchment", "").strip()
    
    if not raw_name or raw_name.lower() in ["unnamed", "export_output", ""]:
        raw_name = doc_clean
        
    mapping = {
        "TanakpurCorrected": "Tanakpur",
        "SubLowdam": "Subansiri Lower",
        "tld4": "Teesta Low Dam IV",
        "nbpdam": "Nimoo Bazgo",
        "ChutakPS": "Chutak",
        "Uri_I": "Uri I",
        "Uri_II": "Uri II"
    }
    
    if raw_name in mapping:
        raw_name = mapping[raw_name]
        
    if doc_clean in mapping:
        doc_clean = mapping[doc_clean]
        
    if raw_name.lower() in ["unnamed", "export_output", ""]:
        raw_name = doc_clean
        
    # Append (Project) or (Catchment) to distinguish duplicates
    if doc_name.endswith('.kml') and raw_name in ["Kishanganga", "Dibang"]:
        raw_name = f"{raw_name} (Project)"
    elif doc_name.endswith('.shp') and raw_name in ["Kishanganga"]:
        raw_name = f"{raw_name} (Catchment)"
        
    raw_name = raw_name.replace("_", " ")
    return raw_name.strip()

def downsample_coordinates(coords, max_points=100):
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

def parse_kml(kml_path):
    print(f"Parsing KML file: {kml_path}")
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    tree = ET.parse(kml_path)
    root = tree.getroot()
    
    power_plants = []
    
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
            polygons = []
            all_points = []
            
            for elem in coord_elements:
                text = elem.text or ""
                parts = text.strip().split()
                poly_coords = []
                for p in parts:
                    if not p:
                        continue
                    c_parts = p.split(',')
                    if len(c_parts) >= 2:
                        try:
                            lon = float(c_parts[0])
                            lat = float(c_parts[1])
                            poly_coords.append([lat, lon]) # Leaflet standard is [lat, lon]
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
            
            power_plants.append({
                "id": len(power_plants) + 1,
                "name": cleaned,
                "document": doc_name,
                "lat": round(centroid_lat, 5),
                "lon": round(centroid_lon, 5),
                "boundaries": polygons
            })
            
    return power_plants

def analyze_forecast(forecast_data, start_time_ist):
    rain_list = [safe_float(r) for r in forecast_data.get("apcp", [])]
    temp_list = [safe_float(t) for t in forecast_data.get("temp", [])]
    wind_list = [safe_float(w) for w in forecast_data.get("wspd", [])]
    gust_list = [safe_float(g) for g in forecast_data.get("gust", [])]
    rh_list = [safe_float(h) for h in forecast_data.get("rh", [])]
    cloud_list = [safe_float(c) for c in forecast_data.get("tcdc", [])]
    
    num_steps = min(41, len(rain_list), len(temp_list), len(wind_list))
    
    times_ist = []
    for i in range(num_steps):
        time_val = start_time_ist + timedelta(hours=i*3)
        times_ist.append(time_val.strftime("%Y-%m-%d %H:%M"))
        
    warnings = []
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
    
    # Determine alert thresholds
    reasons = []
    if max_3h_rain > 30.0:
        alert_level = "RED"
        reasons.append(f"Extreme peak rainfall of {max_3h_rain:.1f} mm in 3h expected at {max_3h_rain_time}")
    elif max_3h_rain > 15.0:
        alert_level = "YELLOW"
        reasons.append(f"Heavy peak rainfall of {max_3h_rain:.1f} mm in 3h expected at {max_3h_rain_time}")
        
    if rain_24h > 100.0:
        alert_level = "RED"
        reasons.append(f"Extreme 24-hour cumulative rainfall of {rain_24h:.1f} mm expected")
    elif rain_24h > 50.0 and alert_level != "RED":
        alert_level = "YELLOW"
        reasons.append(f"Heavy 24-hour cumulative rainfall of {rain_24h:.1f} mm expected")
        
    if max_gust > 25.0:
        alert_level = "RED"
        reasons.append(f"Extreme wind gust of {max_gust:.1f} m/s expected")
    elif max_gust > 15.0 and alert_level != "RED":
        alert_level = "YELLOW"
        reasons.append(f"High wind gust of {max_gust:.1f} m/s expected")
        
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

# --- ALERTS NOTIFICATIONS ---
def send_telegram_alert(plant_name, old_status, new_status, reasons):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
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
        print(f"  [Telegram Alert Sent] for {plant_name}")
    except Exception as ex:
        print(f"  [Telegram Error] Failed to send alert: {ex}")

def send_slack_alert(plant_name, old_status, new_status, reasons):
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
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
        print(f"  [Slack Alert Sent] for {plant_name}")
    except Exception as ex:
        print(f"  [Slack Error] Failed to send alert: {ex}")

def send_email_alert(plant_name, old_status, new_status, reasons):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_SENDER", smtp_user)
    recipient = os.environ.get("ALERT_RECIPIENT_EMAIL")
    
    if not all([smtp_server, smtp_port, smtp_user, smtp_pass, recipient]):
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
        print(f"  [Email Alert Sent] to {recipient} for {plant_name}")
    except Exception as ex:
        print(f"  [Email Error] Failed to send alert: {ex}")

# --- MAIN RUNNER ---
def main():
    workspace_dir = r"d:\bht bhayankar codin\nhpc"
    web_dir = os.path.join(workspace_dir, "web")
    os.makedirs(web_dir, exist_ok=True)
    kml_path = os.path.join(workspace_dir, "Catchment_NHPC.KML")
    summary_txt_path = os.path.join(workspace_dir, "weather_forecast_summary.txt")
    js_data_path = os.path.join(web_dir, "forecast_data.js")
    json_data_path = os.path.join(web_dir, "forecasts.json")
    data_dir = os.path.join(workspace_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    state_path = os.path.join(data_dir, "alert_state.json")
    
    if not os.path.exists(kml_path):
        print(f"Error: KML file not found at {kml_path}")
        return

    # Load previous alert states to check transitions
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as sf:
                previous_states = json.load(sf)
        except Exception:
            previous_states = {}
    else:
        previous_states = {}

    # 1. Parse KML
    power_plants = parse_kml(kml_path)
    
    # 2. Get model date
    try:
        model_str = imd_ping.get_model()
        start_utc = datetime.strptime(model_str, "%Y%m%d%H")
        start_ist = start_utc + timedelta(hours=5, minutes=30)
    except Exception as e:
        print(f"Warning: Failed to get or parse model date ({e}). Using current time.")
        start_ist = datetime.now()
        model_str = start_ist.strftime("%Y%m%d00")

    print(f"Weather forecast start time (IST): {start_ist.strftime('%Y-%m-%d %H:%M')}")
    
    # 3. Fetch forecasts and analyze
    results = []
    total = len(power_plants)
    
    for idx, plant in enumerate(power_plants):
        name = plant["name"]
        lat = plant["lat"]
        lon = plant["lon"]
        
        print(f"[{idx+1}/{total}] Fetching forecast for {name} ({lat}, {lon})...")
        try:
            forecast_raw = imd_ping.get_forecast(lat, lon)
            analysis = analyze_forecast(forecast_raw["forecast"], start_ist)
            
            plant_result = {
                "id": plant["id"],
                "name": name,
                "lat": lat,
                "lon": lon,
                "boundaries": plant["boundaries"],
                "alert_level": analysis["alert_level"],
                "reasons": analysis["reasons"],
                "summary": analysis["summary"],
                "forecast": analysis["details"]
            }
            results.append(plant_result)
            
            # State transition and notification checks
            old_status = previous_states.get(name, "GREEN")
            if old_status != plant_result["alert_level"]:
                print(f"  [State Change Detected] {name}: {old_status} -> {plant_result['alert_level']}")
                # Send notifications
                send_telegram_alert(name, old_status, plant_result["alert_level"], plant_result["reasons"])
                send_slack_alert(name, old_status, plant_result["alert_level"], plant_result["reasons"])
                send_email_alert(name, old_status, plant_result["alert_level"], plant_result["reasons"])
            
            # Update state
            previous_states[name] = plant_result["alert_level"]
            
        except Exception as e:
            print(f"  Error fetching forecast for {name}: {e}")
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
    print(f"Writing summary report to: {summary_txt_path}")
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    red_count = sum(1 for r in results if r["alert_level"] == "RED")
    yellow_count = sum(1 for r in results if r["alert_level"] == "YELLOW")
    green_count = sum(1 for r in results if r["alert_level"] == "GREEN")
    unknown_count = sum(1 for r in results if r["alert_level"] == "UNKNOWN")
    
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
    print(f"Writing JSON data to: {json_data_path}")
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
    
    with open(json_data_path, "w", encoding="utf-8") as f:
        json.dump(web_data, f, indent=2)
        
    print(f"Writing JS wrapper to: {js_data_path}")
    with open(js_data_path, "w", encoding="utf-8") as f:
        f.write("// Consolidates all weather forecasts and shapes for the UI\n")
        f.write("window.FORECAST_DATA = ")
        json.dump(web_data, f)
        f.write(";\n")
        
    print("Forecast scraping, alert analysis, and file generation complete!")

if __name__ == "__main__":
    main()
