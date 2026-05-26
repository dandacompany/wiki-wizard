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


def test_marketplace_json_has_required_fields():
    p = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    assert p.exists(), "marketplace.json must exist at .claude-plugin/marketplace.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for key in ("name", "description", "plugins"):
        assert key in data, f"marketplace.json missing required key: {key}"
    assert data["name"].endswith("-marketplace")
    assert isinstance(data["plugins"], list)
    assert len(data["plugins"]) >= 1


def test_marketplace_json_lists_oh_my_wiki_plugin():
    p = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    plugin_names = [p["name"] for p in data["plugins"]]
    assert "oh-my-wiki" in plugin_names


def test_marketplace_plugin_manifest_paths_resolve():
    p = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for entry in data["plugins"]:
        manifest_path = REPO_ROOT / entry["manifest"].lstrip("./")
        assert manifest_path.exists(), f"manifest path {manifest_path} not found"
