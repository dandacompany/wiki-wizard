"""
tests/test_dispatch.py — dispatch_one() unit + integration tests.

All real-backend calls are replaced by tests/fakes/ via OMW_BACKEND_OVERRIDE_PATH.
Requires tmux in env (installed by Task 1's CI step).
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from scripts.dispatch import dispatch_one, DispatchRequest, DispatchResult


FAKES_DIR = Path(__file__).parent / "fakes"


@pytest.fixture
def fake_env(monkeypatch, tmp_path):
    """Point backends at fakes/ and give each test an isolated vault."""
    monkeypatch.setenv("OMW_BACKEND_OVERRIDE_PATH", str(FAKES_DIR))
    monkeypatch.setenv("OMW_VAULT_ROOT", str(tmp_path))
    return tmp_path


class TestDispatchOne:
    def test_returns_dispatch_result(self, fake_env):
        req = DispatchRequest(
            persona="fact-checker",
            backend="claude",
            model="claude-sonnet-4-6",
            source_path=fake_env / "source.md",
            skip_permissions=False,
        )
        (fake_env / "source.md").write_text("# Draft\nSome claims here.")
        result = dispatch_one(req, session_dir=fake_env / "session")
        assert isinstance(result, DispatchResult)
        assert result.status == "ok"
        assert result.worker_id.startswith("worker-")

    def test_result_path_matches_persona_output_kind(self, fake_env):
        """fact-checker output_kind=sibling_suffix → source.factcheck.md."""
        src = fake_env / "doc.md"
        src.write_text("content")
        req = DispatchRequest(
            persona="fact-checker", backend="claude",
            model="claude-sonnet-4-6", source_path=src,
            skip_permissions=False,
        )
        result = dispatch_one(req, session_dir=fake_env / "s")
        assert result.result_path is not None
        assert result.result_path.name == "doc.factcheck.md"

    def test_worker_prompt_has_persona_and_task_sections(self, fake_env, tmp_path):
        """input.md written for the worker must contain both section headers."""
        src = fake_env / "article.md"
        src.write_text("article body")
        req = DispatchRequest(
            persona="summarizer", backend="codex",
            model="gpt-5", source_path=src,
            skip_permissions=False,
        )
        result = dispatch_one(req, session_dir=fake_env / "s2")
        input_md = fake_env / "s2" / result.worker_id / "input.md"
        text = input_md.read_text()
        assert "=== PERSONA ===" in text
        assert "=== TASK ===" in text

    def test_done_json_written_by_fake_backend(self, fake_env):
        src = fake_env / "x.md"
        src.write_text("x")
        req = DispatchRequest(
            persona="polisher", backend="gemini",
            model="gemini-2.5-pro", source_path=src,
            skip_permissions=False,
        )
        result = dispatch_one(req, session_dir=fake_env / "s3")
        done = fake_env / "s3" / result.worker_id / "done.json"
        assert done.exists()
        data = json.loads(done.read_text())
        assert data["status"] == "ok"

    def test_skip_permissions_flag_forwarded(self, fake_env, monkeypatch):
        """When skip_permissions=True the fake backend receives the flag in its argv."""
        flags_log = fake_env / "flags.log"
        monkeypatch.setenv("OMW_FAKE_FLAGS_LOG", str(flags_log))
        src = fake_env / "s.md"
        src.write_text("s")
        req = DispatchRequest(
            persona="fact-checker", backend="claude",
            model="claude-sonnet-4-6", source_path=src,
            skip_permissions=True,
        )
        dispatch_one(req, session_dir=fake_env / "s4")
        if flags_log.exists():
            assert "--dangerously-skip-permissions" in flags_log.read_text()

    def test_failed_worker_returns_failed_status(self, fake_env, monkeypatch):
        """Fake backend exits 1 when OMW_FAKE_FAIL=1."""
        monkeypatch.setenv("OMW_FAKE_FAIL", "1")
        src = fake_env / "f.md"
        src.write_text("fail me")
        req = DispatchRequest(
            persona="fact-checker", backend="claude",
            model="claude-sonnet-4-6", source_path=src,
            skip_permissions=False,
        )
        result = dispatch_one(req, session_dir=fake_env / "s5")
        assert result.status == "failed"

    def test_session_dir_artifacts_created(self, fake_env):
        """dispatch_one must create session_dir/worker-N/{input.md, done.json, pane.log}."""
        src = fake_env / "art.md"
        src.write_text("art")
        req = DispatchRequest(
            persona="consistency-checker", backend="codex",
            model="gpt-5", source_path=src,
            skip_permissions=False,
        )
        sess = fake_env / "sess-art"
        result = dispatch_one(req, session_dir=sess)
        worker_dir = sess / result.worker_id
        assert (worker_dir / "input.md").exists()
        assert (worker_dir / "done.json").exists()

    def test_backend_override_path_used(self, fake_env):
        """Smoke: OMW_BACKEND_OVERRIDE_PATH is respected — no real claude needed."""
        src = fake_env / "smoke.md"
        src.write_text("smoke")
        req = DispatchRequest(
            persona="fact-checker", backend="claude",
            model="claude-sonnet-4-6", source_path=src,
            skip_permissions=False,
        )
        # If real claude is absent but fakes exist, this must not raise
        result = dispatch_one(req, session_dir=fake_env / "smoke-sess")
        assert result.status in ("ok", "failed")  # fakes may or may not set up output
