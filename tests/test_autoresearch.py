"""Autoresearch: session state, rounds, file-back."""
from pathlib import Path

import pytest

from scripts import registry, adapters, reindex, autoresearch


@pytest.fixture
def wiki_vault(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    root = tmp_path / "wiki"
    adapters.get_adapter("markdown").init_vault(root, "wiki")
    vault = registry.add_vault(
        tmp_db, name="w", path=root, type_="markdown", mode="wiki"
    )
    registry.set_active(tmp_db, "w")
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, root


@pytest.fixture
def memo_vault(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    root = tmp_path / "memo-vault"
    adapters.get_adapter("markdown").init_vault(root, "memo")
    vault = registry.add_vault(
        tmp_db, name="m", path=root, type_="markdown", mode="memo"
    )
    registry.set_active(tmp_db, "m")
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, root


def test_init_session_creates_session_dir_and_mission(wiki_vault):
    db, vault, root = wiki_vault
    info = autoresearch.init_session(
        db, vault_id=vault["id"], query="How does attention work?"
    )
    session_dir = Path(info["session_dir"])
    assert session_dir.is_dir()
    assert session_dir.parent == root / ".oh-my-wiki" / "sessions"
    assert "how-does-attention-work" in session_dir.name
    mission_path = session_dir / "mission.json"
    assert mission_path.exists()
    import json
    mission = json.loads(mission_path.read_text(encoding="utf-8"))
    assert mission["query"] == "How does attention work?"
    assert mission["vault_id"] == vault["id"]
    assert mission["max_rounds"] == 3


def test_init_session_rejects_memo_vault(memo_vault):
    db, vault, root = memo_vault
    with pytest.raises(registry.VaultError, match="wiki-mode"):
        autoresearch.init_session(
            db, vault_id=vault["id"], query="anything"
        )


def test_init_session_respects_max_rounds_override(wiki_vault):
    db, vault, root = wiki_vault
    info = autoresearch.init_session(
        db, vault_id=vault["id"], query="q", max_rounds=2
    )
    import json
    mission = json.loads((Path(info["session_dir"]) / "mission.json").read_text())
    assert mission["max_rounds"] == 2


def test_init_session_caps_max_rounds_at_5(wiki_vault):
    db, vault, root = wiki_vault
    info = autoresearch.init_session(
        db, vault_id=vault["id"], query="q", max_rounds=99
    )
    import json
    mission = json.loads((Path(info["session_dir"]) / "mission.json").read_text())
    assert mission["max_rounds"] == 5
