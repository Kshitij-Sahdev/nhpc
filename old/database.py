"""
NHPC Weather Warning System — Production Database Layer.

Provides SQLite database operations for storing power plant metadata,
forecast runs, station weather metrics, alert state transitions, and
on-demand custom coordinate queries.

Features:
- WAL mode for concurrent read/write access
- Foreign key enforcement
- Indexed columns for query performance
- Connection context manager to prevent leaked connections
- Data retention cleanup
- Prometheus metrics instrumentation
"""

import os
import json
import time
import sqlite3
import contextlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from log import get_logger
from config import get_settings
from metrics import DB_QUERY_DURATION, DB_ERROR_TOTAL
from exceptions import DatabaseError

logger = get_logger("nhpc.database")

# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database.

    Args:
        db_path: Optional override for the database file path.
                 Defaults to the configured DB_PATH.

    Returns:
        A configured SQLite connection with row_factory, foreign keys,
        and WAL journal mode enabled.

    Raises:
        DatabaseError: If the connection cannot be established.
    """
    if db_path is None:
        db_path = get_settings().DB_PATH

    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        # Enable Foreign Key support
        conn.execute("PRAGMA foreign_keys = ON;")
        # Enable WAL mode for concurrent read/write access
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn
    except sqlite3.Error as e:
        DB_ERROR_TOTAL.labels(operation="connect").inc()
        logger.error("Failed to connect to database at %s: %s", db_path, e)
        raise DatabaseError(f"Database connection failed: {e}") from e


@contextlib.contextmanager
def get_db(db_path: Optional[str] = None):
    """Context manager for database connections.

    Automatically commits on success, rolls back on exception,
    and always closes the connection.

    Usage:
        with get_db() as conn:
            conn.execute("SELECT ...")
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema Initialization
# ---------------------------------------------------------------------------

