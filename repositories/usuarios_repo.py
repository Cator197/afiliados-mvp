from database import get_connection
from werkzeug.security import generate_password_hash


def get_user_by_codigo(codigo_usuario: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE codigo_usuario = ? AND ativo = 1
    """, (codigo_usuario,))
    row = cursor.fetchone()

    conn.close()
    return row


def get_user_by_id(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()

    conn.close()
    return row


def hash_user_password(password: str) -> str:
    return generate_password_hash(password)


def update_user_password(user_id: int, password: str) -> int:
    password_hash = hash_user_password(password)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE usuarios
        SET password_hash = ?
        WHERE id = ?
        """,
        (password_hash, user_id),
    )
    conn.commit()
    rows_updated = cursor.rowcount
    conn.close()
    return rows_updated


def user_has_password(user_id: int) -> bool:
    user = get_user_by_id(user_id)
    if not user:
        return False
    return bool(user["password_hash"])
