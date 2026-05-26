"""Session-to-session hot cache. Generates wiki/hot.md (or hot.md root)
with a concise summary the dispatcher loads at SessionStart."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

from scripts import registry

CACHE_CAP = 2000  # chars
RECENT_LIMIT = 10  # most-recently-touched pages

_DEFAULT_SUMMARY = "(no prior session summary)"


def _resolve_cache_path(db_path: Path, *, data_dir: Path | None = None) -> Path:
    """Choose where the cache file lives based on active vault + mode."""
    active = registry.get_active(db_path)
    if active is None:
        base = data_dir or db_path.parent
        base.mkdir(parents=True, exist_ok=True)
        return base / "hot.md"
    root = Path(active["path"])
    if active["mode"] == "wiki":
        return root / "wiki" / "hot.md"
    return root / "hot.md"


def _list_vaults(db_path: Path) -> list[dict]:
    rows = registry.list_vaults(db_path)
    out = []
    for r in rows:
        out.append({
            "name": r["name"],
            "mode": r["mode"],
            "type": r["type"],
            "is_active": bool(r["is_active"]),
            "path": r["path"],
        })
    return out


def _recent_notes(db_path: Path, vault_id: int, limit: int) -> list[dict]:
    conn = registry.connect(db_path)
    try:
        rows = list(conn.execute(
            """
            SELECT relpath, title, summary, mtime
            FROM notes
            WHERE vault_id = ? AND parse_error = 0
            ORDER BY mtime DESC
            LIMIT ?
            """,
            (vault_id, limit),
        ))
    finally:
        conn.close()
    return [
        {
            "relpath": r["relpath"],
            "title": r["title"],
            "summary": r["summary"],
            "mtime": r["mtime"],
        }
        for r in rows
    ]


def build(
    db_path: Path,
    *,
    last_session_summary: str | None = None,
) -> str:
    """Render the hot cache markdown. Caller decides where to write it."""
    active = registry.get_active(db_path)
    vault_label = active["name"] if active else "(none)"
    mode_label = active["mode"] if active else "(none)"

    vaults = _list_vaults(db_path)
    vaults_section = "## Active vaults\n"
    if not vaults:
        vaults_section += "(no vaults registered)\n"
    else:
        for v in vaults:
            star = "* " if v["is_active"] else "- "
            vaults_section += (
                f"{star}{v['name']} ({v['mode']}, {v['type']}) — {v['path']}\n"
            )

    recent_section = "\n## Recent activity (last 10 pages)\n"
    if active is not None:
        notes = _recent_notes(db_path, active["id"], RECENT_LIMIT)
        if not notes:
            recent_section += "(no notes yet)\n"
        else:
            for n in notes:
                title = n["title"] or "(untitled)"
                recent_section += f"- {n['relpath']} — \"{title}\"\n"
    else:
        recent_section += "(no active vault)\n"

    summary = last_session_summary if last_session_summary else _DEFAULT_SUMMARY
    summary_section = "\n## Last session summary\n" + summary + "\n"

    header = (
        f"---\n"
        f"generated_at: {datetime.now().isoformat(timespec='seconds')}\n"
        f"generated_by: hot_cache.build\n"
        f"vault: {vault_label}\n"
        f"mode: {mode_label}\n"
        f"---\n\n"
    )

    text = header + vaults_section + recent_section + summary_section

    if len(text) > CACHE_CAP:
        # Truncate from the summary section first (it's the longest, last)
        excess = len(text) - CACHE_CAP
        cut_summary = max(0, len(summary) - excess - 20)
        summary_truncated = summary[:cut_summary] + "\n…(truncated)"
        summary_section = "\n## Last session summary\n" + summary_truncated + "\n"
        text = header + vaults_section + recent_section + summary_section
        if len(text) > CACHE_CAP:
            text = text[:CACHE_CAP]

    return text


def write(
    db_path: Path,
    *,
    last_session_summary: str | None = None,
    data_dir: Path | None = None,
) -> Path:
    """Build the cache and write it atomically. Returns the path written."""
    target = _resolve_cache_path(db_path, data_dir=data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = build(db_path, last_session_summary=last_session_summary)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".hot.md.", dir=str(target.parent), text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
    return target


def read(db_path: Path, *, data_dir: Path | None = None) -> str | None:
    """Read the cache for the current active vault. None if not present."""
    target = _resolve_cache_path(db_path, data_dir=data_dir)
    if not target.exists():
        return None
    return target.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys as _sys

    p = argparse.ArgumentParser(prog="scripts.hot_cache")
    p.add_argument("--db", default="data/registry.db")
    p.add_argument("--data-dir", default=None,
                   help="Override fallback dir when no active vault")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--on-session-start", action="store_true",
                   help="Read cache and print to stdout (silent if none)")
    g.add_argument("--on-session-stop", action="store_true",
                   help="Refresh cache from current state + optional summary on stdin")
    g.add_argument("--refresh", action="store_true",
                   help="Manual refresh equivalent to --on-session-stop without stdin")
    args = p.parse_args(argv)

    db_path = Path(args.db)
    data_dir = Path(args.data_dir) if args.data_dir else None

    if args.on_session_start:
        text = read(db_path, data_dir=data_dir)
        if text is not None:
            _sys.stdout.write(text)
        return 0

    # session-stop / refresh
    summary = None
    if args.on_session_stop and not _sys.stdin.isatty():
        summary = _sys.stdin.read().strip() or None
    target = write(db_path, last_session_summary=summary, data_dir=data_dir)
    _sys.stderr.write(f"hot_cache refreshed → {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
