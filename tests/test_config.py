"""~/.omw config.yaml + .env read/write layer."""
import os
import stat

from scripts import config
from scripts.paths import omw_home


def test_set_and_load_config(tmp_path, monkeypatch):
    config.set_config("search.provider", "brave")
    config.set_config("search.enabled", True)
    data = config.load_config()
    assert data["search"]["provider"] == "brave"
    assert data["search"]["enabled"] is True


def test_load_config_missing_returns_empty():
    assert config.load_config() == {}


def test_set_secret_writes_env_0600_and_reads_back(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    config.set_secret("BRAVE_API_KEY", "sk-xyz")
    assert config.read_secret("BRAVE_API_KEY") == "sk-xyz"
    envf = omw_home() / ".env"
    assert envf.is_file()
    assert stat.S_IMODE(os.stat(envf).st_mode) == 0o600


def test_read_secret_prefers_live_env(monkeypatch):
    config.set_secret("BRAVE_API_KEY", "from-file")
    monkeypatch.setenv("BRAVE_API_KEY", "from-env")
    assert config.read_secret("BRAVE_API_KEY") == "from-env"


def test_read_secret_missing_returns_none(monkeypatch):
    monkeypatch.delenv("NOPE_KEY", raising=False)
    assert config.read_secret("NOPE_KEY") is None
