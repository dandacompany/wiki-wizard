"""Wiki link graph: extract [[wikilink]] + markdown internal [](*.md) refs,
populate the `links` table, resolve to notes by basename-slug, and query
backlinks / orphans / broken-links / graph. Semantic edge types are F#2.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts import registry

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_MDLINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:")


def _slugify(target: str) -> str:
    """basename without .md, alias/heading/query stripped, lowercased."""
    t = target.split("|", 1)[0].split("#", 1)[0].split("?", 1)[0]
    t = t.strip().split("/")[-1]
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.strip().lower()


def extract_links(body: str) -> list[tuple[str, str, int]]:
    """Return [(dst_slug, link_type, position), ...] in document order.

    link_type is 'wikilink' or 'markdown'. External URLs, mailto:, pure
    fragments, and non-.md markdown targets are skipped.
    """
    found: list[tuple[int, str, str]] = []  # (offset, slug, kind)
    for m in _WIKILINK_RE.finditer(body):
        slug = _slugify(m.group(1))
        if slug:
            found.append((m.start(), slug, "wikilink"))
    for m in _MDLINK_RE.finditer(body):
        target = m.group(1).strip()
        low = target.lower()
        if not target or low.startswith(_EXTERNAL_PREFIXES) or target.startswith("#"):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0].strip()
        if not path_part.lower().endswith(".md"):
            continue
        slug = _slugify(target)
        if slug:
            found.append((m.start(), slug, "markdown"))
    found.sort(key=lambda x: x[0])
    return [(slug, kind, i) for i, (_, slug, kind) in enumerate(found)]


def replace_links(db_path: Path, *, vault_id: int, src_note_id: int, body: str) -> None:
    """Replace all outbound links for one note (dst_note_id left NULL)."""
    conn = registry.connect(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM links WHERE src_note_id = ?", (src_note_id,))
            for slug, link_type, position in extract_links(body):
                conn.execute(
                    "INSERT INTO links(vault_id, src_note_id, dst_slug, dst_note_id, "
                    "link_type, position) VALUES (?, ?, ?, NULL, ?, ?)",
                    (vault_id, src_note_id, slug, link_type, position),
                )
    finally:
        conn.close()


def resolve(db_path: Path, vault_id: int) -> None:
    """Set links.dst_note_id by basename-slug match; ambiguous/missing -> NULL."""
    conn = registry.connect(db_path)
    try:
        with conn:
            slug_to_ids: dict[str, list[int]] = {}
            for row in conn.execute(
                "SELECT id, relpath FROM notes WHERE vault_id = ?", (vault_id,)
            ):
                slug_to_ids.setdefault(_slugify(row["relpath"]), []).append(row["id"])
            for row in conn.execute(
                "SELECT DISTINCT dst_slug FROM links WHERE vault_id = ?", (vault_id,)
            ):
                ids = slug_to_ids.get(row["dst_slug"], [])
                dst = ids[0] if len(ids) == 1 else None
                conn.execute(
                    "UPDATE links SET dst_note_id = ? WHERE vault_id = ? AND dst_slug = ?",
                    (dst, vault_id, row["dst_slug"]),
                )
    finally:
        conn.close()
