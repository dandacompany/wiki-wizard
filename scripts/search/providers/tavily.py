from __future__ import annotations
from scripts.search import base

SECRETS = {"api_key": "TAVILY_API_KEY"}


class TavilyProvider:
    name = "tavily"

    def __init__(self, *, api_key: str):
        self.api_key = api_key

    def search(self, query: str, *, limit: int = 10) -> list[dict]:
        data = base._http_json(
            "https://api.tavily.com/search", method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            body={"query": query, "max_results": min(limit, 20)},
        )
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": r.get("content", "")} for r in data.get("results") or []][:limit]
