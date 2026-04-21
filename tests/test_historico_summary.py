import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection
from repositories.usuarios_repo import hash_user_password


class HistoricoSummaryTests(unittest.TestCase):
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
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM links_gerados")
        cursor.execute("DELETE FROM usuarios")
        cursor.execute(
            """
            INSERT INTO usuarios (codigo_usuario, nome, password_hash, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?), (?, ?, ?, ?, ?)
            """,
            (
                "USR001", "Usuário 1", hash_user_password("senha123"), 1, "2026-01-01 00:00:00",
                "USR002", "Usuário 2", hash_user_password("senha123"), 1, "2026-01-01 00:00:00",
            ),
        )
        conn.commit()

        cursor.execute("SELECT id FROM usuarios WHERE codigo_usuario = ?", ("USR001",))
        self.user1_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM usuarios WHERE codigo_usuario = ?", ("USR002",))
        self.user2_id = cursor.fetchone()["id"]

        cursor.executemany(
            """
            INSERT INTO links_gerados (
                usuario_id, job_id, url_original, plataforma, url_afiliado, status,
                percentual_cashback, valor_comissao, valor_cashback,
                observacoes_admin, criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (self.user1_id, "job-1", "https://a.com/1", "mercadolivre", "https://af.com/1", "compra_confirmada", 50, 20, 10, None, "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
                (self.user1_id, "job-2", "https://a.com/2", "mercadolivre", "https://af.com/2", "compra_confirmada", 50, 30, None, None, "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
                (self.user1_id, "job-3", "https://a.com/3", "shopee", "https://af.com/3", "cashback_pago", 50, 16, 8, None, "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
                (self.user1_id, "job-4", "https://a.com/4", "shopee", "https://af.com/4", "cashback_pago", 50, 8, None, None, "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
                (self.user1_id, "job-5", "https://a.com/5", "mercadolivre", "https://af.com/5", "compra_nao_confirmada", 50, None, 0, None, "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
                (self.user1_id, "job-6", "https://a.com/6", "shopee", "https://af.com/6", "aguardando_verificacao", 50, None, 99, None, "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
                (self.user2_id, "job-7", "https://b.com/1", "mercadolivre", "https://af.com/x", "compra_confirmada", 50, 100, 50, None, "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
            ],
        )
        conn.commit()
        conn.close()

    def _login(self, codigo_usuario="USR001", senha="senha123"):
        return self.client.post(
            "/api/login",
            json={"codigo_usuario": codigo_usuario, "senha": senha},
        )

    def test_resumo_appears_and_has_expected_aggregates(self):
        self._login()
        response = self.client.get("/api/usuario/USR001/resumo")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])

        summary = payload["summary"]
        self.assertEqual(summary["quantidade_pendente"], 2)
        self.assertEqual(summary["quantidade_pago"], 2)
        self.assertEqual(summary["quantidade_perdido"], 1)
        self.assertEqual(summary["valor_pendente"], 10)
        self.assertEqual(summary["valor_pago"], 8)

    def test_resumo_blocks_access_to_other_user(self):
        self._login("USR001")
        response = self.client.get("/api/usuario/USR002/resumo")

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertFalse(payload["ok"])

    def test_historico_links_endpoint_still_works(self):
        self._login("USR001")
        response = self.client.get("/api/usuario/USR001/links")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(len(payload["links"]), 1)
        plataformas = {item["plataforma_label"] for item in payload["links"]}
        self.assertIn("Mercado Livre", plataformas)
        self.assertIn("Shopee", plataformas)

    def test_resumo_returns_zero_with_no_links(self):
        self._login("USR002")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM links_gerados WHERE usuario_id = ?", (self.user2_id,))
        conn.commit()
        conn.close()

        response = self.client.get("/api/usuario/USR002/resumo")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])

        summary = payload["summary"]
        self.assertEqual(summary["quantidade_pendente"], 0)
        self.assertEqual(summary["quantidade_pago"], 0)
        self.assertEqual(summary["quantidade_perdido"], 0)
        self.assertEqual(summary["valor_pendente"], 0)
        self.assertEqual(summary["valor_pago"], 0)


if __name__ == "__main__":
    unittest.main()
