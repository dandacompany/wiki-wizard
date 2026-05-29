"""Migration detection + copy (wizard status needs='migrate', wizard migrate)."""
from pathlib import Path

import pytest

from scripts import paths, registry, wizard


def _seed_legacy(path: Path, vault_name: str = "old") -> None:
    """Create a legacy registry with one vault row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    registry.init_db(path)
    root = path.parent / "content"
    root.mkdir(exist_ok=True)
    registry.add_vault(path, name=vault_name, path=root, type_="markdown", mode="memo")


def test_status_migrate_when_legacy_present_and_new_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("OMW_HOME", str(tmp_path / "home"))
    legacy = tmp_path / "legacy" / "registry.db"
    _seed_legacy(legacy)
    monkeypatch.setattr(paths, "legacy_registry_candidates", lambda: [legacy])
    result = wizard.status(paths.registry_path())
    assert result["needs"] == "migrate"
    assert result["legacy_path"] == str(legacy)
    assert result["legacy_vault_count"] == 1


def test_status_setup_when_no_legacy_and_new_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("OMW_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(paths, "legacy_registry_candidates", lambda: [])
    result = wizard.status(paths.registry_path())
    assert result["needs"] == "setup"


def test_status_setup_when_migrated_marker_present(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("OMW_HOME", str(home))
    home.mkdir(parents=True)
    (home / "registry.db.migrated").write_text("")
    legacy = tmp_path / "legacy" / "registry.db"
    _seed_legacy(legacy)
    monkeypatch.setattr(paths, "legacy_registry_candidates", lambda: [legacy])
    # marker present → do not re-trigger migrate
    assert wizard.status(paths.registry_path())["needs"] == "setup"


def test_migrate_copies_and_renames_legacy(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("OMW_HOME", str(home))
    legacy = tmp_path / "legacy" / "registry.db"
    _seed_legacy(legacy, vault_name="kept")
    n = wizard.migrate(legacy)
    assert n == 1                                        # rows verified
    new = paths.registry_path()
    assert new.exists()
    assert [v["name"] for v in registry.list_vaults(new)] == ["kept"]
    assert (legacy.parent / "registry.db.migrated").exists()
    assert (paths.omw_home() / "registry.db.migrated").exists()  # status() sentinel
    assert not legacy.exists()


def test_status_normal_routing_when_new_present(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("OMW_HOME", str(home))
    home.mkdir(parents=True)
    registry.init_db(paths.registry_path())
    assert wizard.status(paths.registry_path())["needs"] == "setup"  # empty → setup


def test_migrate_refuses_to_overwrite_existing_registry(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("OMW_HOME", str(home))
    home.mkdir(parents=True)
    registry.init_db(paths.registry_path())  # dest already exists
    legacy = tmp_path / "legacy" / "registry.db"
    _seed_legacy(legacy)
    with pytest.raises(RuntimeError, match="already exists"):
        wizard.migrate(legacy)
    assert legacy.exists()  # legacy untouched


def test_status_setup_when_legacy_is_corrupt(monkeypatch, tmp_path):
    monkeypatch.setenv("OMW_HOME", str(tmp_path / "home"))
    legacy = tmp_path / "legacy" / "registry.db"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("not a sqlite database")  # garbage / non-OMW file
    monkeypatch.setattr(paths, "legacy_registry_candidates", lambda: [legacy])
    # unreadable legacy must not crash status(); treat as absent → setup
    assert wizard.status(paths.registry_path())["needs"] == "setup"
