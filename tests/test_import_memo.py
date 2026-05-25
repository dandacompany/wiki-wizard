from pathlib import Path
import shutil
import pytest

from scripts import registry, reindex, import_memo

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def imported_vault(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    dest = tmp_path / "imported"
    shutil.copytree(FIXTURES / "memo-vault", dest)
    vault = registry.add_vault(
        tmp_db, name="m", path=dest, type_="markdown", mode="memo"
    )
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, dest


def test_dry_run_lists_files_needing_migration(imported_vault):
    db, vault, root = imported_vault
    report = import_memo.dry_run(db, vault_id=vault["id"])
    by_relpath = {r["relpath"]: r for r in report["files"]}
    assert by_relpath["2026-01-15-kickoff-meeting.md"]["changes"] == []
    assert any(
        c["field"] == "type" and c["op"] == "add"
        for c in by_relpath["article-no-type.md"]["changes"]
    )
    assert any(
        c["field"] == "tags" and c["op"] == "normalize"
        for c in by_relpath["tag-string.md"]["changes"]
    )
    assert any(
        c["field"] == "date" and c["op"] == "add"
        for c in by_relpath["no-date.md"]["changes"]
    )
    assert "nested/topic-x.md" in by_relpath


def test_dry_run_summary_counts(imported_vault):
    db, vault, root = imported_vault
    report = import_memo.dry_run(db, vault_id=vault["id"])
    assert report["summary"]["total"] == 5
    assert report["summary"]["needs_changes"] == 3
    assert report["summary"]["clean"] == 2
