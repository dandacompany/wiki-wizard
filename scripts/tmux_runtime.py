"""tmux session/pane lifecycle for OMW dispatch workers.

Design decisions (from spec §4.3):
- Each dispatch run gets one tmux session named omw-dispatch-<short-id>.
- Each worker gets one window inside that session.
- Workers write a done.json sentinel atomically on completion.
- Pane scraping is NOT used; sentinel polling is the only completion signal.
- tmux >= 3.0 required; aborts clearly if absent.

done.json sentinel fields (spec §3 decision 8 + T7 expectation):
  {status, exit_code, result_path, model, duration_seconds, timestamp,
   worker_name, session_id, finished_at}
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


class TmuxError(Exception):
    """Raised for tmux availability problems or session management failures."""


# ---------------------------------------------------------------------------
# Version check
# ---------------------------------------------------------------------------

_MIN_TMUX_MAJOR = 3


def check_tmux_version() -> dict[str, Any]:
    """Verify tmux >= 3.0 is available. Returns {ok, version, message}."""
    try:
        cp = subprocess.run(
            ["tmux", "-V"],
            capture_output=True, text=True, timeout=5,
        )
        if cp.returncode != 0:
            return {"ok": False, "version": "", "message": "tmux -V failed"}
        raw = (cp.stdout or cp.stderr or "").strip()
        # "tmux 3.3a" → extract major version number
        m = re.search(r"(\d+)\.", raw)
        if not m:
            return {
                "ok": False, "version": raw,
                "message": f"could not parse tmux version: {raw!r}",
            }
        major = int(m.group(1))
        if major < _MIN_TMUX_MAJOR:
            return {
                "ok": False, "version": raw,
                "message": (
                    f"tmux {raw} is too old; v2.3 requires tmux >= {_MIN_TMUX_MAJOR}.0. "
                    "Install: apt-get install tmux  OR  brew install tmux"
                ),
            }
        return {"ok": True, "version": raw, "message": "ok"}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False, "version": "",
            "message": (
                f"tmux not found: {exc}. "
                "Install: apt-get install tmux  OR  brew install tmux"
            ),
        }


def _require_tmux() -> None:
    result = check_tmux_version()
    if not result["ok"]:
        raise TmuxError(result["message"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _session_exists(session_id: str) -> bool:
    r = subprocess.run(
        ["tmux", "has-session", "-t", session_id],
        capture_output=True, timeout=5,
    )
    return r.returncode == 0


def _tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["tmux", *args],
        capture_output=True, text=True, timeout=10,
        check=check,
    )


# ---------------------------------------------------------------------------
# spawn_worker
# ---------------------------------------------------------------------------

def _write_worker_script(
    worker_dir: Path,
    command: list[str],
    worker_name: str,
    session_id: str,
    extra_env: dict[str, str] | None = None,
) -> Path:
    """Write a self-contained bash wrapper script for the worker.

    The script runs the command, captures exit code, and writes done.json
    atomically (tmp → rename) regardless of exit code.

    done.json fields (spec §3 decision 8 + T7 expectation):
      status: "ok" | "failed"
      exit_code: integer
      result_path: from $OMW_RESULT_PATH env if set, else ""
      model: from $OMW_MODEL env if set, else ""
      duration_seconds: integer
      timestamp: ISO-8601 UTC
      worker_name: string
      session_id: string
      finished_at: ISO-8601 UTC (alias for timestamp for T7 compat)
    """
    done_tmp = worker_dir / "done.json.tmp"
    done_path = worker_dir / "done.json"
    pane_log = worker_dir / "pane.log"

    cmd_str = shlex.join(command)
    worker_name_json = json.dumps(worker_name)
    session_id_json = json.dumps(session_id)

    # Build export lines for extra_env (e.g. OMW_RESULT_PATH, OMW_MODEL)
    env_exports = ""
    if extra_env:
        for k, v in extra_env.items():
            env_exports += f"export {k}={shlex.quote(v)}\n"

    script_content = f"""#!/bin/bash
# OMW worker script — auto-generated, do not edit
set -o pipefail 2>/dev/null || true

{env_exports}
_START=$(date +%s 2>/dev/null || echo 0)

# Run command, tee stdout+stderr to pane.log
{cmd_str} 2>&1 | tee {shlex.quote(str(pane_log))}
_EXIT=${{PIPESTATUS[0]:-$?}}

_END=$(date +%s 2>/dev/null || echo 0)
_DUR=$(( _END - _START )) 2>/dev/null || _DUR=0
_NOW=$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u)

if [ "$_EXIT" -eq 0 ]; then _STATUS=ok; else _STATUS=failed; fi

_RESULT_PATH="${{OMW_RESULT_PATH:-}}"
_MODEL="${{OMW_MODEL:-}}"

printf '{{"status":"%s","exit_code":%d,"result_path":"%s","model":"%s","duration_seconds":%d,"timestamp":"%s","worker_name":{worker_name_json},"session_id":{session_id_json},"finished_at":"%s"}}\\n' \\
  "$_STATUS" \\
  "$_EXIT" \\
  "$_RESULT_PATH" \\
  "$_MODEL" \\
  "$_DUR" \\
  "$_NOW" \\
  "$_NOW" \\
  > {shlex.quote(str(done_tmp))} && mv {shlex.quote(str(done_tmp))} {shlex.quote(str(done_path))}

