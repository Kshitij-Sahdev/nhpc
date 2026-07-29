import os
import json
import sqlite3
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "nhpc_weather.db")

def get_connection(db_path=DB_PATH):
    """Establishes and returns a connection to the SQLite database."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # Enable Foreign Key support
    conn.execute("PRAGMA foreign_keys = ON;")
    # Enable WAL mode for concurrent read/write access
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db(db_path=DB_PATH):
    """Initializes the database schema and indexes if they do not exist."""
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
        alert_level TEXT NOT NULL,
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
        old_status TEXT NOT NULL,
        new_status TEXT NOT NULL,
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
        alert_level TEXT NOT NULL,
        summary_json TEXT,
        forecast_json TEXT,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Indexes for high performance querying
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plant_forecasts_run ON plant_forecasts(forecast_run_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plant_forecasts_name ON plant_forecasts(plant_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_plant ON alert_history(plant_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON alert_history(triggered_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_forecast_runs_fetched ON forecast_runs(fetched_at);")

    conn.commit()
    conn.close()
    print(f"[Database] Schema initialized successfully at {db_path}")

def upsert_plants(plants, db_path=DB_PATH):
    """Inserts or updates plant metadata in the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    for p in plants:
        plant_id = str(p.get("id"))
        name = p.get("name")
        document = p.get("document", "")
        lat = p.get("lat")
        lon = p.get("lon")
        boundaries_json = json.dumps(p.get("boundaries", []))
        
        cursor.execute("""
        INSERT INTO plants (id, name, document, lat, lon, boundaries_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(name) DO UPDATE SET
            document=excluded.document,
            lat=excluded.lat,
            lon=excluded.lon,
            boundaries_json=excluded.boundaries_json,
            updated_at=CURRENT_TIMESTAMP;
        """, (plant_id, name, document, lat, lon, boundaries_json))
        
    conn.commit()
    conn.close()

def record_forecast_run(model_run_time, statistics, plants_results, db_path=DB_PATH):
    """Records a complete forecast run along with all plant forecast outputs."""
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
            cursor.execute("""
            INSERT INTO plant_forecasts (
                forecast_run_id, plant_id, plant_name, lat, lon, alert_level,
                rain_24h, rain_48h, rain_72h, max_3h_rain, max_wind, max_gust,
                reasons_json, summary_json, forecast_details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id,
                str(r.get("id")),
                r.get("name"),
                r.get("lat"),
                r.get("lon"),
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
        print(f"[Database] Forecast run #{run_id} persisted with {len(plants_results)} station forecasts.")
        return run_id
    except Exception as e:
        conn.rollback()
        print(f"[Database Error] Failed to record forecast run: {e}")
        raise
    finally:
        conn.close()

def record_alert_transition(plant_id, plant_name, old_status, new_status, reasons, db_path=DB_PATH):
    """Records an alert status transition event."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO alert_history (plant_id, plant_name, old_status, new_status, reasons_json)
    VALUES (?, ?, ?, ?, ?);
    """, (str(plant_id), plant_name, old_status, new_status, json.dumps(reasons)))
    conn.commit()
    conn.close()
    print(f"[Database] Recorded alert transition for {plant_name}: {old_status} -> {new_status}")

def record_on_demand_query(query_id, name, lat, lon, alert_level, summary, forecast, db_path=DB_PATH):
    """Records an on-demand custom coordinate forecast query."""
    conn = get_connection(db_path)
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
    conn.commit()
    conn.close()

def get_latest_forecast_run(db_path=DB_PATH):
    """Fetches the latest forecast run and its associated plant forecasts."""
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
    return {
        "run": dict(run),
        "forecasts": [dict(f) for f in forecasts]
    }

def get_alert_history(limit=50, db_path=DB_PATH):
    """Fetches recent alert transition history records."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_history ORDER BY id DESC LIMIT ?;", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_plants(db_path=DB_PATH):
    """Fetches all power plants metadata."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plants ORDER BY name ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

if __name__ == "__main__":
    init_db()

