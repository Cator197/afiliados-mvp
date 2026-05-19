from database import get_connection


def create_link_gerado(usuario_id, job_id, url_original, plataforma, url_afiliado,
                       status, percentual_cashback, criado_em, atualizado_em,
                       descricao_item=None, foto_item_url=None, valor_produto=None,
                       percentual_comissao=None, metadados_status="pendente",
                       metadados_erro=None, metadados_atualizado_em=None, source="site"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO links_gerados (
            usuario_id, job_id, url_original, plataforma, url_afiliado, status,
            percentual_cashback, descricao_item, foto_item_url, valor_produto, percentual_comissao,
            metadados_status, metadados_erro, metadados_atualizado_em, criado_em, atualizado_em, source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        usuario_id,
        job_id,
        url_original,
        plataforma,
        url_afiliado,
        status,
        percentual_cashback,
        descricao_item,
        foto_item_url,
        valor_produto,
        percentual_comissao,
        metadados_status,
        metadados_erro,
        metadados_atualizado_em,
        criado_em,
        atualizado_em,
        source
    ))

    conn.commit()
    conn.close()


def get_links_by_usuario_id(usuario_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM links_gerados
        WHERE usuario_id = ?
        ORDER BY id DESC
    """, (usuario_id,))
    rows = cursor.fetchall()

    conn.close()
    return rows


def get_link_by_id(link_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT lg.*, u.codigo_usuario, u.nome
        FROM links_gerados lg
        JOIN usuarios u ON u.id = lg.usuario_id
        WHERE lg.id = ?
    """, (link_id,))
    row = cursor.fetchone()

    conn.close()
    return row


def get_all_links(status=None, codigo_usuario=None, plataforma=None, descricao=None, source=None, page=1, limit=20):
    conn = get_connection()
    cursor = conn.cursor()

    base_query = """
        FROM links_gerados lg
        JOIN usuarios u ON u.id = lg.usuario_id
        WHERE 1=1
    """
    params = []

    if status:
        base_query += " AND lg.status = ?"
        params.append(status)

    if codigo_usuario:
        base_query += " AND u.codigo_usuario = ?"
        params.append(codigo_usuario)

    if plataforma:
        base_query += " AND lg.plataforma = ?"
        params.append(plataforma)

    if descricao:
        base_query += " AND LOWER(COALESCE(lg.descricao_item, '')) LIKE ?"
        params.append(f"%{descricao.lower()}%")
    if source:
        base_query += " AND COALESCE(lg.source, 'site') = ?"
        params.append(source)

    cursor.execute(f"SELECT COUNT(*) AS total {base_query}", tuple(params))
    total = cursor.fetchone()["total"]

    query = f"""
        SELECT lg.*, u.codigo_usuario, u.nome
        {base_query}
        ORDER BY lg.id DESC
        LIMIT ? OFFSET ?
    """
    page = max(page, 1)
    limit = max(limit, 1)
    offset = (page - 1) * limit

    cursor.execute(query, tuple(params + [limit, offset]))
    rows = cursor.fetchall()

    conn.close()
    return rows, total


def update_link_admin_fields(link_id, status=None, valor_comissao=None,
                             percentual_cashback=None, valor_cashback=None,
                             observacoes_admin=None, atualizado_em=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE links_gerados
        SET status = COALESCE(?, status),
            valor_comissao = COALESCE(?, valor_comissao),
            percentual_cashback = COALESCE(?, percentual_cashback),
            valor_cashback = COALESCE(?, valor_cashback),
            observacoes_admin = COALESCE(?, observacoes_admin),
            atualizado_em = COALESCE(?, atualizado_em)
        WHERE id = ?
    """, (
        status,
        valor_comissao,
        percentual_cashback,
        valor_cashback,
        observacoes_admin,
        atualizado_em,
        link_id
    ))

    conn.commit()
    conn.close()


def update_product_metadata(link_id, descricao_item=None, foto_item_url=None,
                            valor_produto=None, percentual_comissao=None,
                            metadados_status=None, metadados_erro=None,
                            metadados_atualizado_em=None, atualizado_em=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE links_gerados
        SET descricao_item = COALESCE(?, descricao_item),
            foto_item_url = COALESCE(?, foto_item_url),
            valor_produto = COALESCE(?, valor_produto),
            percentual_comissao = COALESCE(?, percentual_comissao),
            metadados_status = COALESCE(?, metadados_status),
            metadados_erro = COALESCE(?, metadados_erro),
            metadados_atualizado_em = COALESCE(?, metadados_atualizado_em),
            atualizado_em = COALESCE(?, atualizado_em)
        WHERE id = ?
    """, (
        descricao_item,
        foto_item_url,
        valor_produto,
        percentual_comissao,
        metadados_status,
        metadados_erro,
        metadados_atualizado_em,
        atualizado_em,
        link_id
    ))

    conn.commit()
    conn.close()


