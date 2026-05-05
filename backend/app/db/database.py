import sqlite3
import uuid
from pathlib import Path
from app.config import settings


def get_db_path() -> str:
    return str(settings.db_path)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def generate_id() -> str:
    return uuid.uuid4().hex[:12]
