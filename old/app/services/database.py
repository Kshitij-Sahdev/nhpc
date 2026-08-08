"""
NHPC Hydro Power & NDMA GeoAlert — Production Database Layer.

Provides SQLite database operations for storing power plant metadata,
forecast runs, station weather metrics, alert state transitions, NDMA alerts,
project proximity warnings, and system settings.
"""

import os
import json
import sqlite3
import contextlib
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger("nhpc.database")
DB_PATH = os.path.join("data", "nhpc_weather.db")


def get_connection(db_file: Optional[str] = None) -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database."""
    target_path = db_file or DB_PATH
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        conn = sqlite3.connect(target_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Failed to connect to database at {target_path}: {e}")
        raise


@contextlib.contextmanager
def get_db(db_file: Optional[str] = None):
    """Context manager for database connections."""
    conn = get_connection(db_file)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_file: Optional[str] = None) -> None:
    """Initializes the database schema and indexes."""
    conn = get_connection(db_file)
    cursor = conn.cursor()

    # 1. Plants table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plants (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        document TEXT,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        boundaries_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Forecast Runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecast_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_run_time TEXT NOT NULL,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_plants INTEGER NOT NULL,
        red_count INTEGER NOT NULL,
        yellow_count INTEGER NOT NULL,
        green_count INTEGER NOT NULL,
        unknown_count INTEGER NOT NULL
    );
    """)

    # 3. Plant Forecasts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plant_forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        forecast_run_id INTEGER NOT NULL,
        plant_id TEXT NOT NULL,
        plant_name TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        alert_level TEXT NOT NULL CHECK(alert_level IN ('GREEN','YELLOW','ORANGE','RED','UNKNOWN')),
        rain_24h REAL DEFAULT 0.0,
        rain_48h REAL DEFAULT 0.0,
        rain_72h REAL DEFAULT 0.0,
        max_3h_rain REAL DEFAULT 0.0,
        max_wind REAL DEFAULT 0.0,
        max_gust REAL DEFAULT 0.0,
        reasons_json TEXT,
        summary_json TEXT,
        forecast_details_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(forecast_run_id) REFERENCES forecast_runs(id) ON DELETE CASCADE
    );
    """)

    # 4. Alert History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plant_id TEXT NOT NULL,
        plant_name TEXT NOT NULL,
        old_status TEXT NOT NULL,
        new_status TEXT NOT NULL,
        reasons_json TEXT,
        triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. NDMA Alerts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ndma_alerts (
        alert_id TEXT PRIMARY KEY,
        identifier TEXT,
        event TEXT NOT NULL,
        severity TEXT NOT NULL,
        urgency TEXT,
        certainty TEXT,
        headline TEXT,
        description TEXT,
        area_description TEXT,
        effective TEXT,
        expires TEXT,
        polygons_json TEXT,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. Integrated Project & Catchment Warnings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_type TEXT NOT NULL,
        site_name TEXT NOT NULL,
        project_id TEXT,
        alert_id TEXT NOT NULL,
        event TEXT NOT NULL,
        severity TEXT NOT NULL,
        warning_type TEXT NOT NULL,
        distance_km REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 7. System Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # Seed default settings
    cursor.execute("SELECT COUNT(*) FROM settings;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);", [
            ("warning_distance_km", "25"),
            ("scheduler_minutes", "15"),
            ("severity_extreme", "#d20f39"),
            ("severity_severe", "#fe640b"),
            ("severity_moderate", "#df8e1d"),
            ("severity_minor", "#40a02b"),
        ])

    conn.commit()
    conn.close()
    logger.info(f"Database schema initialized at {db_file or DB_PATH}")


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


def upsert_plants(plants: List[Dict[str, Any]]) -> None:
    """Inserts or updates plant metadata."""
    with get_db() as conn:
        cursor = conn.cursor()
        for p in plants:
            name = p.get("name", "")
            lat = p.get("lat")
            lon = p.get("lon")
            if name in VERIFIED_COORDS:
                lat, lon = VERIFIED_COORDS[name]

            cursor.execute("""
            INSERT INTO plants (id, name, document, lat, lon, boundaries_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                lat=excluded.lat,
                lon=excluded.lon,
                boundaries_json=excluded.boundaries_json,
                updated_at=CURRENT_TIMESTAMP;
            """, (
                str(p.get("id")),
                name,
                p.get("document", ""),
                lat,
                lon,
                json.dumps(p.get("boundaries", []))
            ))


def record_forecast_run(model_run_time: str, statistics: Dict[str, int], plants_results: List[Dict[str, Any]]) -> int:
    """Records a forecast run cycle."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO forecast_runs (model_run_time, total_plants, red_count, yellow_count, green_count, unknown_count)
        VALUES (?, ?, ?, ?, ?, ?);
        """, (
            model_run_time,
            len(plants_results),
            statistics.get("red", 0),
            statistics.get("yellow", 0),
            statistics.get("green", 0),
            statistics.get("unknown", 0)
        ))

        run_id = cursor.lastrowid

        for p in plants_results:
            summary = p.get("summary", {})
            name = p.get("plant_name", "")
            lat = p.get("lat")
            lon = p.get("lon")
            if name in VERIFIED_COORDS:
                lat, lon = VERIFIED_COORDS[name]

            cursor.execute("""
            INSERT INTO plant_forecasts (
                forecast_run_id, plant_id, plant_name, lat, lon, alert_level,
                rain_24h, rain_48h, rain_72h, max_3h_rain, max_wind, max_gust,
                reasons_json, summary_json, forecast_details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id,
                str(p.get("id")),
                p.get("name"),
                lat,
                lon,
                p.get("alert_level"),
                summary.get("rain_24h", 0.0),
                summary.get("rain_48h", 0.0),
                summary.get("rain_72h", 0.0),
                summary.get("max_3h_rain", 0.0),
                summary.get("max_wind", 0.0),
                summary.get("max_gust", 0.0),
                json.dumps(p.get("reasons", [])),
                json.dumps(summary),
                json.dumps(p.get("forecast", {}))
            ))
        return run_id