def claim_next_metadata_job(atualizado_em):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            SELECT id, job_id, usuario_id, url_original, percentual_cashback
            FROM links_gerados
            WHERE metadados_status = 'pendente'
            ORDER BY id ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()

        if not row:
            conn.commit()
            return None

        cursor.execute(
            """
            UPDATE links_gerados
            SET metadados_status = 'processando',
                metadados_erro = NULL,
                metadados_atualizado_em = ?,
                atualizado_em = ?
            WHERE id = ?
            """,
            (atualizado_em, atualizado_em, row["id"]),
        )

        cursor.execute(
            """
            SELECT id, job_id, usuario_id, url_original, percentual_cashback
            FROM links_gerados
            WHERE id = ?
            """,
            (row["id"],),
        )
        claimed = cursor.fetchone()
        conn.commit()
        return claimed
    finally:
        conn.close()


def reenfileirar_metadados(link_id, atualizado_em):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE links_gerados
        SET metadados_status = 'pendente',
            metadados_erro = NULL,
            metadados_atualizado_em = ?,
            atualizado_em = ?
        WHERE id = ?
        """,
        (atualizado_em, atualizado_em, link_id),
    )

    conn.commit()
    conn.close()


def enqueue_metadata_refresh(link_id, atualizado_em):
    reenfileirar_metadados(link_id=link_id, atualizado_em=atualizado_em)


def recalcular_valores(link_id, percentual_cashback=None, atualizado_em=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT valor_produto, percentual_comissao, percentual_cashback
        FROM links_gerados
        WHERE id = ?
    """, (link_id,))
    link = cursor.fetchone()

    if not link:
        conn.close()
        return None

    percentual_cashback_base = percentual_cashback
    if percentual_cashback_base is None:
        percentual_cashback_base = link["percentual_cashback"]

    valor_comissao = None
    valor_cashback = None

    if link["valor_produto"] is not None and link["percentual_comissao"] is not None:
        valor_comissao = round(link["valor_produto"] * (link["percentual_comissao"] / 100), 2)
        if percentual_cashback_base is not None:
            valor_cashback = round(valor_comissao * (percentual_cashback_base / 100), 2)

    cursor.execute("""
        UPDATE links_gerados
        SET percentual_cashback = COALESCE(?, percentual_cashback),
            valor_comissao = ?,
            valor_cashback = ?,
            atualizado_em = COALESCE(?, atualizado_em)
        WHERE id = ?
    """, (
        percentual_cashback,
        valor_comissao,
        valor_cashback,
        atualizado_em,
        link_id
    ))

    conn.commit()
    conn.close()

    return {
        "valor_comissao": valor_comissao,
        "valor_cashback": valor_cashback,
        "percentual_cashback": percentual_cashback_base,
    }


def get_user_history_summary(usuario_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            SUM(CASE WHEN status = 'compra_confirmada' THEN 1 ELSE 0 END) AS quantidade_pendente,
            SUM(CASE WHEN status = 'cashback_pago' THEN 1 ELSE 0 END) AS quantidade_pago,
            SUM(CASE WHEN status = 'compra_nao_confirmada' THEN 1 ELSE 0 END) AS quantidade_perdido,
            COALESCE(SUM(CASE WHEN status = 'compra_confirmada' THEN COALESCE(valor_cashback, 0) ELSE 0 END), 0) AS valor_pendente,
            COALESCE(SUM(CASE WHEN status = 'cashback_pago' THEN COALESCE(valor_cashback, 0) ELSE 0 END), 0) AS valor_pago
        FROM links_gerados
        WHERE usuario_id = ?
    """, (usuario_id,))

    summary = cursor.fetchone()
    conn.close()

    if not summary:
        return {
            "quantidade_pendente": 0,
            "quantidade_pago": 0,
            "quantidade_perdido": 0,
            "valor_pendente": 0,
            "valor_pago": 0,
        }

    return {
        "quantidade_pendente": summary["quantidade_pendente"] or 0,
        "quantidade_pago": summary["quantidade_pago"] or 0,
        "quantidade_perdido": summary["quantidade_perdido"] or 0,
        "valor_pendente": summary["valor_pendente"] or 0,
        "valor_pago": summary["valor_pago"] or 0,
    }
