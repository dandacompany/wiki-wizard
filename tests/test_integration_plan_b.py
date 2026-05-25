"""End-to-end Plan B scenario: setup → create → find → edit → move → delete → lint."""
from pathlib import Path

import pytest

from scripts import (
    adapters, import_memo, lint, memo_ops, registry, reindex, search,
)


@pytest.fixture
def fresh_db(tmp_db):
    registry.init_db(tmp_db)
    return tmp_db


def test_full_memo_workflow(fresh_db, tmp_path):
    db = fresh_db
    root = tmp_path / "daily"
    root.mkdir()

    # vault-setup
    adapters.get_adapter("markdown").init_vault(root, "memo")
    vault = registry.add_vault(
        db, name="daily", path=root, type_="markdown", mode="memo"
    )
    registry.set_active(db, "daily")
    reindex.full(db, vault_id=vault["id"])

    # create
    rel = memo_ops.write(
        db, vault_id=vault["id"],
        title="Standup 2026-05-24",
        body="Discussed plan B rollout.",
        folder="inbox", tags=["standup", "may"],
        type_="note", date_str="2026-05-24",
    )
    assert (root / rel).exists()

    # find
    hits = search.query(db, vault_id=vault["id"], query="standup", limit=5)
    assert any(h["relpath"] == rel for h in hits)

    # edit (rename via title field)
    memo_ops.edit_meta(
        db, vault_id=vault["id"], relpath=rel, key="title", value="Standup — renamed",
    )
    text = (root / rel).read_text(encoding="utf-8")
    assert "Standup — renamed" in text

    # move to archive
    (root / "archive").mkdir()
    new_rel = memo_ops.move(
        db, vault_id=vault["id"], relpath=rel, dest_folder="archive",
    )
    assert (root / new_rel).exists()
    assert not (root / rel).exists()

    # soft delete
    trash_rel = memo_ops.delete(
        db, vault_id=vault["id"], relpath=new_rel, hard=False,
    )
    assert trash_rel.startswith(".trash/")
    assert (root / trash_rel).exists()

    # lint after all this — should report no frontmatter issues
    report = lint.check(db, vault_id=vault["id"])
    assert report["frontmatter_issues"] == []
    assert report["drift"]["missing_files"] == []


def test_full_import_memo_workflow(fresh_db, tmp_path):
    db = fresh_db
    import shutil
    src_fixture = Path(__file__).parent / "fixtures" / "memo-vault"
    root = tmp_path / "imported-memo"
    shutil.copytree(src_fixture, root)

    # register
    vault = registry.add_vault(
        db, name="legacy", path=root, type_="markdown", mode="memo"
    )
    reindex.full(db, vault_id=vault["id"])

    # dry-run + apply
    plan = import_memo.dry_run(db, vault_id=vault["id"])
    assert plan["summary"]["needs_changes"] >= 1
    result = import_memo.apply(db, vault_id=vault["id"], plan=plan)
    assert result["applied"] >= 1

    # re-run dry_run — should be a no-op
    plan2 = import_memo.dry_run(db, vault_id=vault["id"])
    assert plan2["summary"]["needs_changes"] == 0
