from database import get_connection
from werkzeug.security import check_password_hash, generate_password_hash


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


def get_user_by_codigo_any_status(codigo_usuario: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE codigo_usuario = ?
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


def get_user_by_email(email: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE LOWER(email) = LOWER(?)", (email,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_user_by_codigo_or_email(identificador: str):
    valor = (identificador or "").strip()
    if not valor:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM usuarios
        WHERE UPPER(codigo_usuario) = UPPER(?)
           OR LOWER(email) = LOWER(?)
        LIMIT 1
        """,
        (valor, valor),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def list_users():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, codigo_usuario, nome, email, ativo, criado_em, must_change_password
        FROM usuarios
        ORDER BY codigo_usuario ASC
        """
    )
    rows = cursor.fetchall()

    conn.close()
    return rows


def create_user(codigo_usuario: str, nome: str, password: str, criado_em: str, ativo: int = 1, must_change_password: int = 1, email: str | None = None) -> int:
    password_hash = hash_user_password(password)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO usuarios (codigo_usuario, nome, email, password_hash, ativo, criado_em, must_change_password)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (codigo_usuario, nome, email, password_hash, ativo, criado_em, must_change_password),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def hash_user_password(password: str) -> str:
    return generate_password_hash(password)


def update_user_password(user_id: int, password: str, must_change_password: int = 0) -> int:
    password_hash = hash_user_password(password)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE usuarios
        SET password_hash = ?,
            must_change_password = ?
        WHERE id = ?
        """,
        (password_hash, must_change_password, user_id),
    )
    conn.commit()
    rows_updated = cursor.rowcount
    conn.close()
    return rows_updated


def update_user_active_status(user_id: int, ativo: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE usuarios
        SET ativo = ?
        WHERE id = ?
        """,
        (ativo, user_id),
    )
    conn.commit()
    rows_updated = cursor.rowcount
    conn.close()
    return rows_updated


def update_user_email(user_id: int, email: str | None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET email = ? WHERE id = ?", (email, user_id))
    conn.commit()
    rows_updated = cursor.rowcount
    conn.close()
    return rows_updated


def user_has_password(user_id: int) -> bool:
    user = get_user_by_id(user_id)
    if not user:
        return False
    return bool(user["password_hash"])


def validate_user_login(codigo_usuario: str, password: str) -> dict:
    usuario = get_user_by_codigo_any_status(codigo_usuario)

    if not usuario:
        return {"ok": False, "erro": "Credenciais inválidas.", "status_code": 401}

    if not usuario["ativo"]:
        return {"ok": False, "erro": "Usuário inativo.", "status_code": 403}

    password_hash = usuario["password_hash"]
    if not password_hash:
        return {"ok": False, "erro": "Usuário sem senha definida. Solicite a criação de senha ao suporte.", "status_code": 403}

    if not check_password_hash(password_hash, password):
        return {"ok": False, "erro": "Credenciais inválidas.", "status_code": 401}

    return {"ok": True, "usuario": usuario}
