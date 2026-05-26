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
