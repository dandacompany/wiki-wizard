from __future__ import annotations
from scripts.search import base

SECRETS = {"api_key": "EXA_API_KEY"}


class ExaProvider:
    name = "exa"

    def __init__(self, *, api_key: str):
        self.api_key = api_key

    def search(self, query: str, *, limit: int = 10) -> list[dict]:
        data = base._http_json(
            "https://api.exa.ai/search", method="POST",
            headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
            body={"query": query, "numResults": min(limit, 100), "contents": {"highlights": True}},
        )
        out = []
        for r in data.get("results") or []:
            hl = r.get("highlights") or []
            snippet = hl[0] if hl else (r.get("text") or "")[:300]
            out.append({"title": r.get("title", ""), "url": r.get("url", ""), "snippet": snippet})
        return out[:limit]
