from app.services.db import get_connection


def get_selected_states():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT state_id, state_name, feed_slug
                FROM states
                WHERE is_selected = TRUE
            """
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        connection.close()


def get_all_states():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT state_id, state_name, is_selected
                FROM states
                ORDER BY state_name
                """)
            return cursor.fetchall()
    finally:
        connection.close()


def update_selected_states(selected_state_ids):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE states
                SET is_selected = FALSE
                """)
            if selected_state_ids:
                placeholders = ", ".join(["%s"] * len(selected_state_ids))
                query = f"""
                    UPDATE states
                    SET is_selected = TRUE
                    WHERE state_id IN ({placeholders})
                """
                cursor.execute(query, selected_state_ids)
        connection.commit()
    finally:
        connection.close()
