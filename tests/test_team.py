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
