import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection
from repositories.usuarios_repo import hash_user_password
from config import JOB_STATUS_NA_FILA


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
        cursor.execute("DELETE FROM jobs")
        cursor.execute("DELETE FROM links_gerados")
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
        self.assertEqual(payload["estimated_cashback_percent"], 3.0)
        self.assertIn("estimated_cashback_label", payload)
        self.assertIn("cashback_rule", payload)


    def test_product_preview_with_price_returns_estimated_value(self):
        response = self.client.post(
            "/api/extension/product-preview",
            json={"url": "https://www.mercadolivre.com.br/p/MLB123", "price": "R$ 419,27"},
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["estimated_cashback_percent"], 3.0)
        self.assertEqual(payload["estimated_cashback_value"], 12.58)
        self.assertEqual(payload["estimated_cashback_label"], "Cashback estimado de até R$ 12,58")
        self.assertEqual(payload["cashback_rule"]["match_type"], "default")

    def test_product_preview_invalid_price_keeps_percent_without_value(self):
        response = self.client.post(
            "/api/extension/product-preview",
            json={"url": "https://www.mercadolivre.com.br/p/MLB123", "price": "abc"},
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["estimated_cashback_percent"], 3.0)
        self.assertIsNone(payload["estimated_cashback_value"])

    def test_product_preview_never_creates_job(self):
        response = self.client.post(
            "/api/extension/product-preview",
            json={"url": "https://www.mercadolivre.com.br/p/MLB123", "price": 100},
        )
        self.assertEqual(response.status_code, 200)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) AS total FROM jobs")
        row = cursor.fetchone()
        conn.close()
        self.assertEqual(row["total"], 0)

    def test_product_preview_fake_domain_is_rejected(self):
        response = self.client.post("/api/extension/product-preview", json={"url": "https://mercadolivre.com.br.fake.com/p/MLB123"})
        payload = response.get_json()
        self.assertFalse(payload["is_valid"])

    def test_generate_link_requires_login(self):
        response = self.client.post("/api/extension/generate-link", json={"url": "https://www.mercadolivre.com.br/p/MLB123"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "login_required")

    def test_generate_link_invalid_url(self):
        self._login()
        response = self.client.post("/api/extension/generate-link", json={"url": "abc"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_url")

    def test_generate_link_not_product_page(self):
        self._login()
        response = self.client.post("/api/extension/generate-link", json={"url": "https://www.mercadolivre.com.br"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "not_product_page")

    def test_generate_link_creates_job(self):
        self._login()
        response = self.client.post("/api/extension/generate-link", json={"url": "https://www.mercadolivre.com.br/p/MLB123"})
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("job_id", payload)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status, resultado_link FROM jobs WHERE id = ?", (payload["job_id"],))
        row = cursor.fetchone()
        conn.close()
        self.assertEqual(row["status"], JOB_STATUS_NA_FILA)
        self.assertIsNone(row["resultado_link"])


    def test_generate_link_sets_source_extension(self):
        self._login()
        response = self.client.post("/api/extension/generate-link", json={"url": "https://www.mercadolivre.com.br/p/MLB123"})
        self.assertEqual(response.status_code, 201)
        job_id = response.get_json()["job_id"]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT source FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        self.assertEqual(row["source"], "extension")

    def test_extension_job_get_requires_login(self):
        response = self.client.get("/api/extension/jobs/nao-existe")
        self.assertEqual(response.status_code, 401)

    def test_extension_job_get_not_found_for_other_user(self):
        self._login()
        create = self.client.post("/api/extension/generate-link", json={"url": "https://www.mercadolivre.com.br/p/MLB123"})
        job_id = create.get_json()["job_id"]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (codigo_usuario, nome, password_hash, ativo, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("OUTRO1", "Outro", hash_user_password("senha456"), 1, "2026-01-01 00:00:00"),
        )
        conn.commit()
        conn.close()

        other_client = self.app.test_client()
        other_client.post("/api/login", json={"codigo_usuario": "OUTRO1", "senha": "senha456"})
        response = other_client.get(f"/api/extension/jobs/{job_id}")
        self.assertEqual(response.status_code, 404)

    def test_extension_job_get_success_status(self):
        self._login()
        create = self.client.post("/api/extension/generate-link", json={"url": "https://www.mercadolivre.com.br/p/MLB123"})
        job_id = create.get_json()["job_id"]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE jobs SET status = 'concluido', resultado_link = ? WHERE id = ?", ("https://afiliado.exemplo", job_id))
        conn.commit()
        conn.close()
        response = self.client.get(f"/api/extension/jobs/{job_id}")
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["affiliate_url"], "https://afiliado.exemplo")


if __name__ == "__main__":
    unittest.main()
