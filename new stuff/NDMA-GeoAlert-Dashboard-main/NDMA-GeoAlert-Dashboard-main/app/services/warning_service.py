import logging
from collections import defaultdict

from pyproj import Geod
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points

from app.services.alert_service import get_active_alerts
from app.services.db import get_connection
from app.services.settings_service import get_settings
from app.services.site_service import get_gnd_sites, get_project_sites

GEOD = Geod(ellps="WGS84")


def parse_polygons(polygon_string):
    coordinates = polygon_string.strip().split()

    points = []

    for coordinate in coordinates:
        lat, lng = map(float, coordinate.split(","))
        points.append((lng, lat))
    return Polygon(points)


def distance_to_polygon_km(point, polygon):
    nearest_geom, _ = nearest_points(polygon.boundary, point)
    _, _, distance_m = GEOD.inv(point.x, point.y, nearest_geom.x, nearest_geom.y)
    return distance_m / 1000


def evaluate_site_against_alert(site, alert):
    settings = get_settings()
    warning_distance_km = int(settings["warning_distance_km"])
    point = Point(site["lng"], site["lat"])

    nearest_distance = None

    for polygon_string in alert["polygons"]:
        polygon = parse_polygons(polygon_string)

        if polygon.contains(point):
            return {"warning_type": "INSIDE_ALERT_POLYGON", "distance_km": 0}

        distance_km = distance_to_polygon_km(point, polygon)

        if nearest_distance is None or distance_km < nearest_distance:
            nearest_distance = distance_km

    if nearest_distance is not None and nearest_distance <= warning_distance_km:
        return {
            "warning_type": "NEAR_ALERT_POLYGON",
            "distance_km": round(nearest_distance, 2),
        }

    return None


def generate_warnings():
    warnings = []

    alerts = get_active_alerts()
    project_sites = get_project_sites()
    gnd_sites = get_gnd_sites()

    project_lookup = {}

    for project in project_sites:
        project_lookup[project["project_id"]] = project

    sites = []

    for site in project_sites:
        sites.append(
            {
                "site_type": "PROJECT",
                "site_name": site["project_name"],
                "project_id": site["project_id"],
                "lat": site["lat"],
                "lng": site["lng"],
            }
        )

    for site in gnd_sites:
        sites.append(
            {
                "site_type": "GND",
                "site_name": site["site_name"],
                "project_id": site["project_id"],
                "lat": site["lat"],
                "lng": site["lng"],
            }
        )

    best_warnings = {}

    for site in sites:
        for alert in alerts:
            warning = evaluate_site_against_alert(site, alert)

            if not warning:
                continue

            warning_key = (site["site_name"], alert["alert_id"])

            candidate = {
                "site_type": site["site_type"],
                "site_name": site["site_name"],
                "project_id": site["project_id"],
                "alert_id": alert["alert_id"],
                "event": alert["event"],
                "severity": alert["severity"],
                **warning,
            }

            existing = best_warnings.get(warning_key)
            if existing is None or candidate["distance_km"] < existing["distance_km"]:
                best_warnings[warning_key] = candidate

    return list(best_warnings.values())


