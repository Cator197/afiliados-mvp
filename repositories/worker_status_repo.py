from database import get_connection


def upsert_worker_heartbeat(worker_id, last_heartbeat_em, last_status=None, last_message=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO worker_heartbeats (
            worker_id,
            last_heartbeat_em,
            last_status,
            last_message,
            updated_em
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(worker_id) DO UPDATE SET
            last_heartbeat_em = excluded.last_heartbeat_em,
            last_status = excluded.last_status,
            last_message = excluded.last_message,
            updated_em = excluded.updated_em
        """,
        (worker_id, last_heartbeat_em, last_status, last_message, last_heartbeat_em),
    )

    conn.commit()
    conn.close()


def get_worker_status(worker_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if worker_id:
        cursor.execute(
            """
            SELECT *
            FROM worker_heartbeats
            WHERE worker_id = ?
            """,
            (worker_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return row

    cursor.execute(
        """
        SELECT *
        FROM worker_heartbeats
        ORDER BY last_heartbeat_em DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()

    conn.close()
    return row
