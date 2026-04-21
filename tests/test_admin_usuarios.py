import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection
from repositories.admin_repo import hash_password
from repositories.usuarios_repo import hash_user_password
from werkzeug.security import check_password_hash


class AdminUsuariosTests(unittest.TestCase):
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
        cursor.execute("DELETE FROM admin_users")
        cursor.execute("DELETE FROM usuarios")

        cursor.execute(
            """
            INSERT INTO admin_users (username, password_hash, ativo, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            ("admin_teste", hash_password("senha_teste"), 1, "2026-01-01 00:00:00"),
        )

        cursor.executemany(
            """
            INSERT INTO usuarios (codigo_usuario, nome, password_hash, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("USR001", "Usuário 1", hash_user_password("senha123"), 1, "2026-01-01 00:00:00"),
                ("USR002", "Usuário 2", hash_user_password("senha123"), 0, "2026-01-01 00:00:00"),
            ],
        )

        conn.commit()
        conn.close()

    def _login_admin(self):
        return self.client.post(
            "/admin/login",
            data={"username": "admin_teste", "password": "senha_teste"},
            follow_redirects=False,
        )

    def _get_user(self, codigo_usuario):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE codigo_usuario = ?", (codigo_usuario,))
        row = cursor.fetchone()
        conn.close()
        return row

    def test_rotas_admin_usuarios_exigem_login(self):
        lista = self.client.get("/admin/usuarios", follow_redirects=False)
        self.assertEqual(lista.status_code, 302)
        self.assertIn("/admin/login", lista.headers.get("Location", ""))

        user = self._get_user("USR001")
        atualiza = self.client.post(
            f"/admin/usuarios/{user['id']}/atualizar",
            data={"acao": "toggle_ativo"},
            follow_redirects=False,
        )
        self.assertEqual(atualiza.status_code, 302)
        self.assertIn("/admin/login", atualiza.headers.get("Location", ""))

    def test_listagem_funciona(self):
        self._login_admin()

        response = self.client.get("/admin/usuarios")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Gerenciar usuários", body)
        self.assertIn("USR001", body)
        self.assertIn("USR002", body)

    def test_ativar_desativar_funciona(self):
        self._login_admin()
        user = self._get_user("USR001")

        self.client.post(
            f"/admin/usuarios/{user['id']}/atualizar",
            data={"acao": "toggle_ativo"},
            follow_redirects=False,
        )

        atualizado = self._get_user("USR001")
        self.assertEqual(atualizado["ativo"], 0)

        self.client.post(
            f"/admin/usuarios/{user['id']}/atualizar",
            data={"acao": "toggle_ativo"},
            follow_redirects=False,
        )

        atualizado = self._get_user("USR001")
        self.assertEqual(atualizado["ativo"], 1)

    def test_reset_senha_funciona(self):
        self._login_admin()
        user = self._get_user("USR001")

        self.client.post(
            f"/admin/usuarios/{user['id']}/atualizar",
            data={"acao": "reset_senha", "nova_senha": "nova-senha-123"},
            follow_redirects=False,
        )

        atualizado = self._get_user("USR001")
        self.assertNotEqual(atualizado["password_hash"], user["password_hash"])
        self.assertTrue(check_password_hash(atualizado["password_hash"], "nova-senha-123"))


if __name__ == "__main__":
    unittest.main()
