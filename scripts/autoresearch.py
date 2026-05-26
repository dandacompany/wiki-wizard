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


def record_round(
    session_dir: Path,
    *,
    round_num: int,
    claims: list[dict],
    gaps_remaining: list[str],
    notes: str = "",
) -> Path:
    """Write round-N.json into session_dir. Idempotent (overwrites)."""
    session_dir = Path(session_dir)
    mission_path = session_dir / "mission.json"
    if not mission_path.exists():
        raise FileNotFoundError(f"no mission.json in {session_dir}")
    mission = json.loads(mission_path.read_text(encoding="utf-8"))
    max_rounds = mission["max_rounds"]
    if not (1 <= round_num <= max_rounds):
        raise ValueError(
            f"round_num={round_num} out of bounds (1..{max_rounds})"
        )
    payload = {
        "round_num": round_num,
        "claims": list(claims),
        "gaps_remaining": list(gaps_remaining),
        "notes": notes,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    target = session_dir / f"round-{round_num}.json"
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def should_stop(session_dir: Path) -> tuple[bool, str]:
    """Return (stop, reason). reason ∈ {max_rounds, no_gaps, in_progress}."""
    session_dir = Path(session_dir)
    mission_path = session_dir / "mission.json"
    if not mission_path.exists():
        raise FileNotFoundError(f"no mission.json in {session_dir}")
    mission = json.loads(mission_path.read_text(encoding="utf-8"))
    max_rounds = mission["max_rounds"]

    round_files = sorted(session_dir.glob("round-*.json"))
    if not round_files:
        return (False, "in_progress")

    last = json.loads(round_files[-1].read_text(encoding="utf-8"))
    if not last["gaps_remaining"]:
        return (True, "no_gaps")
    if len(round_files) >= max_rounds:
        return (True, "max_rounds")
    return (False, "in_progress")
