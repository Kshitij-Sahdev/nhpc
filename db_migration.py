import sqlite3
import os

DB_PATH = r"c:\code\nhpc\data\nhpc_weather.db"

def migrate():
    print(f"Connecting to DB at {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("DB does not exist, nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Rename the old table
    print("Renaming plant_forecasts to plant_forecasts_old...")
    try:
        cursor.execute("ALTER TABLE plant_forecasts RENAME TO plant_forecasts_old")
    except sqlite3.OperationalError as e:
        print(f"Migration might have already run: {e}")
        return

    # Create the new table with ORANGE in the CHECK constraint
    print("Creating new plant_forecasts table...")
    cursor.execute("""
    CREATE TABLE plant_forecasts (
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
        FOREIGN KEY(forecast_run_id) REFERENCES forecast_runs(id) ON DELETE CASCADE
    )
    """)

    # Copy the data
    print("Migrating data from plant_forecasts_old to plant_forecasts...")
    cursor.execute("""
    INSERT INTO plant_forecasts (
        id, forecast_run_id, plant_id, plant_name, lat, lon, alert_level,
        rain_24h, rain_48h, rain_72h, max_3h_rain, max_wind, max_gust,
        reasons_json, summary_json, forecast_details_json
    )
    SELECT id, forecast_run_id, plant_id, plant_name, lat, lon, alert_level,
        rain_24h, rain_48h, rain_72h, max_3h_rain, max_wind, max_gust,
        reasons_json, summary_json, forecast_details_json
    FROM plant_forecasts_old
    """)

    # Drop the old table
    print("Dropping old table...")
    cursor.execute("DROP TABLE plant_forecasts_old")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
