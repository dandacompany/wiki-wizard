"""Tests for scripts.tmux_runtime — requires real tmux >= 3.0 in PATH.

Tests create uniquely-named tmux sessions and tear them down in finally blocks.
Each session name includes the test name + a short random suffix to avoid
collisions in parallel runs.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from scripts import tmux_runtime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_id(prefix: str = "omw-test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _kill_session(session_id: str) -> None:
    """Best-effort session teardown; ignore errors."""
    try:
        subprocess.run(
            ["tmux", "kill-session", "-t", session_id],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# tmux availability guard
# ---------------------------------------------------------------------------

def test_require_tmux_version():
    """tmux >= 3.0 must be present; this test documents the requirement."""
    result = tmux_runtime.check_tmux_version()
    assert result["ok"] is True, (
        f"tmux version check failed: {result['message']}"
    )


# ---------------------------------------------------------------------------
# spawn_worker
# ---------------------------------------------------------------------------

def test_spawn_worker_creates_session(tmp_path):
    session_id = _unique_id("spawn-creates")
    try:
        info = tmux_runtime.spawn_worker(
            session_id=session_id,
            worker_name="test-worker",
            command=["echo", "hello"],
            session_dir=tmp_path,
        )
        assert info["session_id"] == session_id
        assert info["window_name"] == "test-worker"
        # session exists in tmux
        r = subprocess.run(
            ["tmux", "has-session", "-t", session_id],
            capture_output=True, timeout=5,
        )
        assert r.returncode == 0, "tmux session was not created"
    finally:
        _kill_session(session_id)


def test_spawn_worker_writes_done_json(tmp_path):
    session_id = _unique_id("spawn-done")
    try:
        info = tmux_runtime.spawn_worker(
            session_id=session_id,
            worker_name="echo-worker",
            command=["echo", "done"],
            session_dir=tmp_path,
        )
        done_path = Path(info["done_json_path"])
        # Poll for done.json up to 10s
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if done_path.exists():
                break
            time.sleep(0.25)
        assert done_path.exists(), f"done.json not written within 10s at {done_path}"
        payload = json.loads(done_path.read_text(encoding="utf-8"))
        assert "exit_code" in payload
        assert payload["exit_code"] == 0
    finally:
        _kill_session(session_id)


def test_spawn_worker_done_json_contains_required_fields(tmp_path):
    session_id = _unique_id("spawn-fields")
    try:
        info = tmux_runtime.spawn_worker(
            session_id=session_id,
            worker_name="fields-worker",
            command=["echo", "fields"],
            session_dir=tmp_path,
        )
        done_path = Path(info["done_json_path"])
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if done_path.exists():
                break
            time.sleep(0.25)
        assert done_path.exists()
        payload = json.loads(done_path.read_text(encoding="utf-8"))
        # Required fields per spec §3 decision 8 + T7 expectation:
        # {status, exit_code, result_path, model, duration_seconds, timestamp}
        # Plus worker identity fields for T6 tests:
        for key in ("status", "exit_code", "result_path", "model",
                    "duration_seconds", "timestamp",
                    "worker_name", "session_id", "finished_at"):
            assert key in payload, f"done.json missing key: {key!r}"
    finally:
        _kill_session(session_id)


def test_spawn_worker_nonzero_exit_recorded(tmp_path):
    session_id = _unique_id("spawn-fail")
    try:
        info = tmux_runtime.spawn_worker(
            session_id=session_id,
            worker_name="fail-worker",
            command=["bash", "-c", "exit 42"],
            session_dir=tmp_path,
        )
        done_path = Path(info["done_json_path"])
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if done_path.exists():
                break
            time.sleep(0.25)
        assert done_path.exists()
        payload = json.loads(done_path.read_text(encoding="utf-8"))
        assert payload["exit_code"] == 42
        assert payload["status"] == "failed"
    finally:
        _kill_session(session_id)


def test_spawn_multiple_workers_same_session(tmp_path):
    session_id = _unique_id("multi-worker")
    try:
        infos = []
        for i in range(3):
            info = tmux_runtime.spawn_worker(
                session_id=session_id,
                worker_name=f"worker-{i}",
                command=["echo", f"worker-{i}"],
                session_dir=tmp_path,
            )
            infos.append(info)
        # All should share the same session
        assert all(i["session_id"] == session_id for i in infos)
        # Windows should be distinct
        window_names = [i["window_name"] for i in infos]
        assert len(set(window_names)) == 3
    finally:
        _kill_session(session_id)


# ---------------------------------------------------------------------------
# shutdown_session
# ---------------------------------------------------------------------------

def test_shutdown_session_kills_session(tmp_path):
    session_id = _unique_id("shutdown")
    try:
        tmux_runtime.spawn_worker(
            session_id=session_id,
            worker_name="w",
            command=["sleep", "60"],
            session_dir=tmp_path,
        )
        tmux_runtime.shutdown_session(session_id)
        r = subprocess.run(
            ["tmux", "has-session", "-t", session_id],
            capture_output=True, timeout=5,
        )
        assert r.returncode != 0, "session should be gone after shutdown"
    finally:
        _kill_session(session_id)


def test_shutdown_session_is_idempotent(tmp_path):
    session_id = _unique_id("shutdown-idem")
    try:
        tmux_runtime.spawn_worker(
            session_id=session_id,
            worker_name="w",
            command=["echo", "x"],
            session_dir=tmp_path,
        )
        tmux_runtime.shutdown_session(session_id)
        # Second shutdown should not raise
        tmux_runtime.shutdown_session(session_id)
    finally:
        _kill_session(session_id)


def test_shutdown_nonexistent_session_does_not_raise():
    tmux_runtime.shutdown_session("omw-test-nonexistent-9999xxxx")


# ---------------------------------------------------------------------------
# wait_for_workers — T7
# ---------------------------------------------------------------------------

class TestWaitForWorkers:
    """Real-tmux tests for wait_for_workers(); each uses a unique session."""

    def test_returns_ok_when_all_done(self, tmp_path):
        """Single worker running 'true' → status ok."""
        sid = _unique_id("wfw-ok")
        try:
            w = tmux_runtime.spawn_worker(
                session_id=sid,
                worker_name="w-ok",
                command=["true"],
                session_dir=tmp_path,
            )
            results = tmux_runtime.wait_for_workers([w], timeout=30)
            assert len(results) == 1
            assert results[0]["status"] == "ok"
            assert results[0]["exit_code"] == 0
        finally:
            _kill_session(sid)

    def test_all_complete_returns_complete_list(self, tmp_path):
        """Two workers that finish quickly → both status ok."""
        sid = _unique_id("wfw-multi")
        try:
            workers = []
            for i in range(2):
                w = tmux_runtime.spawn_worker(
                    session_id=sid,
                    worker_name=f"wfw-{i}",
                    command=["echo", f"worker-{i}"],
                    session_dir=tmp_path,
                )
                workers.append(w)
            results = tmux_runtime.wait_for_workers(workers, timeout=30)
            assert len(results) == 2
            assert all(r["status"] == "ok" for r in results)
        finally:
            _kill_session(sid)

    def test_partial_results_on_timeout(self, tmp_path):
        """One worker completes; one hangs. Short timeout → ok + timeout."""
        sid = _unique_id("wfw-timeout")
        try:
            w_ok = tmux_runtime.spawn_worker(
                session_id=sid,
                worker_name="w-fast",
                command=["true"],
                session_dir=tmp_path,
            )
            w_hang = tmux_runtime.spawn_worker(
                session_id=sid,
                worker_name="w-hang",
                command=["sleep", "120"],
                session_dir=tmp_path,
            )
            # Give the fast worker time to complete before starting the wait
            time.sleep(2)
            results = tmux_runtime.wait_for_workers(
                [w_ok, w_hang], timeout=3, poll_interval=0.5
            )
            by_name = {r["window_name"]: r for r in results}
            assert by_name["w-fast"]["status"] == "ok"
            assert by_name["w-hang"]["status"] == "timeout"
            assert by_name["w-hang"]["exit_code"] is None
        finally:
            _kill_session(sid)

    def test_propagates_nonzero_exit_as_failed(self, tmp_path):
        """Worker exits 1 → status 'failed'."""
        sid = _unique_id("wfw-fail")
        try:
            w = tmux_runtime.spawn_worker(
                session_id=sid,
                worker_name="w-fail",
                command=["sh", "-c", "exit 1"],
                session_dir=tmp_path,
            )
            results = tmux_runtime.wait_for_workers([w], timeout=15)
            assert results[0]["status"] == "failed"
            assert results[0]["exit_code"] == 1
        finally:
            _kill_session(sid)

    def test_result_contains_done_json_path(self, tmp_path):
        """Each result dict includes done_json_path pointing at a real file."""
        sid = _unique_id("wfw-path")
        try:
            w = tmux_runtime.spawn_worker(
                session_id=sid,
                worker_name="w-path",
                command=["true"],
                session_dir=tmp_path,
            )
            results = tmux_runtime.wait_for_workers([w], timeout=30)
            assert "done_json_path" in results[0]
            assert Path(results[0]["done_json_path"]).exists()
        finally:
            _kill_session(sid)


# ---------------------------------------------------------------------------
# shutdown_session idempotence — T7 verification (T6 already added the function)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fix 2: duplicate worker_name and new-window error handling
# ---------------------------------------------------------------------------

class TestSpawnWorkerErrorHandling:
    """Tests for Fix 2: TmuxError raised for duplicate worker_name and new-window failure."""

    def test_duplicate_worker_name_raises_tmux_error(self, tmp_path):
        """Spawning a second worker with the same name in the same session raises TmuxError."""
        session_id = _unique_id("dup-worker")
        try:
            tmux_runtime.spawn_worker(
                session_id=session_id,
                worker_name="same-name",
                command=["sleep", "60"],
                session_dir=tmp_path,
            )
            with pytest.raises(tmux_runtime.TmuxError, match="duplicate worker_name"):
                tmux_runtime.spawn_worker(
                    session_id=session_id,
                    worker_name="same-name",
                    command=["echo", "duplicate"],
                    session_dir=tmp_path,
                )
        finally:
            _kill_session(session_id)

    def test_new_window_failure_raises_tmux_error_not_called_process_error(self, tmp_path, monkeypatch):
        """A new-window CalledProcessError surfaces as TmuxError (not re-raised raw)."""
        session_id = _unique_id("badwin")
        try:
            # Patch subprocess.run to fail only when 'new-window' is the tmux sub-command
            original_run = subprocess.run

            def patched_run(args, **kwargs):
                if isinstance(args, list) and len(args) >= 2 and args[0] == "tmux" and args[1] == "new-window":
                    raise subprocess.CalledProcessError(1, args, output=b"", stderr=b"forced failure")
                return original_run(args, **kwargs)

            monkeypatch.setattr(subprocess, "run", patched_run)

            with pytest.raises(tmux_runtime.TmuxError, match="new-window failed"):
                tmux_runtime.spawn_worker(
                    session_id=session_id,
                    worker_name="w",
                    command=["echo", "hi"],
                    session_dir=tmp_path,
                )
        finally:
            _kill_session(session_id)


# ---------------------------------------------------------------------------
# shutdown_session idempotence — T7 verification (T6 already added the function)
# ---------------------------------------------------------------------------

class TestShutdownSessionIdempotence:
    """Verify shutdown_session idempotence; complements T6 basic tests."""

    def test_double_shutdown_does_not_raise(self, tmp_path):
        sid = _unique_id("t7-idem")
        try:
            tmux_runtime.spawn_worker(
                session_id=sid,
                worker_name="w",
                command=["sleep", "60"],
                session_dir=tmp_path,
            )
            tmux_runtime.shutdown_session(sid)
            # Second call on dead session must be silent
            tmux_runtime.shutdown_session(sid)
        finally:
            _kill_session(sid)

    def test_shutdown_nonexistent_does_not_raise(self):
        tmux_runtime.shutdown_session("omw-t7-ghost-session-99zz")


# ---------------------------------------------------------------------------
# T9 — extra_env propagation for OMW_SWARM_* vars
# ---------------------------------------------------------------------------

def test_spawn_worker_swarm_env_appears_in_worker_script(tmp_path):
    """OMW_SWARM_* env vars passed via extra_env appear in generated worker.sh."""
    session_id = _unique_id("t9-swarm-env")
    swarm_env = {
        "OMW_SWARM_SESSION_DIR": str(tmp_path),
        "OMW_SWARM_WORKER_ID":   "worker-1-fact-checker",
        "OMW_SWARM_PEERS":       "worker-2-moderator",
    }
    try:
        info = tmux_runtime.spawn_worker(
            session_id=session_id,
            worker_name="fact-checker",
            command=["echo", "hello"],
            session_dir=tmp_path,
            extra_env=swarm_env,
        )
        # The worker script is at <session_dir>/<worker_name>/worker.sh
        worker_script = Path(tmp_path) / "fact-checker" / "worker.sh"
        assert worker_script.exists(), "worker.sh was not created"
        script_text = worker_script.read_text(encoding="utf-8")
        assert "OMW_SWARM_SESSION_DIR" in script_text, (
            "OMW_SWARM_SESSION_DIR missing from worker.sh"
        )
        assert "OMW_SWARM_WORKER_ID" in script_text, (
            "OMW_SWARM_WORKER_ID missing from worker.sh"
        )
        assert "OMW_SWARM_PEERS" in script_text, (
            "OMW_SWARM_PEERS missing from worker.sh"
        )
    finally:
        _kill_session(session_id)


def test_spawn_worker_no_extra_env_no_swarm_vars_in_script(tmp_path):
    """When extra_env is empty, no OMW_SWARM_* vars appear in worker.sh."""
    session_id = _unique_id("t9-no-swarm")
    try:
        tmux_runtime.spawn_worker(
            session_id=session_id,
            worker_name="no-env-worker",
            command=["echo", "hello"],
            session_dir=tmp_path,
            extra_env={},
        )
        worker_script = Path(tmp_path) / "no-env-worker" / "worker.sh"
        assert worker_script.exists(), "worker.sh was not created"
        script_text = worker_script.read_text(encoding="utf-8")
        assert "OMW_SWARM_SESSION_DIR" not in script_text
        assert "OMW_SWARM_WORKER_ID" not in script_text
        assert "OMW_SWARM_PEERS" not in script_text
    finally:
        _kill_session(session_id)
