"""
scripts/dispatch.py — single-persona dispatch: build prompt, spawn worker, wait.

Combines:
  - persona loading (scripts.personas.load_persona)
  - backend resolution (scripts.backends.build_invocation)
  - tmux worker lifecycle (scripts.tmux_runtime.spawn_worker / wait_for_workers)
  - result return as DispatchResult

Worker prompt format (written to worker_dir/input.md, §4.8):
  === PERSONA ===
  <persona body, frontmatter stripped>

  === TASK ===
  Source: <path>
  Source content:
  ---
  <source text>
  ---

  Required output:
  - output_kind: <kind>
  - output_target_path: <absolute path>
  - after producing the output file, write done.json sentinel with:
    {"status": "ok", "result_path": "<target>", "duration_seconds": <int>, "model": "<model>"}
    to: <worker_dir>/done.json

  Do NOT modify any files outside <worker_dir>/ and <output_target_path>.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from scripts.backends import build_invocation, BackendError
from scripts.tmux_runtime import spawn_worker, wait_for_workers, shutdown_session
from scripts.personas import load_persona, PersonaError


# ── Suffix map for sibling_suffix personas ─────────────────────────────────

_SIBLING_SUFFIX_MAP: dict[str, str] = {
    "fact-checker": "factcheck",
    "consistency-checker": "consistency",
}


# ── Public types ──────────────────────────────────────────────────────────────

@dataclass
class DispatchRequest:
    persona: str          # e.g. "fact-checker"
    backend: str          # e.g. "claude"
    model: str            # e.g. "claude-sonnet-4-6"
    source_path: Path
    skip_permissions: bool = False
    extra_args: list[str] = field(default_factory=list)
    timeout: int = 600


@dataclass
class DispatchResult:
    worker_id: str
    status: str           # "ok" | "failed" | "timeout"
    result_path: Path | None
    duration_seconds: float
    model: str
    session_dir: Path
    persona: str = ""     # persona slug name (e.g. "fact-checker")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _output_target(
    source_path: Path,
    output_kind: str,
    persona_name: str,
    session_dir: Path,
    worker_id: str,
    lang: str | None = None,
    suffix: str | None = None,
) -> Path | None:
    """Derive the expected output path from the persona's output_kind.

    Returns None for stdout kind (no file output).
    """
    slug = persona_name

    if output_kind == "stdout":
        return None

    if output_kind == "sibling_suffix":
        # Use explicit suffix if provided, otherwise look up the map
        s = suffix or _SIBLING_SUFFIX_MAP.get(slug, slug.replace("-", ""))
        return source_path.parent / f"{source_path.stem}.{s}{source_path.suffix}"

    if output_kind == "sibling_file":
        # translator → doc.<lang>.md
        resolved_lang = lang or "translated"
        return source_path.parent / f"{source_path.stem}.{resolved_lang}{source_path.suffix}"

    if output_kind == "inplace":
        return source_path

    if output_kind == "new_page":
        vault_root = Path(os.environ.get("OMW_VAULT_ROOT", "."))
        return vault_root / "wiki" / "syntheses" / f"{source_path.stem}.md"

    # Fallback
    return session_dir / worker_id / "output.md"


def _build_worker_prompt(
    persona_body: str,
    source_path: Path,
    output_kind: str,
    output_target: Path | None,
    worker_dir: Path,
    model: str,
) -> str:
    """Build the §4.8 worker prompt with PERSONA + TASK sections."""
    source_content = ""
    if source_path.exists():
        source_content = source_path.read_text(encoding="utf-8")

    target_str = str(output_target) if output_target else "(stdout)"
    done_json_path = worker_dir / "done.json"

    return (
        "=== PERSONA ===\n"
        f"{persona_body.strip()}\n\n"
        "=== TASK ===\n"
        f"Source: {source_path}\n"
        "Source content:\n"
        "---\n"
        f"{source_content}\n"
        "---\n\n"
        "Required output:\n"
        f"- output_kind: {output_kind}\n"
        f"- output_target_path: {target_str}\n"
        "- after producing the output file, write done.json sentinel with:\n"
        f'  {{"status": "ok", "result_path": "{target_str}", '
        f'"duration_seconds": <int>, "model": "{model}"}}\n'
        f"  to: {done_json_path}\n\n"
        f"Do NOT modify any files outside {worker_dir}/ and {target_str}."
    )


# ── Public API ────────────────────────────────────────────────────────────────

def dispatch_one(req: DispatchRequest, session_dir: Path) -> DispatchResult:
    """
    Dispatch a single persona × backend worker into a tmux pane.

    1. Load the persona, extract body + output_kind.
    2. Derive the expected output target path.
    3. Write worker_dir/input.md (the combined prompt per §4.8).
    4. Build the backend CLI invocation (respects OMW_BACKEND_OVERRIDE_PATH).
    5. Spawn the worker via tmux_runtime.spawn_worker.
    6. Wait for done.json via tmux_runtime.wait_for_workers.
    7. Return DispatchResult.
    """
    session_dir = Path(session_dir)

    # Build a stable, unique worker ID
    worker_id = f"worker-{req.persona}-{uuid.uuid4().hex[:6]}"
    worker_dir = session_dir / worker_id
    worker_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load persona
    persona = load_persona(req.persona)
    persona_body: str = persona.get("body", "")
    output_kind: str = persona.get("output_kind", "stdout")

    # 2. Derive output target
    output_target = _output_target(
        source_path=Path(req.source_path),
        output_kind=output_kind,
        persona_name=req.persona,
        session_dir=session_dir,
        worker_id=worker_id,
    )

    # 3. Write input.md prompt
    prompt_text = _build_worker_prompt(
        persona_body=persona_body,
        source_path=Path(req.source_path),
        output_kind=output_kind,
        output_target=output_target,
        worker_dir=worker_dir,
        model=req.model,
    )
    (worker_dir / "input.md").write_text(prompt_text, encoding="utf-8")

    # 4. Build CLI argv
    # OMW_BACKEND_OVERRIDE_PATH substitutes the real CLI binary for tests/fakes
    override_path = os.environ.get("OMW_BACKEND_OVERRIDE_PATH")
    argv = build_invocation(
        req.backend,
        persona_body=persona_body,
        task_prompt=prompt_text,
        model=req.model,
        skip_permissions=req.skip_permissions,
        extra_args=req.extra_args,
        override_cli_path=override_path,
    )

    # 5. Spawn via tmux_runtime
    # Use session_dir name as tmux session name (slug it for tmux compat)
    raw_session_name = session_dir.name
    # tmux session names must not contain dots or colons
    session_id = raw_session_name.replace(".", "-").replace(":", "-")[:48]

    # Build extra env vars for the worker.sh script.
    # OMW_RESULT_PATH: tells worker.sh what to record in done.json
    # OMW_MODEL: recorded in done.json
    # OMW_FAKE_*: propagate test-control env vars into the tmux worker shell
    extra_env: dict[str, str] = {}
    if output_target is not None:
        extra_env["OMW_RESULT_PATH"] = str(output_target)
    extra_env["OMW_MODEL"] = req.model

    # Propagate OMW_FAKE_* env vars so hermetic fake-backend tests work
    # (tmux workers run in a separate shell; they do NOT inherit from pytest)
    for k, v in os.environ.items():
        if k.startswith("OMW_FAKE_"):
            extra_env[k] = v

    info = spawn_worker(
        session_id=session_id,
        worker_name=worker_id,
        command=argv,
        session_dir=session_dir,
        extra_env=extra_env,
    )

    # 6. Wait for done.json
    results = wait_for_workers(
        [info],
        timeout=float(req.timeout),
        poll_interval=0.5,
    )
    r = results[0]

    # 7. Build DispatchResult
    payload = r.get("payload") or {}
    result_path_str = payload.get("result_path", "")
    # Prefer what the worker reported; fall back to what we computed
    if result_path_str:
        resolved_result_path = Path(result_path_str)
    else:
        resolved_result_path = output_target

    duration = payload.get("duration_seconds", 0)
    if isinstance(duration, str):
        try:
            duration = float(duration)
        except ValueError:
            duration = 0.0

    return DispatchResult(
        worker_id=worker_id,
        status=r["status"],
        result_path=resolved_result_path,
        duration_seconds=float(duration),
        model=payload.get("model", req.model),
        session_dir=session_dir,
        persona=req.persona,
    )
