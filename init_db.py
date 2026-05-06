from datetime import datetime

from database import get_connection, ensure_directories
from config import ADMIN_DEFAULT_USERNAME, ADMIN_DEFAULT_PASSWORD
from repositories.admin_repo import hash_password


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_usuario TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        email TEXT,
        password_hash TEXT,
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT NOT NULL,
        must_change_password INTEGER NOT NULL DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        url_original TEXT NOT NULL,
        plataforma TEXT NOT NULL DEFAULT 'mercadolivre',
        status TEXT NOT NULL,
        resultado_link TEXT,
        mensagem_erro TEXT,
        criado_em TEXT NOT NULL,
        iniciado_em TEXT,
        finalizado_em TEXT,
        assigned_worker_id TEXT,
        claimed_em TEXT,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS links_gerados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        job_id TEXT,
        url_original TEXT NOT NULL,
        url_afiliado TEXT,
        plataforma TEXT NOT NULL DEFAULT 'mercadolivre',
        status TEXT NOT NULL,
        percentual_cashback REAL NOT NULL DEFAULT 50.0,
        descricao_item TEXT,
        foto_item_url TEXT,
        valor_produto REAL,
        percentual_comissao REAL,
        valor_comissao REAL,
        valor_cashback REAL,
        metadados_status TEXT NOT NULL DEFAULT 'pendente',
        metadados_erro TEXT,
        metadados_atualizado_em TEXT,
        observacoes_admin TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cadastro_solicitacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_completo TEXT NOT NULL,
        email TEXT NOT NULL,
        codigo_indicacao TEXT,
        whatsapp TEXT,
        status TEXT NOT NULL DEFAULT 'novo',
        observacoes_admin TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_usuario TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'novo',
        observacoes_admin TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        FOREIGN KEY (codigo_usuario) REFERENCES usuarios(codigo_usuario)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS worker_heartbeats (
        worker_id TEXT PRIMARY KEY,
        last_heartbeat_em TEXT NOT NULL,
        last_status TEXT,
        last_message TEXT,
        updated_em TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def ensure_jobs_worker_columns():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(jobs)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "assigned_worker_id" not in existing_columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN assigned_worker_id TEXT")

    if "claimed_em" not in existing_columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN claimed_em TEXT")

    conn.commit()
    conn.close()


def ensure_jobs_platform_column():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(jobs)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "plataforma" not in existing_columns:
        cursor.execute(
            "ALTER TABLE jobs ADD COLUMN plataforma TEXT NOT NULL DEFAULT 'mercadolivre'"
        )

    cursor.execute(
        """
        UPDATE jobs
        SET plataforma = 'mercadolivre'
        WHERE plataforma IS NULL OR TRIM(plataforma) = ''
        """
    )

    conn.commit()
    conn.close()


def ensure_links_platform_column():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(links_gerados)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "plataforma" not in existing_columns:
        cursor.execute(
            "ALTER TABLE links_gerados ADD COLUMN plataforma TEXT NOT NULL DEFAULT 'mercadolivre'"
        )

    cursor.execute(
        """
        UPDATE links_gerados
        SET plataforma = 'mercadolivre'
        WHERE plataforma IS NULL OR TRIM(plataforma) = ''
        """
    )

    conn.commit()
    conn.close()


def ensure_links_metadata_columns():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(links_gerados)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "descricao_item" not in existing_columns:
        cursor.execute("ALTER TABLE links_gerados ADD COLUMN descricao_item TEXT")

    if "foto_item_url" not in existing_columns:
        cursor.execute("ALTER TABLE links_gerados ADD COLUMN foto_item_url TEXT")

    if "valor_produto" not in existing_columns:
        cursor.execute("ALTER TABLE links_gerados ADD COLUMN valor_produto REAL")

    if "percentual_comissao" not in existing_columns:
        cursor.execute("ALTER TABLE links_gerados ADD COLUMN percentual_comissao REAL")

    if "metadados_status" not in existing_columns:
        cursor.execute("ALTER TABLE links_gerados ADD COLUMN metadados_status TEXT NOT NULL DEFAULT 'pendente'")

    if "metadados_erro" not in existing_columns:
        cursor.execute("ALTER TABLE links_gerados ADD COLUMN metadados_erro TEXT")

    if "metadados_atualizado_em" not in existing_columns:
        cursor.execute("ALTER TABLE links_gerados ADD COLUMN metadados_atualizado_em TEXT")

    cursor.execute(
        """
        UPDATE links_gerados
        SET metadados_status = 'pendente'
        WHERE metadados_status IS NULL OR TRIM(metadados_status) = ''
        """
    )

    conn.commit()
    conn.close()


def ensure_usuarios_password_column():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(usuarios)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "password_hash" not in existing_columns:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN password_hash TEXT")

    if "must_change_password" not in existing_columns:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")

    conn.commit()
    conn.close()


def ensure_usuarios_email_column():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(usuarios)")
    existing_columns = {row["name"] for row in cursor.fetchall()}
    if "email" not in existing_columns:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
    conn.commit()
    conn.close()


def ensure_worker_heartbeats_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS worker_heartbeats (
        worker_id TEXT PRIMARY KEY,
        last_heartbeat_em TEXT NOT NULL,
        last_status TEXT,
        last_message TEXT,
        updated_em TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def ensure_worker_diagnostics_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS worker_diagnostics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id TEXT,
        status TEXT NOT NULL,
        etapa TEXT,
        mensagem TEXT,
        detalhes TEXT,
        iniciou_em TEXT,
        finalizou_em TEXT,
        duracao_ms INTEGER,
        criado_em TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()


def ensure_cadastro_solicitacoes_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cadastro_solicitacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_completo TEXT NOT NULL,
        email TEXT NOT NULL,
        codigo_indicacao TEXT,
        whatsapp TEXT,
        status TEXT NOT NULL DEFAULT 'novo',
        observacoes_admin TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    )
    """)

    cursor.execute("PRAGMA table_info(cadastro_solicitacoes)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "whatsapp" not in existing_columns:
        cursor.execute("ALTER TABLE cadastro_solicitacoes ADD COLUMN whatsapp TEXT")

    conn.commit()
    conn.close()


def ensure_password_reset_requests_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_usuario TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'novo',
        observacoes_admin TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        FOREIGN KEY (codigo_usuario) REFERENCES usuarios(codigo_usuario)
    )
    """)

    conn.commit()
    conn.close()


