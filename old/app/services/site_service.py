"""
Site Service — Registered Hydro Power Plants, Catchments, and River G&D Stations.
"""

from typing import Any, Dict, List
from app.services import database
from app.services.spatial_engine import spatial_engine


def get_project_sites() -> List[Dict[str, Any]]:
    """Returns registered hydro power stations."""
    return database.get_all_plants()


def get_catchment_data() -> Dict[str, Dict[str, Any]]:
    """Returns parsed catchment boundary polygons."""
    return spatial_engine.load_catchments()
