from database import get_connection


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