import sqlite3

import pytest

from scripts import registry


def test_init_db_creates_tables(tmp_db, db_connect):
    registry.init_db(tmp_db)
    conn = db_connect(tmp_db)
    tables = {row["name"] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"vaults", "notes", "tags", "note_tags", "schema_migrations"} <= tables


def test_init_db_records_migration_version(tmp_db, db_connect):
    registry.init_db(tmp_db)
    conn = db_connect(tmp_db)
    versions = [row["version"] for row in conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    )]
    assert versions == [1]


def test_init_db_is_idempotent(tmp_db, db_connect):
    registry.init_db(tmp_db)
    registry.init_db(tmp_db)
    conn = db_connect(tmp_db)
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 1
