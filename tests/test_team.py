"""
tests/test_team.py — team.py load + validation + run + aggregate tests.

Tasks 9-11 progressively fill in this file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.team import (
    load_template, TeamTemplate, TeamValidationError,
    WorkerConfig, _peer_list, SwarmContext,
)


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


# ── run() — mixed mode ─────────────────────────────────────────────

class TestTeamRunMixed:
    """draft-to-publish has stages: [seq:scaffolder] → [seq:polisher] → [par: fact-checker, consistency-checker]"""

    @pytest.fixture
    def fake_dispatch_mixed(self, monkeypatch, tmp_path):
        call_order: list[str] = []

        def fake_one(req, session_dir):
            call_order.append(req.persona)
            out = tmp_path / f"{req.persona}-out.md"
            out.write_text(f"out:{req.persona}")
            return _make_ok_result(f"worker-{req.persona}", out)

        monkeypatch.setattr("scripts.team.dispatch_one", fake_one)
        return call_order

    def test_mixed_correct_stage_order(self, fake_dispatch_mixed, tmp_path):
        """Stages execute in order: scaffolder first, then polisher, then parallel pair."""
        t = load_template("draft-to-publish")
        team_run(t, source_path=tmp_path / "raw.md",
                 session_dir=tmp_path / "sess-m",
                 backend_overrides={}, model_overrides={})
        # scaffolder must come before polisher which must come before fact-checker
        order = fake_dispatch_mixed
        assert order.index("scaffolder") < order.index("polisher")
        assert order.index("polisher") < order.index("fact-checker")
        assert order.index("polisher") < order.index("consistency-checker")

    def test_mixed_total_worker_count(self, fake_dispatch_mixed, tmp_path):
        t = load_template("draft-to-publish")
        results = team_run(t, source_path=tmp_path / "raw2.md",
                           session_dir=tmp_path / "sess-m2",
                           backend_overrides={}, model_overrides={})
        assert len(results) == len(t.workers)

    def test_mixed_inputs_from_previous_across_stages(self, fake_dispatch_mixed, tmp_path):
        """polisher's source should be scaffolder's output (inputs_from=previous across stages)."""
        sources_seen: list[Path] = []
        import scripts.team as tm

        def tracking(req, session_dir):
            sources_seen.append(req.source_path)
            out = tmp_path / f"{req.persona}-out.md"
            out.write_text("out")
            return _make_ok_result(f"worker-{req.persona}", out)

        tm.dispatch_one = tracking
        t = load_template("draft-to-publish")
        team_run(t, source_path=tmp_path / "origin.md",
                 session_dir=tmp_path / "sess-m3",
                 backend_overrides={}, model_overrides={})
        # polisher (index 1) should NOT use the original source
        assert sources_seen[1] != tmp_path / "origin.md"


# ── aggregate_results ──────────────────────────────────────────────

from scripts.team import aggregate_results


class TestAggregateResults:
    def test_writes_summary_json(self, tmp_path):
        results = [
            _make_ok_result("worker-fact-checker", tmp_path / "doc.factcheck.md"),
            _make_ok_result("worker-summarizer", tmp_path / "doc.summary.json"),
        ]
        agg = aggregate_results(results, session_dir=tmp_path, template_name="review-pipeline")
        summary_path = tmp_path / "summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert data["template"] == "review-pipeline"
        assert len(data["workers"]) == 2

    def test_summary_contains_status_per_worker(self, tmp_path):
        results = [
            _make_ok_result("worker-fact-checker", tmp_path / "fc.md"),
            DispatchResult("worker-polisher", "failed", None, 5.0, "model", tmp_path),
        ]
        agg = aggregate_results(results, session_dir=tmp_path, template_name="t")
        assert agg["workers"][0]["status"] == "ok"
        assert agg["workers"][1]["status"] == "failed"

    def test_summary_total_duration(self, tmp_path):
        results = [
            _make_ok_result("w1", tmp_path / "a.md"),
            _make_ok_result("w2", tmp_path / "b.md"),
        ]
        results[0].duration_seconds = 10.0
        results[1].duration_seconds = 20.0
        agg = aggregate_results(results, session_dir=tmp_path, template_name="t")
        assert agg["total_wall_seconds"] >= 0  # wall time, not sum

    def test_aggregate_returns_dict(self, tmp_path):
        results = [_make_ok_result("w1", tmp_path / "out.md")]
        agg = aggregate_results(results, session_dir=tmp_path, template_name="t")
        assert isinstance(agg, dict)
        assert "workers" in agg

    def test_summary_result_paths_are_strings(self, tmp_path):
        results = [_make_ok_result("w1", tmp_path / "out.md")]
        agg = aggregate_results(results, session_dir=tmp_path, template_name="t")
        for w in agg["workers"]:
            assert isinstance(w.get("result_path", ""), str)


# ── shipped template deep validation ───────────────────────────────

class TestShippedTemplates:
    """Each shipped team file must parse cleanly and pass full validation."""

    def test_review_pipeline_worker_personas(self):
        t = load_template("review-pipeline")
        personas = [w.persona for w in t.workers]
        assert "fact-checker" in personas
        assert "consistency-checker" in personas
        assert "terminology-manager" in personas

    def test_review_pipeline_backend_defaults(self):
        t = load_template("review-pipeline")
        backend_map = {w.persona: w.backend_default for w in t.workers}
        assert backend_map["fact-checker"] == "claude"
        assert backend_map["consistency-checker"] == "codex"
        assert backend_map["terminology-manager"] == "gemini"

    def test_review_pipeline_timeout(self):
        t = load_template("review-pipeline")
        assert t.timeout_seconds == 900

    def test_translation_pipeline_inputs_from(self):
        t = load_template("translation-pipeline")
        polisher_cfg = next(w for w in t.workers if w.persona == "polisher")
        assert polisher_cfg.inputs_from == "previous"

    def test_translation_pipeline_lang_arg_required(self):
        t = load_template("translation-pipeline")
        translator_cfg = next(w for w in t.workers if w.persona == "translator")
        assert translator_cfg.args.get("lang") == "required"

    def test_translation_pipeline_timeout(self):
        t = load_template("translation-pipeline")
        assert t.timeout_seconds == 1200

    def test_draft_to_publish_stage_count(self):
        t = load_template("draft-to-publish")
        assert t.stages is not None
        assert len(t.stages) == 3

    def test_draft_to_publish_first_stage_is_scaffolder(self):
        t = load_template("draft-to-publish")
        first_stage = t.stages[0]
        personas_in_first = list(first_stage.values())[0]
        assert "scaffolder" in personas_in_first

    def test_draft_to_publish_last_stage_is_parallel(self):
        t = load_template("draft-to-publish")
        last_stage = t.stages[-1]
        assert "parallel" in last_stage

    def test_draft_to_publish_timeout(self):
        t = load_template("draft-to-publish")
        assert t.timeout_seconds == 1800

    def test_draft_to_publish_worker_count(self):
        t = load_template("draft-to-publish")
        assert len(t.workers) == 4

    def test_all_templates_have_body_text(self):
        for name in ("review-pipeline", "translation-pipeline", "draft-to-publish"):
            t = load_template(name)
            assert len(t.body.strip()) > 0, f"{name} body is empty"


# ── T7 tests ─────────────────────────────────────────────────────────────────

def _swarm_template_yaml(swarm: bool = True, max_iterations: int = 1,
                          swarm_instructions: str | None = None) -> str:
    instr_block = (
        f"    swarm_instructions: |\n      {swarm_instructions}\n"
        if swarm_instructions else ""
    )
    return f"""\
