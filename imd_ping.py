"""
NHPC Weather Warning System — IMD Mausamgram API Client.

Fetches weather forecast data from the India Meteorological Department's
(IMD) Mausamgram 0.125° GFS/MME numerical weather prediction model.

Features:
- Thread-safe in-memory forecast caching with configurable TTL
- Stale-on-error disaster fallback (serves cached data during outages)
- Exponential backoff retry on transient failures
- Prometheus metrics instrumentation

Usage:
    from imd_ping import get_model, get_forecast
    model = get_model()
    forecast = get_forecast(31.2, 77.1)
"""

import sys
import json
import time
import threading
from typing import Any, Dict, Optional, Tuple

import requests

from log import get_logger
from config import get_settings
from metrics import IMD_REQUEST_DURATION, IMD_REQUEST_TOTAL, IMD_CACHE_HITS
from exceptions import IMDConnectionError, IMDResponseError

logger = get_logger("nhpc.imd")

# ---------------------------------------------------------------------------
# In-Memory Cache with Stale-On-Error Fallback (Thread Safe)
# ---------------------------------------------------------------------------
_CACHE_LOCK = threading.Lock()
_FORECAST_CACHE: Dict[Tuple[float, float], Dict[str, Any]] = {}
_MODEL_CACHE: Dict[str, Any] = {"model": None, "timestamp": 0}


def snap_grid(value: Any) -> float:
    """Snap a coordinate value to the nearest IMD 0.125° grid point.

    Args:
        value: Latitude or longitude value (float or string).

    Returns:
        Grid-snapped coordinate rounded to 3 decimal places.
    """
    grid = 0.125
    return round(round(float(value) / grid) * grid, 3)


def _request_with_retry(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> requests.Response:
    """Make an HTTP GET request with exponential backoff retry.

    Args:
        url: Target URL.
        headers: Optional HTTP headers.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.

    Returns:
        The HTTP response object.

    Raises:
        IMDConnectionError: If all retry attempts fail.
    """
    settings = get_settings()
    if timeout is None:
        timeout = settings.IMD_REQUEST_TIMEOUT
    if max_retries is None:
        max_retries = settings.IMD_MAX_RETRIES
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
            "Accept": "*/*",
            "Referer": settings.IMD_BASE_URL,
        }

    backoff_base = settings.IMD_RETRY_BACKOFF
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            start = time.monotonic()
            r = requests.get(url, headers=headers, timeout=timeout)
            elapsed = time.monotonic() - start
            IMD_REQUEST_DURATION.labels(endpoint="forecast").observe(elapsed)

            if r.status_code >= 500:
                last_exception = requests.exceptions.HTTPError(
                    f"Server returned {r.status_code} for {url}"
                )
                IMD_REQUEST_TOTAL.labels(endpoint="forecast", status="server_error").inc()
                if attempt < max_retries - 1:
                    wait_time = backoff_base ** (attempt + 1)
                    logger.warning(
                        "IMD returned %d, retrying in %.1fs (attempt %d/%d)",
                        r.status_code, wait_time, attempt + 1, max_retries,
                    )
                    time.sleep(wait_time)
                    continue
                r.raise_for_status()

            IMD_REQUEST_TOTAL.labels(endpoint="forecast", status="success").inc()
            return r

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            last_exception = e
            IMD_REQUEST_TOTAL.labels(endpoint="forecast", status="error").inc()
            if attempt < max_retries - 1:
                wait_time = backoff_base ** (attempt + 1)
                logger.warning(
                    "IMD request failed (%s), retrying in %.1fs (attempt %d/%d)",
                    type(e).__name__, wait_time, attempt + 1, max_retries,
                )
                time.sleep(wait_time)

    raise IMDConnectionError(
        f"IMD API unreachable after {max_retries} attempts: {last_exception}"
    ) from last_exception


