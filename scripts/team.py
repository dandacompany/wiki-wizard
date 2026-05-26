"""
scripts/team.py — team manifest loader, runner, and result aggregator.

Team templates live in teams/<name>.md as YAML-frontmatter Markdown files.
The public API (Tasks 9-11):

  load_template(name_or_path)  →  TeamTemplate
  run(template, source, ...)   →  list[DispatchResult]          (Task 10+)
  aggregate_results(results, session_dir)  →  dict              (Task 11)
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from scripts.backends import BACKENDS
from scripts.dispatch import dispatch_one, DispatchRequest, DispatchResult
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


# ── run() helpers ─────────────────────────────────────────────────────────────

def _resolve_model(worker: WorkerConfig, model_overrides: dict[str, str]) -> str:
    """Pick model: explicit override > hint-based default from backend catalog."""
    if worker.persona in model_overrides:
        return model_overrides[worker.persona]
    from scripts.backends import list_models
    catalog = list_models(worker.backend_default)
    hint = worker.model_hint
    for entry in catalog:
        if entry.get("hint") == hint:
            return entry["id"]
    return catalog[0]["id"] if catalog else "default"


def _make_request(
    worker: WorkerConfig,
    source_path: Path,
    backend_overrides: dict[str, str],
    model_overrides: dict[str, str],
    skip_permissions: dict[str, bool],
    timeout: int,
) -> DispatchRequest:
    backend = backend_overrides.get(worker.persona, worker.backend_default)
    model = _resolve_model(
        WorkerConfig(
            persona=worker.persona,
            backend_default=backend,
            model_hint=worker.model_hint,
        ),
        model_overrides,
    )
    return DispatchRequest(
        persona=worker.persona,
        backend=backend,
        model=model,
        source_path=source_path,
        skip_permissions=skip_permissions.get(worker.persona, False),
        timeout=timeout,
    )


# ── Public run() ──────────────────────────────────────────────────────────────

def run(
    template: TeamTemplate,
    source_path: Path,
    session_dir: Path,
    backend_overrides: dict[str, str],
    model_overrides: dict[str, str],
    skip_permissions: dict[str, bool] | None = None,
) -> list[DispatchResult]:
    """
    Execute all workers in `template` according to `template.mode`.

    parallel:    all workers dispatched concurrently (ThreadPoolExecutor)
    sequential:  workers dispatched one at a time; if inputs_from=previous,
                 the source_path for worker N is set to worker N-1's result_path
    mixed:       handled in Task 11 — raises NotImplementedError for now

    Returns results in the same order as template.workers.
    """
    if skip_permissions is None:
        skip_permissions = {}

    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    if template.mode == "parallel":
        return _run_parallel(
            template, source_path, session_dir,
            backend_overrides, model_overrides, skip_permissions,
        )
    if template.mode == "sequential":
        return _run_sequential(
            template, source_path, session_dir,
            backend_overrides, model_overrides, skip_permissions,
        )
    if template.mode == "mixed":
        raise NotImplementedError(
            "mixed mode is implemented in Task 11 — not yet available"
        )
    raise ValueError(f"Unknown mode: {template.mode!r}")


def _run_parallel(
    template: TeamTemplate,
    source_path: Path,
    session_dir: Path,
    backend_overrides: dict[str, str],
    model_overrides: dict[str, str],
    skip_permissions: dict[str, bool],
) -> list[DispatchResult]:
    results: dict[str, DispatchResult] = {}
    with ThreadPoolExecutor(max_workers=len(template.workers)) as pool:
        future_to_persona: dict[Any, str] = {}
        for w in template.workers:
            req = _make_request(
                w, source_path, backend_overrides,
                model_overrides, skip_permissions,
                template.timeout_seconds,
            )
            f = pool.submit(dispatch_one, req, session_dir)
            future_to_persona[f] = w.persona
        for f in as_completed(future_to_persona):
            persona = future_to_persona[f]
            results[persona] = f.result()
    # Preserve template order
    return [results[w.persona] for w in template.workers]


def _run_sequential(
    template: TeamTemplate,
    source_path: Path,
    session_dir: Path,
    backend_overrides: dict[str, str],
    model_overrides: dict[str, str],
    skip_permissions: dict[str, bool],
) -> list[DispatchResult]:
    results: list[DispatchResult] = []
    original_source = Path(source_path)
    last_result_path: Path | None = None
    for w in template.workers:
        # If this worker requests the previous worker's output as input, use it
        if w.inputs_from == "previous" and last_result_path is not None:
            effective_source = last_result_path
        else:
            effective_source = original_source
        req = _make_request(
            w, effective_source, backend_overrides,
            model_overrides, skip_permissions,
            template.timeout_seconds,
        )
        result = dispatch_one(req, session_dir)
        results.append(result)
        if result.result_path is not None:
            last_result_path = result.result_path
    return results
