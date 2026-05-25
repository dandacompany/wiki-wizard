"""Wiki-mode query helpers. Most of query is an LLM workflow; this is the file-back side."""
from __future__ import annotations

from pathlib import Path

from scripts import frontmatter, ingest, registry, slugify


def write_synthesis(
    db_path: Path,
    *,
    vault_id: int,
    title: str,
    body: str,
    citations: list[str],
    tags: list[str],
    date_str: str,
) -> str:
    """Write a synthesis page under wiki/syntheses/. Returns relpath."""
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

    base = slugify.slugify(title)
    relpath = ingest._resolve_path(root, "wiki/syntheses", base, "md")
    meta = {
        "title": title,
        "date": date_str,
        "type": "synthesis",
        "tags": list(tags),
        "status": "processed",
        "citations": list(citations),
    }
    abs_path = root / relpath
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(frontmatter.dump(meta, body), encoding="utf-8")
    return relpath
