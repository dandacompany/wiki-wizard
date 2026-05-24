"""sqlite-backed registry for wiki-wizard vaults and notes."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
SCHEMA_SQL_PATH = Path(__file__).parent / "db" / "schema.sql"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    """Create schema if absent. Idempotent."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sql = SCHEMA_SQL_PATH.read_text()
    conn = connect(db_path)
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


class VaultError(Exception):
    """Raised on invalid vault operations."""


def add_vault(
    db_path: Path,
    *,
    name: str,
    path: Path,
    type_: str,
    mode: str,
    config_json: str | None = None,
) -> sqlite3.Row:
    conn = connect(db_path)
    try:
        now = _now()
        try:
            cur = conn.execute(
                """
                INSERT INTO vaults(name, path, type, mode, is_active,
                                   created_at, last_used, config_json)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (name, str(Path(path).resolve()), type_, mode, now, now, config_json),
            )
        except sqlite3.IntegrityError as exc:
            msg = str(exc).lower()
            if "vaults.name" in msg:
                raise VaultError(f"vault name {name!r} is already registered") from exc
            if "vaults.path" in msg:
                raise VaultError(f"vault path {path!r} is already registered") from exc
            raise VaultError(str(exc)) from exc
        conn.commit()
        return conn.execute(
            "SELECT * FROM vaults WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    finally:
        conn.close()


def list_vaults(db_path: Path) -> list[sqlite3.Row]:
    conn = connect(db_path)
    try:
        return list(conn.execute("SELECT * FROM vaults ORDER BY last_used DESC"))
    finally:
        conn.close()


def get_active(db_path: Path) -> sqlite3.Row | None:
    conn = connect(db_path)
    try:
        return conn.execute(
            "SELECT * FROM vaults WHERE is_active = 1"
        ).fetchone()
    finally:
        conn.close()


def set_active(db_path: Path, name: str) -> sqlite3.Row:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM vaults WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            raise VaultError(f"vault {name!r} not found")
        with conn:
            conn.execute("UPDATE vaults SET is_active = 0 WHERE is_active = 1")
            conn.execute(
                "UPDATE vaults SET is_active = 1, last_used = ? WHERE id = ?",
                (_now(), row["id"]),
            )
        return conn.execute("SELECT * FROM vaults WHERE id = ?", (row["id"],)).fetchone()
    finally:
        conn.close()


def forget_vault(db_path: Path, name: str) -> None:
    conn = connect(db_path)
    try:
        cur = conn.execute("DELETE FROM vaults WHERE name = ?", (name,))
        if cur.rowcount == 0:
            raise VaultError(f"vault {name!r} not found")
        conn.commit()
    finally:
        conn.close()