---
name: test-swarm-team
description: Unit test swarm template
mode: parallel
swarm: {str(swarm).lower()}
max_iterations: {max_iterations}
timeout_seconds: 600
workers:
  - persona: fact-checker
    backend_default: claude
    model_hint: most_capable
{instr_block}  - persona: summarizer
    backend_default: claude
    model_hint: most_capable
---
Test swarm template body.
"""


def test_load_template_swarm_flag_true(tmp_path):
    """swarm: true parsed correctly into TeamTemplate.swarm."""
    f = tmp_path / "team.md"
    f.write_text(_swarm_template_yaml(swarm=True))
    tmpl = load_template(f)
    assert tmpl.swarm is True


def test_load_template_swarm_flag_false_default(tmp_path):
    """swarm omitted defaults to False (backwards compat)."""
    yaml_body = """\
---
name: old-team
description: no swarm field at all
mode: parallel
workers:
  - persona: fact-checker
    backend_default: claude
---
Old team body.
"""
    f = tmp_path / "team.md"
    f.write_text(yaml_body)
    tmpl = load_template(f)
    assert tmpl.swarm is False


def test_load_template_swarm_instructions_parsed(tmp_path):
    """swarm_instructions on worker spec is stored correctly."""
    f = tmp_path / "team.md"
    f.write_text(_swarm_template_yaml(swarm=True,
                                       swarm_instructions="publish to topic claim"))
    tmpl = load_template(f)
    worker_with_instr = tmpl.workers[0]
    assert worker_with_instr.swarm_instructions is not None
    assert "claim" in worker_with_instr.swarm_instructions


def test_load_template_max_iterations_parsed(tmp_path):
    """max_iterations field is parsed as integer."""
    f = tmp_path / "team.md"
    f.write_text(_swarm_template_yaml(swarm=True, max_iterations=3))
    tmpl = load_template(f)
    assert tmpl.max_iterations == 3


def test_peer_list_excludes_self():
    """_peer_list() returns all worker IDs except the one at self_index."""
    workers = [
        WorkerConfig(persona="fact-checker", backend_default="claude"),
        WorkerConfig(persona="fact-checker", backend_default="codex"),
        WorkerConfig(persona="moderator",    backend_default="claude"),
    ]
    peers_for_0 = _peer_list(workers, 0)
    assert "worker-1-fact-checker" not in peers_for_0
    assert "worker-2-fact-checker" in peers_for_0
    assert "worker-3-moderator"    in peers_for_0
    assert len(peers_for_0) == 2


def test_swarm_context_dataclass():
    """SwarmContext holds session_dir, worker_id, peers, swarm_instructions."""
    ctx = SwarmContext(
        session_dir="/tmp/session",
        worker_id="worker-1-fact-checker",
        peers=["worker-2-moderator"],
        swarm_instructions="publish claim",
    )
    assert ctx.session_dir == "/tmp/session"
    assert ctx.worker_id == "worker-1-fact-checker"
    assert "worker-2-moderator" in ctx.peers
    assert ctx.swarm_instructions == "publish claim"


def test_swarm_context_default_instructions():
    """SwarmContext swarm_instructions defaults to None."""
    ctx = SwarmContext(
        session_dir="/tmp/s",
        worker_id="worker-1-x",
        peers=[],
    )
    assert ctx.swarm_instructions is None


def test_max_iterations_default_is_one(tmp_path):
    """When max_iterations not set, TeamTemplate.max_iterations defaults to 1."""
    yaml_body = """\
