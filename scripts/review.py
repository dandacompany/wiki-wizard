"""Spaced-repetition review schedule for wiki pages (frontmatter `review:` block).

Pure scheduling math + two vault-I/O helpers. `today` is injected (YYYY-MM-DD)
so tests are deterministic; the CLI defaults it to date.today().
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from scripts import frontmatter, links, reindex

_TIERS = {"high": 90, "medium": 30, "low": 7}
_EXEMPT = set(links.META_RELPATHS)
_MAX_INTERVAL = 365


def tier(confidence) -> int:
    return _TIERS.get(confidence, 30)


def next_interval(prev_interval_days, grade: str, confidence) -> int:
    base = tier(confidence)
    if grade == "needs-work":
        return base
    if grade == "pass":
        if not prev_interval_days:
            return base
        return min(prev_interval_days * 2, _MAX_INTERVAL)
    raise ValueError(f"unknown grade: {grade!r}")


def schedule_fields(today: str, interval_days: int) -> dict:
    due = date.fromisoformat(today) + timedelta(days=interval_days)
    return {"last": today, "due": due.isoformat(), "interval_days": interval_days}
