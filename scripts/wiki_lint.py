"""Wiki-mode structural lint: orphan/missing/empty/dangling checks."""
from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from scripts import registry

ORPHAN_GRACE_DAYS = 7

# Matches [[target]] or [[target|alias]] — captures the target slug
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
# Matches [text](./path.md) — captures relpath (without ./ prefix)
_MDLINK_RE = re.compile(r"\[[^\]]+\]\(\./([^)]+\.md)\)")


def check(db_path: Path, *, vault_id: int) -> dict:
    """Return wiki structural lint report. Read-only."""
    conn = registry.connect(db_path)
    try:
        row = conn.execute(
            "SELECT path FROM vaults WHERE id = ?", (vault_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise registry.VaultError(f"unknown vault_id={vault_id}")
    root = Path(row["path"])

    pages = _scan_pages(root)
    return {
        "vault_id": vault_id,
        "vault_path": str(root),
        "orphan_pages":     _orphan_pages(pages),
        "missing_concepts": _missing_concepts(pages, root),
        "empty_data":       [],   # Task 10
        "dangling_links":   [],   # Task 10
    }


def _scan_pages(root: Path) -> list[tuple[str, str, float]]:
    """Return [(relpath, body, mtime), ...] for wiki/* notes (excluding index/log)."""
    out = []
    wiki_dir = root / "wiki"
    if not wiki_dir.is_dir():
        return out
    for p in sorted(wiki_dir.rglob("*.md")):
        if ".trash" in p.parts:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if rel in {"wiki/index.md", "wiki/log.md"}:
            continue
        text = p.read_text(encoding="utf-8")
        out.append((rel, text, p.stat().st_mtime))
    return out


def _slug_from_relpath(relpath: str) -> str:
    """wiki/entities/karpathy.md -> karpathy"""
    name = relpath.rsplit("/", 1)[-1]
    return name[:-3] if name.endswith(".md") else name


def _inbound_link_counts(pages: list[tuple[str, str, float]]) -> Counter:
    counter: Counter[str] = Counter()
    for _rel, body, _mt in pages:
        for m in _WIKILINK_RE.finditer(body):
            counter[m.group(1).strip()] += 1
        for m in _MDLINK_RE.finditer(body):
            target = m.group(1)
            counter[_slug_from_relpath(target)] += 1
    return counter


def _orphan_pages(pages: list[tuple[str, str, float]]) -> list[dict]:
    inbound = _inbound_link_counts(pages)
    now = time.time()
    out = []
    for rel, _body, mt in pages:
        slug = _slug_from_relpath(rel)
        if inbound.get(slug, 0) > 0:
            continue
        age_days = int((now - mt) / 86400)
        if age_days < ORPHAN_GRACE_DAYS:
            continue
        out.append({"relpath": rel, "age_days": age_days})
    return out


def _existing_slugs(root: Path) -> set[str]:
    """Slugs that DO have a page under wiki/entities/ or wiki/concepts/."""
    out: set[str] = set()
    for sub in ("entities", "concepts"):
        d = root / "wiki" / sub
        if not d.is_dir():
            continue
        for p in d.glob("*.md"):
            out.add(p.stem)
    return out


def _missing_concepts(
    pages: list[tuple[str, str, float]],
    root: Path,
    threshold: int = 2,
) -> list[dict]:
    existing = _existing_slugs(root)
    referenced_by: dict[str, list[str]] = defaultdict(list)
    for rel, body, _mt in pages:
        seen_in_this_page: set[str] = set()
        for m in _WIKILINK_RE.finditer(body):
            tgt = m.group(1).strip()
            if tgt in seen_in_this_page:
                continue
            seen_in_this_page.add(tgt)
            if tgt not in existing:
                referenced_by[tgt].append(rel)
    out = []
    for title, refs in sorted(referenced_by.items()):
        if len(refs) >= threshold:
            out.append({"title": title, "referenced_by": refs})
    return out
