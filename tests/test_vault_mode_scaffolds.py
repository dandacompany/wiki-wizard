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
