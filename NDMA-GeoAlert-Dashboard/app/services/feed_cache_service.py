from app.services.db import get_connection


def get_feed_cache(feed_slug):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    etag,
                    last_modified
                FROM feed_cache
                WHERE feed_slug = %s
                """,
                feed_slug,
            )
            return cursor.fetchone()
    finally:
        connection.close()


def update_feed_cache(feed_slug, etag, last_modified):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO feed_cache (

                    feed_slug,
                    etag,
                    last_modified

                )
                VALUES (
                    %s,
                    %s,
                    %s
                )

                ON DUPLICATE KEY UPDATE

                    etag = VALUES(etag),
                    last_modified =
                    VALUES(last_modified)
                """,
                (feed_slug, etag, last_modified),
            )
        connection.commit()
    finally:
        connection.close()
