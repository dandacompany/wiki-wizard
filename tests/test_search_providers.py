"""Search provider adapters parse canned API JSON into {title,url,snippet}."""
import pytest

from scripts.search import base


@pytest.fixture
def fake_http(monkeypatch):
    calls = {}

    def _fake(url, *, method="GET", headers=None, body=None, timeout=15):
        calls["url"] = url
        calls["method"] = method
        calls["headers"] = headers or {}
        calls["body"] = body
        return _fake.payload

    monkeypatch.setattr(base, "_http_json", _fake)
    return calls, _fake


def test_brave_parses_results(fake_http):
    calls, fake = fake_http
    fake.payload = {"web": {"results": [
        {"title": "T1", "url": "https://a", "description": "S1"},
        {"title": "T2", "url": "https://b", "description": "S2"}]}}
    from scripts.search.providers.brave import BraveProvider
    res = BraveProvider(api_key="k").search("agents", limit=10)
    assert res == [{"title": "T1", "url": "https://a", "snippet": "S1"},
                   {"title": "T2", "url": "https://b", "snippet": "S2"}]
    assert calls["headers"]["X-Subscription-Token"] == "k"
    assert "q=agents" in calls["url"] and "count=10" in calls["url"]


def test_tavily_parses_results(fake_http):
    calls, fake = fake_http
    fake.payload = {"results": [{"title": "T", "url": "https://a", "content": "C"}]}
    from scripts.search.providers.tavily import TavilyProvider
    assert TavilyProvider(api_key="k").search("q", limit=5) == [
        {"title": "T", "url": "https://a", "snippet": "C"}]
    assert calls["method"] == "POST" and calls["body"]["query"] == "q"
    assert calls["headers"]["Authorization"] == "Bearer k"


def test_exa_uses_highlights_and_requests_contents(fake_http):
    calls, fake = fake_http
    fake.payload = {"results": [{"title": "T", "url": "https://a", "highlights": ["H1", "H2"]}]}
    from scripts.search.providers.exa import ExaProvider
    assert ExaProvider(api_key="k").search("q", limit=10) == [
        {"title": "T", "url": "https://a", "snippet": "H1"}]
    assert calls["body"]["contents"] == {"highlights": True}
    assert calls["headers"]["x-api-key"] == "k"


def test_firecrawl_parses_data_web(fake_http):
    calls, fake = fake_http
    fake.payload = {"success": True, "data": {"web": [
        {"title": "T", "url": "https://a", "description": "D"}]}}
    from scripts.search.providers.firecrawl import FirecrawlProvider
    assert FirecrawlProvider(api_key="k").search("q", limit=10) == [
        {"title": "T", "url": "https://a", "snippet": "D"}]


def test_firecrawl_parses_flat_data_list(fake_http):
    calls, fake = fake_http
    fake.payload = {"success": True, "data": [{"title": "T", "url": "https://a", "description": "D"}]}
    from scripts.search.providers.firecrawl import FirecrawlProvider
    assert FirecrawlProvider(api_key="k").search("q", limit=10) == [
        {"title": "T", "url": "https://a", "snippet": "D"}]


def test_brave_truncates_to_limit(fake_http):
    calls, fake = fake_http
    fake.payload = {"web": {"results": [
        {"title": f"T{i}", "url": f"u{i}", "description": "d"} for i in range(5)]}}
    from scripts.search.providers.brave import BraveProvider
    assert len(BraveProvider(api_key="k").search("q", limit=2)) == 2


def test_exa_text_fallback_when_no_highlights(fake_http):
    calls, fake = fake_http
    fake.payload = {"results": [{"title": "T", "url": "u", "text": "long text body"}]}
    from scripts.search.providers.exa import ExaProvider
    assert ExaProvider(api_key="k").search("q", limit=10)[0]["snippet"] == "long text body"


def test_brightdata_parses_organic_link(fake_http):
    calls, fake = fake_http
    fake.payload = {"organic": [{"title": "T", "link": "https://a", "description": "D"}]}
    from scripts.search.providers.brightdata import BrightDataProvider
    assert BrightDataProvider(api_key="k", zone="serp1").search("q", limit=10) == [
        {"title": "T", "url": "https://a", "snippet": "D"}]
    assert calls["body"]["zone"] == "serp1" and "brd_json=1" in calls["body"]["url"]


def test_brightdata_no_organic_raises(fake_http):
    calls, fake = fake_http
    fake.payload = {"html": "<html>...</html>"}
    from scripts.search.providers.brightdata import BrightDataProvider
    from scripts.search.base import SearchError
    with pytest.raises(SearchError, match="SERP zone"):
        BrightDataProvider(api_key="k", zone="webunlock").search("q", limit=10)
