import sqlite3
from config import DATA_DIR, LOGS_DIR, DB_PATH


def ensure_directories():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection():
    ensure_directories()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn