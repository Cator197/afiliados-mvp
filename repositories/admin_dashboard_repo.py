from database import get_connection


def count_links_by_status(status: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM links_gerados WHERE status = ?", (status,))
    total = cursor.fetchone()["total"]
    conn.close()
    return total


def get_recent_links_by_status(status: str, limit: int = 5):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT lg.id, lg.criado_em, lg.descricao_item, lg.valor_produto, lg.valor_cashback, u.codigo_usuario, u.nome
        FROM links_gerados lg
        JOIN usuarios u ON u.id = lg.usuario_id
        WHERE lg.status = ?
        ORDER BY lg.id DESC
        LIMIT ?
        """,
        (status, max(limit, 1)),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def count_users_without_email() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM usuarios
        WHERE email IS NULL OR TRIM(email) = ''
        """
    )
    total = cursor.fetchone()["total"]
    conn.close()
    return total


def get_users_without_email(limit: int = 5):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, codigo_usuario, nome
        FROM usuarios
        WHERE email IS NULL OR TRIM(email) = ''
        ORDER BY codigo_usuario ASC
        LIMIT ?
        """,
        (max(limit, 1),),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def count_pending_signup_requests() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM cadastro_solicitacoes
        WHERE status IN ('novo', 'em_analise')
        """
    )
    total = cursor.fetchone()["total"]
    conn.close()
    return total


def count_pending_password_reset_requests() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM password_reset_requests
        WHERE status = 'novo'
        """
    )
    total = cursor.fetchone()["total"]
    conn.close()
    return total


def get_last_worker_diagnostic():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM worker_diagnostics ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row


def get_last_worker_heartbeat():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM worker_heartbeats ORDER BY last_heartbeat_em DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row
