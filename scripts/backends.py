"""Backend detection, model catalog, and CLI invocation builder for OMW dispatch.

Supports 4 backends: claude / codex / gemini / opencode.
Model IDs live in backends/<name>.json — never hardcoded here.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Root of the repo (parent of this file's parent directory)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# BACKENDS table
# ---------------------------------------------------------------------------
BACKENDS: dict[str, dict[str, Any]] = {
    "claude": {
        "cli_name": "claude",
        "detect_cmd": ["claude", "--version"],
        "auth_check_cmd": ["claude", "config", "get", "oauthAccount"],
        "skip_perm_flag": "--dangerously-skip-permissions",
        "non_interactive_flag": "-p",
        "system_prompt_flag": "--append-system-prompt",
        "model_flag": "--model",
        "model_catalog_path": "backends/claude.json",
    },
    "codex": {
        "cli_name": "codex",
        "detect_cmd": ["codex", "--version"],
        "auth_check_cmd": ["codex", "auth", "status"],
        "skip_perm_flag": "--yolo",
        "non_interactive_flag": "exec",
        "system_prompt_flag": "--instructions",
        "model_flag": "--model",
        "model_catalog_path": "backends/codex.json",
    },
    "gemini": {
        "cli_name": "gemini",
        "detect_cmd": ["gemini", "--version"],
        "auth_check_cmd": None,  # auth is implicit via gcloud
        "skip_perm_flag": None,  # no equivalent currently
        "non_interactive_flag": "-p",
        "system_prompt_flag": "--system",
        "model_flag": "--model",
        "model_catalog_path": "backends/gemini.json",
    },
    "opencode": {
        "cli_name": "opencode",
        "detect_cmd": ["opencode", "--version"],
        "auth_check_cmd": None,
        "skip_perm_flag": None,  # TBD per CLI's current state
        "non_interactive_flag": "run",
        "system_prompt_flag": "--system",
        "model_flag": "--model",
        "model_catalog_path": "backends/opencode.json",
    },
}


class BackendError(Exception):
    """Raised for missing/unauthed backend or bad invocation arguments."""


# ---------------------------------------------------------------------------
# detect_available
# ---------------------------------------------------------------------------

def detect_available(
    *,
    override_path: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Run each backend's detect_cmd. Return {name: {installed, version, authed}}.

    Args:
        override_path: If set (e.g. from OMW_BACKEND_OVERRIDE_PATH env var),
            prepend this directory to PATH so fake backends are found first.
            Used in tests with tests/fakes/.
    """
    import os

    env = None
    if override_path is not None:
        env = os.environ.copy()
        env["PATH"] = f"{override_path}:{env.get('PATH', '')}"

    result: dict[str, dict[str, Any]] = {}
    for name, spec in BACKENDS.items():
        info: dict[str, Any] = {"installed": False, "version": "", "authed": None}
        try:
            cp = subprocess.run(
                spec["detect_cmd"],
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
            if cp.returncode == 0:
                info["installed"] = True
                info["version"] = (cp.stdout or cp.stderr or "").strip()
            # authed check is advisory; skip if no auth_check_cmd
            if info["installed"] and spec.get("auth_check_cmd"):
                try:
                    acp = subprocess.run(
                        spec["auth_check_cmd"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        env=env,
                    )
                    info["authed"] = acp.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    info["authed"] = None
        except (OSError, subprocess.TimeoutExpired):
            pass
        result[name] = info
    return result


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------

def list_models(
    backend: str,
    *,
    repo_root: Path | None = None,
    hint_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Read backends/<name>.json model catalog.

    Returns list of {id, hint, description} dicts, optionally filtered by hint.
    Model IDs are sourced from the JSON file; never hardcoded in Python.

    Args:
        backend: one of the keys in BACKENDS.
        repo_root: override repo root (useful in tests with tmp catalogs).
        hint_filter: if given, return only models with this hint value.
                     Must be one of: fast, standard, most_capable.
    """
    import json as _json

    if backend not in BACKENDS:
        raise BackendError(f"unknown backend: {backend!r}")

    root = repo_root if repo_root is not None else _REPO_ROOT
    catalog_rel = BACKENDS[backend]["model_catalog_path"]
    catalog_path = root / catalog_rel

    if not catalog_path.exists():
        raise BackendError(
            f"model catalog not found for backend {backend!r}: {catalog_path}"
        )

    with catalog_path.open(encoding="utf-8") as fh:
        models: list[dict[str, Any]] = _json.load(fh)

    if hint_filter is not None:
        models = [m for m in models if m.get("hint") == hint_filter]

    return models
