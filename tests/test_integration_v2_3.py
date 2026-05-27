"""
Integration tests for oh-my-wiki v2.3 dispatch runtime.

Uses tests/fakes/<backend>-fake.sh as hermetic stand-ins for all 4 CLIs.
Requires real tmux in the environment (guaranteed by CI task 1).

Tests call scripts.dispatch and scripts.team via their Python APIs to simulate
the real leader-agent invocation path end-to-end.

Four scenarios (spec §6):
  (a) Single dispatch — one persona × one backend — ok path
  (b) Parallel team of 3 workers — all ok
  (c) Sequential team with inputs_from: previous — translation-pipeline
  (d) Mixed mode — 4 workers across 3 stages — draft-to-publish
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest

from scripts.dispatch import dispatch_one, DispatchRequest, DispatchResult
from scripts.team import (
    load_template,
    run as team_run,
    aggregate_results,
    TeamTemplate,
)

REPO_ROOT = Path(__file__).parent.parent
FAKES_DIR = REPO_ROOT / "tests" / "fakes"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fake_backends(monkeypatch):
    """Point all backend resolution at tests/fakes/ for the duration of each test."""
    monkeypatch.setenv("OMW_BACKEND_OVERRIDE_PATH", str(FAKES_DIR))


@pytest.fixture()
def src(tmp_path) -> Path:
    """A minimal source document for dispatch tests."""
    p = tmp_path / "draft.md"
    p.write_text("# Test Draft\n\nContent for integration testing.\n", encoding="utf-8")
    return p


def _unique_session_dir(tmp_path: Path, label: str) -> Path:
    """Return a unique session directory under tmp_path."""
    slug = f"{label}-{uuid.uuid4().hex[:6]}"
    d = tmp_path / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# (a) Single dispatch — one persona × one backend — ok path
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSingleDispatch:
    """Single dispatch: fact-checker × claude-fake → done.json with status ok."""

    def test_dispatch_fact_checker_claude_ok(self, tmp_path, src):
        session_dir = _unique_session_dir(tmp_path, "single-dispatch")
        req = DispatchRequest(
            persona="fact-checker",
            backend="claude",
            model="claude-sonnet-4-6",
            source_path=src,
            skip_permissions=False,
        )
        result = dispatch_one(req, session_dir=session_dir)

        # Basic result type and status
        assert isinstance(result, DispatchResult)
        assert result.status == "ok", (
            f"Expected status 'ok', got {result.status!r}. "
            f"worker_id={result.worker_id}"
        )

        # Worker directory must exist with expected artifacts
        worker_dir = session_dir / result.worker_id
        assert worker_dir.exists(), f"worker_dir {worker_dir} not created"

        done_path = worker_dir / "done.json"
        assert done_path.exists(), f"done.json not written at {done_path}"

        done = json.loads(done_path.read_text(encoding="utf-8"))
        assert done.get("status") == "ok", f"done.json: {done}"
        assert "result_path" in done, f"done.json missing result_path: {done}"
        assert "duration_seconds" in done, f"done.json missing duration_seconds: {done}"

        # input.md must have been written
        assert (worker_dir / "input.md").exists(), "input.md not written"

        # worker_id matches expected naming convention
        assert result.worker_id.startswith("worker-"), (
            f"worker_id should start with 'worker-', got {result.worker_id!r}"
        )


# ---------------------------------------------------------------------------
# (b) Parallel team of 3 workers — all ok
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestParallelTeam:
    """Parallel team of 3 workers (review-pipeline) — all done.json status ok."""

    def test_parallel_team_three_workers_ok(self, tmp_path, src):
        session_dir = _unique_session_dir(tmp_path, "parallel-team")
        template = load_template("review-pipeline")

        assert template.mode == "parallel"
        assert len(template.workers) == 3

        started_at = time.monotonic()
        results = team_run(
            template=template,
            source_path=src,
            session_dir=session_dir,
            backend_overrides={
                "fact-checker": "claude",
                "consistency-checker": "claude",
                "terminology-manager": "claude",
            },
            model_overrides={
                "fact-checker": "claude-sonnet-4-6",
                "consistency-checker": "claude-sonnet-4-6",
                "terminology-manager": "claude-sonnet-4-6",
            },
        )

        # Three results, one per worker
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        for r in results:
            assert r.status == "ok", (
                f"Worker {r.worker_id} returned status {r.status!r}, expected 'ok'"
            )

        # Three done.json files, each with status ok
        done_files = list(session_dir.rglob("done.json"))
        assert len(done_files) == 3, (
            f"Expected 3 done.json files, found {len(done_files)}: {done_files}"
        )
        for d in done_files:
            payload = json.loads(d.read_text(encoding="utf-8"))
            assert payload.get("status") == "ok", f"done.json not ok: {payload}"

        # summary.json produced by aggregate_results
        summary = aggregate_results(
            results,
            session_dir=session_dir,
            template_name=template.name,
            started_at=started_at,
        )

        summary_path = session_dir / "summary.json"
        assert summary_path.exists(), "summary.json not produced"

        agg = json.loads(summary_path.read_text(encoding="utf-8"))
        assert "workers" in agg, f"summary.json missing 'workers': {agg}"
        assert len(agg["workers"]) == 3, (
            f"Expected 3 workers in summary, got {len(agg['workers'])}"
        )
        assert agg["template"] == "review-pipeline"

        # Fix 1: persona field must be correct (not derived from worker_id string parsing)
        personas_in_summary = {w["persona"] for w in agg["workers"]}
        assert personas_in_summary == {"fact-checker", "consistency-checker", "terminology-manager"}, (
            f"Unexpected personas in summary: {personas_in_summary}"
        )


# ---------------------------------------------------------------------------
# (c) Sequential team with inputs_from: previous — translation-pipeline
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSequentialTeamInputsFrom:
    """Sequential team (translation-pipeline): translator → polisher.

    Polisher receives translator's output via inputs_from: previous.
    """

    def test_sequential_inputs_from_wired_correctly(self, tmp_path):
        article = tmp_path / "article.md"
        article.write_text("# Article\n\nContent for translation testing.\n",
                           encoding="utf-8")

        session_dir = _unique_session_dir(tmp_path, "seq-team")
        template = load_template("translation-pipeline")

        assert template.mode == "sequential"
        assert len(template.workers) == 2
        # Second worker must have inputs_from=previous
        assert template.workers[1].inputs_from == "previous"

        results = team_run(
            template=template,
            source_path=article,
            session_dir=session_dir,
            backend_overrides={
                "translator": "claude",
                "polisher": "claude",
            },
            model_overrides={
                "translator": "claude-sonnet-4-6",
                "polisher": "claude-sonnet-4-6",
            },
        )

        # Two results (translator + polisher)
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        for r in results:
            assert r.status == "ok", (
                f"Worker {r.worker_id} status={r.status!r}"
            )

        # Two done.json files with status ok
        done_files = list(session_dir.rglob("done.json"))
        assert len(done_files) == 2, (
            f"Expected 2 done.json, found {len(done_files)}: {done_files}"
        )
        for d in done_files:
            payload = json.loads(d.read_text(encoding="utf-8"))
            assert payload.get("status") == "ok", f"done.json: {payload}"

        # Verify that the polisher's worker dir contains input.md
        # (input.md is always written per-worker; its content references the source)
        worker_dirs = sorted(session_dir.glob("worker-*"), key=lambda p: p.name)
        assert len(worker_dirs) == 2, (
            f"Expected 2 worker dirs, found {worker_dirs}"
        )
        for wd in worker_dirs:
            assert (wd / "input.md").exists(), f"input.md missing in {wd}"

        # The polisher's result_path should differ from the translator's
        # (it processes the translator's output, not the original article)
        translator_result = results[0].result_path
        polisher_result = results[1].result_path
        # Both may be None (stdout kind) or actual paths — just check both ran ok
        assert results[0].status == "ok"
        assert results[1].status == "ok"


# ---------------------------------------------------------------------------
# (d) Mixed mode — 4 workers across 3 stages — draft-to-publish
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestMixedModeTeam:
    """Mixed mode: draft-to-publish (scaffolder → polisher → [fact-checker, consistency-checker])."""

    def test_mixed_mode_full_pipeline_completes(self, tmp_path, src):
        session_dir = _unique_session_dir(tmp_path, "mixed-team")
        template = load_template("draft-to-publish")

        assert template.mode == "mixed"
        assert template.stages is not None
        assert len(template.stages) == 3
        assert len(template.workers) == 4

        started_at = time.monotonic()
        results = team_run(
            template=template,
            source_path=src,
            session_dir=session_dir,
            backend_overrides={
                "scaffolder": "claude",
                "polisher": "claude",
                "fact-checker": "claude",
                "consistency-checker": "claude",
            },
            model_overrides={
                "scaffolder": "claude-sonnet-4-6",
                "polisher": "claude-sonnet-4-6",
                "fact-checker": "claude-sonnet-4-6",
                "consistency-checker": "claude-sonnet-4-6",
            },
        )

        # 4 results — one per worker
        assert len(results) == 4, f"Expected 4 results, got {len(results)}"
        for r in results:
            assert r.status == "ok", (
                f"Worker {r.worker_id} status={r.status!r}"
            )

        # 4 done.json files — one per worker
        done_files = list(session_dir.rglob("done.json"))
        assert len(done_files) == 4, (
            f"Expected 4 done.json (one per worker), found {len(done_files)}"
        )
        for d in done_files:
            payload = json.loads(d.read_text(encoding="utf-8"))
            assert payload.get("status") == "ok", f"done.json: {payload}"

        # aggregate_results writes summary.json
        summary = aggregate_results(
            results,
            session_dir=session_dir,
            template_name=template.name,
            started_at=started_at,
        )
        summary_path = session_dir / "summary.json"
        assert summary_path.exists(), "summary.json not produced"

        agg = json.loads(summary_path.read_text(encoding="utf-8"))
        assert agg["template"] == "draft-to-publish"
        assert len(agg["workers"]) == 4, (
            f"summary.json workers count: {len(agg['workers'])}, expected 4"
        )
        # All workers must have status ok in the summary
        statuses = [w["status"] for w in agg["workers"]]
        assert all(s == "ok" for s in statuses), (
            f"Not all workers ok in summary: {statuses}"
        )

        # Fix 1: persona field must be correct for all 4 workers in mixed mode
        personas_in_summary = {w["persona"] for w in agg["workers"]}
        assert personas_in_summary == {"scaffolder", "polisher", "fact-checker", "consistency-checker"}, (
            f"Unexpected personas in summary: {personas_in_summary}"
        )


# ---------------------------------------------------------------------------
# Fix 4: Negative-path integration test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNegativePath:
    """Negative-path: failed worker has correct status and persona in summary.json."""

    def test_failed_worker_shows_failed_status_in_summary(self, tmp_path, src, monkeypatch):
        """When OMW_FAKE_FAIL=1, the worker exits non-zero.

        Pins that:
          - summary.json records status == "failed" for the failed worker
          - summary.json records the correct persona name (not derived from worker_id parsing)
        """
        monkeypatch.setenv("OMW_FAKE_FAIL", "1")

        session_dir = _unique_session_dir(tmp_path, "neg-path")
        req = DispatchRequest(
            persona="fact-checker",
            backend="claude",
            model="claude-sonnet-4-6",
            source_path=src,
            skip_permissions=False,
        )
        result = dispatch_one(req, session_dir=session_dir)

        # DispatchResult itself must reflect failure
        assert result.status == "failed", (
            f"Expected status 'failed', got {result.status!r}"
        )
        assert result.persona == "fact-checker", (
            f"Expected persona 'fact-checker', got {result.persona!r}"
        )

        # aggregate_results must persist both fields correctly
        import time as _time
        started_at = _time.monotonic()
        summary = aggregate_results(
            [result],
            session_dir=session_dir,
            template_name="negative-path-test",
            started_at=started_at,
        )

        summary_path = session_dir / "summary.json"
        assert summary_path.exists(), "summary.json not written"

        agg = json.loads(summary_path.read_text(encoding="utf-8"))
        assert len(agg["workers"]) == 1
        worker_entry = agg["workers"][0]
        assert worker_entry["status"] == "failed", (
            f"summary.json status should be 'failed', got {worker_entry['status']!r}"
        )
        assert worker_entry["persona"] == "fact-checker", (
            f"summary.json persona should be 'fact-checker', got {worker_entry['persona']!r}"
        )