def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database schema and indexes if they do not exist.

    This function is idempotent — safe to call on every startup.

    Args:
        db_path: Optional override for the database file path.
    """
    start = time.monotonic()

    if db_path is None:
        db_path = get_settings().DB_PATH

    conn = get_connection(db_path)
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

    # 3. Plant Forecasts table (historical forecast records)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plant_forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        forecast_run_id INTEGER NOT NULL,
        plant_id TEXT NOT NULL,
        plant_name TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        alert_level TEXT NOT NULL CHECK(alert_level IN ('GREEN','YELLOW','RED','UNKNOWN')),
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

    # 4. Alert History table (auditing state changes GREEN -> YELLOW -> RED)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plant_id TEXT NOT NULL,
        plant_name TEXT NOT NULL,
        old_status TEXT NOT NULL CHECK(old_status IN ('GREEN','YELLOW','RED','UNKNOWN')),
        new_status TEXT NOT NULL CHECK(new_status IN ('GREEN','YELLOW','RED','UNKNOWN')),
        reasons_json TEXT,
        triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. On-Demand Custom Queries table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS on_demand_forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_id TEXT NOT NULL,
        plant_name TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        alert_level TEXT NOT NULL CHECK(alert_level IN ('GREEN','YELLOW','RED','UNKNOWN')),
        summary_json TEXT,
        forecast_json TEXT,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. NDMA Alerts table
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

    # 7. Gauge & Discharge (GND) River Monitoring Sites table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gnd_sites (
        site_id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_name TEXT NOT NULL,
        project_id TEXT,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 8. Integrated Project & Catchment Warnings table
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

    # 9. System Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # Seed default settings if empty
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

    # Indexes for high performance querying
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plant_forecasts_run ON plant_forecasts(forecast_run_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plant_forecasts_name ON plant_forecasts(plant_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plant_forecasts_run_name ON plant_forecasts(forecast_run_id, plant_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_plant ON alert_history(plant_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON alert_history(triggered_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_forecast_runs_fetched ON forecast_runs(fetched_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ndma_alerts_fetched ON ndma_alerts(fetched_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_warnings_created ON project_warnings(created_at);")

    conn.commit()
    conn.close()

    elapsed = time.monotonic() - start
    DB_QUERY_DURATION.labels(operation="init_db").observe(elapsed)
    logger.info("Database schema initialized at %s (%.1fms)", db_path, elapsed * 1000)


# ---------------------------------------------------------------------------
# Plant Operations
# ---------------------------------------------------------------------------

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


def upsert_plants(plants: List[Dict[str, Any]], db_path: Optional[str] = None) -> None:
    """Inserts or updates plant metadata in the database.

    Args:
        plants: List of plant dictionaries with id, name, document, lat, lon, boundaries.
        db_path: Optional database path override.
    """
    start = time.monotonic()

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        for p in plants:
            plant_id = str(p.get("id"))
            name = p.get("name")
            document = p.get("document", "")
            lat = p.get("lat")
            lon = p.get("lon")
            if name in VERIFIED_COORDS:
                lat, lon = VERIFIED_COORDS[name]
            boundaries_json = json.dumps(p.get("boundaries", []))

            cursor.execute("""
            INSERT INTO plants (id, name, document, lat, lon, boundaries_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                document=excluded.document,
                lat=excluded.lat,
                lon=excluded.lon,
                boundaries_json=excluded.boundaries_json,
                updated_at=CURRENT_TIMESTAMP;
            """, (plant_id, name, document, lat, lon, boundaries_json))

    elapsed = time.monotonic() - start
    DB_QUERY_DURATION.labels(operation="upsert_plants").observe(elapsed)


# ---------------------------------------------------------------------------
# Forecast Run Operations
# ---------------------------------------------------------------------------

def record_forecast_run(
    model_run_time: str,
    statistics: Dict[str, int],
    plants_results: List[Dict[str, Any]],
    db_path: Optional[str] = None,
) -> int:
    """Records a complete forecast run along with all plant forecast outputs.

    Args:
        model_run_time: IMD model run timestamp string.
        statistics: Dict with red/yellow/green/unknown counts.
        plants_results: List of plant forecast result dicts.
        db_path: Optional database path override.

    Returns:
        The ID of the created forecast run.

    Raises:
        DatabaseError: If the transaction fails.
    """
    start = time.monotonic()

    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Insert Forecast Run
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

        # Insert Plant Forecasts
        for r in plants_results:
            summary = r.get("summary", {})
            name = r.get("name", "")
            lat = r.get("lat")
            lon = r.get("lon")
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
                str(r.get("id")),
                name,
                lat,
                lon,
                r.get("alert_level"),
                summary.get("rain_24h", 0.0),
                summary.get("rain_48h", 0.0),
                summary.get("rain_72h", 0.0),
                summary.get("max_3h_rain", 0.0),
                summary.get("max_wind", 0.0),
                summary.get("max_gust", 0.0),
                json.dumps(r.get("reasons", [])),
                json.dumps(summary),
                json.dumps(r.get("forecast", {}))
            ))

        conn.commit()

        elapsed = time.monotonic() - start
        DB_QUERY_DURATION.labels(operation="record_forecast_run").observe(elapsed)
        logger.info(
            "Forecast run #%d persisted with %d station forecasts (%.1fms)",
            run_id, len(plants_results), elapsed * 1000,
        )
        return run_id

    except Exception as e:
        conn.rollback()
        DB_ERROR_TOTAL.labels(operation="record_forecast_run").inc()
        logger.error("Failed to record forecast run: %s", e, exc_info=True)
        raise DatabaseError(f"Failed to record forecast run: {e}") from e
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Alert Operations
# ---------------------------------------------------------------------------

def record_alert_transition(
    plant_id: Any,
    plant_name: str,
    old_status: str,
    new_status: str,
    reasons: List[str],
    db_path: Optional[str] = None,
) -> None:
    """Records an alert status transition event.

    Args:
        plant_id: Identifier for the plant.
        plant_name: Display name of the plant.
        old_status: Previous alert level.
        new_status: New alert level.
        reasons: List of hazard reason strings.
        db_path: Optional database path override.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO alert_history (plant_id, plant_name, old_status, new_status, reasons_json)
        VALUES (?, ?, ?, ?, ?);
        """, (str(plant_id), plant_name, old_status, new_status, json.dumps(reasons)))

    logger.info("Recorded alert transition for %s: %s -> %s", plant_name, old_status, new_status)


def record_on_demand_query(
    query_id: str,
    name: str,
    lat: float,
    lon: float,
    alert_level: str,
    summary: Dict[str, Any],
    forecast: Dict[str, Any],
    db_path: Optional[str] = None,
) -> None:
    """Records an on-demand custom coordinate forecast query.

    Args:
        query_id: Unique identifier for the query.
        name: Display name for the queried location.
        lat: Latitude of the queried location.
        lon: Longitude of the queried location.
        alert_level: Computed alert level.
        summary: Forecast summary dict.
        forecast: Detailed forecast data dict.
        db_path: Optional database path override.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO on_demand_forecasts (query_id, plant_name, lat, lon, alert_level, summary_json, forecast_json)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            query_id,
            name,
            lat,
            lon,
            alert_level,
            json.dumps(summary),
            json.dumps(forecast)
        ))


# ---------------------------------------------------------------------------
# Query Operations
# ---------------------------------------------------------------------------

