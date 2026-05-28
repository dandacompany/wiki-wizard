"""tests/test_swarm_integration.py — Simulated swarm integration tests.

Each test spawns 2-3 shell "workers" (subprocess.Popen of swarm-helper.sh
behaviors or direct python -m scripts.swarm calls) sharing a tmp_path
session_dir. Tests assert on file-system state after workers complete.

No tmux. No LLM backends. Pure file-bus verification.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SWARM = ["python3", "-m", "scripts.swarm"]


def _make_session(tmp_path: Path, workers: list[str]) -> dict[str, str]:
    """Create per-worker inbox dirs and return env dict for each worker."""
    (tmp_path / "messages").mkdir(parents=True, exist_ok=True)
    (tmp_path / "proposals").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rpc").mkdir(parents=True, exist_ok=True)
    for wid in workers:
        (tmp_path / wid / "inbox").mkdir(parents=True, exist_ok=True)
    return {}  # caller builds per-worker env from this


def _env(tmp_path: Path, worker_id: str, peers: list[str]) -> dict[str, str]:
    e = os.environ.copy()
    e["OMW_SWARM_SESSION_DIR"] = str(tmp_path)
    e["OMW_SWARM_WORKER_ID"] = worker_id
    e["OMW_SWARM_PEERS"] = ",".join(peers)
    return e


def _run(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, env=env, capture_output=True, text=True, timeout=30
    )


def _swarm(op: str, extra: list[str], env: dict) -> subprocess.CompletedProcess:
    return _run(SWARM + [op] + extra, env)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTwoWorkerHandshake:
    def test_two_worker_handshake(self, tmp_path):
        workers = ["worker-1", "worker-2"]
        _make_session(tmp_path, workers)

        env_w1 = _env(tmp_path, "worker-1", ["worker-2"])
        env_w2 = _env(tmp_path, "worker-2", ["worker-1"])

        # W1 sends to W2
        result = _swarm("send", ["--to", "worker-2", "--body", "hello from W1"], env_w1)
        assert result.returncode == 0, result.stderr

        # W2 reads inbox
        result = _swarm("inbox", ["--unread-only"], env_w2)
        assert result.returncode == 0, result.stderr
        msgs = json.loads(result.stdout)
        assert len(msgs) == 1
        assert msgs[0]["from"] == "worker-1"
        assert msgs[0]["body"] == "hello from W1"


class TestThreeWorkerBroadcast:
    def test_broadcast_reaches_all_peers(self, tmp_path):
        workers = ["worker-1", "worker-2", "worker-3"]
        _make_session(tmp_path, workers)

        env_w1 = _env(tmp_path, "worker-1", ["worker-2", "worker-3"])
        env_w2 = _env(tmp_path, "worker-2", ["worker-1", "worker-3"])
        env_w3 = _env(tmp_path, "worker-3", ["worker-1", "worker-2"])

        result = _swarm("broadcast", ["--body", "broadcast body"], env_w1)
        assert result.returncode == 0, result.stderr

        for env in [env_w2, env_w3]:
            result = _swarm("inbox", ["--unread-only"], env)
            msgs = json.loads(result.stdout)
            assert len(msgs) == 1
            assert msgs[0]["body"] == "broadcast body"

    def test_broadcast_excludes_self(self, tmp_path):
        workers = ["worker-1", "worker-2"]
        _make_session(tmp_path, workers)
        env_w1 = _env(tmp_path, "worker-1", ["worker-2"])

        _swarm("broadcast", ["--body", "selftest"], env_w1)

        result = _swarm("inbox", ["--unread-only"], env_w1)
        msgs = json.loads(result.stdout)
        assert len(msgs) == 0, "sender must not receive own broadcast"


class TestPubSubTopicFiltering:
    def test_topic_filter_matches(self, tmp_path):
        workers = ["worker-1", "worker-2"]
        _make_session(tmp_path, workers)
        env_w1 = _env(tmp_path, "worker-1", ["worker-2"])
        env_w2 = _env(tmp_path, "worker-2", ["worker-1"])

        _swarm("publish", ["--topic", "alpha", "--body", "alpha msg"], env_w1)

        result = _swarm("inbox", ["--topic", "alpha", "--unread-only"], env_w2)
        msgs = json.loads(result.stdout)
        assert len(msgs) == 1

        result = _swarm("inbox", ["--topic", "beta", "--unread-only"], env_w2)
        msgs = json.loads(result.stdout)
        assert len(msgs) == 0


class TestVoteConsensus:
    def test_vote_quorum_and_winner(self, tmp_path):
        workers = ["worker-1", "worker-2", "worker-3"]
        _make_session(tmp_path, workers)
        env_w1 = _env(tmp_path, "worker-1", ["worker-2", "worker-3"])
        env_w2 = _env(tmp_path, "worker-2", ["worker-1", "worker-3"])
        env_w3 = _env(tmp_path, "worker-3", ["worker-1", "worker-2"])

        # W1 creates proposal
        result = _swarm("vote-create", ["--proposal", "Python year?", "--quorum", "3"], env_w1)
        assert result.returncode == 0, result.stderr
        proposal_id = json.loads(result.stdout)["proposal_id"]

        # all three vote
        _swarm("vote", ["--proposal-id", proposal_id, "--choice", "1991"], env_w1)
        _swarm("vote", ["--proposal-id", proposal_id, "--choice", "1991"], env_w2)
        _swarm("vote", ["--proposal-id", proposal_id, "--choice", "1989"], env_w3)

        result = _swarm("vote-result", ["--proposal-id", proposal_id], env_w1)
        assert result.returncode == 0, result.stderr
        tally = json.loads(result.stdout)
        assert tally["winner"] == "1991"
        assert tally["quorum_reached"] is True
        assert len(tally["dissenters"]) == 1
        assert tally["dissenters"][0]["choice"] == "1989"

    def test_vote_tie_broken_lexicographically(self, tmp_path):
        workers = ["worker-1", "worker-2"]
        _make_session(tmp_path, workers)
        env_w1 = _env(tmp_path, "worker-1", ["worker-2"])
        env_w2 = _env(tmp_path, "worker-2", ["worker-1"])

        result = _swarm("vote-create", ["--proposal", "tie test?", "--quorum", "2"], env_w1)
        proposal_id = json.loads(result.stdout)["proposal_id"]

        _swarm("vote", ["--proposal-id", proposal_id, "--choice", "zebra"], env_w1)
        _swarm("vote", ["--proposal-id", proposal_id, "--choice", "alpha"], env_w2)

        result = _swarm("vote-result", ["--proposal-id", proposal_id], env_w1)
        tally = json.loads(result.stdout)
        assert tally["winner"] == "alpha", "tie broken by lexicographic order (smallest wins)"


class TestRPCRoundtrip:
    def test_rpc_roundtrip(self, tmp_path):
        workers = ["worker-1", "worker-2"]
        _make_session(tmp_path, workers)
        env_w1 = _env(tmp_path, "worker-1", ["worker-2"])
        env_w2 = _env(tmp_path, "worker-2", ["worker-1"])

        # Set up: W2 will respond after W1 sends RPC.
        # We simulate this with two subprocesses:
        #   1. Start W2's rpc-respond in background (polls for request)
        #   2. W1 sends rpc --to worker-2

        # First, have W1 send the RPC request (writes request file)
        # We'll use a helper: write request.json manually so W2 can respond.
        import uuid
        rpc_id = f"rpc-{uuid.uuid4().hex[:8]}"
        rpc_dir = tmp_path / "rpc" / rpc_id
        rpc_dir.mkdir(parents=True)
        request = {
            "from": "worker-1",
            "to": "worker-2",
            "body": "review draft",
            "sent_at": "2026-05-27T00:00:00Z",
        }
        (rpc_dir / "request.json").write_text(json.dumps(request))

        # W2 responds
        result = _swarm("rpc-respond", ["--rpc-id", rpc_id, "--body", "OK"], env_w2)
        assert result.returncode == 0, result.stderr

        # Verify response file written
        response_file = rpc_dir / "response.json"
        assert response_file.exists()
        resp = json.loads(response_file.read_text())
        assert resp["body"] == "OK"

    def test_rpc_timeout_exits_124(self, tmp_path):
        workers = ["worker-1", "worker-2"]
        _make_session(tmp_path, workers)
        env_w1 = _env(tmp_path, "worker-1", ["worker-2"])

        # Send RPC with very short timeout — W2 will never respond
        result = _run(
            SWARM + ["rpc", "--to", "worker-2", "--body", "hello", "--timeout", "1"],
            env_w1,
        )
        assert result.returncode == 124, (
            f"Expected exit 124 on timeout, got {result.returncode}. "
            f"stderr: {result.stderr}"
        )


class TestHeartbeatAndMonitor:
    def test_heartbeat_appears_in_monitor(self, tmp_path):
        workers = ["worker-1"]
        _make_session(tmp_path, workers)
        env_w1 = _env(tmp_path, "worker-1", [])

        result = _swarm(
            "heartbeat",
            ["--status", "verifying claim 3 of 7", "--progress", "0.43"],
            env_w1,
        )
        assert result.returncode == 0, result.stderr

        # monitor reads session dir from env (no --session flag)
        monitor_env = _env(tmp_path, "worker-1", [])
        result = subprocess.run(
            SWARM + ["monitor"],
            env=monitor_env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        dashboard = json.loads(result.stdout)
        worker_states = {w["worker_id"]: w for w in dashboard["workers"]}
        assert "worker-1" in worker_states
        hb = worker_states["worker-1"]["heartbeat"]
        assert hb["status"] == "verifying claim 3 of 7"
        assert abs(hb["progress"] - 0.43) < 0.01


class TestDeliveredMessagesNotReturnedAsUnread:
    def test_delivered_messages_not_returned_in_unread(self, tmp_path):
        workers = ["worker-1", "worker-2"]
        _make_session(tmp_path, workers)
        env_w1 = _env(tmp_path, "worker-1", ["worker-2"])
        env_w2 = _env(tmp_path, "worker-2", ["worker-1"])

        _swarm("send", ["--to", "worker-2", "--body", "msg1"], env_w1)

        # First read with mark-delivered
        result = _swarm("inbox", ["--unread-only", "--mark-delivered"], env_w2)
        msgs = json.loads(result.stdout)
        assert len(msgs) == 1

        # Second read — should be empty
        result = _swarm("inbox", ["--unread-only"], env_w2)
        msgs = json.loads(result.stdout)
        assert len(msgs) == 0, "delivered messages must not appear as unread"
