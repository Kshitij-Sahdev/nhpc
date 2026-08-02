import csv
import logging
import os
from pathlib import Path

from app.services.db import get_connection

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

DISTRICTS_DATA = BASE_DIR / os.getenv("DISTRICTS_DATA")
STATES_DATA = BASE_DIR / os.getenv("STATES_DATA")
PROJECT_SITES_DATA = BASE_DIR / os.getenv("PROJECT_SITES_DATA")
GND_SITES_DATA = BASE_DIR / os.getenv("GND_SITES_DATA")


def execute_schema():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as file:
                sql_script = file.read()

            queries = sql_script.split(";")

            for query in queries:
                query = query.strip()

                if query:
                    cursor.execute(query)
        connection.commit()
    finally:
        connection.close()


def table_is_empty(cursor, table_name):
    cursor.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
    result = cursor.fetchone()
    return result["count"] == 0


def seed_states(cursor):
    try:
        logging.info(STATES_DATA)
        with open(STATES_DATA, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                sql = """
                    INSERT IGNORE INTO states (state_name, feed_slug)
                    VALUES (%s, %s)
                """
                cursor.execute(sql, (row["state_name"], row["feed_slug"]))
    except FileNotFoundError:
        raise SystemExit(
            "Initial data missing for States. Please add the data and retry execution."
        )


def seed_districts(cursor):
    try:
        with open(DISTRICTS_DATA, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                sql = """
                    INSERT IGNORE INTO districts (district_code, district_name)
                    VALUES (%s, %s)
                """
                cursor.execute(sql, (int(row["district_code"]), row["district_name"]))
    except FileNotFoundError:
        raise SystemExit(
            "Initial data missing for Districts. Please add the data and retry execution."
        )


def seed_gnd_sites(cursor):
    try:
        with open(GND_SITES_DATA, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                sql = """
                    INSERT IGNORE INTO gnd_sites (site_name, project_id, lat, lng)
                    VALUES (%s, %s, %s, %s)
                """

                project_id = None
                if row["project_id"] != "NULL":
                    project_id = int(row["project_id"])

                if (row["lat"] == "NULL") or (row["lng"] == "NULL"):
                    continue

                cursor.execute(
                    sql,
                    (
                        row["site_name"],
                        project_id,
                        float(row["lat"]),
                        float(row["lng"]),
                    ),
                )
    except FileNotFoundError:
        raise SystemExit(
            "Initial data missing for G&D Sites. Please add the data and retry execution."
        )


def seed_project_sites(cursor):
    try:
        with open(PROJECT_SITES_DATA, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                sql = """
                    INSERT IGNORE INTO project_sites (project_id, project_name, lat, lng)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(
                    sql,
                    (
                        int(row["project_id"]),
                        row["project_name"],
                        float(row["lat"]),
                        float(row["lng"]),
                    ),
                )
    except FileNotFoundError:
        raise SystemExit(
            "Initial data missing for Project Sites. Please add the data and retry execution."
        )


def seed_settings(cursor):
    try:
        cursor.execute("""
            INSERT INTO settings
            VALUES
                ('scheduler_minutes', '15'),
                ('request_delay_seconds', '1'),
                ('max_retries', '3'),
                ('retry_delay_seconds', '5'),
                ('warning_distance_km', '50'),
                ('severity_extreme', '#d20f39'),
                ('severity_severe', '#fe640b'),
                ('severity_moderate', '#df8e1d'),
                ('severity_minor', '#40a02b');
            """)
    except Exception as error_msg:
        logging.error(f"Error: Failed to seed settings.")
        logging.error(error_msg)


def seed_database():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            if table_is_empty(cursor, "states"):
                logging.info("Seeding States Data...")
                seed_states(cursor)
            if table_is_empty(cursor, "districts"):
                logging.info("Seeding Districts Data...")
                seed_districts(cursor)
            if table_is_empty(cursor, table_name="gnd_sites"):
                logging.info("Seeding GND Sites Data...")
                seed_gnd_sites(cursor)
            if table_is_empty(cursor, table_name="project_sites"):
                logging.info("Seeding Project Sites Data...")
                seed_project_sites(cursor)
            if table_is_empty(cursor, table_name="settings"):
                logging.info("Seeding Default Settings...")
                seed_settings(cursor)
        connection.commit()
    finally:
        connection.close()


def initialize_database():
    execute_schema()
    seed_database()
    logging.info("Database initialization complete.")
