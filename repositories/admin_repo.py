import hashlib
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_connection


LEGACY_SHA256_HEX_LENGTH = 64


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def _hash_password_legacy(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _is_legacy_sha256_hash(password_hash: str) -> bool:
    if not password_hash or len(password_hash) != LEGACY_SHA256_HEX_LENGTH:
        return False
    return all(char in "0123456789abcdef" for char in password_hash.lower())


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


def _update_admin_password_hash(admin_id: int, password_hash: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE admin_users
        SET password_hash = ?
        WHERE id = ?
        """,
        (password_hash, admin_id),
    )
    conn.commit()
    conn.close()


def _password_matches(admin_password_hash: str, raw_password: str) -> bool:
    if _is_legacy_sha256_hash(admin_password_hash):
        return admin_password_hash == _hash_password_legacy(raw_password)
    return check_password_hash(admin_password_hash, raw_password)


def validate_admin_login(username: str, password: str):
    admin = get_admin_by_username(username)
    if not admin:
        return None

    stored_hash = admin["password_hash"]
    if not _password_matches(stored_hash, password):
        return None

    if _is_legacy_sha256_hash(stored_hash):
        _update_admin_password_hash(admin["id"], hash_password(password))

    return admin
