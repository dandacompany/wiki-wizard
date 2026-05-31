"""Per-vault sqlite glossary runtime.

Stores terminology state at <vault_root>/.oh-my-wiki/glossary.db.
Owned by the terminology-manager persona; fact-checker and
consistency-checker do not write here.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from scripts import text_match

_NEVER = re.compile(r"(?!x)x")

GLOSSARY_DIR = ".oh-my-wiki"
GLOSSARY_FILE = "glossary.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS terms (
    id INTEGER PRIMARY KEY,
    vault_id INTEGER NOT NULL,
    canonical TEXT NOT NULL,
    aliases TEXT NOT NULL,
    definition TEXT,
    first_seen_relpath TEXT,
    last_updated TEXT NOT NULL,
    UNIQUE(vault_id, canonical)
);
CREATE INDEX IF NOT EXISTS idx_terms_vault ON terms(vault_id);
"""


class GlossaryError(Exception):
    """Raised for invalid input, missing term, etc."""


def open_db(vault_root: Path) -> Path:
    """Ensure .oh-my-wiki/glossary.db exists with schema; return the path."""
    vault_root = Path(vault_root)
    db_dir = vault_root / GLOSSARY_DIR
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / GLOSSARY_FILE
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return db_path


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "vault_id": row["vault_id"],
        "canonical": row["canonical"],
        "aliases": json.loads(row["aliases"]) if row["aliases"] else [],
        "definition": row["definition"],
        "first_seen_relpath": row["first_seen_relpath"],
        "last_updated": row["last_updated"],
    }


def upsert_term(
    db_path: Path,
    *,
    vault_id: int,
    canonical: str,
    aliases: list[str],
    definition: str | None = None,
    first_seen_relpath: str | None = None,
) -> int:
    """Insert or update a term. Returns row id."""
    if not canonical or not canonical.strip():
        raise GlossaryError("canonical term must be non-empty")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    aliases_json = json.dumps(list(aliases), ensure_ascii=False)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            "INSERT INTO terms (vault_id, canonical, aliases, definition, "
            "first_seen_relpath, last_updated) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(vault_id, canonical) DO UPDATE SET "
            "  aliases=excluded.aliases, "
            "  definition=COALESCE(excluded.definition, terms.definition), "
            "  first_seen_relpath=COALESCE(terms.first_seen_relpath, excluded.first_seen_relpath), "
            "  last_updated=excluded.last_updated",
            (vault_id, canonical, aliases_json, definition, first_seen_relpath, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM terms WHERE vault_id = ? AND canonical = ?",
            (vault_id, canonical),
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


def get_term(db_path: Path, *, vault_id: int, canonical: str) -> dict | None:
    """Lookup by canonical form."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM terms WHERE vault_id = ? AND canonical = ?",
            (vault_id, canonical),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_terms(db_path: Path, *, vault_id: int) -> list[dict]:
    """All terms for a vault, ordered by canonical."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM terms WHERE vault_id = ? ORDER BY canonical",
            (vault_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _build_variant_pattern(canonical: str, aliases: list[str]) -> re.Pattern:
    return text_match.build_name_pattern([canonical]) or _NEVER


def find_inconsistencies(
    db_path: Path,
    *,
    vault_id: int,
    vault_root: Path,
) -> list[dict]:
    """Scan vault markdown for surface forms that match a term's pattern
    but use an unrecognized case/spacing variant.

    Returns [{"canonical": str, "surface_form": str,
              "found_in": [relpath, ...]}, ...]
    """
    vault_root = Path(vault_root)
    terms = list_terms(db_path, vault_id=vault_id)
    if not terms:
        return []

    # Collect markdown files, skipping the glossary db dir
    md_files = []
    for path in vault_root.rglob("*.md"):
        if GLOSSARY_DIR in path.relative_to(vault_root).parts:
            continue
        md_files.append(path)

    findings: dict[tuple[str, str], set[str]] = {}
    for term in terms:
        canonical = term["canonical"]
        aliases = set(term["aliases"])
        known = {canonical} | aliases
        pattern = _build_variant_pattern(canonical, term["aliases"])
        for md in md_files:
            try:
                text = md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in pattern.finditer(text):
                surface = match.group(0)
                if surface in known:
                    continue
                key = (canonical, surface)
                rel = str(md.relative_to(vault_root))
                findings.setdefault(key, set()).add(rel)

    return [
        {
            "canonical": c,
            "surface_form": s,
            "found_in": sorted(paths),
        }
        for (c, s), paths in sorted(findings.items())
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys as _sys

    p = argparse.ArgumentParser(prog="scripts.glossary")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize .oh-my-wiki/glossary.db")
    p_init.add_argument("--vault-root", required=True, help="vault root directory")

    p_list = sub.add_parser("list", help="List all terms (JSON)")
    p_list.add_argument("--vault-root", required=True, help="vault root directory")
    p_list.add_argument("--vault-id", type=int, required=True)

    p_show = sub.add_parser("show", help="Show one term by canonical (JSON)")
    p_show.add_argument("--vault-root", required=True, help="vault root directory")
    p_show.add_argument("--vault-id", type=int, required=True)
    p_show.add_argument("--canonical", required=True)

    p_up = sub.add_parser("upsert", help="Insert or update a term")
    p_up.add_argument("--vault-root", required=True, help="vault root directory")
    p_up.add_argument("--vault-id", type=int, required=True)
    p_up.add_argument("--canonical", required=True)
    p_up.add_argument("--alias", action="append", default=[],
                      help="repeatable; each --alias adds one alias")
    p_up.add_argument("--definition")
    p_up.add_argument("--first-seen-relpath")

    p_lint = sub.add_parser("lint", help="Find surface-form inconsistencies (JSON)")
    p_lint.add_argument("--vault-root", required=True, help="vault root directory")
    p_lint.add_argument("--vault-id", type=int, required=True)

    args = p.parse_args(argv)
    vault_root = Path(args.vault_root)
    db_path = open_db(vault_root)

    if args.cmd == "init":
        print(str(db_path))
        return 0

    if args.cmd == "list":
        print(json.dumps(list_terms(db_path, vault_id=args.vault_id),
                         ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "show":
        row = get_term(db_path, vault_id=args.vault_id, canonical=args.canonical)
        if row is None:
            print(f"term not found: {args.canonical!r}", file=_sys.stderr)
            return 2
        print(json.dumps(row, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "upsert":
        try:
            term_id = upsert_term(
                db_path,
                vault_id=args.vault_id,
                canonical=args.canonical,
                aliases=args.alias,
                definition=args.definition,
                first_seen_relpath=args.first_seen_relpath,
            )
        except GlossaryError as exc:
            print(str(exc), file=_sys.stderr)
            return 2
        print(json.dumps({"id": term_id, "canonical": args.canonical},
                         ensure_ascii=False))
        return 0

    if args.cmd == "lint":
        result = find_inconsistencies(
            db_path, vault_id=args.vault_id, vault_root=vault_root,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    raise SystemExit(f"unknown cmd: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
