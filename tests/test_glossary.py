"""Tests for scripts.glossary — per-vault sqlite glossary runtime."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts import glossary


def test_open_db_creates_file_and_schema(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = glossary.open_db(vault)
    assert db_path == vault / ".oh-my-wiki" / "glossary.db"
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='terms'"
        ).fetchall()
        assert len(rows) == 1
        cols = {row[1] for row in conn.execute("PRAGMA table_info(terms)")}
        assert {"id", "vault_id", "canonical", "aliases", "definition",
                "first_seen_relpath", "last_updated"} <= cols
    finally:
        conn.close()


def test_open_db_is_idempotent(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db1 = glossary.open_db(vault)
    db2 = glossary.open_db(vault)
    assert db1 == db2
    assert db1.exists()


def test_open_db_creates_parent_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    assert not (vault / ".oh-my-wiki").exists()
    glossary.open_db(vault)
    assert (vault / ".oh-my-wiki").is_dir()


def test_glossary_error_is_exception():
    assert issubclass(glossary.GlossaryError, Exception)
