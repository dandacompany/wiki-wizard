"""sqlite-backed registry for wiki-wizard vaults and notes."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
SCHEMA_SQL_PATH = Path(__file__).parent / "db" / "schema.sql"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    """Create schema if absent. Idempotent."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sql = SCHEMA_SQL_PATH.read_text()
    conn = _connect(db_path)
    try:
        conn.executescript(sql)
        existing = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, _now()),
            )
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
