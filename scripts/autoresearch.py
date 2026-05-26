"""Autoresearch: stateful 3-round (capped at 5) research loop.

LLM does the open-ended work (decompose query into claims, invoke MCP search,
read sources, judge confidence, detect gaps, draft synthesis).
This script handles deterministic state: session directory, per-round JSON
artifacts, stop criterion, and final file-back to wiki/syntheses/.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from scripts import ingest, query, registry, slugify

MAX_ROUNDS_HARD_CAP = 5
DEFAULT_MAX_ROUNDS = 3


def _vault_row(db_path: Path, vault_id: int):
    conn = registry.connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM vaults WHERE id = ?", (vault_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise registry.VaultError(f"unknown vault_id={vault_id}")
    return row


def init_session(
    db_path: Path,
    *,
    vault_id: int,
    query: str,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> dict:
    """Create .oh-my-wiki/sessions/<ts>-<slug>/ with mission.json.
    Raises registry.VaultError if vault is not wiki-mode.
    Returns {session_id, session_dir, max_rounds}.
    """
    vault = _vault_row(db_path, vault_id)
    if vault["mode"] != "wiki":
        raise registry.VaultError(
            f"autoresearch requires a wiki-mode vault; vault {vault['name']!r} is {vault['mode']!r}"
        )
    capped = min(max(1, max_rounds), MAX_ROUNDS_HARD_CAP)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    slug = slugify.slugify(query)[:60] or "untitled"
    session_id = f"{ts}-{slug}"
    sessions_root = Path(vault["path"]) / ".oh-my-wiki" / "sessions"
    session_dir = sessions_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    mission = {
        "session_id": session_id,
        "query": query,
        "vault_id": vault_id,
        "vault_name": vault["name"],
        "max_rounds": capped,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (session_dir / "mission.json").write_text(
        json.dumps(mission, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "max_rounds": capped,
    }
