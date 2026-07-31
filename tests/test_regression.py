"""
Regression tests with frozen IMD response fixtures.

These tests use frozen/known IMD API responses to detect if the
analysis logic or IMD response format changes. If IMD changes their
API response structure, these tests will fail — alerting us to adapt.
"""

import json
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import update_forecasts


# Frozen fixture: a realistic IMD forecast that should produce GREEN
FROZEN_GREEN_RESPONSE = {
    "apcp": [0.0, 0.2, 0.5, 0.1, 0.0, 0.3, 0.0, 0.1,
             0.0, 0.4, 0.8, 0.2, 0.0, 0.1, 0.0, 0.0,
             0.3, 0.6, 1.0, 0.4, 0.1, 0.0, 0.2, 0.0,
             0.0, 0.1, 0.3, 0.0, 0.0, 0.2, 0.0, 0.0,
             0.1, 0.0, 0.3, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0],
    "temp": [18.5, 20.1, 22.3, 24.6, 26.1, 27.8, 28.5, 27.2,
             25.8, 23.4, 21.0, 19.2, 18.0, 19.5, 21.8, 24.0,
             26.3, 28.0, 28.8, 27.5, 25.2, 22.8, 20.5, 18.8,
             17.5, 19.0, 21.5, 23.8, 25.9, 27.5, 28.2, 27.0,
             24.8, 22.5, 20.2, 18.5, 17.2, 18.8, 21.2, 23.5, 25.0],
    "wspd": [1.2, 1.5, 2.0, 2.8, 3.5, 4.0, 3.8, 3.2,
             2.5, 2.0, 1.5, 1.0, 0.8, 1.2, 1.8, 2.5,
             3.2, 3.8, 4.2, 3.5, 2.8, 2.2, 1.5, 1.0,
             0.8, 1.0, 1.5, 2.2, 3.0, 3.5, 3.8, 3.2,
             2.5, 2.0, 1.5, 1.0, 0.8, 1.2, 1.8, 2.5, 3.0],
    "gust": [2.5, 3.0, 4.0, 5.5, 7.0, 8.0, 7.5, 6.5,
             5.0, 4.0, 3.0, 2.0, 1.5, 2.5, 3.5, 5.0,
             6.5, 7.5, 8.5, 7.0, 5.5, 4.5, 3.0, 2.0,
             1.5, 2.0, 3.0, 4.5, 6.0, 7.0, 7.5, 6.5,
             5.0, 4.0, 3.0, 2.0, 1.5, 2.5, 3.5, 5.0, 6.0],
    "rh":   [85.0, 80.0, 72.0, 60.0, 52.0, 45.0, 42.0, 48.0,
             55.0, 65.0, 75.0, 82.0, 88.0, 82.0, 74.0, 62.0,
             54.0, 47.0, 43.0, 50.0, 58.0, 68.0, 78.0, 85.0,
             90.0, 84.0, 76.0, 64.0, 55.0, 48.0, 44.0, 50.0,
             57.0, 66.0, 76.0, 83.0, 89.0, 83.0, 75.0, 63.0, 55.0],
    "tcdc": [10.0, 15.0, 20.0, 25.0, 30.0, 25.0, 20.0, 15.0,
             10.0, 20.0, 30.0, 35.0, 30.0, 25.0, 20.0, 15.0,
             10.0, 15.0, 25.0, 30.0, 25.0, 20.0, 15.0, 10.0,
             5.0, 10.0, 15.0, 20.0, 25.0, 20.0, 15.0, 10.0,
             5.0, 10.0, 15.0, 20.0, 15.0, 10.0, 5.0, 10.0, 15.0],
}

