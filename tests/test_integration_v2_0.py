"""End-to-end v2.0 scenario."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import adapters, hot_cache, ingest, registry, reindex, wiki_lint

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fresh_db(tmp_db):
    registry.init_db(tmp_db)
    return tmp_db


def test_plugin_marketplace_pair_loads_without_error(fresh_db):
    """Smoke: plugin.json + marketplace.json parse and reference real files."""
    plugin = json.loads((REPO_ROOT / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((REPO_ROOT / ".claude-plugin/marketplace.json").read_text())
    assert plugin["name"] == "oh-my-wiki"
    assert marketplace["name"].endswith("-marketplace")
    for op in plugin["ops"]:
        assert (REPO_ROOT / "commands" / f"{op}.md").exists()


def test_personal_mode_setup_then_hot_cache_then_lint(fresh_db, tmp_path):
    db = fresh_db
    root = tmp_path / "my-personal"
    adapters.get_adapter("markdown").init_vault(root, "personal")
    vault = registry.add_vault(
        db, name="me", path=root, type_="markdown", mode="personal"
    )
    registry.set_active(db, "me")
    reindex.full(db, vault_id=vault["id"])

    for sub in ("journal", "goals", "people", "health"):
        assert (root / sub).is_dir()

    path = hot_cache.write(db)
    assert path == root / "hot.md"
    assert "## Active vaults" in path.read_text(encoding="utf-8")


def test_wiki_vault_v2_lint_returns_all_8_categories(fresh_db, tmp_path):
    db = fresh_db
    root = tmp_path / "wiki-vault"
    adapters.get_adapter("markdown").init_vault(root, "wiki")
    vault = registry.add_vault(
        db, name="w", path=root, type_="markdown", mode="wiki"
    )
    reindex.full(db, vault_id=vault["id"])

    report = wiki_lint.check(db, vault_id=vault["id"])
    for key in (
        "orphan_pages", "missing_concepts", "empty_data", "dangling_links",
        "contradiction_candidates", "stale_claim_candidates",
        "link_bidirectionality_gaps", "terminology_drift_candidates",
    ):
        assert key in report, f"missing key {key!r}"
        assert isinstance(report[key], list)
