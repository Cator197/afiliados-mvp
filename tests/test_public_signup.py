import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection
from repositories.admin_repo import hash_password


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

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO admin_users (id, username, password_hash, ativo, criado_em)
            VALUES (
                COALESCE((SELECT id FROM admin_users WHERE username = ?), NULL),
                ?, ?, 1, ?
            )
            """,
            ("admin_teste", "admin_teste", hash_password("senha_teste"), "2026-01-01 00:00:00"),
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def setUp(self):
        self.client = self.app.test_client()

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

    def _login_admin(self):
        return self.client.post(
            "/admin/login",
            data={"username": "admin_teste", "password": "senha_teste"},
            follow_redirects=False,
        )

    def _criar_solicitacao(self, nome, email, status="novo", observacoes=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cadastro_solicitacoes (
                nome_completo, email, codigo_indicacao, whatsapp, status, observacoes_admin, criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nome,
                email,
                "CAIO001",
                None,
                status,
                observacoes,
                "2026-01-01 00:00:00",
                "2026-01-01 00:00:00",
            ),
        )
        solicitacao_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return solicitacao_id

    def test_admin_logado_abre_pagina_solicitacoes(self):
        self._login_admin()
        response = self.client.get("/admin/solicitacoes")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Solicitações de cadastro", response.get_data(as_text=True))

    def test_filtro_por_status_funciona(self):
        self._criar_solicitacao("Pessoa Novo", "novo@example.com", status="novo")
        self._criar_solicitacao("Pessoa Aprovada", "aprovado@example.com", status="aprovado")
        self._login_admin()

        response = self.client.get("/admin/solicitacoes?status=aprovado")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("aprovado@example.com", body)
        self.assertNotIn("novo@example.com", body)

    def test_atualizacao_de_status_funciona(self):
        solicitacao_id = self._criar_solicitacao("Pessoa Status", "status@example.com", status="novo")
        self._login_admin()

        response = self.client.post(
            f"/admin/solicitacoes/{solicitacao_id}/atualizar",
            data={"status": "em_analise", "observacoes_admin": "em revisão"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        from repositories.cadastro_solicitacoes_repo import get_cadastro_solicitacao_by_id

        row = get_cadastro_solicitacao_by_id(solicitacao_id)
        self.assertEqual(row["status"], "em_analise")

    def test_atualizacao_de_observacoes_funciona(self):
        solicitacao_id = self._criar_solicitacao("Pessoa Obs", "obs@example.com", status="novo")
        self._login_admin()

        self.client.post(
            f"/admin/solicitacoes/{solicitacao_id}/atualizar",
            data={"status": "novo", "observacoes_admin": "documento pendente"},
            follow_redirects=False,
        )

        from repositories.cadastro_solicitacoes_repo import get_cadastro_solicitacao_by_id

        row = get_cadastro_solicitacao_by_id(solicitacao_id)
        self.assertEqual(row["observacoes_admin"], "documento pendente")

    def test_usuario_nao_admin_nao_acessa_solicitacoes(self):
        response = self.client.get("/admin/solicitacoes", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers.get("Location", ""))

    def test_painel_admin_links_continua_funcionando(self):
        self._login_admin()
        response = self.client.get("/admin/links")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Painel administrativo", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