def refresh_warnings():
    warnings = generate_warnings()
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM warnings")
            for warning in warnings:
                cursor.execute(
                    """
                    INSERT INTO warnings (
                        alert_id,
                        site_type,
                        site_name,
                        project_id,
                        warning_type,
                        distance_km
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        warning["alert_id"],
                        warning["site_type"],
                        warning["site_name"],
                        warning["project_id"],
                        warning["warning_type"],
                        warning["distance_km"],
                    ),
                )
        logging.info("Warnings regenerated and stored in DB")
        connection.commit()
    except Exception as error_msg:
        logging.error(f"Error: Failed to regenerate warnings")
        logging.error(error_msg)
    finally:
        connection.close()


def get_all_warnings():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    project_id,
                    project_name
                FROM project_sites
                """)
            project_names = {
                row["project_id"]: row["project_name"] for row in cursor.fetchall()
            }

            cursor.execute("""
                SELECT
                    warnings.alert_id,
                    warnings.site_type,
                    warnings.site_name,
                    warnings.project_id,
                    warnings.warning_type,
                    warnings.distance_km,

                    alerts.event,
                    alerts.severity,
                    alerts.expires,

                    states.state_name

                FROM warnings

                JOIN alerts
                    ON warnings.alert_id = alerts.alert_id

                JOIN states
                    ON alerts.state_id = states.state_id

                ORDER BY
                    warnings.distance_km
                """)
            warnings = cursor.fetchall()

        projects = {}

        for warning in warnings:
            project_id = warning["project_id"]

            if project_id is None:
                continue

            project_name = project_names.get(project_id, f"Project {project_id}")

            if project_id not in projects:
                projects[project_id] = {
                    "project_id": project_id,
                    "project_name": project_name,
                    "alerts": {},
                }

            alert_id = warning["alert_id"]

            if alert_id not in projects[project_id]["alerts"]:
                projects[project_id]["alerts"][alert_id] = {
                    "alert_id": alert_id,
                    "event": warning["event"],
                    "severity": warning["severity"],
                    "state_name": warning["state_name"],
                    "expires": warning["expires"],
                    "warning_type": warning["warning_type"],
                    "distance_km": warning["distance_km"],
                    "affected_sites": [],
                }

            alert = projects[project_id]["alerts"][alert_id]

            alert["affected_sites"].append(
                {
                    "site_type": warning["site_type"],
                    "site_name": warning["site_name"],
                    "distance_km": warning["distance_km"],
                }
            )

            alert["distance_km"] = min(alert["distance_km"], warning["distance_km"])

        result = []

        for project in projects.values():
            project["alerts"] = list(project["alerts"].values())

            result.append(project)

        return sorted(
            result,
            key=lambda project: len(project["alerts"]),
            reverse=True,
        )

    finally:
        connection.close()


def get_project_warnings(project_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    project_id,
                    project_name
                FROM project_sites
                WHERE project_id = %s
                """,
                (project_id,),
            )
            project = cursor.fetchone()

            if not project:
                return {
                    "project_exists": False,
                    "message": "No associated project site in database.",
                }

            cursor.execute(
                """
                SELECT
                    warnings.alert_id,
                    warnings.project_id,
                    warnings.site_type,
                    warnings.site_name,
                    warnings.warning_type,
                    warnings.distance_km,

                    alerts.event,
                    alerts.severity,
                    alerts.expires

                FROM warnings

                JOIN alerts
                    ON warnings.alert_id = alerts.alert_id

                WHERE
                    warnings.project_id = %s

                ORDER BY
                    warnings.distance_km
                """,
                (project_id,),
            )

            warnings = cursor.fetchall()

            if not warnings:
                return {
                    "project_exists": True,
                    "project": project,
                    "message": "No active alerts affecting this project site.",
                }

            alerts = {}

            for warning in warnings:
                alert_id = warning["alert_id"]

                if alert_id not in alerts:
                    alerts[alert_id] = {
                        "alert_id": alert_id,
                        "project_id": warning["project_id"],
                        "event": warning["event"],
                        "severity": warning["severity"],
                        "expires": warning["expires"],
                        "warning_type": warning["warning_type"],
                        "distance_km": warning["distance_km"],
                        "affected_sites": [],
                    }

                alerts[alert_id]["affected_sites"].append(
                    {
                        "site_type": warning["site_type"],
                        "site_name": warning["site_name"],
                        "distance_km": warning["distance_km"],
                    }
                )

                alerts[alert_id]["distance_km"] = min(
                    alerts[alert_id]["distance_km"], warning["distance_km"]
                )

            grouped_warnings = list(alerts.values())

            return {
                "project_exists": True,
                "project": project,
                "warning_count": len(grouped_warnings),
                "warnings": grouped_warnings,
            }
    finally:
        connection.close()


def get_projects_by_alerts():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    alert_id,
                    project_id,
                    site_name
                FROM warnings
                ORDER BY site_name
                """)
            rows = cursor.fetchall()

        projects_by_alert = defaultdict(list)
        for row in rows:
            projects_by_alert[row["alert_id"]].append(
                {"project_id": row["project_id"], "project_name": row["site_name"]}
            )

        return projects_by_alert
    finally:
        connection.close()


def search_projects(query):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    project_sites.project_id,
                    project_sites.project_name,

                    EXISTS (
                        SELECT 1
                        FROM warnings
                        WHERE warnings.project_id = project_sites.project_id
                    ) AS has_warnings

                FROM project_sites

                WHERE
                    LOWER(project_sites.project_name)
                    LIKE LOWER(%s)

                ORDER BY
                    project_sites.project_name

                LIMIT 20
                """,
                (f"%{query}%",),
            )

            return cursor.fetchall()
    finally:
        connection.close()