exit $_EXIT
"""
    script_path = worker_dir / "worker.sh"
    script_path.write_text(script_content, encoding="utf-8")
    script_path.chmod(0o755)
    return script_path


def _list_window_names(session_id: str) -> list[str]:
    """Return the list of existing window names in a tmux session.

    Returns an empty list if the session doesn't exist or tmux fails.
    """
    try:
        r = subprocess.run(
            ["tmux", "list-windows", "-t", session_id, "-F", "#{window_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return []
        return [line for line in r.stdout.splitlines() if line]
    except (OSError, subprocess.TimeoutExpired):
        return []


def spawn_worker(
    *,
    session_id: str,
    worker_name: str,
    command: list[str],
    session_dir: Path,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Spawn a worker command in a detached tmux session window.

    Creates the tmux session if it doesn't exist yet. Writes a bash wrapper
    script that runs the command and writes done.json atomically on completion.
    The script is passed directly as the window command (not via send-keys) to
    avoid shell quoting / line-wrap issues.

    Caller must guarantee ``worker_name`` uniqueness within ``session_id``.
    A duplicate name raises :class:`TmuxError` before any tmux call is made.

    Args:
        session_id:   tmux session name (e.g. "omw-dispatch-abc123").
        worker_name:  window name + label in done.json (e.g. "fact-checker").
                      Must be unique within the session.
        command:      argv list to execute (NOT a shell string).
        session_dir:  directory for done.json + pane.log.
                      Typically <vault>/.oh-my-wiki/dispatch-sessions/<ts>-<slug>/
                      A <worker_name>/ subdir is created automatically.
        extra_env:    optional dict of env vars to export inside the worker
                      script before running the command (e.g. OMW_RESULT_PATH).

    Returns:
        {session_id, window_name, done_json_path, pane_log_path}

    Raises:
        TmuxError: if tmux is unavailable, session creation fails, a duplicate
                   worker_name is detected, or new-window fails.
    """
    _require_tmux()

    worker_dir = Path(session_dir) / worker_name
    worker_dir.mkdir(parents=True, exist_ok=True)

    done_path = worker_dir / "done.json"
    pane_log = worker_dir / "pane.log"

    script_path = _write_worker_script(
        worker_dir=worker_dir,
        command=command,
        worker_name=worker_name,
        session_id=session_id,
        extra_env=extra_env,
    )

    shell_cmd = f"/bin/bash {shlex.quote(str(script_path))}"

    if not _session_exists(session_id):
        # Create detached session with a keepalive window so the session
        # persists even if all worker windows exit quickly.
        # Use check=False to handle TOCTOU race: parallel workers may
        # simultaneously try to create the same session; the second caller
        # will get a non-zero exit which we silently ignore if session now exists.
        r_new = subprocess.run(
            [
                "tmux", "new-session", "-d",
                "-s", session_id,
                "-n", "_keepalive",
                "-x", "220", "-y", "50",
                "sleep 86400",
            ],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if r_new.returncode != 0 and not _session_exists(session_id):
            # Session creation truly failed (not a race); raise to caller.
            raise TmuxError(
                f"Failed to create tmux session {session_id!r}: "
                f"{r_new.stderr.strip()}"
            )

    # Guard against duplicate worker_name within the same session
    existing_names = _list_window_names(session_id)
    if worker_name in existing_names:
        raise TmuxError(f"duplicate worker_name: {worker_name!r} already exists in session {session_id!r}")

    # Add the worker window to the (now-existing) session
    try:
        subprocess.run(
            [
                "tmux", "new-window",
                "-t", session_id,
                "-n", worker_name,
                shell_cmd,
            ],
            capture_output=True, text=True, timeout=10, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise TmuxError(f"new-window failed: {e}") from e

    return {
        "session_id": session_id,
        "window_name": worker_name,
        "done_json_path": str(done_path),
        "pane_log_path": str(pane_log),
    }


# ---------------------------------------------------------------------------
# wait_for_workers
# ---------------------------------------------------------------------------

def wait_for_workers(
    workers: list[dict[str, Any]],
    *,
    timeout: float = 600.0,
    poll_interval: float = 1.0,
) -> list[dict[str, Any]]:
    """Poll each worker's done.json until all complete or timeout.

    Args:
        workers:       list of dicts returned by spawn_worker().
        timeout:       total seconds to wait before returning partial results.
        poll_interval: seconds between polls.

    Returns:
        List of {worker_name, session_id, done_json_path, status, exit_code}.
        status is "ok", "failed" (non-zero exit), or "timeout".
    """
    pending = {w["done_json_path"]: w for w in workers}
    completed: list[dict[str, Any]] = []
    deadline = time.monotonic() + timeout

    while pending and time.monotonic() < deadline:
        for done_path_str, w in list(pending.items()):
            p = Path(done_path_str)
            if p.exists():
                try:
                    payload = json.loads(p.read_text(encoding="utf-8"))
                    exit_code = payload.get("exit_code", -1)
                    status = payload.get("status", "ok" if exit_code == 0 else "failed")
                    completed.append({
                        **w,
                        "status": status,
                        "exit_code": exit_code,
                        "payload": payload,
                    })
                except (json.JSONDecodeError, OSError):
                    # partial write — wait for next poll
                    continue
                del pending[done_path_str]
        if pending:
            time.sleep(poll_interval)

    # Anything still pending hit the timeout
    for done_path_str, w in pending.items():
        completed.append({
            **w,
            "status": "timeout",
            "exit_code": None,
            "payload": None,
        })

    return completed


# ---------------------------------------------------------------------------
# shutdown_session
# ---------------------------------------------------------------------------

def shutdown_session(session_id: str) -> None:
    """Kill the tmux session. Idempotent — does not raise if already gone."""
    try:
        subprocess.run(
            ["tmux", "kill-session", "-t", session_id],
            capture_output=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
