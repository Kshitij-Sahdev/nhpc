import sys
import json
import time
import threading
import requests

BASE = "https://mausamgram.imd.gov.in"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "*/*",
    "Referer": BASE
}

# Default timeout for IMD API calls (seconds)
REQUEST_TIMEOUT = 10

# Retry configuration
MAX_RETRIES = 2
RETRY_BACKOFF_BASE = 1.5

# In-Memory Cache with Stale-On-Error Fallback (Thread Safe)
_CACHE_LOCK = threading.Lock()
_FORECAST_CACHE = {}  # key: (lat_gfs, lon_gfs) -> {"data": result_dict, "timestamp": float}
_MODEL_CACHE = {"model": None, "timestamp": 0}
CACHE_TTL_SECONDS = 1800  # 30 minutes TTL


def snap_grid(value):
    grid = 0.125
    return round(round(float(value) / grid) * grid, 3)


def _request_with_retry(url, headers=None, timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES):
    """Make an HTTP GET request with exponential backoff retry."""
    last_exception = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code >= 500:
                last_exception = requests.exceptions.HTTPError(
                    f"Server returned {r.status_code} for {url}"
                )
                if attempt < max_retries - 1:
                    wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                    time.sleep(wait_time)
                    continue
                r.raise_for_status()
            return r
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                time.sleep(wait_time)
    raise last_exception


def get_model():
    """Fetches IMD model date string with thread-safe caching."""
    now = time.time()
    with _CACHE_LOCK:
        if _MODEL_CACHE["model"] and (now - _MODEL_CACHE["timestamp"]) < CACHE_TTL_SECONDS:
            return _MODEL_CACHE["model"]

    url = f"{BASE}/mmem_3hr.txt"
    try:
        r = _request_with_retry(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        model_str = r.text.split(",")[0].strip()
        with _CACHE_LOCK:
            _MODEL_CACHE["model"] = model_str
            _MODEL_CACHE["timestamp"] = now
        return model_str
    except Exception as e:
        with _CACHE_LOCK:
            if _MODEL_CACHE["model"]:
                print(f"  [IMD Warning] Model date fetch failed ({e}). Using cached model string.")
                return _MODEL_CACHE["model"]
        # Default fallback string if no cache available
        return time.strftime("%Y%m%d00")


def get_forecast(lat, lon, use_cache=True):
    """Fetches IMD weather forecast with thread-safe RAM cache & stale-on-error fallback."""
    lat_gfs = snap_grid(lat)
    lon_gfs = snap_grid(lon)
    cache_key = (lat_gfs, lon_gfs)
    now = time.time()

    # 1. Check active cache
    if use_cache:
        with _CACHE_LOCK:
            cached_entry = _FORECAST_CACHE.get(cache_key)
            if cached_entry and (now - cached_entry["timestamp"]) < CACHE_TTL_SECONDS:
                result = dict(cached_entry["data"])
                result["cached"] = True
                result["stale"] = False
                return result

    model = get_model()
    url = (
        f"{BASE}/test4_mme.php"
        f"?lat_gfs={lat_gfs}"
        f"&lon_gfs={lon_gfs}"
        f"&date={model}_3hr_0p125"
    )

    try:
        r = _request_with_retry(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        try:
            data = r.json()
        except (ValueError, json.JSONDecodeError):
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
        print(f"  [IMD Outage/Error] Failed to fetch live forecast for ({lat}, {lon}): {e}")
        # Stale-on-error disaster fallback
        with _CACHE_LOCK:
            cached_entry = _FORECAST_CACHE.get(cache_key)
            if cached_entry:
                print(f"  [Disaster Fallback] Serving stale forecast for ({lat}, {lon})")
                result = dict(cached_entry["data"])
                result["cached"] = True
                result["stale"] = True
                result["fallback_reason"] = str(e)
                return result
        
        # If no cache exists, raise the exception
        raise e


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python imd_ping.py LAT LON")
        sys.exit(1)

    result = get_forecast(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=4))