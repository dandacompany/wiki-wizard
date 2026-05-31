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


def due_pages(db_path: Path, *, vault_id: int, today: str,
              include_unscheduled: bool = True) -> list[dict]:
    """Pages due for review on `today`. Unscheduled (no review block) → due."""
    root = reindex._vault_path(db_path, vault_id)
    out: list[dict] = []
    for md in sorted(root.rglob("*.md")):
        if ".trash" in md.parts:
            continue
        rel = str(md.relative_to(root)).replace("\\", "/")
        if rel in _EXEMPT or rel.startswith("raw/"):
            continue
        try:
            meta, _ = frontmatter.parse(md.read_text(encoding="utf-8"))
        except frontmatter.FrontmatterError:
            continue
        rv = meta.get("review") if isinstance(meta.get("review"), dict) else {}
        due = rv.get("due")
        confidence = meta.get("confidence")
        if due is not None:
            if str(due) <= today:  # zero-padded ISO dates compare lexicographically
                out.append({"relpath": rel, "due": str(due),
                            "interval_days": rv.get("interval_days"), "confidence": confidence})
        elif include_unscheduled:
            out.append({"relpath": rel, "due": None, "interval_days": None,
                        "confidence": confidence})
    out.sort(key=lambda r: (r["due"] is not None, r["due"] or ""))
    return out


def reschedule(db_path: Path, *, vault_id: int, relpath: str, grade: str,
               today: str) -> dict:
    """Re-verify outcome → recompute the schedule, write frontmatter, reindex."""
    root = reindex._vault_path(db_path, vault_id)
    abs_path = root / relpath
    if not abs_path.exists():
        raise FileNotFoundError(f"page not found: {relpath}")
    meta, body = frontmatter.parse(abs_path.read_text(encoding="utf-8"))
    rv = meta.get("review") if isinstance(meta.get("review"), dict) else {}
    interval = next_interval(rv.get("interval_days"), grade, meta.get("confidence"))
    meta["review"] = schedule_fields(today, interval)
    abs_path.write_text(frontmatter.dump(meta, body), encoding="utf-8")
    reindex.incremental(db_path, vault_id=vault_id)
    return {"relpath": relpath, "review": meta["review"]}
