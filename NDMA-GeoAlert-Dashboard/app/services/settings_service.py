from app.services.db import get_connection

DEFAULT_SETTINGS = {
    "scheduler_minutes": "15",
    "request_delay_seconds": "1",
    "max_retries": "3",
    "retry_delay_seconds": "5",
    "warning_distance_km": "50",
    "severity_extreme": "#d20f39",
    "severity_severe": "#fe640b",
    "severity_moderate": "#df8e1d",
    "severity_minor": "#40a02b",
    "alert_rain_3h_red": "30.0",
    "alert_rain_3h_yellow": "15.0",
    "alert_rain_24h_red": "100.0",
    "alert_rain_24h_yellow": "50.0",
    "alert_gust_red": "25.0",
    "alert_gust_yellow": "15.0",
}


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

            result = {row["setting_key"]: row["setting_value"] for row in rows}

            # Fill defaults if missing
            updated = False
            for k, v in DEFAULT_SETTINGS.items():
                if k not in result:
                    result[k] = v
                    cursor.execute(
                        "INSERT INTO settings (setting_key, setting_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                        (k, v),
                    )
                    updated = True

            if updated:
                connection.commit()

            return result
    finally:
        connection.close()


def update_settings(data):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for key, value in data.items():
                cursor.execute(
                    """
                    INSERT INTO settings (setting_key, setting_value)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE setting_value = %s
                    """,
                    (key, value, value),
                )
            connection.commit()
    finally:
        connection.close()