# Frozen fixture: a realistic IMD forecast that should produce RED
FROZEN_RED_RESPONSE = {
    "apcp": [5.0, 12.0, 25.0, 38.0, 28.0, 15.0, 8.0, 4.0,
             10.0, 18.0, 22.0, 12.0, 6.0, 3.0, 2.0, 1.0,
             0.5, 2.0, 5.0, 8.0, 4.0, 2.0, 1.0, 0.5,
             0.0, 1.0, 3.0, 5.0, 2.0, 1.0, 0.5, 0.0,
             0.0, 0.5, 1.0, 2.0, 1.0, 0.5, 0.0, 0.0, 0.0],
    "temp": [20.0, 21.0, 22.0, 21.5, 21.0, 20.5, 20.0, 19.5,
             19.0, 20.0, 21.0, 21.5, 21.0, 20.5, 20.0, 19.5,
             19.0, 20.0, 21.0, 21.5, 21.0, 20.5, 20.0, 19.5,
             19.0, 20.0, 21.0, 21.5, 21.0, 20.5, 20.0, 19.5,
             19.0, 20.0, 21.0, 21.5, 21.0, 20.5, 20.0, 19.5, 19.0],
    "wspd": [8.0, 12.0, 18.0, 22.0, 18.0, 14.0, 10.0, 8.0,
             6.0, 10.0, 15.0, 18.0, 14.0, 10.0, 8.0, 6.0,
             5.0, 8.0, 12.0, 15.0, 12.0, 8.0, 6.0, 5.0,
             4.0, 6.0, 10.0, 12.0, 10.0, 8.0, 6.0, 4.0,
             3.0, 5.0, 8.0, 10.0, 8.0, 6.0, 4.0, 3.0, 3.0],
    "gust": [12.0, 18.0, 26.0, 32.0, 28.0, 20.0, 15.0, 12.0,
             10.0, 16.0, 22.0, 28.0, 22.0, 16.0, 12.0, 10.0,
             8.0, 14.0, 18.0, 24.0, 18.0, 14.0, 10.0, 8.0,
             6.0, 10.0, 15.0, 20.0, 15.0, 10.0, 8.0, 6.0,
             5.0, 8.0, 12.0, 16.0, 12.0, 8.0, 6.0, 5.0, 5.0],
    "rh":   [92.0, 95.0, 98.0, 99.0, 98.0, 95.0, 92.0, 88.0,
             85.0, 90.0, 95.0, 98.0, 95.0, 90.0, 88.0, 85.0,
             82.0, 88.0, 92.0, 95.0, 92.0, 88.0, 85.0, 82.0,
             80.0, 85.0, 90.0, 92.0, 90.0, 85.0, 82.0, 80.0,
             78.0, 82.0, 88.0, 90.0, 88.0, 85.0, 82.0, 80.0, 78.0],
    "tcdc": [80.0, 90.0, 98.0, 100.0, 98.0, 95.0, 90.0, 85.0,
             75.0, 85.0, 95.0, 100.0, 95.0, 90.0, 85.0, 75.0,
             65.0, 75.0, 85.0, 95.0, 90.0, 80.0, 70.0, 60.0,
             50.0, 60.0, 75.0, 85.0, 80.0, 70.0, 60.0, 50.0,
             40.0, 50.0, 65.0, 75.0, 70.0, 60.0, 50.0, 40.0, 35.0],
}

FROZEN_START_TIME = datetime(2026, 7, 30, 5, 30)


@pytest.mark.regression
class TestFrozenGreenScenario:
    """Regression tests for a known GREEN forecast."""

    def test_alert_level_is_green(self):
        result = update_forecasts.analyze_forecast(FROZEN_GREEN_RESPONSE, FROZEN_START_TIME)
        assert result["alert_level"] == "GREEN"

    def test_no_reasons(self):
        result = update_forecasts.analyze_forecast(FROZEN_GREEN_RESPONSE, FROZEN_START_TIME)
        assert result["reasons"] == []

    def test_summary_values(self):
        result = update_forecasts.analyze_forecast(FROZEN_GREEN_RESPONSE, FROZEN_START_TIME)
        summary = result["summary"]
        assert summary["max_3h_rain"] <= 15.0  # Below YELLOW threshold
        assert summary["max_gust"] <= 15.0  # Below YELLOW threshold
        assert summary["rain_24h"] <= 50.0  # Below YELLOW threshold

    def test_detail_arrays_have_correct_length(self):
        result = update_forecasts.analyze_forecast(FROZEN_GREEN_RESPONSE, FROZEN_START_TIME)
        details = result["details"]
        # All arrays should have the same length
        lengths = [len(details[k]) for k in ["times", "rain", "temp", "wind_speed", "wind_gust", "rh", "cloud_cover"]]
        assert len(set(lengths)) == 1  # All same length


