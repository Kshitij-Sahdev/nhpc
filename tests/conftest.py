"""
Pytest configuration and shared fixtures for the NHPC test suite.

Provides reusable fixtures for database setup, mock IMD responses,
sample data, and test server lifecycle management.
"""

import os
import sys
import time
import socket
import threading
from datetime import datetime
from typing import Any, Dict, Generator, List

from werkzeug.serving import make_server
import pytest

# Ensure project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path(tmp_path) -> str:
    """Returns a temporary database file path.

    The directory is created by pytest's tmp_path fixture and
    automatically cleaned up after the test.
    """
    return str(tmp_path / "test_nhpc.db")


@pytest.fixture
def initialized_db(tmp_db_path) -> str:
    """Returns a temporary database path with initialized schema.

    Calls init_db() to create all tables and indexes, then yields
    the path for use in tests.
    """
    import database
    database.init_db(db_path=tmp_db_path)
    return tmp_db_path


# ---------------------------------------------------------------------------
# Sample Data Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_plants() -> List[Dict[str, Any]]:
    """Returns a list of sample power plant dicts for testing."""
    return [
        {
            "id": 1,
            "name": "Test Plant Alpha",
            "document": "test_catchment.kml",
            "lat": 31.5,
            "lon": 77.0,
            "boundaries": [[[31.4, 76.9], [31.6, 76.9], [31.6, 77.1], [31.4, 77.1], [31.4, 76.9]]]
        },
        {
            "id": 2,
            "name": "Test Plant Beta",
            "document": "test_catchment.kml",
            "lat": 28.0,
            "lon": 93.5,
            "boundaries": [[[27.9, 93.4], [28.1, 93.4], [28.1, 93.6], [27.9, 93.6], [27.9, 93.4]]]
        },
    ]


@pytest.fixture
def sample_forecast_green() -> Dict[str, Any]:
    """Returns a mock IMD forecast response that should trigger GREEN alert."""
    return {
        "apcp": [0.0, 1.0, 0.5, 0.0, 2.0, 1.0, 0.0, 0.5] * 5,  # Low rain
        "temp": [22.0, 24.0, 26.0, 28.0, 27.0, 25.0, 23.0, 22.0] * 5,
        "wspd": [2.0, 3.0, 4.0, 3.0, 2.0, 3.0, 2.0, 1.0] * 5,
        "gust": [4.0, 5.0, 6.0, 5.0, 4.0, 5.0, 4.0, 3.0] * 5,
        "rh": [60.0, 65.0, 70.0, 75.0, 70.0, 65.0, 60.0, 55.0] * 5,
        "tcdc": [20.0, 30.0, 40.0, 50.0, 40.0, 30.0, 20.0, 10.0] * 5,
    }


@pytest.fixture
def forecast_start_time() -> datetime:
    """Returns a fixed forecast start time for deterministic testing."""
    return datetime(2026, 7, 30, 5, 30)


# ---------------------------------------------------------------------------
# Server Fixtures
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    """Find a free TCP port for test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def test_server_port(initialized_db) -> Generator[int, None, None]:
    """Starts a test HTTP server on a random port and yields the port number.

    The server is started in a daemon thread and automatically
    shut down after the test completes. The database path is patched
    so the server queries use the initialized test database.
    """
    import config
    import start_server

    port = _find_free_port()

    # Clear the cached settings so it picks up the patched DB_PATH
    config.get_settings.cache_clear()

    # Patch DB_PATH via environment variable
    old_db_path = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = initialized_db

    # Reload settings with the patched DB path
    start_server.settings = config.get_settings()

    server = make_server("127.0.0.1", port, start_server.app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.3)

    yield port

    server.shutdown()

    # Restore original DB_PATH
    if old_db_path is None:
        os.environ.pop("DB_PATH", None)
    else:
        os.environ["DB_PATH"] = old_db_path
    config.get_settings.cache_clear()

