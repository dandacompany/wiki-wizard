"""Per-vault sqlite glossary runtime.

Stores terminology state at <vault_root>/.oh-my-wiki/glossary.db.
Owned by the terminology-manager persona; fact-checker and
consistency-checker do not write here.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

GLOSSARY_DIR = ".oh-my-wiki"
GLOSSARY_FILE = "glossary.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS terms (
    id INTEGER PRIMARY KEY,
    vault_id INTEGER NOT NULL,
    canonical TEXT NOT NULL,
    aliases TEXT NOT NULL,
    definition TEXT,
    first_seen_relpath TEXT,
    last_updated TEXT NOT NULL,
    UNIQUE(vault_id, canonical)
);
CREATE INDEX IF NOT EXISTS idx_terms_vault ON terms(vault_id);
"""


class GlossaryError(Exception):
    """Raised for invalid input, missing term, etc."""


def open_db(vault_root: Path) -> Path:
    """Ensure .oh-my-wiki/glossary.db exists with schema; return the path."""
    vault_root = Path(vault_root)
    db_dir = vault_root / GLOSSARY_DIR
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / GLOSSARY_FILE
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return db_path


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "vault_id": row["vault_id"],
        "canonical": row["canonical"],
        "aliases": json.loads(row["aliases"]) if row["aliases"] else [],
        "definition": row["definition"],
        "first_seen_relpath": row["first_seen_relpath"],
        "last_updated": row["last_updated"],
    }


def upsert_term(
    db_path: Path,
    *,
    vault_id: int,
    canonical: str,
    aliases: list[str],
    definition: str | None = None,
    first_seen_relpath: str | None = None,
) -> int:
    """Insert or update a term. Returns row id."""
    if not canonical or not canonical.strip():
        raise GlossaryError("canonical term must be non-empty")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    aliases_json = json.dumps(list(aliases), ensure_ascii=False)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            "INSERT INTO terms (vault_id, canonical, aliases, definition, "
            "first_seen_relpath, last_updated) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(vault_id, canonical) DO UPDATE SET "
            "  aliases=excluded.aliases, "
            "  definition=COALESCE(excluded.definition, terms.definition), "
            "  first_seen_relpath=COALESCE(terms.first_seen_relpath, excluded.first_seen_relpath), "
            "  last_updated=excluded.last_updated",
            (vault_id, canonical, aliases_json, definition, first_seen_relpath, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM terms WHERE vault_id = ? AND canonical = ?",
            (vault_id, canonical),
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


def get_term(db_path: Path, *, vault_id: int, canonical: str) -> dict | None:
    """Lookup by canonical form."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM terms WHERE vault_id = ? AND canonical = ?",
            (vault_id, canonical),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_terms(db_path: Path, *, vault_id: int) -> list[dict]:
    """All terms for a vault, ordered by canonical."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM terms WHERE vault_id = ? ORDER BY canonical",
            (vault_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
