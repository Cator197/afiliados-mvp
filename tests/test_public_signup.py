import tempfile
import unittest
from pathlib import Path

import config


class PublicSignupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        temp_data_dir = Path(cls.tmpdir.name)

        config.DATA_DIR = temp_data_dir
        config.LOGS_DIR = temp_data_dir / "logs"
        config.DB_PATH = temp_data_dir / "afiliados_test.db"

        from init_db import create_tables, ensure_usuarios_password_column, ensure_jobs_worker_columns, ensure_worker_heartbeats_table, ensure_cadastro_solicitacoes_table

        create_tables()
        ensure_usuarios_password_column()
        ensure_jobs_worker_columns()
        ensure_worker_heartbeats_table()
        ensure_cadastro_solicitacoes_table()

        from app import app
        cls.app = app
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def test_get_signup_page(self):
        response = self.client.get("/solicitar-cadastro")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Solicitar cadastro", response.get_data(as_text=True))

    def test_post_signup_valid(self):
        response = self.client.post(
            "/api/solicitar-cadastro",
            json={
                "nome_completo": "Pessoa Teste",
                "email": "pessoa@example.com",
                "codigo_indicacao": "CAIO001",
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("solicitacao_id", payload)

        from repositories.cadastro_solicitacoes_repo import get_cadastro_solicitacao_by_id

        row = get_cadastro_solicitacao_by_id(payload["solicitacao_id"])
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "novo")
        self.assertEqual(row["email"], "pessoa@example.com")

    def test_post_signup_invalid(self):
        response = self.client.post(
            "/api/solicitar-cadastro",
            json={
                "nome_completo": "",
                "email": "email-invalido",
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("erro", payload)

    def test_login_page_still_works(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Entrar", response.get_data(as_text=True))

    def test_authenticated_route_unchanged(self):
        response = self.client.post(
            "/api/solicitar-link",
            json={"codigo_usuario": "CAIO001", "url": "https://www.mercadolivre.com.br"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