def ensure_password_reset_tokens_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        email TEXT,
        token_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ativo',
        criado_em TEXT NOT NULL,
        expira_em TEXT NOT NULL,
        usado_em TEXT,
        ip_solicitante TEXT,
        user_agent TEXT,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    )
    """)
    conn.commit()
    conn.close()


def create_default_admin():
    if not ADMIN_DEFAULT_USERNAME or not ADMIN_DEFAULT_PASSWORD:
        print("[INFO] Admin padrão não configurado. Defina ADMIN_DEFAULT_USERNAME e ADMIN_DEFAULT_PASSWORD para bootstrap explícito.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM admin_users WHERE username = ?",
        (ADMIN_DEFAULT_USERNAME,)
    )
    existing = cursor.fetchone()

    if not existing:
        cursor.execute("""
            INSERT INTO admin_users (username, password_hash, ativo, criado_em)
            VALUES (?, ?, ?, ?)
        """, (
            ADMIN_DEFAULT_USERNAME,
            hash_password(ADMIN_DEFAULT_PASSWORD),
            1,
            now_str()
        ))
        conn.commit()
        print("[OK] Admin bootstrap criado via variáveis de ambiente.")
    else:
        print("[INFO] Admin bootstrap já existe.")

    conn.close()


def create_sample_users():
    conn = get_connection()
    cursor = conn.cursor()

    usuarios = [
        ("CAIO001", "Usuário Teste 1"),
        ("CAIO002", "Usuário Teste 2")
    ]

    for codigo_usuario, nome in usuarios:
        cursor.execute(
            "SELECT id FROM usuarios WHERE codigo_usuario = ?",
            (codigo_usuario,)
        )
        existing = cursor.fetchone()

        if not existing:
            cursor.execute("""
                INSERT INTO usuarios (codigo_usuario, nome, ativo, criado_em, must_change_password)
                VALUES (?, ?, ?, ?, ?)
            """, (
                codigo_usuario,
                nome,
                1,
                now_str(),
                0,
            ))

    conn.commit()
    conn.close()
    print("[OK] Usuários de teste verificados.")


if __name__ == "__main__":
    ensure_directories()
    create_tables()
    ensure_usuarios_password_column()
    ensure_jobs_worker_columns()
    ensure_jobs_platform_column()
    ensure_links_platform_column()
    ensure_links_metadata_columns()
    ensure_worker_heartbeats_table()
    ensure_cadastro_solicitacoes_table()
    ensure_password_reset_requests_table()
    create_default_admin()
    create_sample_users()
    print("[OK] Banco inicializado com sucesso.")
