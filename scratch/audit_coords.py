import sys
sys.path.insert(0, ".")
import update_forecasts

plants = update_forecasts.parse_kml("Catchment_NHPC.KML")
for p in plants:
    print(f"ID: {p['id']:2d} | Name: {p['name']:35s} | Lat: {p['lat']:8.4f} | Lon: {p['lon']:8.4f}")
