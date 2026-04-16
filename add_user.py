from datetime import datetime
from database import get_connection


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


codigo = input("Código do usuário: ").strip()
nome = input("Nome do usuário: ").strip()

conn = get_connection()
cursor = conn.cursor()

cursor.execute("""
INSERT INTO usuarios (codigo_usuario, nome, ativo, criado_em)
VALUES (?, ?, 1, ?)
""", (codigo, nome, now()))

conn.commit()
conn.close()

print("Usuário criado com sucesso.")