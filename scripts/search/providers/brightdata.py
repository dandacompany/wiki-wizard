from __future__ import annotations
import urllib.parse
from scripts.search import base

SECRETS = {"api_key": "BRIGHTDATA_API_KEY", "zone": ("BRIGHTDATA_ZONE", "WEB_UNLOCKER_ZONE")}


class BrightDataProvider:
    name = "brightdata"

    def __init__(self, *, api_key: str, zone: str):
        self.api_key = api_key
        self.zone = zone

    def search(self, query: str, *, limit: int = 10) -> list[dict]:
        target = "https://www.google.com/search?" + urllib.parse.urlencode({"q": query}) + "&brd_json=1"
        data = base._http_json(
            "https://api.brightdata.com/request", method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            body={"zone": self.zone, "url": target, "format": "raw"},
        )
        organic = data.get("organic") if isinstance(data, dict) else None
        if organic is None:
            raise base.SearchError(
                "Bright Data returned no 'organic' results — ensure the configured zone "
                "serves brd_json SERP output. Set BRIGHTDATA_ZONE (or WEB_UNLOCKER_ZONE) "
                "via `omw setup search`."
            )
        return [{"title": r.get("title", ""), "url": r.get("link", ""),
                 "snippet": r.get("description", "")} for r in organic][:limit]
