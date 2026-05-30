"""Vault health checks: frontmatter validity + sqlite↔disk drift."""
from __future__ import annotations

from pathlib import Path

from scripts import frontmatter, links, registry
from scripts.paths import registry_path

REQUIRED_FIELDS = ("title", "date", "type", "tags")
VALID_TYPES = {
    # memo-mode types
    "article", "link", "note", "paper", "video", "book", "doc",
    # wiki-mode layer types
    "summary", "entity", "concept", "comparison", "synthesis",
    # meta pages (index.md, log.md)
    "meta",
}

# Files whose frontmatter is intentionally minimal (no full REQUIRED_FIELDS check)
_META_RELPATHS = set(links.META_RELPATHS)


def check(db_path: Path, *, vault_id: int) -> dict:
    """Return a categorized report dict. Read-only."""
    conn = registry.connect(db_path)
    try:
        vault_row = conn.execute(
            "SELECT path FROM vaults WHERE id = ?", (vault_id,)
        ).fetchone()
        if vault_row is None:
            raise registry.VaultError(f"unknown vault_id={vault_id}")
        root = Path(vault_row["path"])
        rows = list(conn.execute(
            "SELECT relpath, mtime FROM notes WHERE vault_id = ?",
            (vault_id,),
        ))
    finally:
        conn.close()

    fm_issues: list[dict] = []
    missing_files: list[dict] = []
    mtime_drift: list[dict] = []

    # 1) sqlite rows vs disk
    for row in rows:
        abs_path = root / row["relpath"]
        if not abs_path.exists():
            missing_files.append({"relpath": row["relpath"]})
            continue
        disk_mtime = abs_path.stat().st_mtime
        if abs(disk_mtime - row["mtime"]) > 1.0:
            mtime_drift.append({
                "relpath": row["relpath"],
                "indexed_mtime": row["mtime"],
                "disk_mtime": disk_mtime,
            })

    # 2) disk files (.md, excluding .trash and raw/) — frontmatter checks
    for md in sorted(root.rglob("*.md")):
        if ".trash" in md.parts:
            continue
        relpath = str(md.relative_to(root)).replace("\\", "/")
        # Raw source files and meta pages have intentionally loose/absent frontmatter.
        if relpath in _META_RELPATHS or relpath.startswith("raw/"):
            continue
        text = md.read_text(encoding="utf-8")
        try:
            meta, _ = frontmatter.parse(text)
        except frontmatter.FrontmatterError as exc:
            fm_issues.append({
                "relpath": relpath,
                "issue": "malformed_yaml",
                "detail": str(exc),
            })
            continue
        for key in REQUIRED_FIELDS:
            if key not in meta:
                fm_issues.append({
                    "relpath": relpath,
                    "issue": f"missing_field:{key}",
                    "detail": None,
                })
        if "tags" in meta and not isinstance(meta["tags"], list):
            fm_issues.append({
                "relpath": relpath,
                "issue": "tags_not_list",
                "detail": f"got {type(meta['tags']).__name__}",
            })
        if "type" in meta and meta["type"] not in VALID_TYPES:
            fm_issues.append({
                "relpath": relpath,
                "issue": "invalid_type",
                "detail": str(meta["type"]),
            })

    broken = links.broken_links(db_path, vault_id=vault_id)
    orphan_pages = links.orphans(db_path, vault_id=vault_id)

    return {
        "vault_id": vault_id,
        "vault_path": str(root),
        "frontmatter_issues": fm_issues,
        "drift": {
            "missing_files": missing_files,
            "mtime_drift": mtime_drift,
        },
        "links": {
            "broken": broken,
            "orphans": orphan_pages,
        },
        "auto_fix_hints": _hints(fm_issues, missing_files, mtime_drift, broken, orphan_pages),
    }


def _hints(fm_issues, missing, drift, broken=None, orphan_pages=None) -> list[str]:
    hints = []
    if drift:
        hints.append("Run `reindex.incremental(db, vault_id=...)` to refresh mtime drift.")
    if missing:
        hints.append("Missing files: delete the orphan rows or restore the files.")
    if fm_issues:
        hints.append("Edit each file's YAML frontmatter to fix the reported issues.")
    if broken:
        hints.append("Broken links: fix the target slug or create the missing page.")
    if orphan_pages:
        hints.append("Orphan pages: add an inbound link from a related page, or archive.")
    return hints


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys

    p = argparse.ArgumentParser(description="Lint a registered vault.")
    p.add_argument("--db", default=None)
    p.add_argument("--vault-id", type=int, required=True)
    args = p.parse_args(argv)
    db = Path(args.db) if args.db else registry_path()
    report = check(db, vault_id=args.vault_id)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
