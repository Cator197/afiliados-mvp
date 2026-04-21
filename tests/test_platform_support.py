import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection
from repositories.usuarios_repo import hash_user_password
from services.platform_utils import (
    PLATFORM_MERCADOLIVRE,
    PLATFORM_SHOPEE,
    detect_platform_from_url,
)


class PlatformSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        temp_data_dir = Path(cls.tmpdir.name)

        config.DATA_DIR = temp_data_dir
        config.LOGS_DIR = temp_data_dir / "logs"
        config.DB_PATH = temp_data_dir / "afiliados_test.db"

        from init_db import (
            create_tables,
            ensure_cadastro_solicitacoes_table,
            ensure_jobs_platform_column,
            ensure_jobs_worker_columns,
            ensure_links_platform_column,
            ensure_usuarios_password_column,
            ensure_worker_heartbeats_table,
        )

        create_tables()
        ensure_usuarios_password_column()
        ensure_jobs_worker_columns()
        ensure_jobs_platform_column()
        ensure_links_platform_column()
        ensure_worker_heartbeats_table()
        ensure_cadastro_solicitacoes_table()

        from app import app

        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM links_gerados")
        cursor.execute("DELETE FROM jobs")
        cursor.execute("DELETE FROM usuarios")
        cursor.execute(
            """
            INSERT INTO usuarios (codigo_usuario, nome, password_hash, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("USR001", "Usuário 1", hash_user_password("senha123"), 1, "2026-01-01 00:00:00"),
        )
        conn.commit()
        conn.close()

    def _login(self):
        return self.client.post(
            "/api/login",
            json={"codigo_usuario": "USR001", "senha": "senha123"},
        )

    def test_detect_platform_from_url(self):
        self.assertEqual(
            detect_platform_from_url("https://produto.mercadolivre.com.br/MLB-123"),
            PLATFORM_MERCADOLIVRE,
        )
        self.assertEqual(
            detect_platform_from_url("https://shopee.com.br/product/1/2"),
            PLATFORM_SHOPEE,
        )
        self.assertIsNone(detect_platform_from_url("https://example.com/produto"))

    def test_mercadolivre_job_creation_persists_platform(self):
        self._login()

        response = self.client.post(
            "/api/solicitar-link",
            json={
                "codigo_usuario": "USR001",
                "url": "https://www.mercadolivre.com.br/oferta/xpto",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["plataforma"], PLATFORM_MERCADOLIVRE)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT plataforma, status FROM jobs WHERE id = ?", (payload["job_id"],))
        row = cursor.fetchone()
        conn.close()

        self.assertEqual(row["plataforma"], PLATFORM_MERCADOLIVRE)
        self.assertEqual(row["status"], "na_fila")

    def test_shopee_is_recognized_but_not_processed_as_ready(self):
        self._login()

        response = self.client.post(
            "/api/solicitar-link",
            json={
                "codigo_usuario": "USR001",
                "url": "https://shopee.com.br/produto-teste-i.123.456",
            },
        )

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["plataforma"], PLATFORM_SHOPEE)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT plataforma, status, mensagem_erro FROM jobs WHERE id = ?",
            (payload["job_id"],),
        )
        row = cursor.fetchone()
        conn.close()

        self.assertEqual(row["plataforma"], PLATFORM_SHOPEE)
        self.assertEqual(row["status"], "erro")
        self.assertIn("implantação", row["mensagem_erro"])

    def test_legacy_data_remains_compatible_after_platform_migration(self):
        legacy_db = Path(self.tmpdir.name) / "legacy.db"

        import sqlite3

        conn = sqlite3.connect(legacy_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                url_original TEXT NOT NULL,
                status TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE links_gerados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                job_id TEXT,
                url_original TEXT NOT NULL,
                url_afiliado TEXT,
                status TEXT NOT NULL,
                percentual_cashback REAL NOT NULL DEFAULT 50.0,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            "INSERT INTO jobs (id, usuario_id, url_original, status, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("job-legacy", 1, "https://www.mercadolivre.com.br/item", "concluido", "2026-01-01 00:00:00"),
        )
        cursor.execute(
            """
            INSERT INTO links_gerados (
                usuario_id, job_id, url_original, url_afiliado, status, percentual_cashback, criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "job-legacy", "https://www.mercadolivre.com.br/item", "https://afiliado", "aguardando_verificacao", 50, "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
        )
        conn.commit()
        conn.close()

        import database

        original_db_path = config.DB_PATH
        original_database_db_path = database.DB_PATH
        config.DB_PATH = legacy_db
        database.DB_PATH = legacy_db
        try:
            from init_db import ensure_jobs_platform_column, ensure_links_platform_column

            ensure_jobs_platform_column()
            ensure_links_platform_column()

            migrated_conn = get_connection()
            migrated_cursor = migrated_conn.cursor()
            migrated_cursor.execute("SELECT plataforma FROM jobs WHERE id = 'job-legacy'")
            jobs_row = migrated_cursor.fetchone()
            migrated_cursor.execute("SELECT plataforma FROM links_gerados WHERE job_id = 'job-legacy'")
            links_row = migrated_cursor.fetchone()
            migrated_conn.close()

            self.assertEqual(jobs_row["plataforma"], PLATFORM_MERCADOLIVRE)
            self.assertEqual(links_row["plataforma"], PLATFORM_MERCADOLIVRE)
        finally:
            config.DB_PATH = original_db_path
            database.DB_PATH = original_database_db_path


if __name__ == "__main__":
    unittest.main()
