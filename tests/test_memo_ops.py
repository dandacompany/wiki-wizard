import time
from pathlib import Path
from datetime import date

import pytest

from scripts import registry, memo_ops


@pytest.fixture
def memo_vault(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    vault_dir = tmp_path / "memo-vault"
    vault_dir.mkdir()
    (vault_dir / "inbox").mkdir()
    (vault_dir / ".trash").mkdir()
    row = registry.add_vault(
        tmp_db, name="t", path=vault_dir, type_="markdown", mode="memo"
    )
    return tmp_db, row, vault_dir


def test_write_creates_file_with_frontmatter(memo_vault):
    db_path, vault, root = memo_vault
    relpath = memo_ops.write(
        db_path,
        vault_id=vault["id"],
        title="My First Memo",
        body="Hello world.",
        folder="inbox",
        tags=["test", "first"],
        type_="note",
        date_str="2026-05-24",
    )
    assert relpath == "inbox/my-first-memo.md"
    text = (root / relpath).read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "title: My First Memo" in text
    assert "tags:" in text
    assert text.rstrip().endswith("Hello world.")


def test_write_resolves_slug_collision(memo_vault):
    db_path, vault, root = memo_vault
    memo_ops.write(
        db_path, vault_id=vault["id"], title="dup", body="a",
        folder="inbox", tags=["x"], type_="note", date_str="2026-05-24",
    )
    second = memo_ops.write(
        db_path, vault_id=vault["id"], title="dup", body="b",
        folder="inbox", tags=["x"], type_="note", date_str="2026-05-24",
    )
    assert second == "inbox/dup-2.md"


def test_edit_meta_replaces_single_field(memo_vault):
    db_path, vault, root = memo_vault
    relpath = memo_ops.write(
        db_path, vault_id=vault["id"], title="m", body="b",
        folder="inbox", tags=["a"], type_="note", date_str="2026-05-24",
    )
    memo_ops.edit_meta(
        db_path, vault_id=vault["id"], relpath=relpath, key="title", value="Renamed"
    )
    text = (root / relpath).read_text(encoding="utf-8")
    assert "title: Renamed" in text
    # body untouched
    assert text.rstrip().endswith("b")


def test_move_relocates_file_and_updates_registry(memo_vault):
    db_path, vault, root = memo_vault
    (root / "archive").mkdir()
    relpath = memo_ops.write(
        db_path, vault_id=vault["id"], title="m", body="b",
        folder="inbox", tags=["a"], type_="note", date_str="2026-05-24",
    )
    new_relpath = memo_ops.move(
        db_path, vault_id=vault["id"], relpath=relpath, dest_folder="archive"
    )
    assert new_relpath == "archive/m.md"
    assert (root / new_relpath).exists()
    assert not (root / relpath).exists()
    rows = registry.list_notes(db_path, vault_id=vault["id"])
    paths = [r["relpath"] for r in rows]
    assert "archive/m.md" in paths
    assert "inbox/m.md" not in paths


def test_delete_soft_moves_to_trash(memo_vault):
    db_path, vault, root = memo_vault
    relpath = memo_ops.write(
        db_path, vault_id=vault["id"], title="bye", body="b",
        folder="inbox", tags=["a"], type_="note", date_str="2026-05-24",
    )
    trash_relpath = memo_ops.delete(
        db_path, vault_id=vault["id"], relpath=relpath, hard=False
    )
    assert trash_relpath.startswith(".trash/")
    assert (root / trash_relpath).exists()
    assert not (root / relpath).exists()
    rows = registry.list_notes(db_path, vault_id=vault["id"])
    assert all(r["relpath"] != relpath for r in rows)


def test_delete_hard_removes_file_entirely(memo_vault):
    db_path, vault, root = memo_vault
    relpath = memo_ops.write(
        db_path, vault_id=vault["id"], title="gone", body="b",
        folder="inbox", tags=["a"], type_="note", date_str="2026-05-24",
    )
    result = memo_ops.delete(
        db_path, vault_id=vault["id"], relpath=relpath, hard=True
    )
    assert result is None
    assert not (root / relpath).exists()
    rows = registry.list_notes(db_path, vault_id=vault["id"])
    assert all(r["relpath"] != relpath for r in rows)
