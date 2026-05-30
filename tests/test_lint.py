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


def test_lint_reports_links_broken_and_orphans(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    vroot = tmp_path / "lv"
    (vroot / "wiki").mkdir(parents=True)
    row = registry.add_vault(
        tmp_db, name="lv", path=str(vroot), type_="markdown", mode="wiki"
    )
    vid = row["id"]
    (vroot / "wiki" / "a.md").write_text(
        "---\ntitle: a\ntype: concept\ndate: 2026-05-30\ntags: []\n---\n\n[[ghost]]", encoding="utf-8"
    )
    (vroot / "wiki" / "b.md").write_text(
        "---\ntitle: b\ntype: concept\ndate: 2026-05-30\ntags: []\n---\n\norphan page", encoding="utf-8"
    )
    reindex.full(tmp_db, vault_id=vid)
    report = lint.check(tmp_db, vault_id=vid)
    assert report["frontmatter_issues"] == []   # fixture is otherwise clean
    assert [r["dst_slug"] for r in report["links"]["broken"]] == ["ghost"]
    orphan_paths = {r["relpath"] for r in report["links"]["orphans"]}
    assert {"wiki/a.md", "wiki/b.md"} <= orphan_paths


def test_lint_reports_index_drift(tmp_db, tmp_path):
    from scripts import registry, reindex, lint
    registry.init_db(tmp_db)
    vroot = tmp_path / "lid"
    (vroot / "wiki").mkdir(parents=True)
    row = registry.add_vault(tmp_db, name="lid", path=str(vroot), type_="markdown", mode="wiki")
    vid = row["id"]
    (vroot / "wiki" / "index.md").write_text("# Index\n\n- [A](a.md)\n", encoding="utf-8")
    (vroot / "wiki" / "a.md").write_text(
        "---\ntitle: a\ntype: concept\ndate: 2026-05-31\ntags: []\n---\n\nbody", encoding="utf-8")
    (vroot / "wiki" / "b.md").write_text(
        "---\ntitle: b\ntype: concept\ndate: 2026-05-31\ntags: []\n---\n\nbody", encoding="utf-8")
    reindex.full(tmp_db, vault_id=vid)
    report = lint.check(tmp_db, vault_id=vid)
    assert "index_drift" in report["links"]
    assert [n["relpath"] for n in report["links"]["index_drift"]["missing_from_index"]] == ["wiki/b.md"]
