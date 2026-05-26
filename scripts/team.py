"""
scripts/team.py — team manifest loader, runner, and result aggregator.

Team templates live in teams/<name>.md as YAML-frontmatter Markdown files.
The public API (Tasks 9-11):

  load_template(name_or_path)  →  TeamTemplate
  run(template, source, ...)   →  list[DispatchResult]          (Task 10+)
  aggregate_results(results, session_dir)  →  dict              (Task 11)
"""
from __future__ import annotations

import datetime
import json
import time
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
        return _run_mixed(
            template, source_path, session_dir,
            backend_overrides, model_overrides, skip_permissions,
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


def _run_mixed(
    template: TeamTemplate,
    source_path: Path,
    session_dir: Path,
    backend_overrides: dict[str, str],
    model_overrides: dict[str, str],
    skip_permissions: dict[str, bool],
) -> list[DispatchResult]:
    """
    Execute stages in order. Within each stage entry:
      - {"parallel": [persona_name, ...]}  → dispatch all concurrently
      - {"sequential": [persona_name, ...]}  → dispatch one at a time

    inputs_from=previous is resolved across stages: each stage receives
    the last result_path of the preceding stage as its source_path.

    Returns results in template.workers order.
    """
    stages: list[dict] = template.stages or []

    # Build persona → WorkerConfig lookup
    worker_map: dict[str, WorkerConfig] = {w.persona: w for w in template.workers}

    results_by_persona: dict[str, DispatchResult] = {}
    current_source = Path(source_path)
    last_result_path: Path | None = None

    for stage_def in stages:
        stage_results: list[DispatchResult] = []

        if "parallel" in stage_def:
            personas = stage_def["parallel"]
            workers_in_stage = [worker_map[p] for p in personas]
            # Parallel: all workers in this stage share the same current_source
            with ThreadPoolExecutor(max_workers=len(workers_in_stage)) as pool:
                fmap: dict[Any, str] = {}
                for w in workers_in_stage:
                    src = last_result_path if (w.inputs_from == "previous"
                                               and last_result_path) else current_source
                    req = _make_request(w, src, backend_overrides,
                                        model_overrides, skip_permissions,
                                        template.timeout_seconds)
                    fmap[pool.submit(dispatch_one, req, session_dir)] = w.persona
                for f in as_completed(fmap):
                    stage_results.append(f.result())

        elif "sequential" in stage_def:
            personas = stage_def["sequential"]
            stage_source = last_result_path if last_result_path else current_source
            for p in personas:
                w = worker_map[p]
                src = stage_source if w.inputs_from == "previous" else current_source
                req = _make_request(w, src, backend_overrides,
                                    model_overrides, skip_permissions,
                                    template.timeout_seconds)
                r = dispatch_one(req, session_dir)
                stage_results.append(r)
                if r.result_path:
                    stage_source = r.result_path

        for r in stage_results:
            # Derive persona from worker_id (strip "worker-" prefix)
            persona_key = r.worker_id.split("-", 1)[1] if "-" in r.worker_id else r.worker_id
            results_by_persona[persona_key] = r
        # Update last_result_path to the last result for the next stage
        if stage_results:
            last_result_path = stage_results[-1].result_path

    # Preserve template.workers order
    return [
        results_by_persona.get(
            w.persona,
            DispatchResult(f"worker-{w.persona}", "skipped", None, 0, "", session_dir),
        )
        for w in template.workers
    ]


def aggregate_results(
    results: list[DispatchResult],
    session_dir: Path,
    template_name: str,
    started_at: float | None = None,
) -> dict:
    """
    Aggregate DispatchResult list into a summary dict and write summary.json.

    summary.json shape:
    {
      "template": "<name>",
      "started_at": "<iso>",
      "total_wall_seconds": <float>,
      "workers": [
        {
          "worker_id": "...",
          "persona": "...",
          "status": "ok"|"failed"|"timeout"|"skipped",
          "result_path": "/abs/path/or/empty",
          "duration_seconds": <float>,
          "model": "..."
        }, ...
      ]
    }
    """
    now = time.monotonic()
    wall = now - started_at if started_at is not None else 0.0

    workers_summary = []
    for r in results:
        # Derive persona from worker_id (strip "worker-" prefix)
        persona = r.worker_id.split("-", 1)[1] if "-" in r.worker_id else r.worker_id
        workers_summary.append({
            "worker_id": r.worker_id,
            "persona": persona,
            "status": r.status,
            "result_path": str(r.result_path) if r.result_path else "",
            "duration_seconds": r.duration_seconds,
            "model": r.model,
        })

    summary = {
        "template": template_name,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_wall_seconds": wall,
        "workers": workers_summary,
    }

    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    return summary
