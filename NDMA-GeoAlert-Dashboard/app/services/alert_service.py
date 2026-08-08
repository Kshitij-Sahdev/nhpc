import json
import logging
from datetime import datetime

from app.services.db import get_connection


def save_alert(alert_data, state_id):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            polygons_json = json.dumps(alert_data["polygons"])

            cursor.execute(
                """
                INSERT INTO alerts (

                    alert_identifier,
                    state_id,
                    event,
                    headline_en,
                    urgency,
                    severity,
                    certainty,
                    effective,
                    onset,
                    expires,
                    polygons

                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s
                )

                ON DUPLICATE KEY UPDATE

                    state_id = VALUES(state_id),
                    event = VALUES(event),
                    headline_en = VALUES(headline_en),
                    urgency = VALUES(urgency),
                    severity = VALUES(severity),
                    certainty = VALUES(certainty),
                    effective = VALUES(effective),
                    onset = VALUES(onset),
                    expires = VALUES(expires),
                    polygons = VALUES(polygons)
                """,
                (
                    alert_data["identifier"],
                    state_id,
                    alert_data["event"],
                    alert_data["headline_en"],
                    alert_data["urgency"],
                    alert_data["severity"],
                    alert_data["certainty"],
                    alert_data["effective"],
                    alert_data["onset"],
                    alert_data["expires"],
                    polygons_json,
                ),
            )

            cursor.execute(
                """
                SELECT alert_id
                FROM alerts
                WHERE alert_identifier = %s
                """,
                alert_data["identifier"],
            )

            alert = cursor.fetchone()
            alert_id = alert["alert_id"]

            cursor.execute(
                """
                DELETE FROM alert_districts
                WHERE alert_id = %s
                """,
                alert_id,
            )

            for district_code in alert_data["district_codes"]:
                cursor.execute(
                    """
                    INSERT IGNORE INTO
                    alert_districts (alert_id, district_code)
                    VALUES (%s, %s)
                    """,
                    (alert_id, district_code),
                )
        connection.commit()
    finally:
        connection.close()


def get_all_alerts():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    state_id,
                    state_name
                FROM states
                WHERE is_selected = TRUE
                ORDER BY state_name
                """)
            states = cursor.fetchall()

            # Circular import temporary fix
            from app.services.warning_service import get_projects_by_alerts

            projects_by_alert = get_projects_by_alerts()

            state_dashboard = []
            for state in states:
                cursor.execute(
                    """
                    SELECT
                        alert_id,
                        alert_identifier,
                        event,
                        headline_en,
                        urgency,
                        severity,
                        certainty,
                        effective,
                        onset,
                        expires
                    FROM alerts
                    WHERE state_id = %s
                    ORDER BY effective DESC
                    """,
                    state["state_id"],
                )
                alerts = cursor.fetchall()

                for alert in alerts:
                    cursor.execute(
                        """
                        SELECT districts.district_name
                        FROM alert_districts
                        JOIN districts
                        ON alert_districts.district_code = districts.district_code
                        WHERE alert_districts.alert_id = %s
                        """,
                        alert["alert_id"],
                    )
                    districts = cursor.fetchall()

                    alert["district_names"] = [
                        district["district_name"] for district in districts
                    ]

                    alert["affected_projects"] = projects_by_alert.get(
                        alert["alert_id"], []
                    )

                state_dashboard.append(
                    {"state_name": state["state_name"], "alerts": alerts}
                )
            state_dashboard.sort(
                key=lambda state: (len(state["alerts"]) == 0, state["state_name"])
            )
            return state_dashboard
    finally:
        connection.close()


def get_polygon_data():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    alert_id,
                    severity,
                    polygons
                FROM alerts
                """)
            polygon_alerts = cursor.fetchall()
            for alert in polygon_alerts:
                if alert["polygons"]:
                    alert["polygons"] = json.loads(alert["polygons"])
                else:
                    alert["polygons"] = []
            return polygon_alerts
    finally:
        connection.close()


def get_active_alerts():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                    SELECT
                        alert_id,
                        event,
                        severity,
                        expires,
                        polygons
                    FROM alerts
                """)
            alerts = cursor.fetchall()
            for alert in alerts:
                if alert["polygons"]:
                    alert["polygons"] = json.loads(alert["polygons"])
                else:
                    alert["polygons"] = []
            return alerts
    finally:
        connection.close()


def get_alert_by_id(alert_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM alerts
                WHERE alert_id = %s
                """,
                (alert_id,),
            )
            return cursor.fetchone()
    finally:
        connection.close()


def delete_expired_alerts():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM alerts
                WHERE expires IS NOT NULL
                AND expires < NOW()
                """)
        logging.info("Expired XMLs successfully deleted")
        connection.commit()
    except Exception as error_msg:
        logging.error(f"Error: Failed to delete expired XMLs")
        logging.error(error_msg)
    finally:
        connection.close()


def alert_exists(alert_identifier):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM alerts
                WHERE alert_identifier = %s
                LIMIT 1
                """,
                alert_identifier,
            )

            return cursor.fetchone() is not None
    finally:
        connection.close()


def is_alert_expired(alert_data):
    expires = alert_data.get("expires")
    if not expires:
        return False
    return expires < datetime.now(expires.tzinfo)
