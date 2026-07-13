import sys
import json
import requests


BASE = "https://mausamgram.imd.gov.in"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "*/*",
    "Referer": BASE
}


def snap_grid(value):

    grid = 0.125

    return round(
        round(float(value) / grid)
        * grid,
        3
    )


def get_model():

    url = f"{BASE}/mmem_3hr.txt"

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=10
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


    r = requests.get(
        url,
        headers=HEADERS
    )


    try:
        data = r.json()

    except:
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