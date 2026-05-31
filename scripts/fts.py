"""SQLite FTS5 full-text index for wiki pages (optional; auto-detected).

A standalone FTS5 virtual table (notes_fts) populated during reindex. Created in
CODE (not schema.sql) so init_db never breaks on a sqlite build lacking FTS5.
search_index falls back to the token scorer when FTS5 is unavailable.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from scripts import registry

_FTS5_AVAILABLE: bool | None = None
_TOKEN_RE = re.compile(r"[\w가-힣]+", re.UNICODE)


def fts5_available() -> bool:
    global _FTS5_AVAILABLE
    if _FTS5_AVAILABLE is None:
        try:
            c = sqlite3.connect(":memory:")
            c.execute("CREATE VIRTUAL TABLE _probe USING fts5(x)")
            c.close()
            _FTS5_AVAILABLE = True
        except sqlite3.OperationalError:
            _FTS5_AVAILABLE = False
    return _FTS5_AVAILABLE


def ensure_fts(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5("
        "relpath, title, summary, tags, body, vault_id UNINDEXED, "
        "tokenize='unicode61')"
    )


def clear_vault(conn: sqlite3.Connection, *, vault_id: int) -> None:
    conn.execute("DELETE FROM notes_fts WHERE vault_id = ?", (str(vault_id),))


def index_note(conn: sqlite3.Connection, *, vault_id: int, relpath: str,
               title, summary, tags, body) -> None:
    conn.execute("DELETE FROM notes_fts WHERE vault_id = ? AND relpath = ?",
                 (str(vault_id), relpath))
    conn.execute(
        "INSERT INTO notes_fts(relpath, title, summary, tags, body, vault_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (relpath, title or "", summary or "", " ".join(tags or []),
         body or "", str(vault_id)),
    )


def _match_query(query: str) -> str:
    """Build a safe FTS5 MATCH expression: quote each token, OR-join.
    Quoting neutralizes FTS5 operators (*, :, AND, NEAR, quotes) so user input never raises."""
    toks = _TOKEN_RE.findall(query or "")
    return " OR ".join(f'"{t}"' for t in toks)


def search(db_path: Path, *, vault_id: int, query: str, limit: int):
    """FTS5 BM25 search. Returns a list of hit dicts, [] for no match, or
    None when the vault isn't indexed yet (caller should fall back)."""
    match = _match_query(query)
    conn = registry.connect(db_path)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts'"
        ).fetchone()
        if not exists:
            return None
        has_rows = conn.execute(
            "SELECT 1 FROM notes_fts WHERE vault_id = ? LIMIT 1", (str(vault_id),)
        ).fetchone()
        if not has_rows:
            return None  # vault not indexed (e.g. pre-F#6) → fall back
        if not match:
            return []
        rows = list(conn.execute(
            "SELECT relpath, title, summary, tags, bm25(notes_fts) AS rank "
            "FROM notes_fts WHERE notes_fts MATCH ? AND vault_id = ? "
            "ORDER BY rank LIMIT ?",
            (match, str(vault_id), limit),
        ))
        return [{
            "relpath": r["relpath"],
            "title": r["title"] or None,
            "summary": r["summary"] or None,
            "tags": r["tags"].split() if r["tags"] else [],
            "score": round(-r["rank"], 3),  # bm25: lower = better; negate so higher = better
        } for r in rows]
    finally:
        conn.close()
