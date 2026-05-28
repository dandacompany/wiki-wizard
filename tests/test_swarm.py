"""Unit tests for scripts.swarm — swarm CLI subcommand by subcommand.

Each test sets:
    monkeypatch.setenv("OMW_SWARM_SESSION_DIR", str(tmp_path))
    monkeypatch.setenv("OMW_SWARM_WORKER_ID",   "worker-test-1")
    monkeypatch.setenv("OMW_SWARM_PEERS",        "worker-test-2,worker-test-3")

and calls subcommands via subprocess so the env vars reach the module.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PYTHON = sys.executable


def _swarm(args: list[str], env: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run `python3 -m scripts.swarm <args>` with given env, capturing output."""
    return subprocess.run(
        [PYTHON, "-m", "scripts.swarm", *args],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        cwd=str(cwd) if cwd else None,
    )


def _base_env(tmp_path: Path) -> dict[str, str]:
    return {
        "OMW_SWARM_SESSION_DIR": str(tmp_path),
        "OMW_SWARM_WORKER_ID":   "worker-test-1",
        "OMW_SWARM_PEERS":       "worker-test-2,worker-test-3",
    }


def _plant_message(
    session_dir: Path,
    worker_id: str,
    msg_id: str,
    payload: dict,
    delivered: bool = False,
) -> Path:
    """Write a pre-crafted message into a worker's inbox for test setup."""
    inbox = session_dir / worker_id / "inbox"
    if delivered:
        inbox = inbox / ".delivered"
    inbox.mkdir(parents=True, exist_ok=True)
    msg_path = inbox / f"{msg_id}.json"
    msg_path.write_text(json.dumps(payload), encoding="utf-8")
    return msg_path


# ============================================================
# T1 — _load_env_context + path layout + inbox
# ============================================================

class TestLoadEnvContext:
    def test_missing_session_dir_exits_2(self, tmp_path):
        env = {"OMW_SWARM_WORKER_ID": "w1"}  # no SESSION_DIR
        r = _swarm(["inbox"], env, cwd=tmp_path)
        assert r.returncode == 2, f"expected exit 2, got {r.returncode}: {r.stderr}"

    def test_missing_worker_id_exits_2(self, tmp_path):
        env = {"OMW_SWARM_SESSION_DIR": str(tmp_path)}  # no WORKER_ID
        r = _swarm(["inbox"], env, cwd=tmp_path)
        assert r.returncode == 2, f"expected exit 2, got {r.returncode}: {r.stderr}"

    def test_valid_env_exits_0_with_empty_inbox(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(["inbox"], env, cwd=tmp_path)
        assert r.returncode == 0, f"stderr: {r.stderr}"
        data = json.loads(r.stdout)
        assert data == []


class TestInbox:
    def test_inbox_returns_messages(self, tmp_path):
        env = _base_env(tmp_path)
        msg = {
            "msg_id": "msg-001",
            "from": "worker-test-2",
            "to": "worker-test-1",
            "topic": "claim",
            "body": "Python was created in 1991",
            "sent_at": "2026-05-27T09:00:00Z",
        }
        _plant_message(tmp_path, "worker-test-1", "msg-001", msg)
        r = _swarm(["inbox"], env, cwd=tmp_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert len(data) == 1
        assert data[0]["msg_id"] == "msg-001"

    def test_inbox_topic_filter(self, tmp_path):
        env = _base_env(tmp_path)
        _plant_message(tmp_path, "worker-test-1", "msg-001", {
            "msg_id": "msg-001", "from": "w2", "to": "worker-test-1",
            "topic": "claim", "body": "A", "sent_at": "2026-05-27T09:00:00Z",
        })
        _plant_message(tmp_path, "worker-test-1", "msg-002", {
            "msg_id": "msg-002", "from": "w2", "to": "worker-test-1",
            "topic": "status", "body": "B", "sent_at": "2026-05-27T09:00:01Z",
        })
        r = _swarm(["inbox", "--topic", "claim"], env, cwd=tmp_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert len(data) == 1
        assert data[0]["topic"] == "claim"

    def test_inbox_unread_only_excludes_delivered(self, tmp_path):
        env = _base_env(tmp_path)
        _plant_message(tmp_path, "worker-test-1", "msg-001", {
            "msg_id": "msg-001", "from": "w2", "to": "worker-test-1",
            "body": "unread", "sent_at": "2026-05-27T09:00:00Z",
        }, delivered=False)
        _plant_message(tmp_path, "worker-test-1", "msg-002", {
            "msg_id": "msg-002", "from": "w2", "to": "worker-test-1",
            "body": "read", "sent_at": "2026-05-27T09:00:01Z",
        }, delivered=True)
        r = _swarm(["inbox", "--unread-only"], env, cwd=tmp_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert len(data) == 1
        assert data[0]["msg_id"] == "msg-001"

    def test_inbox_mark_delivered_moves_to_delivered(self, tmp_path):
        env = _base_env(tmp_path)
        _plant_message(tmp_path, "worker-test-1", "msg-001", {
            "msg_id": "msg-001", "from": "w2", "to": "worker-test-1",
            "body": "hello", "sent_at": "2026-05-27T09:00:00Z",
        })
        r = _swarm(["inbox", "--mark-delivered"], env, cwd=tmp_path)
        assert r.returncode == 0
        # msg-001 must now live in .delivered/
        delivered_path = tmp_path / "worker-test-1" / "inbox" / ".delivered" / "msg-001.json"
        assert delivered_path.exists(), "message not moved to .delivered/"
        # Original path must be gone
        original = tmp_path / "worker-test-1" / "inbox" / "msg-001.json"
        assert not original.exists(), "original message file still present after mark-delivered"

    def test_inbox_without_mark_delivered_leaves_originals(self, tmp_path):
        env = _base_env(tmp_path)
        _plant_message(tmp_path, "worker-test-1", "msg-001", {
            "msg_id": "msg-001", "from": "w2", "to": "worker-test-1",
            "body": "hello", "sent_at": "2026-05-27T09:00:00Z",
        })
        _swarm(["inbox"], env, cwd=tmp_path)
        original = tmp_path / "worker-test-1" / "inbox" / "msg-001.json"
        assert original.exists(), "inbox without --mark-delivered must not move messages"

    def test_inbox_returns_sorted_by_sent_at(self, tmp_path):
        env = _base_env(tmp_path)
        for i, ts in enumerate(["2026-05-27T09:00:02Z", "2026-05-27T09:00:00Z", "2026-05-27T09:00:01Z"]):
            _plant_message(tmp_path, "worker-test-1", f"msg-{i:03d}", {
                "msg_id": f"msg-{i:03d}", "from": "w2", "to": "worker-test-1",
                "body": f"msg {i}", "sent_at": ts,
            })
        r = _swarm(["inbox"], env, cwd=tmp_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert len(data) == 3
        timestamps = [d["sent_at"] for d in data]
        assert timestamps == sorted(timestamps), "inbox output not sorted by sent_at"

    def test_inbox_unknown_subcommand_exits_2(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(["nonexistent-op"], env, cwd=tmp_path)
        assert r.returncode == 2
