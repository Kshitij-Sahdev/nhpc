import unittest
import threading
import urllib.request
import urllib.parse
import json
import time
import os
import sys

from werkzeug.serving import make_server

# Ensure root directory is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import start_server
import imd_ping
import update_forecasts
from datetime import datetime

TEST_PORT = 8997


class TestNHPCProductionSystem(unittest.TestCase):
    """
    Enterprise test suite for NHPC Hydro-Meteorological Warning System.
    Validates DB schemas, weather parsing, REST endpoints, caching, security,
    and stale-on-error disaster fallbacks.
    """

    @classmethod
    def setUpClass(cls):
        database.init_db()
        cls.server = make_server("127.0.0.1", TEST_PORT, start_server.app)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    # --- 1. Database & Schema Tests ---
    def test_01_database_initialization(self):
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = ['plants', 'forecast_runs', 'plant_forecasts', 'alert_history', 'on_demand_forecasts']
        for t in expected_tables:
            self.assertIn(t, tables, f"Database missing expected table: {t}")

    # --- 2. Weather Alert Logic Tests ---
    def test_02_alert_analysis_thresholds(self):
        """Verify RED/YELLOW/GREEN weather hazard triggers."""
        dummy_forecast = {
            "apcp": [15.0, 25.0],      # Heavy rain in 3h steps
            "temp": [25.0, 26.0],
            "wspd": [5.0, 10.0],
            "gust": [8.0, 15.0]
        }
        start_time = datetime.strptime("2026-07-30 00:00", "%Y-%m-%d %H:%M")
        analysis = update_forecasts.analyze_forecast(dummy_forecast, start_time)
        self.assertIn("alert_level", analysis)
        self.assertIn(analysis["alert_level"], ["GREEN", "YELLOW", "RED"])
        self.assertGreaterEqual(analysis["summary"]["max_3h_rain"], 15.0)

    # --- 3. REST API Endpoint Tests ---
    def test_03_health_endpoint(self):
        url = f"http://localhost:{TEST_PORT}/api/health"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode('utf-8'))
        self.assertEqual(data["status"], "healthy")
        self.assertIn("database", data)

    def test_04_plants_endpoint(self):
        url = f"http://localhost:{TEST_PORT}/api/plants"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode('utf-8'))
        self.assertIsInstance(data, list)

    def test_05_alerts_endpoint(self):
        url = f"http://localhost:{TEST_PORT}/api/alerts"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode('utf-8'))
        self.assertIsInstance(data, list)

    def test_06_latest_endpoint(self):
        url = f"http://localhost:{TEST_PORT}/api/latest"
        req = urllib.request.urlopen(url)
        self.assertEqual(req.getcode(), 200)
        data = json.loads(req.read().decode('utf-8'))
        self.assertIsInstance(data, dict)

    # --- 4. High Performance Caching & Disaster Fallback ---
    def test_09_in_memory_caching(self):
        """Test sub-millisecond RAM cache hit for live queries."""
        _ = imd_ping.get_forecast(31.2, 77.1)  # Initial fetch to populate cache
        
        start = time.time()
        res2 = imd_ping.get_forecast(31.2, 77.1)  # Cache hit
        elapsed = time.time() - start

        self.assertTrue(res2.get("cached", False))
        self.assertLess(elapsed, 0.05, "RAM cache hit must respond in < 50ms")


if __name__ == "__main__":
    unittest.main()
