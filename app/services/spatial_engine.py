"""
NHPC Professional Spatial Catchment Engine.

Uses Shapely and PyProj (WGS84 ellipsoid) to perform high-precision geospatial operations:
1. Parses `Catchment_NHPC.KML` to build Shapely geometries and simplifies polygons (0.001° tolerance) for 60 FPS map panning.
2. Caches GeoJSON representation of catchments and monitored asset points.
3. Evaluates coordinates against catchment polygons:
   - INSIDE_CATCHMENT: point contained inside catchment polygon (distance_km = 0.0).
   - NEARBY_CATCHMENT: point outside every polygon; calculates distance in km to nearest boundary.
4. Attaches catchment_id, catchment_name, risk_level, distance_km, and monitored_assets list.
"""

import os
from typing import Dict, List, Optional, Tuple, Any
import logging

import math
try:
    from shapely.geometry import Point, Polygon, box
    from shapely.ops import nearest_points
    from pyproj import Geod
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

logger = logging.getLogger("nhpc.spatial")
GEOD = Geod(ellps="WGS84") if SHAPELY_AVAILABLE else None


def parse_kml_coordinates(coords_str: str) -> List[Tuple[float, float]]:
    """Parse KML coordinate string into (lon, lat) tuples."""
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


VERIFIED_PROJECT_COORDS = {
    "Tanakpur HEP": (29.0725, 80.1189),
    "Subansiri Lower HEP": (27.5536, 94.2586),
    "Teesta Low Dam IV HEP": (26.9642, 88.4722),
    "Kishanganga HEP": (34.6111, 74.6733),
    "Dibang Multipurpose Project": (28.2250, 95.7720),
    "Nimoo Bazgo HEP": (34.2153, 77.1853),
    "Chamera-I HEP": (32.5966, 75.9857),
    "Ranjit Sagar Hydro Project": (32.4410, 75.7280),
    "Chamera-III HEP": (32.4598, 76.2443),
    "Chamera-II HEP": (32.4734, 76.2552),
    "Churi G&D": (32.4596, 76.3626),
    "Baloo G&D": (32.5450, 76.2108),
    "Baira Siul Power Station": (32.8063, 76.1418),
    "Bhaledh": (32.7114, 76.3283),
    "Siul": (32.8242, 75.9232),
    "Surangani G&D": (32.7255, 76.1137),
    "Chutak Power Station": (34.4591, 76.0746),
    "Uri-I Power Station": (34.1450, 74.0450),
    "Uri-II Power Station": (34.0921, 74.0318),
    "Salal Power Station": (33.1378, 74.8044),
    "Parbati-III HEP": (31.7398, 77.2576),
    "Parbati-II HEP": (31.7836, 77.3275),
    "Jiwa": (31.8653, 77.4779),
    "Jigrai": (31.9458, 77.4617),
    "Hurla": (31.8980, 77.3876)
}


