from database import get_connection


RESET_REQUEST_STATUS_OPEN = "novo"
RESET_REQUEST_STATUS_SENT = "senha_enviada"
RESET_REQUEST_STATUS_DONE = "concluido"
RESET_REQUEST_STATUS_IGNORED = "ignorado"


RESET_REQUEST_ACTIVE_STATUSES = (
    RESET_REQUEST_STATUS_OPEN,
    RESET_REQUEST_STATUS_SENT,
)


def create_password_reset_request(codigo_usuario: str, criado_em: str, atualizado_em: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO password_reset_requests (
            codigo_usuario,
            status,
            observacoes_admin,
            criado_em,
            atualizado_em
        )
        VALUES (?, ?, NULL, ?, ?)
        """,
        (codigo_usuario, RESET_REQUEST_STATUS_OPEN, criado_em, atualizado_em),
    )

    request_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return request_id


def get_password_reset_request_by_id(request_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM password_reset_requests
        WHERE id = ?
        """,
        (request_id,),
    )
    row = cursor.fetchone()

    conn.close()
    return row


def get_active_password_reset_request(codigo_usuario: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM password_reset_requests
        WHERE codigo_usuario = ?
          AND status IN (?, ?)
        ORDER BY id DESC
        LIMIT 1
        """,
        (codigo_usuario, *RESET_REQUEST_ACTIVE_STATUSES),
    )
    row = cursor.fetchone()

    conn.close()
    return row


def list_password_reset_requests(status=None, codigo_usuario=None, page=1, limit=20):
    conn = get_connection()
    cursor = conn.cursor()

    base_query = """
        FROM password_reset_requests pr
        LEFT JOIN usuarios u ON u.codigo_usuario = pr.codigo_usuario
        WHERE 1=1
    """
    params = []

    if status:
        base_query += " AND pr.status = ?"
        params.append(status)

    if codigo_usuario:
        base_query += " AND pr.codigo_usuario LIKE ?"
        params.append(f"%{codigo_usuario}%")

    cursor.execute(f"SELECT COUNT(*) AS total {base_query}", tuple(params))
    total = cursor.fetchone()["total"]

    page = max(page, 1)
    limit = max(limit, 1)
    offset = (page - 1) * limit

    query = f"""
        SELECT pr.*, u.nome AS usuario_nome, u.ativo AS usuario_ativo
        {base_query}
        ORDER BY pr.id DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(query, tuple(params + [limit, offset]))
    rows = cursor.fetchall()

    conn.close()
    return rows, total


def update_password_reset_request(request_id: int, status=None, observacoes_admin=None, atualizado_em=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE password_reset_requests
        SET status = COALESCE(?, status),
            observacoes_admin = COALESCE(?, observacoes_admin),
            atualizado_em = COALESCE(?, atualizado_em)
        WHERE id = ?
        """,
        (status, observacoes_admin, atualizado_em, request_id),
    )

    conn.commit()
    rows_updated = cursor.rowcount
    conn.close()
    return rows_updated


def close_active_password_reset_requests(codigo_usuario: str, atualizado_em: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE password_reset_requests
        SET status = ?,
            atualizado_em = ?
        WHERE codigo_usuario = ?
          AND status IN (?, ?)
        """,
        (RESET_REQUEST_STATUS_DONE, atualizado_em, codigo_usuario, *RESET_REQUEST_ACTIVE_STATUSES),
    )

    conn.commit()
    rows_updated = cursor.rowcount
    conn.close()
    return rows_updated
