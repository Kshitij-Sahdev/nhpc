"""
River Service — GeoJSON Vector Channels for All Major Indian River Systems.

Provides high-resolution LineString geometries for all rivers powering NHPC hydro projects:
- Indus, Jhelum, Kishanganga, Chenab, Ravi, Baira, Siul, Beas, Parbati, Sainj, Suru,
- Sharda/Mahakali, Teesta, Subansiri, Dibang, Brahmaputra, and Ganga river systems.
"""

from typing import Any, Dict

RIVER_GEOJSON: Dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "Teesta River", "type": "Major River System", "basin": "Teesta Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [88.75, 27.95], [88.62, 27.75], [88.54, 27.55],
                    [88.48, 27.32], [88.4722, 26.9642], [88.58, 26.70], [88.72, 26.45]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Subansiri River", "type": "Major River System", "basin": "Brahmaputra Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [93.10, 28.50], [93.45, 28.15], [93.85, 27.85],
                    [94.2586, 27.5536], [94.18, 27.30], [94.12, 26.95]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Dibang River", "type": "Major River System", "basin": "Brahmaputra Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [96.10, 28.90], [95.95, 28.65], [95.8253, 28.5233],
                    [95.7720, 28.2250], [95.65, 28.05], [95.55, 27.85]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Chenab River", "type": "Major River System", "basin": "Indus Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [77.40, 32.50], [76.95, 32.75], [76.40, 32.90],
                    [75.85, 33.15], [75.20, 33.18], [74.8044, 33.1378], [74.45, 33.00], [74.15, 32.85]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Jhelum River", "type": "Major River System", "basin": "Indus Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [75.25, 33.65], [74.90, 34.05], [74.60, 34.18],
                    [74.0450, 34.1450], [74.0318, 34.0921], [73.75, 34.10]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Kishanganga / Neelum River", "type": "Tributary River", "basin": "Jhelum Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [75.15, 34.50], [74.8847, 34.6107], [74.6733, 34.6111],
                    [74.45, 34.55], [73.90, 34.38]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Indus River", "type": "Major River System", "basin": "Indus Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [78.50, 33.20], [77.80, 33.80], [77.1853, 34.2153],
                    [76.80, 34.40], [76.20, 34.65], [75.50, 35.10]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Suru River", "type": "Tributary River", "basin": "Indus Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [76.40, 33.90], [76.15, 34.20], [76.0746, 34.4591],
                    [76.02, 34.55], [75.90, 34.62]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Ravi River", "type": "Major River System", "basin": "Indus Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [77.05, 32.35], [76.60, 32.42], [76.2552, 32.4734], [76.2443, 32.4598],
                    [75.9857, 32.5966], [75.7280, 32.4410], [75.45, 32.20], [75.10, 31.95]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Baira Siul River", "type": "Tributary River", "basin": "Ravi Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [76.35, 32.90], [76.1418, 32.8063], [76.05, 32.75],
                    [75.9232, 32.8242], [75.9857, 32.5966]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Parbati & Sainj Rivers", "type": "Tributary River", "basin": "Beas Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [77.55, 31.95], [77.3275, 31.7836], [77.2576, 31.7398],
                    [77.15, 31.70], [76.98, 31.72]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Beas River", "type": "Major River System", "basin": "Indus Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [77.15, 32.35], [77.18, 32.00], [77.12, 31.80],
                    [76.90, 31.70], [76.35, 31.85], [75.80, 31.95]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Sharda / Mahakali River", "type": "Major River System", "basin": "Ganga Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [80.80, 30.70], [80.45, 30.00], [80.20, 29.50],
                    [80.1189, 29.0725], [80.05, 28.65], [80.15, 28.10]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Brahmaputra River (Main Channel)", "type": "Major River System", "basin": "Brahmaputra Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [95.40, 27.80], [94.50, 27.10], [93.20, 26.60],
                    [91.80, 26.20], [90.50, 26.10], [89.80, 25.80]
                ]
            }
        },
        {
            "type": "Feature",
            "properties": {"name": "Ganga River", "type": "Major River System", "basin": "Ganga Basin"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [78.60, 30.15], [78.15, 29.95], [78.10, 29.50],
                    [79.80, 27.50], [82.50, 25.50], [85.00, 25.60], [88.00, 24.80]
                ]
            }
        }
    ]
}


def get_river_geojson() -> Dict[str, Any]:
    """Returns GeoJSON FeatureCollection of river vectors."""
    return RIVER_GEOJSON
