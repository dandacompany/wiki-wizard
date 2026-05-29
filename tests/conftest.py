from pathlib import Path

import pytest

from scripts import registry

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


@pytest.fixture
def db_connect():
    return registry.connect


@pytest.fixture(autouse=True)
def _isolate_omw_home(monkeypatch, tmp_path):
    """Every test gets an isolated OMW_HOME so the real ~/.omw is never touched."""
    monkeypatch.setenv("OMW_HOME", str(tmp_path / ".omw-test"))
