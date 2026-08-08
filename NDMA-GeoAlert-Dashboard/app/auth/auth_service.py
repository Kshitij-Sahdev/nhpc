import os

from werkzeug.security import check_password_hash


def validate_admin_login(username, password):
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH")

    if username != admin_username:
        return False

    return check_password_hash(admin_password_hash, password)
