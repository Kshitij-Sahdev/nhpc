import sys
import json
import time
import requests


BASE = "https://mausamgram.imd.gov.in"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "*/*",
    "Referer": BASE
}

# Default timeout for all IMD API calls (seconds)
REQUEST_TIMEOUT = 30

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds: 2, 4, 8


def snap_grid(value):

    grid = 0.125

    return round(
        round(float(value) / grid)
        * grid,
        3
    )


def _request_with_retry(url, headers=None, timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES):
    """Make an HTTP GET request with exponential backoff retry.
    
    Retries on connection errors, timeouts, and 5xx server errors.
    Raises the last exception if all retries are exhausted.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            # Retry on server errors (5xx) from IMD
            if r.status_code >= 500:
                last_exception = requests.exceptions.HTTPError(
                    f"Server returned {r.status_code} for {url}"
                )
                if attempt < max_retries - 1:
                    wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                    print(f"  [IMD Retry] Server error {r.status_code}, retrying in {wait_time}s (attempt {attempt+1}/{max_retries})")
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
                print(f"  [IMD Retry] {type(e).__name__}: {e}, retrying in {wait_time}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"  [IMD Error] All {max_retries} attempts failed for {url}")
    raise last_exception


def get_model():

    url = f"{BASE}/mmem_3hr.txt"

    r = _request_with_retry(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )

    r.raise_for_status()

    return r.text.split(",")[0].strip()



def get_forecast(lat, lon):

    model = get_model()

    lat_gfs = snap_grid(lat)
    lon_gfs = snap_grid(lon)

    url = (
        f"{BASE}/test4_mme.php"
        f"?lat_gfs={lat_gfs}"
        f"&lon_gfs={lon_gfs}"
        f"&date={model}_3hr_0p125"
    )

    print("CALLING:", url)


    r = _request_with_retry(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )


    try:
        data = r.json()
    except (ValueError, json.JSONDecodeError):
        print(f"  [IMD Warning] Non-JSON response for ({lat}, {lon}), raw text: {r.text[:200]}")
        data = r.text


    return {
        "original": {
            "lat": lat,
            "lon": lon
        },

        "gfs_grid": {
            "lat": lat_gfs,
            "lon": lon_gfs
        },

        "model": model,

        "forecast": data
    }



if __name__ == "__main__":


    if len(sys.argv) != 3:

        print(
            "usage: python imd_ping.py LAT LON"
        )

        exit()


    result = get_forecast(
        sys.argv[1],
        sys.argv[2]
    )


    print(
        json.dumps(
            result,
            indent=4
        )
    )