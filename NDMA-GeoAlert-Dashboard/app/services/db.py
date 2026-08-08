import os

import pymysql


def get_connection(database=True):
    connection_config = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "cursorclass": pymysql.cursors.DictCursor,
    }

    if database:
        connection_config["database"] = os.getenv("DB_NAME")

    ca_cert = os.getenv("DB_CA_CERT")

    if ca_cert:
        connection_config["ssl"] = {"ca": ca_cert}

    return pymysql.connect(**connection_config)