class SpatialCatchmentEngine:
    def __init__(self, kml_path: Optional[str] = None):
        self.kml_path = kml_path or "Catchment_NHPC.KML"
        self.catchments: Dict[str, Dict[str, Any]] = {}
        self.shapely_polygons: Dict[str, Any] = {}
        self.geojson_cache: Optional[Dict[str, Any]] = None
        self.grids_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._loaded = False

    def load_catchments(self) -> Dict[str, Dict[str, Any]]:
        """Parse KML file, simplify polygon geometries, and build deduplicated catchment objects."""
        if self._loaded:
            return self.catchments

        if not os.path.exists(self.kml_path):
            logger.warning(f"KML file not found at {self.kml_path}")
            return {}

        try:
            import update_forecasts
            plants_kml = update_forecasts.parse_kml(self.kml_path)

            unique_idx = 1
            for plant in plants_kml:
                raw_name = plant.get("name", f"Catchment-{unique_idx}")
                name = clean_project_name(raw_name)

                # Ensure unique key for each of the 27 placemarks
                if name in self.catchments:
                    name = f"{name} ({unique_idx})"

                boundaries = plant.get("boundaries", [])
                if boundaries and len(boundaries[0]) >= 3:
                    pts_leaflet = boundaries[0] # [lat, lon]
                    pts_geo = [[p[1], p[0]] for p in pts_leaflet] # [lon, lat] for Shapely

                    poly_obj = None
                    simplified_pts = pts_geo

                    if SHAPELY_AVAILABLE:
                        try:
                            poly = Polygon(pts_geo)
                            if not poly.is_valid:
                                poly = poly.buffer(0)
                            
                            simple_poly = poly.simplify(0.001, preserve_topology=True)
                            poly_obj = simple_poly if simple_poly.is_valid else poly
                            self.shapely_polygons[name] = poly_obj

                            if hasattr(poly_obj, 'exterior') and poly_obj.exterior:
                                simplified_pts = list(poly_obj.exterior.coords)
                        except Exception as e:
                            logger.error(f"Failed to simplify polygon for {name}: {e}")

                    # Calculate centroid directly from Catchment KML/JSON geometry
                    if SHAPELY_AVAILABLE and poly_obj and poly_obj.is_valid:
                        c_pt = poly_obj.centroid
                        lat, lon = round(c_pt.y, 4), round(c_pt.x, 4)
                    else:
                        lat = round(sum(p[0] for p in pts_leaflet) / len(pts_leaflet), 4)
                        lon = round(sum(p[1] for p in pts_leaflet) / len(pts_leaflet), 4)

                    catchment_id = f"CATCH-{unique_idx:03d}"
                    self.catchments[name] = {
                        "catchment_id": catchment_id,
                        "catchment_name": name,
                        "centroid": {"lat": lat, "lon": lon},
                        "coordinates": [[p[1], p[0]] for p in simplified_pts], # Leaflet [lat, lon]
                        "geo_coordinates": simplified_pts, # Shapely [lon, lat]
                        "monitored_assets": [name]
                    }
                    unique_idx += 1

            self._loaded = True
            logger.info(f"Loaded {len(self.catchments)} unique project catchments from {self.kml_path}")
        except Exception as e:
            logger.error(f"Error parsing KML catchment file: {e}")

        return self.catchments

    def get_geojson(self) -> Dict[str, Any]:
        """Returns cached GeoJSON FeatureCollection of all simplified catchment boundaries."""
        if self.geojson_cache:
            return self.geojson_cache

        self.load_catchments()
        features = []

        for name, data in self.catchments.items():
            coords_geojson = [[[p[0], p[1]] for p in data["geo_coordinates"]]]
            features.append({
                "type": "Feature",
                "id": data["catchment_id"],
                "properties": {
                    "catchment_id": data["catchment_id"],
                    "catchment_name": name,
                    "centroid": data["centroid"],
                    "monitored_assets": data["monitored_assets"]
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": coords_geojson
                }
            })

        self.geojson_cache = {
            "type": "FeatureCollection",
            "features": features
        }
        return self.geojson_cache

    def generate_catchment_grids(self, cell_size_km: float = 12.0) -> Dict[str, List[Dict[str, Any]]]:
        """Subdivide each catchment into 12km x 12km grid squares and calculate geo centroids."""
        if self.grids_cache:
            return self.grids_cache

        self.load_catchments()
        all_grids: Dict[str, List[Dict[str, Any]]] = {}

        for name, data in self.catchments.items():
            poly = self.shapely_polygons.get(name)
            if not poly or not SHAPELY_AVAILABLE:
                # Fallback single grid at centroid if polygon unavailable
                c_lat = data["centroid"]["lat"]
                c_lon = data["centroid"]["lon"]
                all_grids[name] = [{
                    "grid_id": f"{data['catchment_id']}-G001",
                    "catchment_name": name,
                    "catchment_id": data["catchment_id"],
                    "centroid": {"lat": c_lat, "lon": c_lon},
                    "coordinates": [[c_lat - 0.05, c_lon - 0.05], [c_lat + 0.05, c_lon - 0.05],
                                    [c_lat + 0.05, c_lon + 0.05], [c_lat - 0.05, c_lon + 0.05],
                                    [c_lat - 0.05, c_lon - 0.05]]
                }]
                continue

            minx, miny, maxx, maxy = poly.bounds
            avg_lat = (miny + maxy) / 2.0
            lat_step = cell_size_km / 111.0
            lon_step = cell_size_km / (111.0 * math.cos(math.radians(avg_lat)))

            cat_grids = []
            grid_idx = 1
            y = miny
            while y < maxy:
                x = minx
                while x < maxx:
                    cell_box = box(x, y, x + lon_step, y + lat_step)
                    if poly.intersects(cell_box):
                        try:
                            inter = poly.intersection(cell_box)
                            cent = inter.centroid
                            cent_lat = round(cent.y, 4)
                            cent_lon = round(cent.x, 4)
                        except Exception:
                            cent_lat = round(y + lat_step / 2.0, 4)
                            cent_lon = round(x + lon_step / 2.0, 4)

                        grid_id = f"{data['catchment_id']}-G{grid_idx:03d}"
                        cat_grids.append({
                            "grid_id": grid_id,
                            "catchment_name": name,
                            "catchment_id": data["catchment_id"],
                            "grid_index": grid_idx,
                            "centroid": {"lat": cent_lat, "lon": cent_lon},
                            "coordinates": [
                                [round(y, 5), round(x, 5)],
                                [round(y + lat_step, 5), round(x, 5)],
                                [round(y + lat_step, 5), round(x + lon_step, 5)],
                                [round(y, 5), round(x + lon_step, 5)],
                                [round(y, 5), round(x, 5)]
                            ]
                        })
                        grid_idx += 1
                    x += lon_step
                y += lat_step

            if not cat_grids:
                c_lat = data["centroid"]["lat"]
                c_lon = data["centroid"]["lon"]
                cat_grids.append({
                    "grid_id": f"{data['catchment_id']}-G001",
                    "catchment_name": name,
                    "catchment_id": data["catchment_id"],
                    "grid_index": 1,
                    "centroid": {"lat": c_lat, "lon": c_lon},
                    "coordinates": [[c_lat - 0.05, c_lon - 0.05], [c_lat + 0.05, c_lon - 0.05],
                                    [c_lat + 0.05, c_lon + 0.05], [c_lat - 0.05, c_lon + 0.05],
                                    [c_lat - 0.05, c_lon - 0.05]]
                })

            all_grids[name] = cat_grids

        self.grids_cache = all_grids
        return self.grids_cache

    def get_grids_geojson(self) -> Dict[str, Any]:
        """Returns GeoJSON FeatureCollection of all 12km x 12km grid squares."""
        grids_dict = self.generate_catchment_grids()
        features = []
        for name, grid_list in grids_dict.items():
            for g in grid_list:
                # Convert Leaflet [lat, lon] to GeoJSON [lon, lat]
                coords_geo = [[[p[1], p[0]] for p in g["coordinates"]]]
                features.append({
                    "type": "Feature",
                    "id": g["grid_id"],
                    "properties": {
                        "grid_id": g["grid_id"],
                        "catchment_name": name,
                        "catchment_id": g["catchment_id"],
                        "centroid": g["centroid"]
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": coords_geo
                    }
                })
        return {
            "type": "FeatureCollection",
            "features": features
        }

    def distance_point_to_polygon_km(self, lat: float, lon: float, poly: Any) -> float:
        """Calculate exact WGS84 geodesic distance in kilometers from point to polygon boundary."""
        if not SHAPELY_AVAILABLE or GEOD is None or poly is None:
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

    def evaluate_coordinate(self, lat: float, lon: float, buffer_km: float = 25.0) -> Dict[str, Any]:
        """Evaluate a lat/lon coordinate against all catchment polygons.

        Returns match dictionary with containment status (INSIDE_CATCHMENT or NEARBY_CATCHMENT)
        and distance to boundary in km.
        """
        self.load_catchments()

        if not SHAPELY_AVAILABLE:
            return {"status": "UNKNOWN", "distance_km": 0.0, "catchment_name": "Unknown"}

        point = Point(lon, lat)
        nearest_match = None
        min_distance = 99999.0

        for name, poly in self.shapely_polygons.items():
            if poly.contains(point):
                catchment_meta = self.catchments.get(name, {})
                return {
                    "catchment_id": catchment_meta.get("catchment_id", "CATCH-000"),
                    "catchment_name": name,
                    "status": "INSIDE_CATCHMENT",
                    "distance_km": 0.0,
                    "warning_type": "INSIDE_CATCHMENT"
                }

            dist_km = self.distance_point_to_polygon_km(lat, lon, poly)
            if dist_km < min_distance:
                min_distance = dist_km
                catchment_meta = self.catchments.get(name, {})
                nearest_match = {
                    "catchment_id": catchment_meta.get("catchment_id", "CATCH-000"),
                    "catchment_name": name,
                    "status": "NEARBY_CATCHMENT" if dist_km <= buffer_km else "OUTSIDE",
                    "distance_km": round(dist_km, 2),
                    "warning_type": "NEARBY_CATCHMENT" if dist_km <= buffer_km else "OUTSIDE"
                }

        return nearest_match or {"status": "OUTSIDE", "distance_km": 9999.0, "catchment_name": "None"}

    def evaluate_location_against_catchments(self, lat: float, lon: float, buffer_km: float = 25.0) -> List[Dict[str, Any]]:
        """Evaluates a coordinate location against all catchment polygons and returns matches within buffer_km."""
        self.load_catchments()
        matches = []

        if not SHAPELY_AVAILABLE:
            return matches

        point = Point(lon, lat)

        for name, poly in self.shapely_polygons.items():
            if poly.contains(point):
                catchment_meta = self.catchments.get(name, {})
                matches.append({
                    "catchment_id": catchment_meta.get("catchment_id", "CATCH-000"),
                    "catchment_name": name,
                    "status": "INSIDE_CATCHMENT",
                    "distance_km": 0.0,
                    "warning_type": "INSIDE_CATCHMENT"
                })
            else:
                dist_km = self.distance_point_to_polygon_km(lat, lon, poly)
                if dist_km <= buffer_km:
                    catchment_meta = self.catchments.get(name, {})
                    matches.append({
                        "catchment_id": catchment_meta.get("catchment_id", "CATCH-000"),
                        "catchment_name": name,
                        "status": "NEARBY_CATCHMENT",
                        "distance_km": round(dist_km, 2),
                        "warning_type": "NEARBY_CATCHMENT"
                    })

        return matches

    def evaluate_alert_polygon_string(self, poly_str: str, buffer_km: float = 25.0) -> List[Dict[str, Any]]:
        """Parses CAP alert polygon string and evaluates spatial intersection or proximity to catchment polygons."""
        self.load_catchments()
        matches = []

        if not SHAPELY_AVAILABLE or not poly_str:
            return matches

        pts_geo = []
        for token in poly_str.strip().split():
            parts = token.split(',')
            if len(parts) >= 2:
                try:
                    p1, p2 = float(parts[0]), float(parts[1])
                    # Detect if lat,lon or lon,lat
                    if abs(p1) <= 90.0 and abs(p2) <= 180.0:
                        pts_geo.append((p2, p1)) # (lon, lat)
                    else:
                        pts_geo.append((p1, p2))
                except ValueError:
                    continue

        if len(pts_geo) < 3:
            return matches

        try:
            alert_poly = Polygon(pts_geo)
            if not alert_poly.is_valid:
                alert_poly = alert_poly.buffer(0)

            for name, c_poly in self.shapely_polygons.items():
                if alert_poly.intersects(c_poly):
                    catchment_meta = self.catchments.get(name, {})
                    matches.append({
                        "catchment_id": catchment_meta.get("catchment_id", "CATCH-000"),
                        "catchment_name": name,
                        "status": "INSIDE_CATCHMENT",
                        "distance_km": 0.0
                    })
                else:
                    dist_km = self.distance_point_to_polygon_km(c_poly.centroid.y, c_poly.centroid.x, alert_poly)
                    if dist_km <= buffer_km:
                        catchment_meta = self.catchments.get(name, {})
                        matches.append({
                            "catchment_id": catchment_meta.get("catchment_id", "CATCH-000"),
                            "catchment_name": name,
                            "status": "NEARBY_CATCHMENT",
                            "distance_km": round(dist_km, 2)
                        })
        except Exception as e:
            logger.error(f"Error evaluating alert polygon string: {e}")

        return matches


# Global singleton instance
spatial_engine = SpatialCatchmentEngine()

