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


# ============================================================
# T2 — send + broadcast
# ============================================================

class TestSend:
    def test_send_creates_canonical_message(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["send", "--to", "worker-test-2", "--body", "hello peer"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        result = json.loads(r.stdout)
        assert "msg_id" in result
        # Canonical message must exist in messages/
        messages_dir = tmp_path / "messages"
        assert messages_dir.exists()
        msg_files = list(messages_dir.glob("*.json"))
        assert len(msg_files) == 1

    def test_send_links_to_recipient_inbox(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["send", "--to", "worker-test-2", "--body", "hello peer"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0
        result = json.loads(r.stdout)
        msg_id = result["msg_id"]
        inbox_copy = tmp_path / "worker-test-2" / "inbox" / f"{msg_id}.json"
        assert inbox_copy.exists(), f"inbox copy not found: {inbox_copy}"

    def test_send_envelope_has_required_fields(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["send", "--to", "worker-test-2", "--body", "test body",
             "--topic", "claim"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0
        result = json.loads(r.stdout)
        msg_id = result["msg_id"]
        canonical = list((tmp_path / "messages").glob(f"{msg_id}*.json"))
        assert canonical, "canonical message file not found"
        envelope = json.loads(canonical[0].read_text(encoding="utf-8"))
        for field in ("msg_id", "from", "to", "body", "sent_at"):
            assert field in envelope, f"envelope missing field: {field}"
        assert envelope["topic"] == "claim"
        assert envelope["from"] == "worker-test-1"
        assert envelope["to"] == "worker-test-2"

    def test_send_wildcard_to_rejected(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["send", "--to", "*", "--body", "should fail"],
            env, cwd=tmp_path,
        )
        assert r.returncode in (1, 2), f"expected error exit, got {r.returncode}"

    def test_send_with_correlation_id(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["send", "--to", "worker-test-2", "--body", "linked msg",
             "--correlation-id", "rpc-001"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0
        result = json.loads(r.stdout)
        msg_id = result["msg_id"]
        canonical = list((tmp_path / "messages").glob(f"{msg_id}*.json"))
        envelope = json.loads(canonical[0].read_text(encoding="utf-8"))
        assert envelope.get("correlation_id") == "rpc-001"


class TestBroadcast:
    def test_broadcast_delivers_to_all_peers(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["broadcast", "--body", "hello everyone"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        result = json.loads(r.stdout)
        assert "msg_id" in result
        assert "recipients" in result
        # Both peers should have received it
        msg_id = result["msg_id"]
        for peer in ("worker-test-2", "worker-test-3"):
            inbox_copy = tmp_path / peer / "inbox" / f"{msg_id}.json"
            assert inbox_copy.exists(), f"{peer} inbox missing broadcast message"

    def test_broadcast_excludes_self(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(["broadcast", "--body", "no self-mail"], env, cwd=tmp_path)
        assert r.returncode == 0
        result = json.loads(r.stdout)
        assert "worker-test-1" not in result["recipients"], "self must be excluded from broadcast"
        self_inbox = tmp_path / "worker-test-1" / "inbox"
        if self_inbox.exists():
            self_msgs = list(self_inbox.glob("*.json"))
            assert len(self_msgs) == 0, "self received its own broadcast"


# ============================================================
# T3 — publish + subscribe
# ============================================================

class TestPublish:
    def test_publish_is_alias_for_broadcast_with_topic(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["publish", "--topic", "claim", "--body", '{"claim": "Python 1991"}'],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        result = json.loads(r.stdout)
        assert "msg_id" in result
        # Both peers should have received it
        msg_id = result["msg_id"]
        for peer in ("worker-test-2", "worker-test-3"):
            inbox_copy = tmp_path / peer / "inbox" / f"{msg_id}.json"
            assert inbox_copy.exists(), f"{peer} inbox missing published message"

    def test_publish_sets_topic_in_envelope(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["publish", "--topic", "status", "--body", "processing"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0
        result = json.loads(r.stdout)
        msg_id = result["msg_id"]
        canonical = list((tmp_path / "messages").glob(f"{msg_id}*.json"))
        assert canonical
        envelope = json.loads(canonical[0].read_text(encoding="utf-8"))
        assert envelope.get("topic") == "status"

    def test_publish_without_topic_exits_error(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(["publish", "--body", "no topic"], env, cwd=tmp_path)
        # --topic is required for publish
        assert r.returncode != 0


class TestSubscribe:
    def test_subscribe_writes_subscriptions_json(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(["subscribe", "--topic", "claim"], env, cwd=tmp_path)
        assert r.returncode == 0, f"stderr: {r.stderr}"
        subs_path = tmp_path / "worker-test-1" / "subscriptions.json"
        assert subs_path.exists(), "subscriptions.json not created"
        subs = json.loads(subs_path.read_text(encoding="utf-8"))
        assert "claim" in subs.get("topics", [])

    def test_subscribe_multiple_topics_accumulates(self, tmp_path):
        env = _base_env(tmp_path)
        _swarm(["subscribe", "--topic", "claim"], env, cwd=tmp_path)
        _swarm(["subscribe", "--topic", "status"], env, cwd=tmp_path)
        subs_path = tmp_path / "worker-test-1" / "subscriptions.json"
        subs = json.loads(subs_path.read_text(encoding="utf-8"))
        assert "claim" in subs["topics"]
        assert "status" in subs["topics"]


# ============================================================
# T4 — heartbeat + monitor
# ============================================================

import signal


class TestHeartbeat:
    def test_heartbeat_writes_heartbeat_json(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["heartbeat", "--status", "processing claim 3 of 7"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        hb_path = tmp_path / "worker-test-1" / "heartbeat.json"
        assert hb_path.exists(), "heartbeat.json not created"
        hb = json.loads(hb_path.read_text(encoding="utf-8"))
        assert hb["worker_id"] == "worker-test-1"
        assert hb["status"] == "processing claim 3 of 7"

    def test_heartbeat_with_progress(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["heartbeat", "--status", "half done", "--progress", "0.5"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0
        hb = json.loads(
            (tmp_path / "worker-test-1" / "heartbeat.json").read_text(encoding="utf-8")
        )
        assert abs(hb.get("progress", -1) - 0.5) < 0.001

    def test_heartbeat_overwrites_previous(self, tmp_path):
        env = _base_env(tmp_path)
        _swarm(["heartbeat", "--status", "first"], env, cwd=tmp_path)
        _swarm(["heartbeat", "--status", "second"], env, cwd=tmp_path)
        hb = json.loads(
            (tmp_path / "worker-test-1" / "heartbeat.json").read_text(encoding="utf-8")
        )
        assert hb["status"] == "second", "heartbeat must overwrite, not append"


class TestMonitor:
    def _setup_workers(self, tmp_path: Path) -> None:
        """Pre-create heartbeats + inbox messages for 2 workers."""
        for wid in ("worker-test-1", "worker-test-2"):
            hb = {
                "worker_id": wid,
                "ts": "2026-05-27T09:00:00Z",
                "status": f"{wid} running",
                "progress": 0.5,
            }
            _atomic_write_direct(tmp_path / wid / "heartbeat.json", hb)
        # Plant 2 unread messages in worker-test-1's inbox
        for i in range(2):
            _plant_message(tmp_path, "worker-test-1", f"monitor-msg-{i:03d}", {
                "msg_id": f"monitor-msg-{i:03d}", "from": "worker-test-2",
                "to": "worker-test-1", "body": f"msg {i}",
                "sent_at": "2026-05-27T09:00:00Z",
            })

    def test_monitor_returns_dashboard_json(self, tmp_path):
        self._setup_workers(tmp_path)
        env = _base_env(tmp_path)
        r = _swarm(["monitor"], env, cwd=tmp_path)
        assert r.returncode == 0, f"stderr: {r.stderr}"
        data = json.loads(r.stdout)
        assert "workers" in data
        assert "polled_at" in data
        assert "session" in data

    def test_monitor_includes_all_workers(self, tmp_path):
        self._setup_workers(tmp_path)
        env = _base_env(tmp_path)
        r = _swarm(["monitor"], env, cwd=tmp_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        worker_ids = {w["worker_id"] for w in data["workers"]}
        assert "worker-test-1" in worker_ids
        assert "worker-test-2" in worker_ids

    def test_monitor_counts_inbox_unread(self, tmp_path):
        self._setup_workers(tmp_path)
        env = _base_env(tmp_path)
        r = _swarm(["monitor"], env, cwd=tmp_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        w1 = next(w for w in data["workers"] if w["worker_id"] == "worker-test-1")
        assert w1["inbox_unread"] == 2

    def test_monitor_watch_produces_multiple_snapshots(self, tmp_path):
        env = _base_env(tmp_path)
        # --interval 0.2 → should produce ≥2 snapshots in ~1s before we kill it
        proc = subprocess.Popen(
            [PYTHON, "-m", "scripts.swarm", "monitor", "--watch", "--interval", "0.2"],
            env={**os.environ, **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.8)
        proc.terminate()
        proc.wait(timeout=3)
        output = proc.stdout.read() if proc.stdout else ""
        # Should have at least 2 JSON objects in the output (newline-separated)
        snapshots = [line for line in output.splitlines() if line.strip().startswith("{")]
        assert len(snapshots) >= 2, f"expected ≥2 snapshots, got {len(snapshots)}: {output!r}"

    def test_monitor_reports_alive_status(self, tmp_path):
        """Worker whose heartbeat ts is < 30s old is marked alive=True."""
        self._setup_workers(tmp_path)
        # Overwrite heartbeat with current time so it's definitely alive
        hb = {
            "worker_id": "worker-test-1",
            "ts": _now_iso_direct(),
            "status": "active",
            "progress": 0.1,
        }
        _atomic_write_direct(tmp_path / "worker-test-1" / "heartbeat.json", hb)
        env = _base_env(tmp_path)
        r = _swarm(["monitor"], env, cwd=tmp_path)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        w1 = next(w for w in data["workers"] if w["worker_id"] == "worker-test-1")
        assert w1["alive"] is True


# Test-level helpers (avoid importing swarm internals; replicate tiny pieces)
def _atomic_write_direct(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp-test")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)

def _now_iso_direct() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


# ============================================================
# T5 — rpc + rpc-respond
# ============================================================

import threading


class TestRpc:
    def _write_response_after_delay(
        self, session_dir: Path, rpc_id: str, body: str, delay: float
    ) -> threading.Thread:
        """Background thread that writes response.json after `delay` seconds."""
        rpc_resp_path = session_dir / "rpc" / rpc_id / "response.json"

        def writer():
            time.sleep(delay)
            rpc_resp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = rpc_resp_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"body": body, "rpc_id": rpc_id}), encoding="utf-8")
            tmp.replace(rpc_resp_path)

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        return t

    def _pre_write_request(self, session_dir: Path, rpc_id: str, to_worker: str) -> None:
        """Pre-write a request.json so rpc-respond can validate it."""
        req_path = session_dir / "rpc" / rpc_id / "request.json"
        req_path.parent.mkdir(parents=True, exist_ok=True)
        req_path.write_text(json.dumps({
            "rpc_id": rpc_id,
            "from": "worker-test-1",
            "to": to_worker,
            "body": "test request",
            "sent_at": "2026-05-27T09:00:00Z",
        }), encoding="utf-8")

    def test_rpc_sends_request_to_recipient_inbox(self, tmp_path):
        env = _base_env(tmp_path)
        # Pre-stage a response so rpc doesn't time out
        # We need the rpc-id first — use a side effect: start rpc in background
        # and capture the rpc-id via the request.json it writes.
        proc = subprocess.Popen(
            [PYTHON, "-m", "scripts.swarm", "rpc",
             "--to", "worker-test-2", "--body", "check this", "--timeout", "3"],
            env={**os.environ, **env},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        # Wait a moment for request.json to appear
        rpc_dir = tmp_path / "rpc"
        deadline = time.monotonic() + 3.0
        rpc_id = None
        while time.monotonic() < deadline:
            if rpc_dir.exists():
                children = list(rpc_dir.iterdir())
                if children:
                    rpc_id = children[0].name
                    break
            time.sleep(0.05)

        assert rpc_id is not None, "rpc-id directory not created within 3s"
        # Write response to unblock rpc
        resp_path = rpc_dir / rpc_id / "response.json"
        resp_path.parent.mkdir(parents=True, exist_ok=True)
        resp_path.write_text(json.dumps({"body": "ok", "rpc_id": rpc_id}), encoding="utf-8")

        proc.wait(timeout=5)
        # Recipient's inbox must have a message with correlation_id = rpc_id
        peer_inbox = tmp_path / "worker-test-2" / "inbox"
        assert peer_inbox.exists(), "recipient inbox not created"
        msgs = list(peer_inbox.glob("*.json"))
        assert len(msgs) >= 1, "no message delivered to recipient inbox"
        envelope = json.loads(msgs[0].read_text(encoding="utf-8"))
        assert envelope.get("correlation_id") == rpc_id

    def test_rpc_returns_response_body(self, tmp_path):
        env = _base_env(tmp_path)
        rpc_id_holder: list[str] = []

        def stage_response():
            rpc_dir = tmp_path / "rpc"
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if rpc_dir.exists():
                    children = list(rpc_dir.iterdir())
                    if children:
                        rid = children[0].name
                        rpc_id_holder.append(rid)
                        resp = rpc_dir / rid / "response.json"
                        resp.parent.mkdir(parents=True, exist_ok=True)
                        resp.write_text(json.dumps({"body": "pong", "rpc_id": rid}), encoding="utf-8")
                        return
                time.sleep(0.05)

        t = threading.Thread(target=stage_response, daemon=True)
        t.start()
        r = _swarm(
            ["rpc", "--to", "worker-test-2", "--body", "ping", "--timeout", "5"],
            env, cwd=tmp_path,
        )
        t.join(timeout=2)
        assert r.returncode == 0, f"rpc failed: {r.stderr}"
        result = json.loads(r.stdout)
        assert result.get("body") == "pong"

    def test_rpc_exits_124_on_timeout(self, tmp_path):
        env = _base_env(tmp_path)
        # No responder — should time out
        r = _swarm(
            ["rpc", "--to", "worker-test-2", "--body", "ping", "--timeout", "0.3"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 124, f"expected 124, got {r.returncode}: {r.stderr}"

    def test_rpc_creates_request_json(self, tmp_path):
        env = _base_env(tmp_path)
        proc = subprocess.Popen(
            [PYTHON, "-m", "scripts.swarm", "rpc",
             "--to", "worker-test-2", "--body", "hello", "--timeout", "2"],
            env={**os.environ, **env},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        rpc_dir = tmp_path / "rpc"
        deadline = time.monotonic() + 2.0
        found = False
        while time.monotonic() < deadline:
            if rpc_dir.exists() and any(rpc_dir.iterdir()):
                found = True
                break
            time.sleep(0.05)
        proc.terminate()
        proc.wait(timeout=3)
        assert found, "rpc/<rpc-id>/request.json not created"


class TestRpcRespond:
    def test_rpc_respond_writes_response_json(self, tmp_path):
        env = {**_base_env(tmp_path), "OMW_SWARM_WORKER_ID": "worker-test-2"}
        rpc_id = "rpc-test-001"
        # Pre-write request.json with to=worker-test-2
        req_path = tmp_path / "rpc" / rpc_id / "request.json"
        req_path.parent.mkdir(parents=True, exist_ok=True)
        req_path.write_text(json.dumps({
            "rpc_id": rpc_id, "from": "worker-test-1",
            "to": "worker-test-2", "body": "question",
            "sent_at": "2026-05-27T09:00:00Z",
        }), encoding="utf-8")
        r = _swarm(
            ["rpc-respond", "--rpc-id", rpc_id, "--body", "the answer"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        resp_path = tmp_path / "rpc" / rpc_id / "response.json"
        assert resp_path.exists(), "response.json not created"
        resp = json.loads(resp_path.read_text(encoding="utf-8"))
        assert resp["body"] == "the answer"

    def test_rpc_respond_rejects_to_mismatch(self, tmp_path):
        # Worker-test-1 tries to respond to an RPC addressed to worker-test-2
        env = _base_env(tmp_path)  # worker_id = worker-test-1
        rpc_id = "rpc-test-002"
        req_path = tmp_path / "rpc" / rpc_id / "request.json"
        req_path.parent.mkdir(parents=True, exist_ok=True)
        req_path.write_text(json.dumps({
            "rpc_id": rpc_id, "from": "worker-test-3",
            "to": "worker-test-2",  # addressed to someone else
            "body": "Q", "sent_at": "2026-05-27T09:00:00Z",
        }), encoding="utf-8")
        r = _swarm(
            ["rpc-respond", "--rpc-id", rpc_id, "--body", "unauthorized"],
            env, cwd=tmp_path,
        )
        assert r.returncode != 0, "rpc-respond must reject to-mismatch"


# ============================================================
# T6 — vote-create + vote + vote-result
# ============================================================

class TestVote:
    def _create_proposal(self, tmp_path: Path, env: dict, proposal: str,
                         choices: str = "", quorum: int = 0) -> str:
        """Helper: call vote-create, return proposal_id."""
        args = ["vote-create", "--proposal", proposal]
        if choices:
            args += ["--choices", choices]
        if quorum:
            args += ["--quorum", str(quorum)]
        r = _swarm(args, env, cwd=tmp_path)
        assert r.returncode == 0, f"vote-create failed: {r.stderr}"
        result = json.loads(r.stdout)
        return result["proposal_id"]

    def _cast_vote(self, tmp_path: Path, worker_id: str, proposal_id: str, choice: str) -> None:
        """Helper: cast a vote as a specific worker."""
        env = {
            "OMW_SWARM_SESSION_DIR": str(tmp_path),
            "OMW_SWARM_WORKER_ID": worker_id,
            "OMW_SWARM_PEERS": ",".join(
                w for w in ("worker-test-1", "worker-test-2", "worker-test-3")
                if w != worker_id
            ),
        }
        r = _swarm(["vote", "--proposal-id", proposal_id, "--choice", choice], env, cwd=tmp_path)
        assert r.returncode == 0, f"vote failed for {worker_id}: {r.stderr}"

    def test_vote_create_returns_proposal_id(self, tmp_path):
        env = _base_env(tmp_path)
        r = _swarm(
            ["vote-create", "--proposal", "claim: Python year"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        result = json.loads(r.stdout)
        assert "proposal_id" in result
        assert result["proposal_id"]

    def test_vote_create_writes_proposal_json(self, tmp_path):
        env = _base_env(tmp_path)
        proposal_id = self._create_proposal(tmp_path, env, "claim: Python year")
        prop_path = tmp_path / "proposals" / proposal_id / "proposal.json"
        assert prop_path.exists(), "proposal.json not created"
        prop = json.loads(prop_path.read_text(encoding="utf-8"))
        assert prop["proposal_text"] == "claim: Python year"

    def test_vote_records_choice(self, tmp_path):
        env = _base_env(tmp_path)
        proposal_id = self._create_proposal(tmp_path, env, "year vote")
        r = _swarm(
            ["vote", "--proposal-id", proposal_id, "--choice", "1991"],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        vote_file = tmp_path / "proposals" / proposal_id / "vote-worker-test-1.json"
        assert vote_file.exists()
        vote_data = json.loads(vote_file.read_text(encoding="utf-8"))
        assert vote_data["choice"] == "1991"

    def test_vote_revote_overwrites(self, tmp_path):
        env = _base_env(tmp_path)
        proposal_id = self._create_proposal(tmp_path, env, "revote test")
        _swarm(["vote", "--proposal-id", proposal_id, "--choice", "A"], env, cwd=tmp_path)
        _swarm(["vote", "--proposal-id", proposal_id, "--choice", "B"], env, cwd=tmp_path)
        vote_file = tmp_path / "proposals" / proposal_id / "vote-worker-test-1.json"
        vote_data = json.loads(vote_file.read_text(encoding="utf-8"))
        assert vote_data["choice"] == "B", "re-vote must overwrite previous (last-write-wins)"

    def test_vote_result_simple_majority(self, tmp_path):
        env = _base_env(tmp_path)
        proposal_id = self._create_proposal(tmp_path, env, "majority test", quorum=3)
        self._cast_vote(tmp_path, "worker-test-1", proposal_id, "1991")
        self._cast_vote(tmp_path, "worker-test-2", proposal_id, "1991")
        self._cast_vote(tmp_path, "worker-test-3", proposal_id, "1989")
        r = _swarm(
            ["vote-result", "--proposal-id", proposal_id],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        result = json.loads(r.stdout)
        assert result["winner"] == "1991"
        assert result["tally"]["1991"] == 2
        assert result["tally"]["1989"] == 1

    def test_vote_result_tie_broken_by_lex_order(self, tmp_path):
        env = _base_env(tmp_path)
        # 1 vote each for "apple" and "banana" → "apple" wins (lex first)
        proposal_id = self._create_proposal(tmp_path, env, "tie test", quorum=2)
        self._cast_vote(tmp_path, "worker-test-1", proposal_id, "banana")
        self._cast_vote(tmp_path, "worker-test-2", proposal_id, "apple")
        r = _swarm(
            ["vote-result", "--proposal-id", proposal_id],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0
        result = json.loads(r.stdout)
        assert result["winner"] == "apple", (
            f"tie must be broken by lex order; expected 'apple', got {result['winner']!r}"
        )

    def test_vote_result_dissenters_listed(self, tmp_path):
        env = _base_env(tmp_path)
        proposal_id = self._create_proposal(tmp_path, env, "dissent test", quorum=3)
        self._cast_vote(tmp_path, "worker-test-1", proposal_id, "yes")
        self._cast_vote(tmp_path, "worker-test-2", proposal_id, "yes")
        self._cast_vote(tmp_path, "worker-test-3", proposal_id, "no")
        r = _swarm(
            ["vote-result", "--proposal-id", proposal_id],
            env, cwd=tmp_path,
        )
        assert r.returncode == 0
        result = json.loads(r.stdout)
        winner = result["winner"]
        dissenters = result.get("dissenters", [])
        assert len(dissenters) == 1
        assert dissenters[0]["worker_id"] == "worker-test-3"
        assert dissenters[0]["choice"] == "no"
