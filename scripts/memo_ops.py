"""CRUD operations for individual memo files."""
from __future__ import annotations

from pathlib import Path

from scripts import frontmatter, registry, reindex, slugify


def _vault_root(db_path: Path, vault_id: int) -> Path:
    conn = registry.connect(db_path)
    try:
        row = conn.execute("SELECT path FROM vaults WHERE id = ?", (vault_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise registry.VaultError(f"unknown vault_id={vault_id}")
    return Path(row["path"])


def _resolve_slug(root: Path, folder: str, base: str) -> str:
    """Return a non-colliding filename stem under root/folder."""
    folder_dir = root / folder
    candidate = base
    n = 2
    while (folder_dir / f"{candidate}.md").exists():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def write(
    db_path: Path,
    *,
    vault_id: int,
    title: str,
    body: str,
    folder: str,
    tags: list[str],
    type_: str,
    date_str: str,
    summary: str | None = None,
    status: str | None = "inbox",
) -> str:
    """Create a new memo file. Returns the relpath stored in the registry."""
    root = _vault_root(db_path, vault_id)
    base = slugify.slugify(title)
    stem = _resolve_slug(root, folder, base)
    relpath = f"{folder}/{stem}.md"

    meta: dict = {
        "title": title,
        "date": date_str,
        "type": type_,
        "tags": list(tags),
    }
    if summary:
        meta["summary"] = summary
    if status:
        meta["status"] = status

    text = frontmatter.dump(meta, body)
    abs_path = root / relpath
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(text, encoding="utf-8")

    reindex.incremental(db_path, vault_id=vault_id)
    return relpath


def edit_meta(
    db_path: Path,
    *,
    vault_id: int,
    relpath: str,
    key: str,
    value,
) -> None:
    """Edit a single frontmatter field in place. Body untouched."""
    root = _vault_root(db_path, vault_id)
    abs_path = root / relpath
    if not abs_path.exists():
        raise FileNotFoundError(relpath)
    text = abs_path.read_text(encoding="utf-8")
    new_text = frontmatter.edit_field(text, key, value)
    abs_path.write_text(new_text, encoding="utf-8")
    reindex.incremental(db_path, vault_id=vault_id)
