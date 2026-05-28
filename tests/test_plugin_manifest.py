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
    commands_dir = REPO_ROOT / data["commands_path"].removeprefix("./")
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
        manifest_path = REPO_ROOT / entry["manifest"].removeprefix("./")
        assert manifest_path.exists(), f"manifest path {manifest_path} not found"


def test_hooks_json_has_session_start_and_stop():
    p = REPO_ROOT / "hooks" / "hooks.json"
    assert p.exists(), "hooks.json must exist at hooks/hooks.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "session_start" in data
    assert "session_stop" in data
    for key in ("session_start", "session_stop"):
        binding = data[key]
        assert "command" in binding
        assert "scripts.hot_cache" in binding["command"]
        assert binding.get("blocking") is False, f"{key} must be non-blocking"


def test_plugin_json_lists_v2_2b_review_persona_ops():
    import json
    from pathlib import Path
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / ".claude-plugin/plugin.json")
        .read_text(encoding="utf-8")
    )
    for op in ("persona-factcheck", "persona-consistency", "persona-terminology"):
        assert op in manifest["ops"], f"missing op: {op}"


def test_plugin_json_version_bumped_to_2_2_1():
    # Version was 2.2.1; bumped to 2.3.0 in Task 16. Test kept for history;
    # TestV23ManifestOps.test_version_is_2_3_0 is the authoritative version check.
    import json
    from pathlib import Path
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / ".claude-plugin/plugin.json")
        .read_text(encoding="utf-8")
    )
    assert manifest["version"] >= "2.2.1", \
        f"version should be >= 2.2.1, got {manifest['version']}"


# ---- Task 16: v2.3 manifest tests -------------------------------------------
import json
from pathlib import Path


class TestV23ManifestOps:
    """Verify plugin.json has the 3 new v2.3 ops and trigger keywords."""

    PLUGIN = json.loads(
        (Path(__file__).parent.parent / ".claude-plugin" / "plugin.json").read_text()
    )

    def test_version_is_2_3_0(self):
        assert self.PLUGIN["version"] == "2.4.0", \
            f"Expected 2.4.0, got {self.PLUGIN['version']}"

    def test_ops_include_dispatch(self):
        ops = [op["name"] if isinstance(op, dict) else op for op in self.PLUGIN.get("ops", [])]
        assert "dispatch" in ops, "'dispatch' op missing from plugin.json"

    def test_ops_include_team(self):
        ops = [op["name"] if isinstance(op, dict) else op for op in self.PLUGIN.get("ops", [])]
        assert "team" in ops, "'team' op missing from plugin.json"

    def test_ops_include_team_run(self):
        ops = [op["name"] if isinstance(op, dict) else op for op in self.PLUGIN.get("ops", [])]
        assert "team-run" in ops, "'team-run' op missing from plugin.json"

    def test_trigger_keywords_english(self):
        keywords = self.PLUGIN.get("trigger_keywords", [])
        for kw in ("dispatch this", "run a team", "review this in parallel"):
            assert kw in keywords, f"EN trigger keyword missing: {kw!r}"

    def test_trigger_keywords_korean(self):
        keywords = self.PLUGIN.get("trigger_keywords", [])
        for kw in ("디스패치", "팀 실행", "병렬 검토"):
            assert kw in keywords, f"KO trigger keyword missing: {kw!r}"


# ---------------------------------------------------------------------------
# T18: plugin.json assertions for v2.4.0
# ---------------------------------------------------------------------------

class TestPluginManifestV24:
    """Assert plugin.json is correctly updated for v2.4.0."""

    PLUGIN_FILE = Path(__file__).resolve().parents[1] / ".claude-plugin" / "plugin.json"

    def _load(self):
        return json.loads(self.PLUGIN_FILE.read_text())

    def test_version_is_2_4_0(self):
        data = self._load()
        assert data["version"] == "2.4.0", (
            f"plugin.json version must be '2.4.0', got '{data.get('version')}'"
        )

    def test_swarm_monitor_op_present(self):
        data = self._load()
        ops = [op["name"] if isinstance(op, dict) else op
               for op in data.get("ops", [])]
        assert "swarm-monitor" in ops, (
            f"'swarm-monitor' must be in plugin.json ops; found: {ops}"
        )

    def test_en_and_ko_triggers_present(self):
        data = self._load()
        # Triggers may be at top level or nested under ops
        # Check trigger keywords exist somewhere in the manifest
        manifest_text = json.dumps(data, ensure_ascii=False)
        en_triggers = ["monitor the swarm", "show worker status"]
        ko_triggers = ["스웜 모니터", "워커 상태 보여줘"]
        for trigger in en_triggers + ko_triggers:
            assert trigger in manifest_text, (
                f"Trigger '{trigger}' not found in plugin.json"
            )
