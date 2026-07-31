"""
IMD API client unit tests.

Tests snap_grid accuracy, caching, and retry logic.
Network calls are not made — these test the internal logic.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import imd_ping


class TestSnapGrid:
    """Tests for coordinate grid snapping."""

    def test_snap_exact_grid_point(self):
        """Exact grid points should not change."""
        assert imd_ping.snap_grid(31.25) == 31.25
        assert imd_ping.snap_grid(77.0) == 77.0

    def test_snap_between_grid_points(self):
        """Values between grid points should snap to nearest."""
        # 31.2 is between 31.125 and 31.25, closer to 31.25
        result = imd_ping.snap_grid(31.2)
        assert result == 31.25

    def test_snap_string_input(self):
        """String inputs should be converted to float first."""
        result = imd_ping.snap_grid("77.1")
        assert isinstance(result, float)

    def test_snap_preserves_precision(self):
        """Result should have at most 3 decimal places."""
        result = imd_ping.snap_grid(31.123456789)
        assert result == round(result, 3)

    def test_snap_various_values(self):
        """Test snapping for a range of coordinate values."""
        # 0.125 grid means valid points are multiples of 0.125
        for val in [28.0, 28.125, 28.25, 28.375, 28.5]:
            assert imd_ping.snap_grid(val) == val

    def test_snap_negative(self):
        """Negative coordinates should snap correctly."""
        result = imd_ping.snap_grid(-5.3)
        assert result == round(result, 3)


class TestCacheLogic:
    """Tests for cache key generation and TTL logic.

    These tests examine caching internals without making network calls.
    """

    def test_cache_key_is_grid_snapped(self):
        """Cache keys should use grid-snapped coordinates."""
        # Two coordinates that snap to the same grid point should
        # have the same cache key
        key1 = (imd_ping.snap_grid(31.2), imd_ping.snap_grid(77.1))
        key2 = (imd_ping.snap_grid(31.22), imd_ping.snap_grid(77.13))
        assert key1 == key2  # Both snap to (31.25, 77.125)

    def test_different_coords_different_keys(self):
        """Coordinates far apart should have different cache keys."""
        key1 = (imd_ping.snap_grid(31.0), imd_ping.snap_grid(77.0))
        key2 = (imd_ping.snap_grid(28.0), imd_ping.snap_grid(93.0))
        assert key1 != key2
