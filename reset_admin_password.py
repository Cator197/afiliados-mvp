from datetime import datetime

from database import get_connection
from repositories.admin_repo import hash_password


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    username = input("Admin username: ").strip()
    password = input("Nova senha admin: ").strip()

    if not username or not password:
        print("Username e senha são obrigatórios.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM admin_users WHERE username = ?", (username,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            "UPDATE admin_users SET password_hash = ?, ativo = 1 WHERE id = ?",
            (hash_password(password), existing["id"]),
        )
        print("Senha do admin atualizada com sucesso.")
    else:
        cursor.execute(
            """
            INSERT INTO admin_users (username, password_hash, ativo, criado_em)
            VALUES (?, ?, 1, ?)
            """,
            (username, hash_password(password), now_str()),
        )
        print("Admin criado com senha segura.")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
