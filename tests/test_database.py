"""
Database layer unit tests.

Tests schema initialization, CRUD operations, data cleanup,
and error handling for the SQLite database module.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database


class TestSchemaInitialization:
    """Tests for database schema creation and idempotency."""

    def test_init_creates_all_tables(self, initialized_db):
        """All expected tables should be created by init_db()."""
        conn = database.get_connection(initialized_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected = ["plants", "forecast_runs", "plant_forecasts", "alert_history", "on_demand_forecasts"]
        for t in expected:
            assert t in tables, f"Missing table: {t}"

    def test_init_is_idempotent(self, tmp_db_path):
        """Calling init_db() twice should not raise errors."""
        database.init_db(db_path=tmp_db_path)
        database.init_db(db_path=tmp_db_path)  # Should not raise

    def test_init_creates_indexes(self, initialized_db):
        """Expected indexes should exist after init."""
        conn = database.get_connection(initialized_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_indexes = [
            "idx_plant_forecasts_run",
            "idx_plant_forecasts_name",
            "idx_alert_history_plant",
            "idx_alert_history_triggered",
            "idx_forecast_runs_fetched",
        ]
        for idx in expected_indexes:
            assert idx in indexes, f"Missing index: {idx}"


class TestPlantOperations:
    """Tests for plant upsert and retrieval."""

    def test_upsert_inserts_plants(self, initialized_db, sample_plants):
        """Upsert should insert new plants."""
        database.upsert_plants(sample_plants, db_path=initialized_db)
        plants = database.get_all_plants(db_path=initialized_db)
        assert len(plants) == 2
        names = [p["name"] for p in plants]
        assert "Test Plant Alpha" in names
        assert "Test Plant Beta" in names

    def test_upsert_updates_existing(self, initialized_db, sample_plants):
        """Upsert should update existing plants by name."""
        database.upsert_plants(sample_plants, db_path=initialized_db)

        # Modify coordinates
        updated = [sample_plants[0].copy()]
        updated[0]["lat"] = 32.0
        updated[0]["lon"] = 78.0
        database.upsert_plants(updated, db_path=initialized_db)

        plants = database.get_all_plants(db_path=initialized_db)
        alpha = [p for p in plants if p["name"] == "Test Plant Alpha"][0]
        assert alpha["lat"] == 32.0
        assert alpha["lon"] == 78.0

    def test_get_all_plants_sorted(self, initialized_db, sample_plants):
        """Plants should be returned sorted alphabetically by name."""
        database.upsert_plants(sample_plants, db_path=initialized_db)
        plants = database.get_all_plants(db_path=initialized_db)
        names = [p["name"] for p in plants]
        assert names == sorted(names)


class TestForecastRunOperations:
    """Tests for forecast run recording and retrieval."""

    def test_record_and_retrieve_forecast_run(self, initialized_db, sample_plants):
        """Should record a forecast run and retrieve it with get_latest."""
        database.upsert_plants(sample_plants, db_path=initialized_db)

        stats = {"red": 1, "yellow": 0, "green": 1, "unknown": 0}
        plants_results = [
            {
                "id": 1, "name": "Test Plant Alpha", "lat": 31.5, "lon": 77.0,
                "alert_level": "RED",
                "reasons": ["Heavy rain expected"],
                "summary": {"rain_24h": 120.0, "rain_48h": 180.0, "rain_72h": 200.0,
                            "max_3h_rain": 35.0, "max_wind": 10.0, "max_gust": 15.0},
                "forecast": {"times": [], "rain": [], "temp": []}
            },
            {
                "id": 2, "name": "Test Plant Beta", "lat": 28.0, "lon": 93.5,
                "alert_level": "GREEN",
                "reasons": [],
                "summary": {"rain_24h": 5.0, "rain_48h": 10.0, "rain_72h": 12.0,
                            "max_3h_rain": 2.0, "max_wind": 3.0, "max_gust": 5.0},
                "forecast": {"times": [], "rain": [], "temp": []}
            },
        ]

        run_id = database.record_forecast_run(
            "2026-07-30 06:00", stats, plants_results, db_path=initialized_db
        )
        assert run_id is not None
        assert run_id > 0

        latest = database.get_latest_forecast_run(db_path=initialized_db)
        assert latest is not None
        assert latest["run"]["id"] == run_id
        assert latest["run"]["red_count"] == 1
        assert len(latest["forecasts"]) == 2

    def test_latest_returns_none_when_empty(self, initialized_db):
        """get_latest_forecast_run should return None when no runs exist."""
        result = database.get_latest_forecast_run(db_path=initialized_db)
        assert result is None


class TestAlertOperations:
    """Tests for alert transition recording and history retrieval."""

    def test_record_alert_transition(self, initialized_db):
        """Should record an alert transition successfully."""
        database.record_alert_transition(
            plant_id="1",
            plant_name="Test Plant",
            old_status="GREEN",
            new_status="YELLOW",
            reasons=["Heavy rain expected"],
            db_path=initialized_db,
        )

        history = database.get_alert_history(limit=10, db_path=initialized_db)
        assert len(history) == 1
        assert history[0]["plant_name"] == "Test Plant"
        assert history[0]["old_status"] == "GREEN"
        assert history[0]["new_status"] == "YELLOW"

    def test_alert_history_respects_limit(self, initialized_db):
        """get_alert_history should respect the limit parameter."""
        for i in range(10):
            database.record_alert_transition(
                plant_id=str(i),
                plant_name=f"Plant {i}",
                old_status="GREEN",
                new_status="YELLOW",
                reasons=["Test reason"],
                db_path=initialized_db,
            )

        history = database.get_alert_history(limit=5, db_path=initialized_db)
        assert len(history) == 5

    def test_alert_history_newest_first(self, initialized_db):
        """Alert history should be returned newest first."""
        database.record_alert_transition("1", "Plant A", "GREEN", "YELLOW", [], db_path=initialized_db)
        database.record_alert_transition("2", "Plant B", "GREEN", "RED", [], db_path=initialized_db)

        history = database.get_alert_history(db_path=initialized_db)
        assert history[0]["plant_name"] == "Plant B"  # Most recent first


class TestOnDemandQueries:
    """Tests for on-demand forecast query recording."""

    def test_record_on_demand_query(self, initialized_db):
        """Should record an on-demand query without error."""
        database.record_on_demand_query(
            query_id="custom-31_2-77_1",
            name="Custom Location",
            lat=31.2,
            lon=77.1,
            alert_level="GREEN",
            summary={"rain_24h": 5.0},
            forecast={"times": [], "rain": []},
            db_path=initialized_db,
        )

        # Verify via direct query
        conn = database.get_connection(initialized_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM on_demand_forecasts;")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1


class TestDataCleanup:
    """Tests for data retention and cleanup."""

    def test_cleanup_removes_old_data(self, initialized_db):
        """Cleanup should remove data older than retention period."""
        conn = database.get_connection(initialized_db)
        cursor = conn.cursor()

        # Insert an old forecast run (100 days ago)
        cursor.execute("""
            INSERT INTO forecast_runs
            (model_run_time, fetched_at, total_plants, red_count, yellow_count, green_count, unknown_count)
            VALUES (?, datetime('now', '-100 days'), 1, 0, 0, 1, 0);
        """, ("2026-04-20 06:00",))
        old_run_id = cursor.lastrowid

        # Insert a recent forecast run
        cursor.execute("""
            INSERT INTO forecast_runs
            (model_run_time, fetched_at, total_plants, red_count, yellow_count, green_count, unknown_count)
            VALUES (?, datetime('now'), 1, 0, 0, 1, 0);
        """, ("2026-07-30 06:00",))

        conn.commit()
        conn.close()

        deleted = database.cleanup_old_data(forecast_days=90, db_path=initialized_db)
        assert deleted["forecast_runs"] == 1

        # Verify recent run still exists
        latest = database.get_latest_forecast_run(db_path=initialized_db)
        assert latest is not None


class TestDatabaseStats:
    """Tests for database statistics."""

    def test_get_stats(self, initialized_db, sample_plants):
        """get_database_stats should return file size and table counts."""
        database.upsert_plants(sample_plants, db_path=initialized_db)
        stats = database.get_database_stats(db_path=initialized_db)

        assert "file_size_mb" in stats
        assert "tables" in stats
        assert stats["tables"]["plants"] == 2


class TestContextManager:
    """Tests for the get_db context manager."""

    def test_context_manager_commits(self, initialized_db):
        """Context manager should auto-commit on success."""
        with database.get_db(initialized_db) as conn:
            conn.execute(
                "INSERT INTO plants (id, name, lat, lon) VALUES (?, ?, ?, ?);",
                ("99", "Context Test", 30.0, 76.0),
            )

        plants = database.get_all_plants(db_path=initialized_db)
        names = [p["name"] for p in plants]
        assert "Context Test" in names

    def test_context_manager_rollbacks_on_error(self, initialized_db):
        """Context manager should rollback on exception."""
        with pytest.raises(Exception):
            with database.get_db(initialized_db) as conn:
                conn.execute(
                    "INSERT INTO plants (id, name, lat, lon) VALUES (?, ?, ?, ?);",
                    ("99", "Rollback Test", 30.0, 76.0),
                )
                raise RuntimeError("Simulated failure")

        plants = database.get_all_plants(db_path=initialized_db)
        names = [p["name"] for p in plants]
        assert "Rollback Test" not in names
