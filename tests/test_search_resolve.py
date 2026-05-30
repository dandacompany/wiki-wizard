"""resolve_provider reads config + secret, raises actionable SearchError."""
import pytest

from scripts import config, search
from scripts.search import SearchError


def test_resolve_uses_config_provider_and_env_secret(monkeypatch):
    config.set_config("search.provider", "brave")
    monkeypatch.setenv("BRAVE_API_KEY", "k")
    p = search.resolve_provider()
    assert p.__class__.__name__ == "BraveProvider" and p.api_key == "k"


def test_resolve_reads_secret_from_env_file(monkeypatch):
    config.set_config("search.provider", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    config.set_secret("TAVILY_API_KEY", "from-file")
    assert search.resolve_provider().api_key == "from-file"


def test_resolve_no_provider_raises(monkeypatch):
    with pytest.raises(SearchError, match="no search provider configured"):
        search.resolve_provider()


def test_resolve_missing_key_raises(monkeypatch):
    config.set_config("search.provider", "exa")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(SearchError, match="missing API key"):
        search.resolve_provider()


def test_resolve_brave_key_fallback(monkeypatch):
    config.set_config("search.provider", "brave")
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    config.set_secret("BRAVE_SEARCH_API_KEY", "fallback-k")
    assert search.resolve_provider().api_key == "fallback-k"


def test_resolve_unknown_provider_raises():
    with pytest.raises(SearchError, match="unknown search provider"):
        search.resolve_provider("nonexistent")
