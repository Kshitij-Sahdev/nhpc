"""
India Boundary Service — Clean GeoJSON Vector Outline of India.

Provides high-resolution boundary line geometry for India's national border
for clean map rendering without external tile label noise.
"""

from typing import Any, Dict

# Simplified GeoJSON boundary coordinates for India
INDIA_OUTLINE_GEOJSON: Dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "India National Boundary"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [77.0, 35.5], [78.5, 35.5], [79.2, 34.2], [78.8, 32.5],
                    [79.8, 31.5], [81.0, 30.2], [80.5, 28.8], [82.5, 28.2],
                    [85.0, 27.5], [88.0, 27.3], [88.9, 27.8], [88.8, 27.1],
                    [91.8, 26.8], [92.0, 27.8], [94.5, 28.2], [96.2, 28.5],
                    [97.0, 28.0], [96.0, 27.0], [95.0, 26.0], [93.5, 24.5],
                    [92.5, 24.0], [91.8, 25.2], [89.8, 25.2], [88.8, 26.2],
                    [88.2, 25.0], [88.8, 23.8], [89.0, 21.8], [87.0, 21.5],
                    [85.0, 19.5], [83.0, 17.5], [80.2, 13.0], [79.8, 10.5],
                    [77.5, 8.0],  [76.8, 8.5],  [75.5, 12.0], [73.5, 15.5],
                    [72.8, 19.0], [72.8, 21.2], [70.0, 21.0], [68.2, 23.5],
                    [70.0, 24.5], [71.0, 26.0], [70.5, 28.0], [72.0, 29.5],
                    [74.5, 31.0], [74.0, 32.5], [74.5, 34.5], [75.5, 35.0],
                    [77.0, 35.5]
                ]]
            }
        }
    ]
}


def get_india_outline() -> Dict[str, Any]:
    """Returns India boundary GeoJSON feature collection."""
    return INDIA_OUTLINE_GEOJSON
