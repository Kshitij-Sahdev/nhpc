"""
API endpoint integration tests.

Tests HTTP endpoints via actual network requests to a test server.
"""

import json
import os
import sys
import urllib.request
import urllib.error

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_json(url):
    """Helper to make a GET request and parse JSON response."""
    req = urllib.request.urlopen(url, timeout=10)
    return req.getcode(), json.loads(req.read().decode("utf-8")), dict(req.headers)


@pytest.mark.integration
class TestHealthEndpoints:
    """Tests for health check, liveness, and readiness probes."""

    def test_liveness_returns_200(self, test_server_port):
        """GET /api/liveness should return 200 with status=alive."""
        code, data, _ = _get_json(f"http://localhost:{test_server_port}/api/liveness")
        assert code == 200
        assert data["status"] == "alive"

    def test_health_returns_200(self, test_server_port):
        """GET /api/health should return 200 with status field."""
        code, data, _ = _get_json(f"http://localhost:{test_server_port}/api/health")
        assert code == 200
        assert "status" in data
        assert "database" in data
        assert "uptime_seconds" in data

    def test_health_includes_disk_info(self, test_server_port):
        """Health endpoint should include disk usage data."""
        _, data, _ = _get_json(f"http://localhost:{test_server_port}/api/health")
        assert "disk" in data


@pytest.mark.integration
class TestDataEndpoints:
    """Tests for data retrieval endpoints."""

    def test_plants_returns_list(self, test_server_port):
        """GET /api/plants should return a list."""
        code, data, _ = _get_json(f"http://localhost:{test_server_port}/api/plants")
        assert code == 200
        assert isinstance(data, list)

    def test_alerts_returns_list(self, test_server_port):
        """GET /api/alerts should return a list."""
        code, data, _ = _get_json(f"http://localhost:{test_server_port}/api/alerts")
        assert code == 200
        assert isinstance(data, list)

    def test_latest_returns_dict(self, test_server_port):
        """GET /api/latest should return a dict."""
        code, data, _ = _get_json(f"http://localhost:{test_server_port}/api/latest")
        assert code == 200
        assert isinstance(data, dict)


@pytest.mark.integration
class TestSecurityHeaders:
    """Tests for security header presence on API responses."""

    def test_security_headers_present(self, test_server_port):
        """API responses should include security headers."""
        _, _, headers = _get_json(f"http://localhost:{test_server_port}/api/health")

        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"


@pytest.mark.integration
class TestInputValidation:
    """Tests for API input validation."""

    def test_forecast_missing_params_returns_400(self, test_server_port):
        """GET /api/forecast without lat/lon should return 400."""
        try:
            urllib.request.urlopen(
                f"http://localhost:{test_server_port}/api/forecast", timeout=10
            )
            pytest.fail("Expected HTTP 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_forecast_invalid_coords_returns_400(self, test_server_port):
        """GET /api/forecast with out-of-range coords should return 400."""
        try:
            urllib.request.urlopen(
                f"http://localhost:{test_server_port}/api/forecast?lat=99.0&lon=77.0",
                timeout=10,
            )
            pytest.fail("Expected HTTP 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_path_traversal_blocked(self, test_server_port):
        """Path traversal attempts should be blocked."""
        try:
            urllib.request.urlopen(
                f"http://localhost:{test_server_port}/api/../../../etc/passwd",
                timeout=10,
            )
            pytest.fail("Expected HTTP error for path traversal")
        except (urllib.error.HTTPError, urllib.error.URLError):
            pass  # Either 400 or connection error is acceptable


@pytest.mark.integration
class TestCoordinateValidation:
    """Tests for the validate_coordinates function."""

    def test_valid_coordinates(self):
        """Valid Indian coordinates should parse successfully."""
        import start_server
        lat, lon = start_server.validate_coordinates("31.2", "77.1")
        assert lat == 31.2
        assert lon == 77.1

    def test_invalid_latitude(self):
        """Latitude outside India bounds should raise ValueError."""
        import start_server
        with pytest.raises(ValueError):
            start_server.validate_coordinates("99.0", "77.1")

    def test_invalid_longitude(self):
        """Longitude outside India bounds should raise ValueError."""
        import start_server
        with pytest.raises(ValueError):
            start_server.validate_coordinates("31.0", "200.0")

    def test_non_numeric_input(self):
        """Non-numeric input should raise ValueError."""
        import start_server
        with pytest.raises(ValueError):
            start_server.validate_coordinates("abc", "77.1")


@pytest.mark.integration
class TestSanitization:
    """Tests for input sanitization functions."""

    def test_html_sanitization(self):
        """HTML tags should be escaped."""
        import start_server
        raw = "<script>alert('xss')</script> Test"
        cleaned = start_server.sanitize_name(raw)
        assert "<script>" not in cleaned
        assert "&lt;script&gt;" in cleaned

    def test_length_limiting(self):
        """Long names should be truncated."""
        import start_server
        raw = "A" * 500
        cleaned = start_server.sanitize_name(raw)
        assert len(cleaned) <= start_server.settings.NAME_MAX_LENGTH

    def test_empty_input(self):
        """Empty input should return empty string."""
        import start_server
        assert start_server.sanitize_name("") == ""
        assert start_server.sanitize_name(None) == ""
