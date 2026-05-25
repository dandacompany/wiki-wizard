"""Wiki-mode ingest helpers: save raw sources, write wiki pages, update index/log."""
from __future__ import annotations

from pathlib import Path

from scripts import frontmatter, registry, slugify


def _vault_root(db_path: Path, vault_id: int) -> Path:
    conn = registry.connect(db_path)
    try:
        row = conn.execute(
            "SELECT path FROM vaults WHERE id = ?", (vault_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise registry.VaultError(f"unknown vault_id={vault_id}")
    return Path(row["path"])


def _resolve_path(root: Path, folder: str, base: str, ext: str) -> str:
    """Return non-colliding relpath under root/folder with given base + ext."""
    candidate = base
    n = 2
    while (root / folder / f"{candidate}.{ext}").exists():
        candidate = f"{base}-{n}"
        n += 1
    return f"{folder}/{candidate}.{ext}"


def save_raw(
    db_path: Path,
    *,
    vault_id: int,
    content: str,
    ext: str,
    title: str,
    date_str: str,
) -> str:
    """Save a raw source under raw/<date>-<slug>.<ext>. Returns relpath."""
    root = _vault_root(db_path, vault_id)
    base = f"{date_str}-{slugify.slugify(title)}"
    relpath = _resolve_path(root, "raw", base, ext)
    abs_path = root / relpath
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    return relpath


def save_raw_pdf(
    db_path: Path,
    *,
    vault_id: int,
    pdf_bytes: bytes,
    title: str,
    date_str: str,
) -> tuple[str, str]:
    """Save the original PDF bytes AND extract text. Returns (relpath, extracted_text)."""
    from pypdf import PdfReader
    from io import BytesIO

    root = _vault_root(db_path, vault_id)
    base = f"{date_str}-{slugify.slugify(title)}"
    relpath = _resolve_path(root, "raw", base, "pdf")
    abs_path = root / relpath
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(pdf_bytes)

    reader = PdfReader(BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    extracted = "\n\n".join(parts).strip()
    return relpath, extracted
