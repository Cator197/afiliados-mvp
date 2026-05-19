import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection
from repositories.usuarios_repo import hash_user_password


class ExtensionEndpointsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        temp_data_dir = Path(cls.tmpdir.name)

        config.DATA_DIR = temp_data_dir
        config.LOGS_DIR = temp_data_dir / "logs"
        config.DB_PATH = temp_data_dir / "afiliados_test.db"

        from init_db import create_tables, ensure_usuarios_password_column, ensure_jobs_worker_columns, ensure_jobs_platform_column, ensure_links_platform_column, ensure_worker_heartbeats_table, ensure_cadastro_solicitacoes_table

        create_tables()
        ensure_usuarios_password_column()
        ensure_jobs_worker_columns()
        ensure_jobs_platform_column()
        ensure_links_platform_column()
        ensure_worker_heartbeats_table()
        ensure_cadastro_solicitacoes_table()

        from app import app
        app.config["SECRET_KEY"] = "test-secret"
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios")
        cursor.execute(
            """
            INSERT INTO usuarios (codigo_usuario, nome, password_hash, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("CAIO001", "Caio", hash_user_password("senha123"), 1, "2026-01-01 00:00:00"),
        )
        conn.commit()
        conn.close()

    def _login(self):
        return self.client.post("/api/login", json={"codigo_usuario": "CAIO001", "senha": "senha123"})

    def test_extension_status_logged_out(self):
        response = self.client.get("/api/extension/status")
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["logged_in"])
        self.assertIsNone(payload["user"])

    def test_extension_status_logged_in(self):
        self._login()
        response = self.client.get("/api/extension/status")
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["logged_in"])
        self.assertEqual(payload["user"]["codigo_usuario"], "CAIO001")

    def test_product_preview_missing_url(self):
        response = self.client.post("/api/extension/product-preview", json={})
        self.assertEqual(response.status_code, 400)

    def test_product_preview_invalid_url(self):
        response = self.client.post("/api/extension/product-preview", json={"url": "abc"})
        payload = response.get_json()
        self.assertFalse(payload["is_valid"])

    def test_product_preview_google_incompatible(self):
        response = self.client.post("/api/extension/product-preview", json={"url": "https://google.com"})
        payload = response.get_json()
        self.assertFalse(payload["is_valid"])

    def test_product_preview_mercadolivre_home(self):
        response = self.client.post("/api/extension/product-preview", json={"url": "https://www.mercadolivre.com.br"})
        payload = response.get_json()
        self.assertTrue(payload["is_valid"])
        self.assertFalse(payload["is_product_page"])

    def test_product_preview_mercadolivre_product(self):
        response = self.client.post("/api/extension/product-preview", json={"url": "https://www.mercadolivre.com.br/MLB-123456789-smartphone"})
        payload = response.get_json()
        self.assertTrue(payload["is_valid"])
        self.assertTrue(payload["is_product_page"])
        self.assertEqual(payload["estimated_cashback_percent"], 3)

    def test_product_preview_fake_domain_is_rejected(self):
        response = self.client.post("/api/extension/product-preview", json={"url": "https://mercadolivre.com.br.fake.com/p/MLB123"})
        payload = response.get_json()
        self.assertFalse(payload["is_valid"])


if __name__ == "__main__":
    unittest.main()
