import pytest

from scripts import registry


def test_init_db_creates_tables(tmp_db, db_connect):
    registry.init_db(tmp_db)
    conn = db_connect(tmp_db)
    tables = {row["name"] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"vaults", "notes", "tags", "note_tags", "schema_migrations"} <= tables


def test_init_db_records_migration_version(tmp_db, db_connect):
    registry.init_db(tmp_db)
    conn = db_connect(tmp_db)
    versions = [row["version"] for row in conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    )]
    assert versions == [1]


def test_init_db_is_idempotent(tmp_db, db_connect):
    registry.init_db(tmp_db)
    registry.init_db(tmp_db)
    conn = db_connect(tmp_db)
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 1


def test_add_vault_returns_row(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    vault_dir = tmp_path / "myvault"
    vault_dir.mkdir()
    row = registry.add_vault(
        tmp_db,
        name="personal",
        path=vault_dir,
        type_="markdown",
        mode="memo",
    )
    assert row["name"] == "personal"
    assert row["type"] == "markdown"
    assert row["mode"] == "memo"
    assert row["is_active"] == 0


def test_add_vault_rejects_duplicate_name(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    a = tmp_path / "a"; a.mkdir()
    b = tmp_path / "b"; b.mkdir()
    registry.add_vault(tmp_db, name="dup", path=a, type_="markdown", mode="memo")
    with pytest.raises(registry.VaultError, match="name"):
        registry.add_vault(tmp_db, name="dup", path=b, type_="markdown", mode="memo")


def test_add_vault_rejects_duplicate_path(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    a = tmp_path / "shared"; a.mkdir()
    registry.add_vault(tmp_db, name="one", path=a, type_="markdown", mode="memo")
    with pytest.raises(registry.VaultError, match="path"):
        registry.add_vault(tmp_db, name="two", path=a, type_="markdown", mode="memo")


def test_list_vaults_ordered_by_last_used(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    for n in ("a", "b", "c"):
        p = tmp_path / n; p.mkdir()
        registry.add_vault(tmp_db, name=n, path=p, type_="markdown", mode="memo")
    names = [v["name"] for v in registry.list_vaults(tmp_db)]
    assert set(names) == {"a", "b", "c"}


def test_set_active_enforces_single_active(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    for n in ("a", "b"):
        p = tmp_path / n; p.mkdir()
        registry.add_vault(tmp_db, name=n, path=p, type_="markdown", mode="memo")
    registry.set_active(tmp_db, "a")
    registry.set_active(tmp_db, "b")  # must swap, not duplicate
    active = registry.get_active(tmp_db)
    assert active["name"] == "b"
    others = [v for v in registry.list_vaults(tmp_db) if v["is_active"] == 1]
    assert len(others) == 1


def test_get_active_returns_none_when_no_active(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    p = tmp_path / "x"; p.mkdir()
    registry.add_vault(tmp_db, name="x", path=p, type_="markdown", mode="memo")
    assert registry.get_active(tmp_db) is None


def test_forget_vault_removes_row_without_touching_files(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    vault_dir = tmp_path / "keep-me"
    vault_dir.mkdir()
    (vault_dir / "note.md").write_text("hello")
    registry.add_vault(tmp_db, name="keep", path=vault_dir, type_="markdown", mode="memo")
    registry.forget_vault(tmp_db, "keep")
    assert registry.list_vaults(tmp_db) == []
    assert (vault_dir / "note.md").exists(), "files must remain on disk"


def test_forget_unknown_vault_raises(tmp_db):
    registry.init_db(tmp_db)
    with pytest.raises(registry.VaultError, match="not found"):
        registry.forget_vault(tmp_db, "nope")
