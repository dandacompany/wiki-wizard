"""Register a memo folder as a memo-mode vault, with optional frontmatter migration."""
from __future__ import annotations

from datetime import date as _date
from pathlib import Path

from scripts import frontmatter, registry

REQUIRED_FIELDS = ("title", "date", "type", "tags")
DEFAULT_TYPE = "note"


def _scan_files(root: Path) -> list[Path]:
    return [p for p in sorted(root.rglob("*.md")) if ".trash" not in p.parts]


def _plan_changes(meta: dict, today: str) -> list[dict]:
    """Return ordered list of changes to bring meta in line with wiki-wizard rules."""
    changes: list[dict] = []
    if "title" not in meta:
        changes.append({"field": "title", "op": "add", "value": "Untitled"})
    if "date" not in meta:
        changes.append({"field": "date", "op": "add", "value": today})
    if "type" not in meta:
        changes.append({"field": "type", "op": "add", "value": DEFAULT_TYPE})
    if "tags" not in meta:
        changes.append({"field": "tags", "op": "add", "value": []})
    elif not isinstance(meta["tags"], list):
        if isinstance(meta["tags"], str):
            new = [t.strip() for t in meta["tags"].split(",") if t.strip()]
        else:
            new = [str(meta["tags"])]
        changes.append({"field": "tags", "op": "normalize", "value": new})
    return changes


def dry_run(db_path: Path, *, vault_id: int) -> dict:
    """Return a per-file plan without mutating anything."""
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

    today = _date.today().isoformat()
    files: list[dict] = []
    needs = 0
    clean = 0
    for f in _scan_files(root):
        relpath = str(f.relative_to(root))
        text = f.read_text(encoding="utf-8")
        try:
            meta, _ = frontmatter.parse(text)
        except frontmatter.FrontmatterError as exc:
            files.append({
                "relpath": relpath,
                "changes": [{"field": "_yaml_", "op": "skip", "value": str(exc)}],
            })
            needs += 1
            continue
        changes = _plan_changes(meta, today)
        files.append({"relpath": relpath, "changes": changes})
        if changes:
            needs += 1
        else:
            clean += 1

    return {
        "vault_id": vault_id,
        "vault_path": str(root),
        "files": files,
        "summary": {
            "total": len(files),
            "needs_changes": needs,
            "clean": clean,
        },
    }
