from app.services.db import get_connection


def get_project_sites():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    project_id,
                    project_name,
                    lat,
                    lng
                FROM project_sites
                """
            )
            return cursor.fetchall()
    finally:
        connection.close()

def get_gnd_sites():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                    SELECT
                        site_id,
                        site_name,
                        project_id,
                        lat,
                        lng
                    FROM gnd_sites
                """
            )
            return cursor.fetchall()
    finally:
        connection.close()