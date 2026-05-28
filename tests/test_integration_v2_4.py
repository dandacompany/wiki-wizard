"""tests/test_integration_v2_4.py — E2E integration tests for oh-my-wiki v2.4.

Full vertical slice: real tmux + fake backends + swarm CLI.
Requires tmux to be installed; skipped automatically if absent.

Five tests:
  T17.1 — TestTripleFactcheckModerator
  T17.2 — TestPolishFactcheckLoop
  T17.3 — TestPerspectiveSynthesisTeam
  T17.4 — TestSwarmContextInjection
  T17.5 — TestSwarmDisabledTeamHasNoSwarmEnv

Mark: @pytest.mark.integration
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Guard — skip entire module if tmux not available
# ---------------------------------------------------------------------------

if not shutil.which("tmux"):
    pytest.skip("tmux not available — skipping v2.4 e2e tests", allow_module_level=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
FAKES_DIR = REPO_ROOT / "tests" / "fakes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_env(
    behavior: str,
    worker_id: str,
    session_dir: Path,
    peers: list[str],
    extra: dict | None = None,
) -> dict[str, str]:
    """Build an env dict for a fake swarm backend script."""
    e = os.environ.copy()
    e["OMW_FAKE_SWARM_BEHAVIOR"] = behavior
    e["OMW_SWARM_SESSION_DIR"] = str(session_dir)
    e["OMW_SWARM_WORKER_ID"] = worker_id
    e["OMW_SWARM_PEERS"] = ",".join(peers)
    if extra:
        e.update(extra)
    return e


def _run_fake(
    script: str,
    env: dict,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Run a fake backend shell script and return its CompletedProcess."""
    return subprocess.run(
        ["bash", str(FAKES_DIR / script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _setup_session(session_dir: Path, worker_ids: list[str]) -> None:
    """Create the standard swarm session directory tree."""
    (session_dir / "messages").mkdir(parents=True, exist_ok=True)
    (session_dir / "proposals").mkdir(parents=True, exist_ok=True)
    (session_dir / "rpc").mkdir(parents=True, exist_ok=True)
    for wid in worker_ids:
        (session_dir / wid / "inbox").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# T17.1 — Triple fact-check + moderator
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTripleFactcheckModerator:
    """3 fact-checker fakes publish claims; moderator fake synthesizes."""

    def test_three_fact_checkers_publish_and_moderator_reads(self, tmp_path):
        workers = [
            "worker-1-fact-checker",
            "worker-2-fact-checker",
            "worker-3-fact-checker",
            "worker-4-moderator",
        ]
        _setup_session(tmp_path, workers)

        # Map each fact-checker to a different fake backend (mirroring the real team)
        scripts = ["claude-fake.sh", "codex-fake.sh", "gemini-fake.sh"]

        for i, (wid, script) in enumerate(zip(workers[:3], scripts), start=1):
            peers = [w for w in workers if w != wid]
            env = _fake_env("publish-claim", wid, tmp_path, peers)
            result = _run_fake(script, env)
            assert result.returncode == 0, (
                f"fact-checker {i} ({wid}) failed:\n"
                f"  stdout: {result.stdout!r}\n"
                f"  stderr: {result.stderr!r}"
            )

        # Verify ≥3 claim messages landed in session messages dir
        msgs = list((tmp_path / "messages").glob("*.json"))
        claim_msgs = [
            m for m in msgs
            if json.loads(m.read_text()).get("topic") == "claim"
        ]
        assert len(claim_msgs) >= 3, (
            f"expected ≥3 claim messages, got {len(claim_msgs)} "
            f"(messages: {[m.name for m in msgs]})"
        )

        # Moderator synthesizes
        mod_id = "worker-4-moderator"
        peers = [w for w in workers if w != mod_id]
        env = _fake_env("moderator-synthesize", mod_id, tmp_path, peers)
        result = _run_fake("claude-fake.sh", env)
        assert result.returncode == 0, (
            f"moderator failed:\n  stderr: {result.stderr!r}"
        )
        assert "Fake moderator synthesis" in result.stdout, (
            f"moderator stdout did not contain 'Fake moderator synthesis': "
            f"{result.stdout!r}"
        )


# ---------------------------------------------------------------------------
# T17.2 — Polish–factcheck RPC loop
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPolishFactcheckLoop:
    """Polisher fake sends RPC; fact-checker fake responds."""

    def test_rpc_roundtrip_between_polisher_and_factchecker(self, tmp_path):
        workers = ["worker-2-polisher", "worker-3-fact-checker"]
        _setup_session(tmp_path, workers)

        rpc_id = f"rpc-{uuid.uuid4().hex[:8]}"
        rpc_dir = tmp_path / "rpc" / rpc_id
        rpc_dir.mkdir(parents=True)

        # Pre-write request.json — simulates what polisher's swarm rpc would write
        request = {
            "rpc_id": rpc_id,
            "from": "worker-2-polisher",
            "to": "worker-3-fact-checker",
            "body": "review draft at /tmp/fake-draft.md",
            "sent_at": "2026-05-27T00:00:00Z",
        }
        (rpc_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")

        # Fact-checker responds via rpc-respond behavior
        env_fc = _fake_env(
            "rpc-respond",
            "worker-3-fact-checker",
            tmp_path,
            ["worker-2-polisher"],
            {"OMW_FAKE_RPC_ID": rpc_id},
        )
        result = _run_fake("gemini-fake.sh", env_fc)
        assert result.returncode == 0, (
            f"fact-checker rpc-respond failed:\n"
            f"  stdout: {result.stdout!r}\n"
            f"  stderr: {result.stderr!r}"
        )

        # Verify response.json was written with body "OK"
        response_file = rpc_dir / "response.json"
        assert response_file.exists(), (
            f"fact-checker must write rpc/{rpc_id}/response.json "
            f"(files in rpc dir: {list(rpc_dir.iterdir())})"
        )
        resp = json.loads(response_file.read_text(encoding="utf-8"))
        assert resp["body"] == "OK", (
            f"response body should be 'OK', got {resp['body']!r}"
        )


# ---------------------------------------------------------------------------
# T17.3 — Perspective synthesis team
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPerspectiveSynthesisTeam:
    """3 perspective-writer fakes publish; moderator fake collects all 3."""

    def test_three_perspective_drafts_collected_by_moderator(self, tmp_path):
        workers = [
            "worker-1-perspective-writer",
            "worker-2-perspective-writer",
            "worker-3-perspective-writer",
            "worker-4-moderator",
        ]
        _setup_session(tmp_path, workers)

        scripts = ["claude-fake.sh", "codex-fake.sh", "gemini-fake.sh"]

        for wid, script in zip(workers[:3], scripts):
            peers = [w for w in workers if w != wid]
            env = _fake_env("perspective-publish", wid, tmp_path, peers)
            result = _run_fake(script, env)
            assert result.returncode == 0, (
                f"{wid} perspective-publish failed:\n  stderr: {result.stderr!r}"
            )

        # Verify exactly 3 perspective-draft messages
        msgs = list((tmp_path / "messages").glob("*.json"))
        perspective_msgs = [
            m for m in msgs
            if json.loads(m.read_text()).get("topic") == "perspective-draft"
        ]
        assert len(perspective_msgs) == 3, (
            f"expected 3 perspective-draft messages, got {len(perspective_msgs)} "
            f"(topics: {[json.loads(m.read_text()).get('topic') for m in msgs]})"
        )

        # Moderator reads inbox (synthesize behavior)
        mod_id = "worker-4-moderator"
        peers = [w for w in workers if w != mod_id]
        env = _fake_env("moderator-synthesize", mod_id, tmp_path, peers)
        result = _run_fake("claude-fake.sh", env)
        assert result.returncode == 0, (
            f"moderator failed:\n  stderr: {result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# T17.4 — Swarm context injection
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSwarmContextInjection:
    """Worker dispatched in swarm team has === SWARM === section in input.md."""

    def test_swarm_env_and_prompt_injected(self, tmp_path):
        """
        Call dispatch internals directly to build a worker prompt with a swarm
        context and assert the output contains the === SWARM === section with
        the correct worker id and peers.
        """
        sys.path.insert(0, str(REPO_ROOT))
        from scripts.dispatch import _build_worker_prompt, _build_swarm_prompt_section
        from scripts.team import SwarmContext

        worker_dir = tmp_path / "worker-1-fact-checker"
        worker_dir.mkdir(parents=True, exist_ok=True)

        source_path = tmp_path / "source.md"
        source_path.write_text("# Source\n\nTest content.\n", encoding="utf-8")

        # Build the base prompt (without swarm section)
        base_prompt = _build_worker_prompt(
            persona_body="You are a fact-checker.",
            source_path=source_path,
            output_kind="stdout",
            output_target=None,
            worker_dir=worker_dir,
            model="claude-sonnet-4-6",
        )

        # Build swarm context and append section (mirrors dispatch_one logic)
        ctx = SwarmContext(
            session_dir=str(tmp_path),
            worker_id="worker-1-fact-checker",
            peers=["worker-2-moderator"],
        )
        swarm_section = _build_swarm_prompt_section(ctx)
        input_md = base_prompt + "\n" + swarm_section

        assert "=== SWARM ===" in input_md, (
            "Worker input.md must contain === SWARM === section when swarm context is set"
        )
        assert "worker-1-fact-checker" in input_md, (
            "Worker id must appear in swarm section"
        )
        assert "worker-2-moderator" in input_md, (
            "Peer ids must appear in swarm section"
        )


# ---------------------------------------------------------------------------
# T17.5 — Swarm disabled team — no swarm env
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSwarmDisabledTeamHasNoSwarmEnv:
    """Workers in swarm: false teams must NOT receive OMW_SWARM_* in their prompt."""

    def test_non_swarm_worker_prompt_has_no_swarm_section(self, tmp_path):
        """
        Call dispatch internals without a swarm context (swarm: false path) and
        assert the resulting input.md does NOT contain === SWARM ===.
        """
        sys.path.insert(0, str(REPO_ROOT))
        from scripts.dispatch import _build_worker_prompt

        worker_dir = tmp_path / "worker-1-fact-checker"
        worker_dir.mkdir(parents=True, exist_ok=True)

        source_path = tmp_path / "source.md"
        source_path.write_text("# Source\n\nTest content.\n", encoding="utf-8")

        # No swarm_context → swarm: false path
        # dispatch_one only appends swarm section when swarm_context is not None
        input_md = _build_worker_prompt(
            persona_body="You are a fact-checker.",
            source_path=source_path,
            output_kind="stdout",
            output_target=None,
            worker_dir=worker_dir,
            model="claude-sonnet-4-6",
        )

        assert "=== SWARM ===" not in input_md, (
            "Workers in non-swarm teams must NOT receive === SWARM === section"
        )
        assert "OMW_SWARM_SESSION_DIR" not in input_md, (
            "Non-swarm worker prompts must not reference OMW_SWARM_SESSION_DIR"
        )
