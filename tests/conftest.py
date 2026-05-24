import sqlite3
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_db(tmp_path):
    """Empty sqlite file in a tmp dir."""
    return tmp_path / "registry.db"


@pytest.fixture
def markdown_vault_path():
    return FIXTURES / "markdown-vault"


@pytest.fixture
def obsidian_vault_path():
    return FIXTURES / "obsidian-vault"


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@pytest.fixture
def db_connect():
    """Helper that opens a sqlite connection with FK on and row_factory set."""
    return _connect
