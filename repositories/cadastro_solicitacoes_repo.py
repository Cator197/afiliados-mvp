from database import get_connection


def create_cadastro_solicitacao(nome_completo, email, codigo_indicacao, status, criado_em, atualizado_em, whatsapp=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO cadastro_solicitacoes (
            nome_completo,
            email,
            codigo_indicacao,
            whatsapp,
            status,
            observacoes_admin,
            criado_em,
            atualizado_em
        )
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            nome_completo,
            email,
            codigo_indicacao,
            whatsapp,
            status,
            criado_em,
            atualizado_em,
        ),
    )

    solicitacao_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return solicitacao_id


def get_cadastro_solicitacao_by_id(solicitacao_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM cadastro_solicitacoes
        WHERE id = ?
        """,
        (solicitacao_id,),
    )
    row = cursor.fetchone()

    conn.close()
    return row


def list_cadastro_solicitacoes(status=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT *
        FROM cadastro_solicitacoes
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY id DESC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    conn.close()
    return rows


def update_cadastro_solicitacao_status(solicitacao_id, status=None, observacoes_admin=None, atualizado_em=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE cadastro_solicitacoes
        SET status = COALESCE(?, status),
            observacoes_admin = COALESCE(?, observacoes_admin),
            atualizado_em = COALESCE(?, atualizado_em)
        WHERE id = ?
        """,
        (
            status,
            observacoes_admin,
            atualizado_em,
            solicitacao_id,
        ),
    )

    conn.commit()
    rows_updated = cursor.rowcount
    conn.close()

    return rows_updated
