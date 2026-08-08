"""
NHPC Spatial & Catchment Overlay Engine.

Uses Shapely and PyProj (WGS84 ellipsoid) to perform high-precision geospatial calculations:
1. Parses `Catchment_NHPC.KML` to build Shapely geometries for hydro plant catchment polygons.
2. Evaluates point-in-polygon and distance calculations for IMD forecast grids and NDMA alert polygons.
3. Supports customizable warning distance buffers (default: 25 km).
"""

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any
import logging

try:
    from shapely.geometry import Point, Polygon
    from shapely.ops import nearest_points
    from pyproj import Geod
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

logger = logging.getLogger("nhpc.spatial")

# Global Geod object for WGS84 distance calculations
GEOD = Geod(ellps="WGS84") if SHAPELY_AVAILABLE else None


def parse_kml_coordinates(coords_str: str) -> List[Tuple[float, float]]:
    """Parse KML coordinate string (lon,lat,alt format) into (lon, lat) tuples."""
    points = []
    for token in coords_str.strip().split():
        parts = token.split(',')
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                points.append((lon, lat))
            except ValueError:
                continue
    return points


def clean_project_name(raw_name: str) -> str:
    """Normalizes raw KML/GeoJSON placemark names to official NHPC project names."""
    name = raw_name.replace(" (Project)", "").replace(" (Catchment)", "").replace(" Catchment area", "").replace("Corrected", "").strip()
    mapping = {
        "Dibang": "Dibang Multipurpose Project",
        "Dibang Multipurpose Project": "Dibang Multipurpose Project",
        "Kishanganga": "Kishanganga HEP",
        "Kishanganga HEP": "Kishanganga HEP",
        "Tanakpur": "Tanakpur HEP",
        "SubLowdam": "Subansiri Lower HEP",
        "Subansiri Lower": "Subansiri Lower HEP",
        "tld4": "Teesta Low Dam IV HEP",
        "Teesta Low Dam IV": "Teesta Low Dam IV HEP",
        "nbpdam": "Nimoo Bazgo HEP",
        "Nimoo Bazgo": "Nimoo Bazgo HEP",
        "ChutakPS": "Chutak Power Station",
        "Chutak": "Chutak Power Station",
        "Uri_I": "Uri-I Power Station",
        "Uri I": "Uri-I Power Station",
        "Uri_II": "Uri-II Power Station",
        "Uri II": "Uri-II Power Station",
        "Baira": "Baira Siul Power Station",
        "Salal": "Salal Power Station",
        "Chamera-I": "Chamera-I HEP",
        "Chamera-II": "Chamera-II HEP",
        "Chamera-III": "Chamera-III HEP",
        "Parbati-II": "Parbati-II HEP",
        "Parbati-III": "Parbati-III HEP",
        "Ranjit Sagar": "Ranjit Sagar Hydro Project"
    }
    return mapping.get(name, name)


