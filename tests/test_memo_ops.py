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
