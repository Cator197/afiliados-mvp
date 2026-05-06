from database import get_connection


def count_recent_attempts_by_identifier(identificador_hash: str, minutes: int = 30) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM password_reset_attempts
        WHERE identificador_hash = ?
          AND criado_em >= datetime('now', ?)
        """,
        (identificador_hash, f"-{int(minutes)} minutes"),
    )
    total = cursor.fetchone()["total"]
    conn.close()
    return int(total)


def count_recent_attempts_by_ip(ip: str, minutes: int = 30) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM password_reset_attempts
        WHERE ip = ?
          AND criado_em >= datetime('now', ?)
        """,
        (ip, f"-{int(minutes)} minutes"),
    )
    total = cursor.fetchone()["total"]
    conn.close()
    return int(total)


def create_password_reset_attempt(
    ip: str,
    identificador_hash: str,
    usuario_id=None,
    permitido: bool = True,
    motivo: str | None = None,
    criado_em: str | None = None,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO password_reset_attempts (
            ip,
            identificador_hash,
            usuario_id,
            criado_em,
            permitido,
            motivo
        )
        VALUES (?, ?, ?, COALESCE(?, datetime('now')), ?, ?)
        """,
        (ip, identificador_hash, usuario_id, criado_em, 1 if permitido else 0, motivo),
    )
    attempt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return attempt_id
