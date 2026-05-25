from pathlib import Path
import pytest

from scripts import registry, reindex, lint

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def broken_vault(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    import shutil
    dest = tmp_path / "broken"
    shutil.copytree(FIXTURES / "broken-vault", dest)
    vault = registry.add_vault(
        tmp_db, name="b", path=dest, type_="markdown", mode="memo"
    )
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, dest


def test_lint_reports_frontmatter_issues(broken_vault):
    db, vault, root = broken_vault
    report = lint.check(db, vault_id=vault["id"])
    relpaths = {item["relpath"] for item in report["frontmatter_issues"]}
    assert "bad-yaml.md" in relpaths
    assert "missing-title.md" in relpaths
    assert "tags-as-string.md" in relpaths
    assert "good.md" not in relpaths


def test_lint_detects_drift_missing_file(broken_vault):
    db, vault, root = broken_vault
    (root / "good.md").unlink()
    report = lint.check(db, vault_id=vault["id"])
    missing = {item["relpath"] for item in report["drift"]["missing_files"]}
    assert "good.md" in missing


def test_lint_detects_drift_orphan_row(broken_vault):
    db, vault, root = broken_vault
    registry.upsert_note(
        db, vault_id=vault["id"], relpath="ghost.md", layer="memo",
        title="ghost", summary=None, mtime=0.0, size_bytes=0, tags=[],
    )
    report = lint.check(db, vault_id=vault["id"])
    missing = {item["relpath"] for item in report["drift"]["missing_files"]}
    assert "ghost.md" in missing