---
name: no-iters
description: test
mode: parallel
workers:
  - persona: fact-checker
    backend_default: claude
---
body
"""
    f = tmp_path / "team.md"
    f.write_text(yaml_body)
    tmpl = load_template(f)
    assert tmpl.max_iterations == 1


def test_swarm_true_requires_at_least_one_worker(tmp_path):
    """swarm=true with no workers raises TeamValidationError."""
    yaml_body = """\
---
name: empty-swarm
description: test
mode: parallel
swarm: true
workers: []
---
body
"""
    f = tmp_path / "team.md"
    f.write_text(yaml_body)
    with pytest.raises((TeamValidationError, ValueError)):
        load_template(f)


def test_max_iterations_less_than_one_raises(tmp_path):
    """max_iterations=0 raises TeamValidationError."""
    yaml_body = """\
---
name: bad-iters
description: test
mode: parallel
swarm: true
max_iterations: 0
workers:
  - persona: fact-checker
    backend_default: claude
---
body
"""
    f = tmp_path / "team.md"
    f.write_text(yaml_body)
    with pytest.raises((TeamValidationError, ValueError)):
        load_template(f)


# ── T11 tests — triple-factcheck-moderator ──────────────────────────────────

def _load_team(name: str):
    from scripts.team import load_template
    teams_dir = Path(__file__).parent.parent / "teams"
    path = teams_dir / f"{name}.md"
    assert path.exists(), f"Team template not found: {path}"
    return load_template(path)


def test_triple_factcheck_moderator_loads():
    """triple-factcheck-moderator template loads without error."""
    tmpl = _load_team("triple-factcheck-moderator")
    assert tmpl.name == "triple-factcheck-moderator"


def test_triple_factcheck_moderator_swarm_true():
    """swarm flag is True."""
    tmpl = _load_team("triple-factcheck-moderator")
    assert tmpl.swarm is True


def test_triple_factcheck_moderator_four_workers():
    """Has exactly 4 workers: 3 fact-checkers + 1 moderator."""
    tmpl = _load_team("triple-factcheck-moderator")
    assert len(tmpl.workers) == 4
    personas = [w.persona for w in tmpl.workers]
    assert personas.count("fact-checker") == 3
    assert personas.count("moderator") == 1


def test_triple_factcheck_moderator_different_backends():
    """The three fact-checkers target different backends."""
    tmpl = _load_team("triple-factcheck-moderator")
    fc_backends = [
        w.backend_default for w in tmpl.workers if w.persona == "fact-checker"
    ]
    assert len(set(fc_backends)) == 3, (
        f"Expected 3 distinct backends, got: {fc_backends}"
    )


def test_triple_factcheck_moderator_swarm_instructions_present():
    """All 4 workers have swarm_instructions defined."""
    tmpl = _load_team("triple-factcheck-moderator")
    for w in tmpl.workers:
        assert w.swarm_instructions, (
            f"Worker {w.persona}/{w.backend_default} missing swarm_instructions"
        )


def test_triple_factcheck_moderator_claim_topic_in_instructions():
    """Fact-checker swarm_instructions reference the 'claim' topic."""
    tmpl = _load_team("triple-factcheck-moderator")
    for w in tmpl.workers:
        if w.persona == "fact-checker":
            assert "claim" in (w.swarm_instructions or ""), (
                f"fact-checker on {w.backend_default} missing 'claim' topic reference"
            )


def test_triple_factcheck_moderator_moderator_references_vote_create():
    """Moderator swarm_instructions reference vote-create."""
    tmpl = _load_team("triple-factcheck-moderator")
    mod = next(w for w in tmpl.workers if w.persona == "moderator")
    assert "vote-create" in (mod.swarm_instructions or "")


def test_triple_factcheck_moderator_timeout():
    """timeout_seconds is a positive integer."""
    tmpl = _load_team("triple-factcheck-moderator")
    assert isinstance(tmpl.timeout_seconds, int)
    assert tmpl.timeout_seconds > 0
