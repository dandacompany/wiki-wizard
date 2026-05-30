"""Filesystem → sqlite indexer using mtime to skip unchanged files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts import frontmatter, links, registry


def full(db_path: Path, *, vault_id: int) -> int:
    """Rescan everything. Returns number of notes indexed."""
    vault_path = _vault_path(db_path, vault_id)
    return _scan(db_path, vault_id, vault_path, incremental=False)


def incremental(db_path: Path, *, vault_id: int) -> int:
    """Only upsert files whose mtime exceeds the recorded one."""
    vault_path = _vault_path(db_path, vault_id)
    return _scan(db_path, vault_id, vault_path, incremental=True)


def _vault_path(db_path: Path, vault_id: int) -> Path:
    conn = registry.connect(db_path)
    try:
        row = conn.execute(
            "SELECT path FROM vaults WHERE id = ?", (vault_id,)
        ).fetchone()
        if not row:
            raise registry.VaultError(f"vault id {vault_id} not found")
        return Path(row[0])
    finally:
        conn.close()


def _existing_mtimes(db_path: Path, vault_id: int) -> dict[str, float]:
    conn = registry.connect(db_path)
    try:
        return {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT relpath, mtime FROM notes WHERE vault_id = ?", (vault_id,)
            )
        }
    finally:
        conn.close()


def _classify_layer(relpath: str) -> str:
    parts = relpath.split("/")
    if parts[0] == "raw":
        return "raw"
    if parts[0] == "wiki":
        if len(parts) == 2 and parts[1] in {"index.md", "log.md"}:
            return "meta"
        return "wiki"
    return "memo"


def _scan(
    db_path: Path,
    vault_id: int,
    vault_path: Path,
    *,
    incremental: bool,
) -> int:
    registry.init_db(db_path)  # idempotent; guarantees the links table on old vaults
    known = _existing_mtimes(db_path, vault_id) if incremental else {}
    count = 0
    for path in vault_path.rglob("*.md"):
        if any(part in {".trash", ".obsidian", ".git"} for part in path.parts):
            continue
        rel = str(path.relative_to(vault_path)).replace("\\", "/")
        mtime = path.stat().st_mtime
        if incremental and rel in known and known[rel] >= mtime:
            continue
        raw = path.read_text(encoding="utf-8")
        try:
            meta, body = frontmatter.parse(raw)
            parse_error = False
        except frontmatter.FrontmatterError:
            meta = {}
            body = raw  # still extract links from a frontmatter-broken note
            parse_error = True
        if not meta:
            parse_error = True
        tags = meta.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        note_id = registry.upsert_note(
            db_path,
            vault_id=vault_id,
            relpath=rel,
            layer=_classify_layer(rel),
            title=meta.get("title"),
            summary=meta.get("summary"),
            mtime=mtime,
            size_bytes=path.stat().st_size,
            tags=[str(t) for t in tags],
            parse_error=parse_error,
        )
        links.replace_links(db_path, vault_id=vault_id, src_note_id=note_id, body=body)
        count += 1
    links.resolve(db_path, vault_id)
    return count


def main(argv: list[str] | None = None) -> int:
    """CLI: reindex a vault. Default incremental; --full for a full rescan."""
    from scripts.paths import registry_path
    parser = argparse.ArgumentParser(
        prog="reindex", description="Reindex a vault's notes into the registry."
    )
    parser.add_argument("--vault-id", type=int, required=True)
    parser.add_argument("--db", default=None, help="registry db path (default: ~/.omw/registry.db)")
    parser.add_argument("--full", action="store_true", help="full rescan (default: incremental)")
    args = parser.parse_args(argv)
    db = Path(args.db) if args.db else registry_path()
    count = full(db, vault_id=args.vault_id) if args.full else incremental(db, vault_id=args.vault_id)
    print(json.dumps({
        "vault_id": args.vault_id,
        "mode": "full" if args.full else "incremental",
        "indexed": count,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
