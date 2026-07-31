"""
Forecast analysis unit tests.

Tests the analyze_forecast() function with various weather scenarios
to validate alert threshold logic, NaN handling, and edge cases.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import update_forecasts


class TestAlertThresholds:
    """Tests for GREEN/YELLOW/RED alert determination."""

    def test_green_scenario(self, sample_forecast_green, forecast_start_time):
        """Low rain and wind should produce GREEN alert."""
        result = update_forecasts.analyze_forecast(sample_forecast_green, forecast_start_time)
        assert result["alert_level"] == "GREEN"
        assert result["reasons"] == []

    def test_yellow_rain_3h(self, forecast_start_time):
        """3-hour rain > 15mm should produce YELLOW alert."""
        forecast = {
            "apcp": [5.0, 18.0, 3.0, 1.0, 0.5, 0.0, 0.5, 0.0] * 5,
            "temp": [25.0] * 40,
            "wspd": [3.0] * 40,
            "gust": [5.0] * 40,
            "rh": [60.0] * 40,
            "tcdc": [30.0] * 40,
        }
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] == "YELLOW"
        assert any("Heavy peak rainfall" in r for r in result["reasons"])

    def test_red_rain_3h(self, forecast_start_time):
        """3-hour rain > 30mm should produce RED alert."""
        forecast = {
            "apcp": [5.0, 35.0, 10.0, 5.0, 2.0, 1.0, 0.5, 0.0] * 5,
            "temp": [25.0] * 40,
            "wspd": [3.0] * 40,
            "gust": [5.0] * 40,
            "rh": [60.0] * 40,
            "tcdc": [30.0] * 40,
        }
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] == "RED"
        assert any("Extreme peak rainfall" in r for r in result["reasons"])

    def test_yellow_rain_24h(self, forecast_start_time):
        """24-hour cumulative rain > 50mm should produce YELLOW alert."""
        # 8 steps * 7mm = 56mm in 24h
        forecast = {
            "apcp": [7.0] * 8 + [0.0] * 32,
            "temp": [25.0] * 40,
            "wspd": [3.0] * 40,
            "gust": [5.0] * 40,
            "rh": [60.0] * 40,
            "tcdc": [30.0] * 40,
        }
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] == "YELLOW"
        assert any("24-hour cumulative rainfall" in r for r in result["reasons"])

    def test_red_rain_24h(self, forecast_start_time):
        """24-hour cumulative rain > 100mm should produce RED alert."""
        # 8 steps * 14mm = 112mm in 24h
        forecast = {
            "apcp": [14.0] * 8 + [0.0] * 32,
            "temp": [25.0] * 40,
            "wspd": [3.0] * 40,
            "gust": [5.0] * 40,
            "rh": [60.0] * 40,
            "tcdc": [30.0] * 40,
        }
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] == "RED"
        assert any("Extreme 24-hour" in r for r in result["reasons"])

    def test_red_wind_gust(self, forecast_start_time):
        """Wind gust > 25 m/s should produce RED alert."""
        forecast = {
            "apcp": [0.0] * 40,
            "temp": [25.0] * 40,
            "wspd": [10.0] * 40,
            "gust": [5.0, 10.0, 28.0, 15.0, 8.0, 5.0, 3.0, 2.0] * 5,
            "rh": [60.0] * 40,
            "tcdc": [30.0] * 40,
        }
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] == "RED"
        assert any("Extreme wind gust" in r for r in result["reasons"])

    def test_yellow_wind_gust(self, forecast_start_time):
        """Wind gust between 15-25 m/s should produce YELLOW alert."""
        forecast = {
            "apcp": [0.0] * 40,
            "temp": [25.0] * 40,
            "wspd": [5.0] * 40,
            "gust": [5.0, 8.0, 18.0, 10.0, 5.0, 3.0, 2.0, 1.0] * 5,
            "rh": [60.0] * 40,
            "tcdc": [30.0] * 40,
        }
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] == "YELLOW"
        assert any("High wind gust" in r for r in result["reasons"])


class TestForecastSummary:
    """Tests for forecast summary statistics."""

    def test_summary_fields_present(self, sample_forecast_green, forecast_start_time):
        """Summary should contain all expected fields."""
        result = update_forecasts.analyze_forecast(sample_forecast_green, forecast_start_time)
        summary = result["summary"]

        required_fields = [
            "max_temp", "min_temp", "max_3h_rain",
            "rain_24h", "rain_48h", "rain_72h",
            "max_wind", "max_gust"
        ]
        for field in required_fields:
            assert field in summary, f"Missing summary field: {field}"

    def test_details_fields_present(self, sample_forecast_green, forecast_start_time):
        """Forecast details should contain all expected arrays."""
        result = update_forecasts.analyze_forecast(sample_forecast_green, forecast_start_time)
        details = result["details"]

        required = ["times", "rain", "temp", "wind_speed", "wind_gust", "rh", "cloud_cover"]
        for field in required:
            assert field in details, f"Missing details field: {field}"
            assert isinstance(details[field], list)

    def test_times_are_formatted(self, sample_forecast_green, forecast_start_time):
        """Time values should be formatted as YYYY-MM-DD HH:MM."""
        result = update_forecasts.analyze_forecast(sample_forecast_green, forecast_start_time)
        times = result["details"]["times"]
        assert len(times) > 0
        # Verify format by parsing
        datetime.strptime(times[0], "%Y-%m-%d %H:%M")


class TestNaNHandling:
    """Tests for NaN and missing value handling."""

    def test_nan_values_handled(self, forecast_start_time):
        """NaN values should be filled without crashing."""
        forecast = {
            "apcp": [0.0, "NaN", 1.0, None, 0.0, "nan", 0.5, 0.0],
            "temp": [22.0, "NaN", None, 25.0, "nan", 24.0, 23.0, 22.0],
            "wspd": [2.0, None, 3.0, "NaN", 2.0, 1.0, 2.0, 1.0],
            "gust": [3.0, 4.0, "nan", 5.0, None, 3.0, 2.0, 1.0],
            "rh": [60.0, "NaN", 65.0, None, 60.0, 55.0, 50.0, 45.0],
            "tcdc": [20.0, None, "NaN", 30.0, 25.0, 20.0, 15.0, 10.0],
        }
        # Should not raise
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] in ["GREEN", "YELLOW", "RED"]

    def test_empty_forecast_data(self, forecast_start_time):
        """Empty forecast data should produce GREEN with no errors."""
        forecast: Dict[str, Any] = {}
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] == "GREEN"

    def test_all_zeros(self, forecast_start_time):
        """All-zero forecast should produce GREEN."""
        forecast = {
            "apcp": [0.0] * 40,
            "temp": [0.0] * 40,  # Will be treated as None due to treat_zero_as_none
            "wspd": [0.0] * 40,
            "gust": [0.0] * 40,
            "rh": [0.0] * 40,
            "tcdc": [0.0] * 40,
        }
        result = update_forecasts.analyze_forecast(forecast, forecast_start_time)
        assert result["alert_level"] == "GREEN"


class TestUtilityFunctions:
    """Tests for utility functions in update_forecasts."""

    def test_safe_float_normal(self):
        """safe_float should convert normal values."""
        assert update_forecasts.safe_float(3.14) == 3.14
        assert update_forecasts.safe_float("2.5") == 2.5

    def test_safe_float_edge_cases(self):
        """safe_float should return 0.0 for invalid inputs."""
        assert update_forecasts.safe_float(None) == 0.0
        assert update_forecasts.safe_float("NaN") == 0.0
        assert update_forecasts.safe_float("nan") == 0.0
        assert update_forecasts.safe_float("invalid") == 0.0

    def test_clean_name_mapping(self):
        """clean_name should apply known name mappings."""
        assert update_forecasts.clean_name("TanakpurCorrected", "doc.kml") == "Tanakpur"
        assert update_forecasts.clean_name("SubLowdam", "doc.kml") == "Subansiri Lower"
        assert update_forecasts.clean_name("tld4", "doc.kml") == "Teesta Low Dam IV"

    def test_clean_name_unnamed_fallback(self):
        """clean_name should fall back to doc name for unnamed placemarks."""
        result = update_forecasts.clean_name("Unnamed", "Chamera-I.kml")
        assert result == "Chamera-I"

    def test_downsample_small_list(self):
        """Downsampling a small list should return it unchanged."""
        coords = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        result = update_forecasts.downsample_coordinates(coords, max_points=100)
        assert result == coords

    def test_downsample_large_list(self):
        """Downsampling a large list should reduce point count."""
        coords = [[float(i), float(i + 1)] for i in range(500)]
        result = update_forecasts.downsample_coordinates(coords, max_points=50)
        assert len(result) <= 55  # Allow small overshoot for closure