class SpatialCatchmentEngine:
    def __init__(self, kml_path: Optional[str] = None):
        self.kml_path = kml_path or "Catchment_NHPC.KML"
        self.catchments: Dict[str, Dict[str, Any]] = {}
        self.shapely_polygons: Dict[str, Any] = {}
        self._loaded = False

    def load_catchments(self) -> Dict[str, Dict[str, Any]]:
        """Parse KML file and build catchment polygon dictionaries and Shapely objects."""
        if self._loaded:
            return self.catchments

        if not os.path.exists(self.kml_path):
            logger.warning(f"KML file not found at {self.kml_path}")
            return {}

        try:
            tree = ET.parse(self.kml_path)
            root = tree.getroot()
            ns = {'kml': 'http://www.opengis.net/kml/2.2'}

            placemarks = root.findall('.//kml:Placemark', ns)
            if not placemarks:
                placemarks = root.findall('.//Placemark')

            for pm in placemarks:
                name_elem = pm.find('kml:name', ns)
                if name_elem is None:
                    name_elem = pm.find('name')
                raw_name = name_elem.text.strip() if name_elem is not None and name_elem.text else "Unnamed Catchment"
                name = clean_project_name(raw_name)

                if name in self.catchments:
                    continue

                # Find coordinates
                coords_elem = pm.find('.//kml:coordinates', ns)
                if coords_elem is None:
                    coords_elem = pm.find('.//coordinates')

                if coords_elem is not None and coords_elem.text:
                    pts = parse_kml_coordinates(coords_elem.text)
                    if len(pts) >= 3:
                        # Compute centroid
                        avg_lon = sum(p[0] for p in pts) / len(pts)
                        avg_lat = sum(p[1] for p in pts) / len(pts)

                        catchment_data = {
                            "name": name,
                            "centroid": {"lat": avg_lat, "lon": avg_lon},
                            "coordinates": [[p[1], p[0]] for p in pts], # [lat, lon] format for Leaflet
                            "geo_coordinates": pts # [lon, lat] format for Shapely
                        }
                        self.catchments[name] = catchment_data

                        if SHAPELY_AVAILABLE:
                            try:
                                poly = Polygon(pts)
                                if not poly.is_valid:
                                    poly = poly.buffer(0)
                                self.shapely_polygons[name] = poly
                            except Exception as e:
                                logger.error(f"Failed to build Shapely polygon for {name}: {e}")

            self._loaded = True
            logger.info(f"Loaded {len(self.catchments)} catchment boundary polygons from {self.kml_path}")
        except Exception as e:
            logger.error(f"Error parsing KML catchment file: {e}")

        return self.catchments

    def distance_point_to_polygon_km(self, lat: float, lon: float, poly: Any) -> float:
        """Calculate exact WGS84 geodesic distance in kilometers from point to polygon boundary."""
        if not SHAPELY_AVAILABLE or GEOD is None:
            return 0.0

        point = Point(lon, lat)
        if poly.contains(point):
            return 0.0

        try:
            nearest_geom, _ = nearest_points(poly.boundary, point)
            _, _, distance_m = GEOD.inv(point.x, point.y, nearest_geom.x, nearest_geom.y)
            return distance_m / 1000.0
        except Exception as e:
            logger.error(f"Error in distance computation: {e}")
            return 9999.0

    def evaluate_location_against_catchments(
        self, lat: float, lon: float, buffer_km: float = 25.0
    ) -> List[Dict[str, Any]]:
        """Evaluate a lat/lon coordinate against all catchment polygons.

        Returns matching catchments with containment status (INSIDE_CATCHMENT or NEAR_CATCHMENT).
        """
        self.load_catchments()
        results = []

        if not SHAPELY_AVAILABLE:
            return results

        point = Point(lon, lat)

        for name, poly in self.shapely_polygons.items():
            if poly.contains(point):
                results.append({
                    "catchment_name": name,
                    "status": "INSIDE_CATCHMENT",
                    "distance_km": 0.0
                })
            else:
                dist_km = self.distance_point_to_polygon_km(lat, lon, poly)
                if dist_km <= buffer_km:
                    results.append({
                        "catchment_name": name,
                        "status": "NEAR_CATCHMENT",
                        "distance_km": round(dist_km, 2)
                    })

        return results

    def evaluate_alert_polygon_string(
        self, polygon_str: str, buffer_km: float = 25.0
    ) -> List[Dict[str, Any]]:
        """Evaluate an NDMA alert polygon string against registered catchment polygons.

        Polygon string format: "lat,lon lat,lon ..."
        """
        self.load_catchments()
        results = []

        if not SHAPELY_AVAILABLE:
            return results

        try:
            pts = []
            for token in polygon_str.strip().split():
                parts = token.split(',')
                if len(parts) >= 2:
                    lat, lon = float(parts[0]), float(parts[1])
                    pts.append((lon, lat))

            if len(pts) < 3:
                return results

            alert_poly = Polygon(pts)
            if not alert_poly.is_valid:
                alert_poly = alert_poly.buffer(0)

            for name, catchment_poly in self.shapely_polygons.items():
                if alert_poly.intersects(catchment_poly):
                    results.append({
                        "catchment_name": name,
                        "status": "INTERSECTS_CATCHMENT",
                        "distance_km": 0.0
                    })
                else:
                    # Calculate distance between polygons
                    try:
                        p1, p2 = nearest_points(alert_poly.boundary, catchment_poly.boundary)
                        _, _, distance_m = GEOD.inv(p1.x, p1.y, p2.x, p2.y)
                        dist_km = distance_m / 1000.0
                        if dist_km <= buffer_km:
                            results.append({
                                "catchment_name": name,
                                "status": "NEAR_CATCHMENT",
                                "distance_km": round(dist_km, 2)
                            })
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Error evaluating alert polygon string: {e}")

        return results


# Global singleton instance
spatial_engine = SpatialCatchmentEngine()