def record_alert_transition(plant_id: Any, plant_name: str, old_status: str, new_status: str, reasons: List[str]) -> None:
    """Records alert status transition."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO alert_history (plant_id, plant_name, old_status, new_status, reasons_json)
        VALUES (?, ?, ?, ?, ?);
        """, (str(plant_id), plant_name, old_status, new_status, json.dumps(reasons)))


def save_ndma_alerts(alerts: List[Dict[str, Any]]) -> None:
    """Saves NDMA CAP alerts."""
    with get_db() as conn:
        cursor = conn.cursor()
        for a in alerts:
            cursor.execute("""
            INSERT INTO ndma_alerts (
                alert_id, identifier, event, severity, urgency, certainty,
                headline, description, area_description, effective, expires, polygons_json, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(alert_id) DO UPDATE SET
                event=excluded.event,
                severity=excluded.severity,
                headline=excluded.headline,
                description=excluded.description,
                area_description=excluded.area_description,
                polygons_json=excluded.polygons_json,
                fetched_at=CURRENT_TIMESTAMP;
            """, (
                a.get("alert_id"),
                a.get("identifier"),
                a.get("event"),
                a.get("severity"),
                a.get("urgency"),
                a.get("certainty"),
                a.get("headline"),
                a.get("description"),
                a.get("area_description"),
                a.get("effective"),
                a.get("expires"),
                json.dumps(a.get("polygons", []))
            ))


def get_active_ndma_alerts() -> List[Dict[str, Any]]:
    """Fetches active NDMA alerts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ndma_alerts ORDER BY fetched_at DESC LIMIT 50;")
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        item = dict(r)
        if item.get("polygons_json"):
            try:
                item["polygons"] = json.loads(item["polygons_json"])
            except Exception:
                item["polygons"] = []
        else:
            item["polygons"] = []
        result.append(item)
    return result


def save_project_warnings(warnings: List[Dict[str, Any]]) -> None:
    """Saves project and catchment proximity warnings."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_warnings;")
        for w in warnings:
            cursor.execute("""
            INSERT INTO project_warnings (
                site_type, site_name, project_id, alert_id, event, severity, warning_type, distance_km
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                w.get("site_type", "PROJECT"),
                w.get("site_name"),
                str(w.get("project_id", "")),
                w.get("alert_id"),
                w.get("event"),
                w.get("severity"),
                w.get("warning_type"),
                w.get("distance_km", 0.0)
            ))


def get_active_project_warnings() -> List[Dict[str, Any]]:
    """Fetches active project warnings."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM project_warnings ORDER BY distance_km ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_forecast_run() -> Optional[Dict[str, Any]]:
    """Fetches latest forecast run and plant forecasts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM forecast_runs ORDER BY id DESC LIMIT 1;")
    run = cursor.fetchone()
    if not run:
        conn.close()
        return None

    cursor.execute("SELECT * FROM plant_forecasts WHERE forecast_run_id = ? ORDER BY id ASC;", (run['id'],))
    forecasts = cursor.fetchall()
    conn.close()

    result_forecasts = []
    for f in forecasts:
        item = dict(f)
        if item.get("plant_name") in VERIFIED_COORDS:
            v_lat, v_lon = VERIFIED_COORDS[item["plant_name"]]
            item["lat"] = v_lat
            item["lon"] = v_lon
        try:
            item["reasons"] = json.loads(item.get("reasons_json", "[]"))
            item["summary"] = json.loads(item.get("summary_json", "{}"))
            item["forecast"] = json.loads(item.get("forecast_details_json", "{}"))
        except Exception:
            pass
        result_forecasts.append(item)

    return {
        "run": dict(run),
        "forecasts": result_forecasts
    }


def get_all_plants() -> List[Dict[str, Any]]:
    """Fetches all registered plants."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plants ORDER BY name ASC;")
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        item = dict(r)
        if item.get("boundaries_json"):
            try:
                item["boundaries"] = json.loads(item["boundaries_json"])
            except Exception:
                item["boundaries"] = []
        result.append(item)
    return result


def get_alert_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches alert transition audit history."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_history ORDER BY id DESC LIMIT ?;", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_system_settings() -> Dict[str, str]:
    """Fetches system settings dictionary."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings;")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def update_system_setting(key: str, value: str) -> None:
    """Updates a system setting key."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value;
        """, (key, str(value)))