def get_latest_forecast_run(db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetches the latest forecast run and its associated plant forecasts.

    Returns:
        Dict with 'run' and 'forecasts' keys, or None if no runs exist.
    """
    start = time.monotonic()

    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM forecast_runs ORDER BY id DESC LIMIT 1;")
    run = cursor.fetchone()
    if not run:
        conn.close()
        return None

    cursor.execute("SELECT * FROM plant_forecasts WHERE forecast_run_id = ? ORDER BY id ASC;", (run['id'],))
    forecasts = cursor.fetchall()

    conn.close()

    elapsed = time.monotonic() - start
    DB_QUERY_DURATION.labels(operation="get_latest_forecast_run").observe(elapsed)

    res_forecasts = []
    for f in forecasts:
        item = dict(f)
        if item.get("plant_name") in VERIFIED_COORDS:
            v_lat, v_lon = VERIFIED_COORDS[item["plant_name"]]
            item["lat"] = v_lat
            item["lon"] = v_lon
        res_forecasts.append(item)

    return {
        "run": dict(run),
        "forecasts": res_forecasts
    }


def get_alert_history(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches recent alert transition history records.

    Args:
        limit: Maximum number of records to return.

    Returns:
        List of alert transition dicts, newest first.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_history ORDER BY id DESC LIMIT ?;", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_plants(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches all power plants metadata.

    Returns:
        List of plant dicts, sorted by name.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plants ORDER BY name ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Data Retention & Cleanup
# ---------------------------------------------------------------------------

def cleanup_old_data(
    forecast_days: int = 90,
    on_demand_days: int = 30,
    db_path: Optional[str] = None,
) -> Dict[str, int]:
    """Removes old forecast and on-demand data beyond retention period.

    Args:
        forecast_days: Delete forecast runs older than this many days.
        on_demand_days: Delete on-demand queries older than this many days.
        db_path: Optional database path override.

    Returns:
        Dict with counts of deleted rows per table.
    """
    start = time.monotonic()
    deleted = {"forecast_runs": 0, "plant_forecasts": 0, "on_demand_forecasts": 0}

    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # Delete old forecast runs (cascades to plant_forecasts via FK)
        forecast_cutoff = (datetime.now() - timedelta(days=forecast_days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT COUNT(*) FROM forecast_runs WHERE fetched_at < ?;", (forecast_cutoff,))
        deleted["forecast_runs"] = cursor.fetchone()[0]

        if deleted["forecast_runs"] > 0:
            # Count cascaded plant_forecasts before deletion
            cursor.execute("""
                SELECT COUNT(*) FROM plant_forecasts
                WHERE forecast_run_id IN (
                    SELECT id FROM forecast_runs WHERE fetched_at < ?
                );
            """, (forecast_cutoff,))
            deleted["plant_forecasts"] = cursor.fetchone()[0]

            cursor.execute("DELETE FROM forecast_runs WHERE fetched_at < ?;", (forecast_cutoff,))

        # Delete old on-demand forecasts
        od_cutoff = (datetime.now() - timedelta(days=on_demand_days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT COUNT(*) FROM on_demand_forecasts WHERE requested_at < ?;", (od_cutoff,))
        deleted["on_demand_forecasts"] = cursor.fetchone()[0]

        if deleted["on_demand_forecasts"] > 0:
            cursor.execute("DELETE FROM on_demand_forecasts WHERE requested_at < ?;", (od_cutoff,))

    total_deleted = sum(deleted.values())
    if total_deleted > 0:
        logger.info(
            "Data cleanup completed: %d forecast runs, %d plant forecasts, %d on-demand queries removed",
            deleted["forecast_runs"],
            deleted["plant_forecasts"],
            deleted["on_demand_forecasts"],
        )

    elapsed = time.monotonic() - start
    DB_QUERY_DURATION.labels(operation="cleanup_old_data").observe(elapsed)

    return deleted


def get_database_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Returns database statistics for health checks.

    Returns:
        Dict with table row counts and database file size.
    """
    if db_path is None:
        db_path = get_settings().DB_PATH

    stats: Dict[str, Any] = {"file_size_mb": 0.0, "tables": {}}

    if os.path.exists(db_path):
        stats["file_size_mb"] = round(os.path.getsize(db_path) / (1024 * 1024), 2)

    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        for table in ["plants", "forecast_runs", "plant_forecasts", "alert_history", "on_demand_forecasts"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")  # noqa: S608 — table name is hardcoded, not user input
            stats["tables"][table] = cursor.fetchone()[0]
        conn.close()
    except Exception as e:
        logger.warning("Failed to gather database stats: %s", e)

    return stats


# ---------------------------------------------------------------------------
# NDMA Alerts & Settings Operations
# ---------------------------------------------------------------------------

def save_ndma_alerts(alerts: List[Dict[str, Any]], db_path: Optional[str] = None) -> None:
    """Saves or updates NDMA CAP alerts in the database."""
    with get_db(db_path) as conn:
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


def get_active_ndma_alerts(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches active NDMA alerts."""
    conn = get_connection(db_path)
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


def save_project_warnings(warnings: List[Dict[str, Any]], db_path: Optional[str] = None) -> None:
    """Saves generated proximity/catchment warnings."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_warnings;") # Clear old active warnings
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


def get_active_project_warnings(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches active project & catchment warnings."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM project_warnings ORDER BY distance_km ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_system_settings(db_path: Optional[str] = None) -> Dict[str, str]:
    """Fetches all system settings as key-value dictionary."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings;")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def update_system_setting(key: str, value: str, db_path: Optional[str] = None) -> None:
    """Updates a system setting key."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value;
        """, (key, str(value)))


# ---------------------------------------------------------------------------
# Standalone Execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from log import setup_logging
    setup_logging()
    init_db()

