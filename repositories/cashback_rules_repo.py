from database import get_connection


def list_cashback_rules(platform=None):
    conn = get_connection()
    cursor = conn.cursor()
    if platform:
        cursor.execute(
            """
            SELECT * FROM cashback_rules
            WHERE LOWER(platform) = LOWER(?)
            ORDER BY priority ASC, id ASC
            """,
            (platform,),
        )
    else:
        cursor.execute("SELECT * FROM cashback_rules ORDER BY platform ASC, priority ASC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_cashback_rule_by_id(rule_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cashback_rules WHERE id = ?", (rule_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def create_cashback_rule(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO cashback_rules (
            platform, name, match_type, match_value, cashback_percent, priority, active, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["platform"],
            data["name"],
            data["match_type"],
            data.get("match_value"),
            data["cashback_percent"],
            data["priority"],
            data["active"],
            data.get("notes"),
            data["created_at"],
            data["updated_at"],
        ),
    )
    rule_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return rule_id


def update_cashback_rule(rule_id: int, data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE cashback_rules
        SET platform = ?, name = ?, match_type = ?, match_value = ?, cashback_percent = ?,
            priority = ?, active = ?, notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            data["platform"],
            data["name"],
            data["match_type"],
            data.get("match_value"),
            data["cashback_percent"],
            data["priority"],
            data["active"],
            data.get("notes"),
            data["updated_at"],
            rule_id,
        ),
    )
    conn.commit()
    conn.close()


def toggle_cashback_rule(rule_id: int, active: int, updated_at: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE cashback_rules SET active = ?, updated_at = ? WHERE id = ?",
        (active, updated_at, rule_id),
    )
    conn.commit()
    conn.close()
