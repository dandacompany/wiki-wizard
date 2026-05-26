"""Validate Claude Code plugin manifests."""
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_plugin_json_has_required_top_level_fields():
    p = REPO_ROOT / ".claude-plugin" / "plugin.json"
    assert p.exists(), "plugin.json must exist at .claude-plugin/plugin.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for key in ("name", "version", "description", "author", "license",
                "homepage", "trigger_keywords", "ops",
                "skill_path", "commands_path", "scripts_path"):
        assert key in data, f"plugin.json missing required key: {key}"
    assert data["name"] == "oh-my-wiki"
    assert data["version"].startswith("2."), f"v2.x expected, got {data['version']!r}"
    assert data["license"] == "MIT"
    assert "oh-my-wiki" in data["homepage"]


def test_plugin_json_ops_resolve_to_command_files():
    """Every op listed in plugin.json must have a corresponding commands/<op>.md."""
    p = REPO_ROOT / ".claude-plugin" / "plugin.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    commands_dir = REPO_ROOT / data["commands_path"].lstrip("./")
    for op in data["ops"]:
        cmd_path = commands_dir / f"{op}.md"
        assert cmd_path.exists(), f"op {op!r} declared but {cmd_path} missing"


def test_plugin_json_trigger_keywords_non_empty():
    p = REPO_ROOT / ".claude-plugin" / "plugin.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(data["trigger_keywords"], list)
    assert len(data["trigger_keywords"]) >= 4
    has_en = any("wiki" in t.lower() or "omw" in t.lower() for t in data["trigger_keywords"])
    has_ko = any("위키" in t for t in data["trigger_keywords"])
    assert has_en and has_ko, "need both EN and KO triggers"