def get_model() -> str:
    """Fetches IMD model date string with thread-safe caching.

    Returns:
        Model date string in format 'YYYYMMDDHH'.
    """
    settings = get_settings()
    cache_ttl = settings.IMD_CACHE_TTL
    now = time.time()

    with _CACHE_LOCK:
        if _MODEL_CACHE["model"] and (now - _MODEL_CACHE["timestamp"]) < cache_ttl:
            return _MODEL_CACHE["model"]

    url = f"{settings.IMD_BASE_URL}/mmem_3hr.txt"
    try:
        r = _request_with_retry(url)
        r.raise_for_status()
        model_str = r.text.split(",")[0].strip()
        with _CACHE_LOCK:
            _MODEL_CACHE["model"] = model_str
            _MODEL_CACHE["timestamp"] = now
        return model_str
    except Exception as e:
        with _CACHE_LOCK:
            if _MODEL_CACHE["model"]:
                logger.warning(
                    "Model date fetch failed (%s). Using cached model string: %s",
                    e, _MODEL_CACHE["model"],
                )
                return _MODEL_CACHE["model"]
        # Default fallback string if no cache available
        logger.warning("No cached model string available. Using current time as fallback.")
        return time.strftime("%Y%m%d00")


def get_forecast(lat: float, lon: float, use_cache: bool = True) -> Dict[str, Any]:
    """Fetches IMD weather forecast with thread-safe RAM cache & stale-on-error fallback.

    Args:
        lat: Latitude of the target location.
        lon: Longitude of the target location.
        use_cache: Whether to check the in-memory cache first.

    Returns:
        Dict containing forecast data, grid coordinates, model info,
        and cache status flags.

    Raises:
        IMDConnectionError: If the API is unreachable and no cached data exists.
    """
    settings = get_settings()
    cache_ttl = settings.IMD_CACHE_TTL

    lat_gfs = snap_grid(lat)
    lon_gfs = snap_grid(lon)
    cache_key = (lat_gfs, lon_gfs)
    now = time.time()

    # 1. Check active cache
    if use_cache:
        with _CACHE_LOCK:
            cached_entry = _FORECAST_CACHE.get(cache_key)
            if cached_entry and (now - cached_entry["timestamp"]) < cache_ttl:
                result = dict(cached_entry["data"])
                result["cached"] = True
                result["stale"] = False
                IMD_CACHE_HITS.inc()
                return result

    model = get_model()
    url = (
        f"{settings.IMD_BASE_URL}/test4_mme.php"
        f"?lat_gfs={lat_gfs}"
        f"&lon_gfs={lon_gfs}"
        f"&date={model}_3hr_0p125"
    )

    try:
        r = _request_with_retry(url)
        try:
            data = r.json()
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(
                "IMD response for (%s, %s) is not valid JSON: %s",
                lat, lon, e,
            )
            data = r.text

        result = {
            "original": {"lat": lat, "lon": lon},
            "gfs_grid": {"lat": lat_gfs, "lon": lon_gfs},
            "model": model,
            "forecast": data,
            "cached": False,
            "stale": False
        }

        # Store in cache
        with _CACHE_LOCK:
            _FORECAST_CACHE[cache_key] = {"data": result, "timestamp": now}

        return result

    except Exception as e:
        logger.error("Failed to fetch live forecast for (%s, %s): %s", lat, lon, e)
        # Stale-on-error disaster fallback
        with _CACHE_LOCK:
            cached_entry = _FORECAST_CACHE.get(cache_key)
            if cached_entry:
                logger.warning(
                    "Serving STALE forecast for (%s, %s) — disaster fallback active",
                    lat, lon,
                )
                result = dict(cached_entry["data"])
                result["cached"] = True
                result["stale"] = True
                result["fallback_reason"] = str(e)
                return result

        # If no cache exists, raise the exception
        raise IMDConnectionError(
            f"IMD API unreachable for ({lat}, {lon}) and no cached data available: {e}"
        ) from e


if __name__ == "__main__":
    from log import setup_logging
    setup_logging()

    if len(sys.argv) != 3:
        print("usage: python imd_ping.py LAT LON")
        sys.exit(1)

    result = get_forecast(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=4))