from database import get_connection


def create_diagnostic(
    worker_id,
    status,
    etapa,
    mensagem,
    detalhes=None,
    iniciou_em=None,
    finalizou_em=None,
    duracao_ms=None,
    criado_em=None,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO worker_diagnostics (
            worker_id, status, etapa, mensagem, detalhes,
            iniciou_em, finalizou_em, duracao_ms, criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            worker_id,
            status,
            etapa,
            mensagem,
            detalhes,
            iniciou_em,
            finalizou_em,
            duracao_ms,
            criado_em,
        ),
    )
    diagnostic_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return diagnostic_id


def update_diagnostic(diagnostic_id, **fields):
    allowed_fields = {
        "worker_id",
        "status",
        "etapa",
        "mensagem",
        "detalhes",
        "iniciou_em",
        "finalizou_em",
        "duracao_ms",
    }
    updates = {k: v for k, v in fields.items() if k in allowed_fields}
    if not updates:
        return

    set_clause = ", ".join([f"{field} = ?" for field in updates.keys()])
    values = list(updates.values()) + [diagnostic_id]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        UPDATE worker_diagnostics
        SET {set_clause}
        WHERE id = ?
        """,
        values,
    )
    conn.commit()
    conn.close()


def get_last_diagnostics(limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM worker_diagnostics
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_last_diagnostic_by_worker(worker_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM worker_diagnostics
        WHERE worker_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (worker_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def claim_pending_diagnostic(worker_id, claimed_em):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            SELECT *
            FROM worker_diagnostics
            WHERE status = 'executando'
              AND etapa = 'solicitado'
              AND (worker_id IS NULL OR TRIM(worker_id) = '' OR worker_id = ?)
            ORDER BY id ASC
            LIMIT 1
            """,
            (worker_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.commit()
            return None

        cursor.execute(
            """
            UPDATE worker_diagnostics
            SET worker_id = ?,
                etapa = 'heartbeat',
                iniciou_em = COALESCE(iniciou_em, ?),
                mensagem = 'Health check iniciado pelo worker.'
            WHERE id = ?
            """,
            (worker_id, claimed_em, row["id"]),
        )
        cursor.execute("SELECT * FROM worker_diagnostics WHERE id = ?", (row["id"],))
        claimed = cursor.fetchone()
        conn.commit()
        return claimed
    finally:
        conn.close()
