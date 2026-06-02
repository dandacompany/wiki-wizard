import sys
from pathlib import Path

from scripts.viewers import base


def test_quote_value_encodes_space_slash_korean():
    assert base.quote_value("a b") == "a%20b"
    assert base.quote_value("wiki/entities/x.md") == "wiki%2Fentities%2Fx.md"
    assert base.quote_value("안드레이") == "%EC%95%88%EB%93%9C%EB%A0%88%EC%9D%B4"


def test_opener_argv_per_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert base.opener_argv() == ["open"]
    monkeypatch.setattr(sys, "platform", "linux")
    assert base.opener_argv() == ["xdg-open"]
    monkeypatch.setattr(sys, "platform", "win32")
    assert base.opener_argv()[:3] == ["cmd", "/c", "start"]


def test_launch_invokes_runner_with_uri_and_returns_it():
    calls = []
    out = base.launch("obsidian://open?vault=demo", runner=lambda argv, **kw: calls.append(argv))
    assert out == "obsidian://open?vault=demo"
    assert calls and calls[0][-1] == "obsidian://open?vault=demo"


def test_vaultref_fields():
    v = base.VaultRef(root=Path("/tmp/demo"), name="demo")
    assert v.root == Path("/tmp/demo") and v.name == "demo"
