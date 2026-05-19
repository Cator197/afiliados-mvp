import tempfile
import unittest
from pathlib import Path

import config
from database import get_connection


class CashbackRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        d = Path(cls.tmpdir.name)
        config.DATA_DIR = d
        config.LOGS_DIR = d / "logs"
        config.DB_PATH = d / "afiliados_test.db"
        from init_db import create_tables, ensure_cashback_rules_default
        create_tables()
        ensure_cashback_rules_default()
        ensure_cashback_rules_default()

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def test_default_rule_created_once(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) AS total FROM cashback_rules WHERE platform='mercadolivre' AND match_type='default' AND active=1")
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row["total"], 1)

    def test_path_contains_rule_is_selected(self):
        from services.extension_service import build_cashback_preview
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM cashback_rules WHERE match_type='path_contains'")
        cur.execute(
            "INSERT INTO cashback_rules (platform,name,match_type,match_value,cashback_percent,priority,active,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
            ("mercadolivre", "Celulares", "path_contains", "celulares", 5.0, 10, 1, "teste"),
        )
        conn.commit()
        conn.close()

        preview = build_cashback_preview("mercadolivre", "https://www.mercadolivre.com.br/celulares/p/MLB123", price=100)
        self.assertEqual(preview["estimated_cashback_percent"], 5.0)
        self.assertEqual(preview["cashback_rule"]["match_type"], "path_contains")


if __name__ == "__main__":
    unittest.main()
