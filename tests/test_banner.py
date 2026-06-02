import io
import re

from scripts import banner


def test_version_is_semver_and_matches_plugin_json():
    v = banner.version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", v), v
    import json, pathlib
    pj = json.loads((pathlib.Path(banner.__file__).resolve().parents[1]
                     / ".claude-plugin" / "plugin.json").read_text())
    assert v == pj["version"]


def test_version_plugin_json_fallback(monkeypatch):
    import importlib.metadata as m
    def boom(_name):
        raise m.PackageNotFoundError("oh-my-wiki")
    monkeypatch.setattr(m, "version", boom)
    v = banner.version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", v)  # came from plugin.json


def test_banner_text_has_wordmark_footer_and_version():
    t = banner.banner_text()
    assert "|___/" in t                                   # figlet wordmark fragment
    assert "github.com/dandacompany/oh-my-wiki" in t
    assert "https://oh-my-wiki.com" in t
    assert "dante@dante-labs.com" in t
    assert "Dante Labs" in t
    assert banner.version() in t
    assert "\x1b[" not in t                               # no ANSI when color off (default)


def test_should_animate_guard_matrix(monkeypatch):
    class TTY(io.StringIO):
        def isatty(self): return True
    class NoTTY(io.StringIO):
        def isatty(self): return False
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("OMW_NO_BANNER", raising=False)
    assert banner.should_animate(TTY()) is True
    assert banner.should_animate(NoTTY()) is False
    for var in ("NO_COLOR", "CI", "OMW_NO_BANNER"):
        monkeypatch.setenv(var, "1")
        assert banner.should_animate(TTY()) is False
        monkeypatch.delenv(var)


def test_render_static_no_escape_no_sleep():
    calls = []
    out = io.StringIO()
    banner.render(animate=False, stream=out, sleep=lambda *_: calls.append(1))
    s = out.getvalue()
    assert "|___/" in s and banner.version() in s
    assert "\r" not in s and "\x1b[" not in s
    assert calls == []                                    # no animation → no sleep


def test_render_animated_uses_spinner_frames_bounded():
    frames = []
    out = io.StringIO()
    banner.render(animate=True, stream=out, sleep=lambda *_: frames.append(1), color=True)
    s = out.getvalue()
    assert any(ch in s for ch in banner.SPINNER)          # spinner frames emitted
    assert "\r" in s                                      # single-line redraw
    assert 0 < len(frames) < 200                          # bounded, no infinite loop
