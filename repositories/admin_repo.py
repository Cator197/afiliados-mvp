import hashlib
from database import get_connection


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_admin_by_username(username: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM admin_users
        WHERE username = ? AND ativo = 1
    """, (username,))
    row = cursor.fetchone()

    conn.close()
    return row


def validate_admin_login(username: str, password: str):
    admin = get_admin_by_username(username)
    if not admin:
        return None

    password_hash = hash_password(password)
    if admin["password_hash"] != password_hash:
        return None

    return admin