"""omw serve — token-authenticated retrieve-only query API over a local vault.

Retrieve-only by design: the server runs NO LLM. It returns `search_index.query`
hits unchanged; answer synthesis stays in-session (host LLM) or a future flag.
See docs/superpowers/specs/2026-05-30-omw-messenger-query-api-design.md.
"""
from __future__ import annotations

from pathlib import Path

from scripts import registry
from scripts import search_index


class ServeError(Exception):
    """A client-facing error carrying an HTTP status and a safe message."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _resolve_vault(db_path: Path, name: str | None):
    """Resolve a vault row by name, else the active vault. Raises ServeError."""
    if name:
        for row in registry.list_vaults(db_path):
            if row["name"] == name:
                return row
        raise ServeError(404, f"vault not found: {name}")
    row = registry.get_active(db_path)
    if row is None:
        raise ServeError(409, "no active vault; run omw vault use <name>")
    return row


def handle_query(
    payload: dict,
    *,
    db_path: Path,
    default_vault: str | None = None,
    max_limit: int = 10,
) -> dict:
    """Validate, resolve vault, run the ranker. Pure (no HTTP/auth). Raises ServeError."""
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ServeError(400, "missing or empty 'text'")

    raw_limit = payload.get("limit", 5)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        raise ServeError(400, "'limit' must be an integer")
    limit = max(1, min(limit, max_limit))

    row = _resolve_vault(db_path, payload.get("vault") or default_vault)
    hits = search_index.query(db_path, vault_id=row["id"], query=text, limit=limit)
    return {"query": text, "vault": row["name"], "count": len(hits), "hits": hits}
