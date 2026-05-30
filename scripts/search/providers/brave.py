"""Brave Search API adapter. GET, X-Subscription-Token, web.results[]."""
from __future__ import annotations

import urllib.parse

from scripts.search import base

SECRETS = {"api_key": ("BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY")}


class BraveProvider:
    name = "brave"

    def __init__(self, *, api_key: str):
        self.api_key = api_key

    def search(self, query: str, *, limit: int = 10) -> list[dict]:
        qs = urllib.parse.urlencode({"q": query, "count": min(limit, 20)})
        url = f"https://api.search.brave.com/res/v1/web/search?{qs}"
        data = base._http_json(
            url, method="GET",
            headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
        )
        results = (data.get("web") or {}).get("results") or []
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": r.get("description", "")} for r in results][:limit]
