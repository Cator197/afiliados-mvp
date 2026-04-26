import re
import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection
from repositories.admin_repo import hash_password


class AdminLinksMetadataRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        temp_data_dir = Path(cls.tmpdir.name)

        config.DATA_DIR = temp_data_dir
        config.LOGS_DIR = temp_data_dir / "logs"
        config.DB_PATH = temp_data_dir / "afiliados_test.db"
        config.SECRET_KEY = "test-secret-key"

        from init_db import (
            create_tables,
            ensure_cadastro_solicitacoes_table,
            ensure_jobs_platform_column,
            ensure_jobs_worker_columns,
            ensure_links_metadata_columns,
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
        ensure_links_metadata_columns()
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
        cursor.execute("DELETE FROM links_gerados")
        cursor.execute("DELETE FROM usuarios")
        cursor.execute(
            """
            INSERT INTO admin_users (username, password_hash, ativo, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            ("admin_teste", hash_password("senha_teste"), 1, "2026-01-01 00:00:00"),
        )
        cursor.execute(
            """
            INSERT INTO usuarios (codigo_usuario, nome, ativo, criado_em, must_change_password)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("USR001", "Usuário Teste", 1, "2026-01-01 00:00:00", 0),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO links_gerados (
                usuario_id, job_id, url_original, url_afiliado, plataforma, status,
                percentual_cashback, descricao_item, foto_item_url, valor_produto,
                percentual_comissao, valor_comissao, valor_cashback, metadados_status,
                metadados_erro, metadados_atualizado_em, criado_em, atualizado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                None,
                "https://mercadolivre.com.br/item",
                "https://afiliado.com/item",
                "mercadolivre",
                "aguardando_verificacao",
                50.0,
                "Produto antigo",
                "https://img.example/old.jpg",
                100.0,
                10.0,
                10.0,
                5.0,
                "erro",
                "timeout",
                "2026-01-01 00:00:00",
                "2026-01-01 00:00:00",
                "2026-01-01 00:00:00",
            ),
        )
        self.link_id = cursor.lastrowid
        conn.commit()
        conn.close()

    def _extract_csrf_token(self, html):
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(match)
        return match.group(1)

    def _login_admin(self):
        login_page = self.client.get("/admin/login")
        csrf_token = self._extract_csrf_token(login_page.get_data(as_text=True))
        self.client.post(
            "/admin/login",
            data={"username": "admin_teste", "password": "senha_teste", "csrf_token": csrf_token},
            follow_redirects=False,
        )

    def _get_admin_csrf_token(self):
        page = self.client.get("/admin/links")
        return self._extract_csrf_token(page.get_data(as_text=True))

    def _get_link(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM links_gerados WHERE id = ?", (self.link_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def test_atualizar_infos_coloca_link_em_pendente(self):
        self._login_admin()
        csrf_token = self._get_admin_csrf_token()

        response = self.client.post(
            f"/admin/links/{self.link_id}/atualizar-infos",
            headers={"X-CSRF-Token": csrf_token},
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["metadados_status"], "pendente")

        atualizado = self._get_link()
        self.assertEqual(atualizado["metadados_status"], "pendente")
        self.assertIsNone(atualizado["metadados_erro"])
        self.assertIsNone(atualizado["metadados_atualizado_em"])
        self.assertEqual(atualizado["descricao_item"], "Produto antigo")


if __name__ == "__main__":
    unittest.main()
