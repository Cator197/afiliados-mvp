from database import get_connection


def create_job(job_id, usuario_id, url_original, status, criado_em):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO jobs (
            id, usuario_id, url_original, status, criado_em
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        job_id, usuario_id, url_original, status, criado_em
    ))

    conn.commit()
    conn.close()


def update_job_status(job_id, status, iniciado_em=None, finalizado_em=None,
                      resultado_link=None, mensagem_erro=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE jobs
        SET status = ?,
            iniciado_em = COALESCE(?, iniciado_em),
            finalizado_em = COALESCE(?, finalizado_em),
            resultado_link = COALESCE(?, resultado_link),
            mensagem_erro = COALESCE(?, mensagem_erro)
        WHERE id = ?
    """, (
        status,
        iniciado_em,
        finalizado_em,
        resultado_link,
        mensagem_erro,
        job_id
    ))

    conn.commit()
    conn.close()


def get_job_by_id(job_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM jobs
        WHERE id = ?
    """, (job_id,))
    row = cursor.fetchone()

    conn.close()
    return row


def list_jobs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM jobs
        ORDER BY criado_em DESC
    """)
    rows = cursor.fetchall()

    conn.close()
    return rows