import sqlite3
from config import CHROME_PROFILE_DIR, DATA_DIR, LOGS_DIR, DB_PATH, SQLITE_BUSY_TIMEOUT_MS, SECURE_STORAGE_DIR


def ensure_directories():
    SECURE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def get_connection():
    ensure_directories()
    conn = sqlite3.connect(DB_PATH, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    configure_connection(conn)
    return conn


def configure_connection(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
