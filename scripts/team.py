"""
scripts/team.py — team manifest loader, runner, and result aggregator.

Team templates live in teams/<name>.md as YAML-frontmatter Markdown files.
The public API (Tasks 9-11):

  load_template(name_or_path)  →  TeamTemplate
  run(template, source, ...)   →  list[DispatchResult]          (Task 10+)
  aggregate_results(results, session_dir)  →  dict              (Task 11)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from scripts.backends import BACKENDS
from scripts.personas import list_personas as _list_personas_raw


TEAMS_DIR = Path(__file__).parent.parent / "teams"
KNOWN_BACKENDS: frozenset[str] = frozenset(BACKENDS.keys())


# ── Helper: extract known persona names from v2.2a list_personas() ─────────
# list_personas() returns list[dict] with a "name" key per persona.
# We avoid modifying personas.py to keep v2.2a stable.

def _known_persona_names() -> set[str]:
    """Return a set of persona slug names from the existing list_personas()."""
    return {p["name"] for p in _list_personas_raw()}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class WorkerConfig:
    persona: str
    backend_default: str
    model_hint: str = "standard"
    inputs_from: str | None = None   # "previous" or a worker name
    args: dict[str, Any] = field(default_factory=dict)
    when: str = "always"


@dataclass
class TeamTemplate:
    name: str
    description: str
    mode: str                          # "parallel" | "sequential" | "mixed"
    workers: list[WorkerConfig]
    stages: list[dict] | None = None   # only for mode=mixed
    timeout_seconds: int = 600
    body: str = ""                     # markdown body below frontmatter


class TeamValidationError(ValueError):
    """Raised when a team template fails validation."""


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_worker(raw: dict) -> WorkerConfig:
    return WorkerConfig(
        persona=raw["persona"],
        backend_default=raw.get("backend_default", "claude"),
        model_hint=raw.get("model_hint", "standard"),
        inputs_from=raw.get("inputs_from"),
        args=raw.get("args", {}),
        when=raw.get("when", "always"),
    )


def load_template(name_or_path: str | Path) -> TeamTemplate:
    """
    Load and validate a team template.

    ``name_or_path`` can be:
      - a short name like ``"review-pipeline"``  → resolves to ``teams/<name>.md``
      - a ``Path`` or absolute/relative path string → reads directly (test-friendly)

    Raises:
      FileNotFoundError    if the template file does not exist.
      TeamValidationError  if frontmatter is invalid, references an unknown
                           persona or backend, or violates mode↔stages rules.
    """
    path = Path(name_or_path)

    # If no suffix (e.g. "review-pipeline") → look in teams/
    if not path.suffix:
        path = TEAMS_DIR / f"{name_or_path}.md"

    if not path.exists():
        raise FileNotFoundError(f"Team template not found: {path}")

    raw_text = path.read_text(encoding="utf-8")

    # Split YAML frontmatter from markdown body
    if not raw_text.startswith("---"):
        raise TeamValidationError(
            "Team template must start with '---' YAML frontmatter"
        )

    parts = raw_text.split("---", 2)
    # parts[0] == "" (before first ---), parts[1] == fm, parts[2] == body
    fm_text = parts[1] if len(parts) > 1 else ""
    body = parts[2].strip() if len(parts) > 2 else ""

    fm: dict = yaml.safe_load(fm_text) or {}

    name = fm.get("name") or path.stem
    mode = fm.get("mode", "parallel")
    raw_workers: list[dict] = fm.get("workers", [])
    stages = fm.get("stages")

    workers = [_parse_worker(w) for w in raw_workers]

    # ── Validation ────────────────────────────────────────────────────────────
    known_personas = _known_persona_names()

    for w in workers:
        if w.persona not in known_personas:
            raise TeamValidationError(
                f"unknown persona '{w.persona}'. "
                f"Available: {sorted(known_personas)}"
            )
        if w.backend_default not in KNOWN_BACKENDS:
            raise TeamValidationError(
                f"unknown backend '{w.backend_default}'. "
                f"Available: {sorted(KNOWN_BACKENDS)}"
            )

    if mode == "mixed" and not stages:
        raise TeamValidationError(
            "mode=mixed requires a 'stages:' list in frontmatter"
        )

    return TeamTemplate(
        name=name,
        description=fm.get("description", ""),
        mode=mode,
        workers=workers,
        stages=stages,
        timeout_seconds=int(fm.get("timeout_seconds", 600)),
        body=body,
    )
