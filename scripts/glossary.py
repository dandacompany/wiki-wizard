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