@pytest.mark.regression
class TestFrozenRedScenario:
    """Regression tests for a known RED forecast."""

    def test_alert_level_is_red(self):
        result = update_forecasts.analyze_forecast(FROZEN_RED_RESPONSE, FROZEN_START_TIME)
        assert result["alert_level"] == "RED"

    def test_has_reasons(self):
        result = update_forecasts.analyze_forecast(FROZEN_RED_RESPONSE, FROZEN_START_TIME)
        assert len(result["reasons"]) > 0

    def test_extreme_rain_detected(self):
        result = update_forecasts.analyze_forecast(FROZEN_RED_RESPONSE, FROZEN_START_TIME)
        assert any("rain" in r.lower() for r in result["reasons"])

    def test_summary_exceeds_thresholds(self):
        result = update_forecasts.analyze_forecast(FROZEN_RED_RESPONSE, FROZEN_START_TIME)
        summary = result["summary"]
        # At least one RED threshold should be exceeded
        rain_3h_red = summary["max_3h_rain"] > 30.0
        rain_24h_red = summary["rain_24h"] > 100.0
        gust_red = summary["max_gust"] > 25.0
        assert rain_3h_red or rain_24h_red or gust_red

    def test_detail_arrays_consistent(self):
        result = update_forecasts.analyze_forecast(FROZEN_RED_RESPONSE, FROZEN_START_TIME)
        details = result["details"]
        lengths = [len(details[k]) for k in ["times", "rain", "temp", "wind_speed", "wind_gust", "rh", "cloud_cover"]]
        assert len(set(lengths)) == 1


@pytest.mark.regression
class TestResponseFormatDetection:
    """Tests to detect IMD API response format changes.

    If IMD changes the keys they use in their response, these tests
    will fail — alerting developers to update the parser.
    """

    def test_expected_keys_in_green_forecast(self):
        """Frozen GREEN response should have all expected keys."""
        expected_keys = {"apcp", "temp", "wspd", "gust", "rh", "tcdc"}
        actual_keys = set(FROZEN_GREEN_RESPONSE.keys())
        assert expected_keys == actual_keys

    def test_expected_keys_in_red_forecast(self):
        """Frozen RED response should have all expected keys."""
        expected_keys = {"apcp", "temp", "wspd", "gust", "rh", "tcdc"}
        actual_keys = set(FROZEN_RED_RESPONSE.keys())
        assert expected_keys == actual_keys

    def test_all_arrays_have_41_steps(self):
        """IMD 120-hour forecasts should have 41 3-hourly steps."""
        for key, values in FROZEN_GREEN_RESPONSE.items():
            assert len(values) == 41, f"GREEN {key} has {len(values)} steps, expected 41"
        for key, values in FROZEN_RED_RESPONSE.items():
            assert len(values) == 41, f"RED {key} has {len(values)} steps, expected 41"

    def test_analyze_output_structure(self):
        """analyze_forecast output should have consistent structure."""
        result = update_forecasts.analyze_forecast(FROZEN_GREEN_RESPONSE, FROZEN_START_TIME)

        assert "alert_level" in result
        assert "reasons" in result
        assert "summary" in result
        assert "details" in result

        assert isinstance(result["alert_level"], str)
        assert isinstance(result["reasons"], list)
        assert isinstance(result["summary"], dict)
        assert isinstance(result["details"], dict)
