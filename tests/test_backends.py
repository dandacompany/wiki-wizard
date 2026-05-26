"""Tests for scripts.backends — backend detection, model catalog, invocation builder."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts import backends


# ---------------------------------------------------------------------------
# BACKENDS table structure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["claude", "codex", "gemini", "opencode"])
def test_backends_table_has_required_keys(name):
    b = backends.BACKENDS[name]
    required = {
        "cli_name", "detect_cmd", "skip_perm_flag",
        "non_interactive_flag", "system_prompt_flag",
        "model_flag", "model_catalog_path",
    }
    assert required <= set(b.keys()), f"{name} missing keys: {required - set(b.keys())}"


@pytest.mark.parametrize("name", ["claude", "codex", "gemini", "opencode"])
def test_backends_detect_cmd_is_list(name):
    assert isinstance(backends.BACKENDS[name]["detect_cmd"], list)
    assert len(backends.BACKENDS[name]["detect_cmd"]) >= 1


# ---------------------------------------------------------------------------
# detect_available — mocking subprocess
# ---------------------------------------------------------------------------

def _make_completed(returncode=0, stdout="1.0.0", stderr=""):
    cp = MagicMock()
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


def test_detect_available_all_installed(monkeypatch):
    monkeypatch.setattr(
        backends.subprocess, "run",
        lambda cmd, **kw: _make_completed(returncode=0, stdout="2.0.0"),
    )
    result = backends.detect_available()
    assert set(result.keys()) == {"claude", "codex", "gemini", "opencode"}
    for name, info in result.items():
        assert info["installed"] is True, f"{name} should be installed"


def test_detect_available_none_installed(monkeypatch):
    monkeypatch.setattr(
        backends.subprocess, "run",
        lambda cmd, **kw: _make_completed(returncode=1, stdout="", stderr="not found"),
    )
    result = backends.detect_available()
    for name, info in result.items():
        assert info["installed"] is False, f"{name} should not be installed"


def test_detect_available_mixed(monkeypatch):
    installed = {"claude", "gemini"}

    def fake_run(cmd, **kw):
        cli = cmd[0]
        rc = 0 if any(cli == backends.BACKENDS[n]["cli_name"] for n in installed) else 1
        return _make_completed(returncode=rc, stdout="1.0.0" if rc == 0 else "")

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    result = backends.detect_available()
    assert result["claude"]["installed"] is True
    assert result["gemini"]["installed"] is True
    assert result["codex"]["installed"] is False
    assert result["opencode"]["installed"] is False


def test_detect_available_returns_version_string(monkeypatch):
    monkeypatch.setattr(
        backends.subprocess, "run",
        lambda cmd, **kw: _make_completed(returncode=0, stdout="claude 1.2.3\n"),
    )
    result = backends.detect_available()
    assert "1.2.3" in result["claude"]["version"] or result["claude"]["version"] != ""


def test_detect_available_handles_oserror(monkeypatch):
    def raise_oserror(cmd, **kw):
        raise OSError("No such file or directory")

    monkeypatch.setattr(backends.subprocess, "run", raise_oserror)
    result = backends.detect_available()
    for info in result.values():
        assert info["installed"] is False


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["claude", "codex", "gemini", "opencode"])
def test_list_models_returns_nonempty_list(name):
    models = backends.list_models(name, repo_root=PROJECT_ROOT)
    assert isinstance(models, list)
    assert len(models) >= 1, f"{name} catalog must have at least 1 model"


@pytest.mark.parametrize("name", ["claude", "codex", "gemini", "opencode"])
def test_list_models_each_has_required_keys(name):
    models = backends.list_models(name, repo_root=PROJECT_ROOT)
    for m in models:
        assert "id" in m, f"{name} model missing 'id'"
        assert "hint" in m, f"{name} model missing 'hint'"
        assert "description" in m, f"{name} model missing 'description'"


@pytest.mark.parametrize("name", ["claude", "codex", "gemini", "opencode"])
def test_list_models_hints_are_valid(name):
    valid_hints = {"fast", "standard", "most_capable"}
    models = backends.list_models(name, repo_root=PROJECT_ROOT)
    for m in models:
        assert m["hint"] in valid_hints, (
            f"{name} model {m['id']!r} has invalid hint {m['hint']!r}"
        )


def test_list_models_filter_by_hint(monkeypatch, tmp_path):
    catalog = [
        {"id": "fast-model", "hint": "fast", "description": "Quick"},
        {"id": "std-model", "hint": "standard", "description": "Standard"},
        {"id": "cap-model", "hint": "most_capable", "description": "Capable"},
    ]
    (tmp_path / "backends").mkdir()
    (tmp_path / "backends" / "claude.json").write_text(
        __import__("json").dumps(catalog), encoding="utf-8"
    )
    fast_only = backends.list_models("claude", repo_root=tmp_path, hint_filter="fast")
    assert len(fast_only) == 1
    assert fast_only[0]["id"] == "fast-model"


def test_list_models_bad_backend_raises():
    with pytest.raises(backends.BackendError, match="unknown backend"):
        backends.list_models("noexist", repo_root=PROJECT_ROOT)
