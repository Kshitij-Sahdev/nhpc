from app.services.db import get_connection


def get_settings():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    setting_key,
                    setting_value
                FROM settings
                """)
            rows = cursor.fetchall()

            return {row["setting_key"]: row["setting_value"] for row in rows}
    finally:
        connection.close()


def update_settings(data):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for key, value in data.items():
                cursor.execute(
                    """
                    UPDATE settings
                    SET setting_value = %s
                    WHERE setting_key = %s
                    """,
                    (value, key),
                )
            connection.commit()
    finally:
        connection.close()
