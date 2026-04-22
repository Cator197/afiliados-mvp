import re
import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection
from repositories.admin_repo import hash_password
from repositories.usuarios_repo import hash_user_password
from werkzeug.security import check_password_hash


class PasswordFlowTests(unittest.TestCase):
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
            ensure_password_reset_requests_table,
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
        ensure_password_reset_requests_table()

        from app import app

        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def setUp(self):
        self.client = self.app.test_client()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admin_users")
        cursor.execute("DELETE FROM password_reset_requests")
        cursor.execute("DELETE FROM usuarios")
        cursor.execute(
            """
            INSERT INTO admin_users (username, password_hash, ativo, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            ("admin_teste", hash_password("senha_teste"), 1, "2026-01-01 00:00:00"),
        )
        conn.commit()
        conn.close()

    def _create_user(self, codigo_usuario, senha, must_change_password):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO usuarios (codigo_usuario, nome, password_hash, ativo, criado_em, must_change_password)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (codigo_usuario, f"Usuário {codigo_usuario}", hash_user_password(senha), 1, "2026-01-01 00:00:00", must_change_password),
        )
        conn.commit()
        conn.close()

    def _get_user(self, codigo_usuario):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE codigo_usuario = ?", (codigo_usuario,))
        row = cursor.fetchone()
        conn.close()
        return row

    def _extract_admin_csrf_token(self):
        response = self.client.get("/admin/login")
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def _login_admin(self):
        return self.client.post(
            "/admin/login",
            data={
                "username": "admin_teste",
                "password": "senha_teste",
                "csrf_token": self._extract_admin_csrf_token(),
            },
            follow_redirects=False,
        )

    def _extract_page_csrf_token(self, html):
        match = re.search(r'csrf_token: "([^"]+)"', html)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_login_com_senha_temporaria_redireciona_para_alteracao(self):
        self._create_user("TEMP001", "senha-temp", 1)

        response = self.client.post(
            "/api/login",
            json={"codigo_usuario": "TEMP001", "senha": "senha-temp"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["must_change_password"])
        self.assertEqual(payload["redirect_to"], "/usuario/alterar-senha")

    def test_alteracao_de_senha_libera_acesso(self):
        self._create_user("TEMP002", "senha-temp", 1)

        login = self.client.post(
            "/api/login",
            json={"codigo_usuario": "TEMP002", "senha": "senha-temp"},
        )
        self.assertEqual(login.status_code, 200)

        usuario_page = self.client.get("/usuario/TEMP002", follow_redirects=False)
        self.assertEqual(usuario_page.status_code, 302)
        self.assertIn("/usuario/alterar-senha", usuario_page.headers.get("Location", ""))

        csrf_page = self.client.get("/usuario/alterar-senha")
        csrf_token = self._extract_page_csrf_token(csrf_page.get_data(as_text=True))

        response = self.client.post(
            "/api/alterar-senha",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "senha_atual": "senha-temp",
                "nova_senha": "senha-nova-123",
                "confirmar_senha": "senha-nova-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["redirect_to"], "/usuario/TEMP002")

        atualizado = self._get_user("TEMP002")
        self.assertEqual(atualizado["must_change_password"], 0)
        self.assertTrue(check_password_hash(atualizado["password_hash"], "senha-nova-123"))

    def test_esqueci_senha_cria_solicitacao_e_admin_envia_senha_temporaria(self):
        self._create_user("RESET001", "senha-antiga", 0)

        response = self.client.post(
            "/api/esqueci-senha",
            json={"codigo_usuario": "RESET001"},
        )
        self.assertEqual(response.status_code, 201)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM password_reset_requests WHERE codigo_usuario = ?", ("RESET001",))
        solicitacao = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(solicitacao)
        self.assertEqual(solicitacao["status"], "novo")

        self._login_admin()
        page = self.client.get("/admin/reset-senhas")
        self.assertEqual(page.status_code, 200)
        self.assertIn("RESET001", page.get_data(as_text=True))

        update_response = self.client.post(
            f"/admin/reset-senhas/{solicitacao['id']}/atualizar",
            data={
                "status": "novo",
                "nova_senha": "temp-456",
                "observacoes_admin": "Senha enviada pelo suporte",
                "csrf_token": self._extract_admin_csrf_token(),
            },
            follow_redirects=False,
        )
        self.assertEqual(update_response.status_code, 302)

        atualizado = self._get_user("RESET001")
        self.assertEqual(atualizado["must_change_password"], 1)
        self.assertTrue(check_password_hash(atualizado["password_hash"], "temp-456"))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM password_reset_requests WHERE id = ?", (solicitacao["id"],))
        solicitacao_atualizada = cursor.fetchone()
        conn.close()

        self.assertEqual(solicitacao_atualizada["status"], "senha_enviada")


if __name__ == "__main__":
    unittest.main()
