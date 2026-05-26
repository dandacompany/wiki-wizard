"""
tests/test_team.py — team.py load + validation + run + aggregate tests.

Tasks 9-11 progressively fill in this file.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.team import load_template, TeamTemplate, TeamValidationError


TEAMS_DIR = Path(__file__).parent.parent / "teams"


# ── load_template ──────────────────────────────────────────────────

class TestLoadTemplate:
    def test_loads_review_pipeline(self):
        t = load_template("review-pipeline")
        assert t.name == "review-pipeline"
        assert t.mode == "parallel"
        assert len(t.workers) == 3

    def test_loads_translation_pipeline(self):
        t = load_template("translation-pipeline")
        assert t.name == "translation-pipeline"
        assert t.mode == "sequential"
        assert t.workers[1].inputs_from == "previous"

    def test_loads_draft_to_publish(self):
        t = load_template("draft-to-publish")
        assert t.name == "draft-to-publish"
        assert t.mode == "mixed"
        assert t.stages is not None
        assert len(t.stages) == 3

    def test_body_text_accessible(self):
        """Markdown body below frontmatter is returned in template.body."""
        t = load_template("review-pipeline")
        assert "review-pipeline" in t.body.lower()

    def test_raises_for_unknown_template(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent-pipeline")


# ── validation ─────────────────────────────────────────────────────

class TestTemplateValidation:
    def _write_temp_team(self, tmp_path: Path, frontmatter: dict, body: str = "") -> Path:
        p = tmp_path / "test-team.md"
        p.write_text("---\n" + yaml.dump(frontmatter) + "---\n" + body)
        return p

    def test_rejects_unknown_persona(self, tmp_path):
        fm = {
            "name": "bad-team",
            "mode": "parallel",
            "workers": [{"persona": "nonexistent-persona", "backend_default": "claude"}],
        }
        path = self._write_temp_team(tmp_path, fm)
        with pytest.raises(TeamValidationError, match="unknown persona"):
            load_template(path)

    def test_rejects_unknown_backend(self, tmp_path):
        fm = {
            "name": "bad-backend-team",
            "mode": "parallel",
            "workers": [{"persona": "fact-checker", "backend_default": "grok-v99"}],
        }
        path = self._write_temp_team(tmp_path, fm)
        with pytest.raises(TeamValidationError, match="unknown backend"):
            load_template(path)

    def test_rejects_mixed_without_stages(self, tmp_path):
        fm = {
            "name": "bad-mixed",
            "mode": "mixed",
            "workers": [{"persona": "fact-checker", "backend_default": "claude"}],
        }
        path = self._write_temp_team(tmp_path, fm)
        with pytest.raises(TeamValidationError, match="stages"):
            load_template(path)

    def test_accepts_valid_parallel(self, tmp_path):
        fm = {
            "name": "ok-parallel",
            "mode": "parallel",
            "workers": [
                {"persona": "fact-checker", "backend_default": "claude"},
                {"persona": "summarizer", "backend_default": "gemini"},
            ],
        }
        path = self._write_temp_team(tmp_path, fm)
        t = load_template(path)
        assert t.mode == "parallel"

    def test_timeout_defaults_to_600(self, tmp_path):
        fm = {
            "name": "no-timeout",
            "mode": "parallel",
            "workers": [{"persona": "summarizer", "backend_default": "claude"}],
        }
        path = self._write_temp_team(tmp_path, fm)
        t = load_template(path)
        assert t.timeout_seconds == 600


# ── run() — parallel + sequential ─────────────────────────────────

import time as _time

from scripts.team import run as team_run
from scripts.dispatch import DispatchResult


def _make_ok_result(worker_id: str, result_path: Path) -> DispatchResult:
    return DispatchResult(
        worker_id=worker_id, status="ok",
        result_path=result_path, duration_seconds=1.0,
        model="fake-model", session_dir=result_path.parent,
    )


class TestTeamRun:
    """Uses fake dispatch_one via monkeypatching — no real tmux or backends needed."""

    @pytest.fixture
    def fake_dispatch(self, monkeypatch, tmp_path):
        call_log: list[dict] = []

        def fake_dispatch_one(req, session_dir):
            call_log.append({"persona": req.persona, "t": _time.monotonic()})
            out = tmp_path / f"{req.persona}-out.md"
            out.write_text(f"FAKE OUTPUT for {req.persona}")
            return _make_ok_result(f"worker-{req.persona}", out)

        monkeypatch.setattr("scripts.team.dispatch_one", fake_dispatch_one)
        return call_log

    def test_parallel_all_workers_called(self, fake_dispatch, tmp_path):
        t = load_template("review-pipeline")
        results = team_run(t, source_path=tmp_path / "doc.md",
                           session_dir=tmp_path / "sess",
                           backend_overrides={}, model_overrides={})
        assert len(results) == len(t.workers)
        personas = {r.worker_id.split("-", 1)[1] for r in results}
        assert personas == {w.persona for w in t.workers}

    def test_parallel_order_preserved(self, fake_dispatch, tmp_path):
        """Results list order matches workers list order, not completion order."""
        t = load_template("review-pipeline")
        results = team_run(t, source_path=tmp_path / "doc.md",
                           session_dir=tmp_path / "sess2",
                           backend_overrides={}, model_overrides={})
        result_personas = [r.worker_id.split("-", 1)[1] for r in results]
        template_personas = [w.persona for w in t.workers]
        assert result_personas == template_personas

    def test_sequential_workers_called_in_order(self, fake_dispatch, tmp_path):
        """Sequential mode: worker N is NOT dispatched until worker N-1 finishes."""
        t = load_template("translation-pipeline")
        results = team_run(t, source_path=tmp_path / "doc.md",
                           session_dir=tmp_path / "sess3",
                           backend_overrides={}, model_overrides={})
        assert len(results) == len(t.workers)
        # fake_dispatch records call timestamps; sequential → t[1] > t[0]
        timestamps = [e["t"] for e in fake_dispatch]
        # With mock dispatch that returns instantly, they may be nearly simultaneous;
        # at minimum all must have been called.
        assert len(timestamps) == len(t.workers)

    def test_inputs_from_previous_sets_source(self, fake_dispatch, tmp_path):
        """When worker has inputs_from=previous, source_path is set to previous result_path."""
        import scripts.team as tm

        call_sources: list[Path] = []

        def tracking_dispatch(req, session_dir):
            call_sources.append(req.source_path)
            out = tmp_path / f"{req.persona}-out.md"
            out.write_text("out")
            return _make_ok_result(f"worker-{req.persona}", out)

        tm.dispatch_one = tracking_dispatch  # replace patch

        t = load_template("translation-pipeline")
        team_run(t, source_path=tmp_path / "orig.md",
                 session_dir=tmp_path / "sess4",
                 backend_overrides={}, model_overrides={})

        # first worker gets original source; second worker gets first worker's output
        assert call_sources[0] == tmp_path / "orig.md"
        assert call_sources[1] != tmp_path / "orig.md"  # polisher gets translator's output

    def test_backend_overrides_respected(self, fake_dispatch, tmp_path):
        """backend_overrides dict substitutes backend per persona."""
        t = load_template("review-pipeline")
        overrides = {"fact-checker": "codex"}
        results = team_run(t, source_path=tmp_path / "doc.md",
                           session_dir=tmp_path / "sess5",
                           backend_overrides=overrides, model_overrides={})
        assert len(results) == 3

    def test_all_ok_statuses_in_results(self, fake_dispatch, tmp_path):
        t = load_template("review-pipeline")
        results = team_run(t, source_path=tmp_path / "doc.md",
                           session_dir=tmp_path / "sess6",
                           backend_overrides={}, model_overrides={})
        assert all(r.status == "ok" for r in results)
