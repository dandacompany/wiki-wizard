"""Bulk import external corpora (folder / Obsidian / Notion) into an omw vault.

Deterministic file/API I/O. Default target layer is `raw` (preserve originals);
`--layer wiki` prepends a minimal frontmatter stub to files that lack one.
Idempotent: a file whose dest already exists with identical content is skipped.
"""
from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

from scripts import registry, reindex

_SKIP_DIRS = {".obsidian", ".git", ".trash"}
_TEXT_EXTS = {".md", ".txt"}
_IMPORT_EXTS = _TEXT_EXTS | {".pdf"}


def _vault_root(db_path: Path, vault_id: int) -> Path:
    conn = registry.connect(db_path)
    try:
        row = conn.execute("SELECT path FROM vaults WHERE id = ?", (vault_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise registry.VaultError(f"unknown vault_id={vault_id}")
    return Path(row["path"])


def _wiki_stub(title: str, *, date: str) -> str:
    return (f"---\ntitle: {title}\ntype: imported\ndate: {date}\ntags: []\n---\n\n")


def _has_frontmatter(text: str) -> bool:
    return text.lstrip().startswith("---")


def import_folder(db_path: Path, *, vault_id: int, src_dir, layer: str = "raw",
                  source: str = "folder") -> dict:
    """Import .md/.txt/.pdf from a folder (or Obsidian vault) into <layer>/import/."""
    src = Path(src_dir)
    root = _vault_root(db_path, vault_id)
    today = datetime.date.today().isoformat()
    imported, skipped = [], []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in _IMPORT_EXTS:
            continue
        rel_to_src = path.relative_to(src).as_posix()
        dest_rel = f"{layer}/import/{rel_to_src}"
        dest = root / dest_rel
        is_text = path.suffix.lower() in _TEXT_EXTS
        if is_text:
            content = path.read_text(encoding="utf-8")
            if layer == "wiki" and not _has_frontmatter(content):
                content = _wiki_stub(path.stem, date=today) + content
            new_bytes = content.encode("utf-8")
        else:
            new_bytes = path.read_bytes()
        if dest.exists() and hashlib.sha256(dest.read_bytes()).digest() == \
                hashlib.sha256(new_bytes).digest():
            skipped.append(dest_rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(new_bytes)
        imported.append(dest_rel)
    reindex.incremental(db_path, vault_id=vault_id)
    return {"imported": imported, "skipped": skipped, "source": source}
