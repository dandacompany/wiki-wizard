"""Six vault-setup modes: each produces a distinct folder scaffold."""
from pathlib import Path

import pytest

from scripts import adapters


def test_personal_mode_scaffolds_journal_goals_people_health(tmp_path):
    root = tmp_path / "personal-vault"
    adapters.get_adapter("markdown").init_vault(root, "personal")
    for sub in ("journal", "goals", "people", "health", ".trash"):
        assert (root / sub).is_dir(), f"missing {sub}/"
    index = root / "index.md"
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "Personal" in text or "personal" in text


def test_book_mode_scaffolds_chapters_characters_worldbuilding_outlines_drafts(tmp_path):
    root = tmp_path / "book-vault"
    adapters.get_adapter("markdown").init_vault(root, "book")
    for sub in ("chapters", "characters", "worldbuilding", "outlines", "drafts", ".trash"):
        assert (root / sub).is_dir(), f"missing {sub}/"
    index = root / "index.md"
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "Book" in text or "Chapters" in text


def test_business_mode_scaffolds_meetings_decisions_clients_vendors_processes(tmp_path):
    root = tmp_path / "biz-vault"
    adapters.get_adapter("markdown").init_vault(root, "business")
    for sub in ("meetings", "decisions", "clients", "vendors", "processes", ".trash"):
        assert (root / sub).is_dir(), f"missing {sub}/"
    assert (root / "index.md").exists()


def test_github_codebase_mode_scaffolds_modules_apis_decisions_runbooks_glossary(tmp_path):
    root = tmp_path / "code-vault"
    adapters.get_adapter("markdown").init_vault(root, "github-codebase")
    for sub in ("modules", "apis", "decisions", "runbooks", "glossary", ".trash"):
        assert (root / sub).is_dir(), f"missing {sub}/"
    assert (root / "index.md").exists()
