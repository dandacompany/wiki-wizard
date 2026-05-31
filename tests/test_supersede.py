# tests/test_supersede.py
import pytest

from scripts import frontmatter, registry, reindex, supersede


def _vault(tmp_path, monkeypatch):
    monkeypatch.setenv("OMW_HOME", str(tmp_path / ".omw"))
    db = tmp_path / "registry.db"
    registry.init_db(db)
    root = tmp_path / "vault"
    (root / "wiki" / "concepts").mkdir(parents=True)
    v = registry.add_vault(db, name="v", path=root, type_="markdown", mode="wiki")
    return db, root, v["id"]


def test_mark_superseded_sets_fields_and_reindexes(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    page = root / "wiki" / "concepts" / "old.md"
    page.write_text(
        "---\ntitle: Old\ndate: 2026-01-01\ntype: concept\ntags: [x]\n---\nbody\n",
        encoding="utf-8",
    )
    reindex.full(db, vault_id=vid)
    out = supersede.mark_superseded(db, vault_id=vid, relpath="wiki/concepts/old.md",
                                    by_slug="new")
    assert out == {"relpath": "wiki/concepts/old.md", "status": "superseded",
                   "superseded_by": "new"}
    meta, _ = frontmatter.parse(page.read_text(encoding="utf-8"))
    assert meta["status"] == "superseded"
    assert meta["superseded_by"] == "new"


def test_mark_superseded_idempotent(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    page = root / "wiki" / "concepts" / "old.md"
    page.write_text("---\ntitle: Old\ntype: concept\n---\nbody\n", encoding="utf-8")
    reindex.full(db, vault_id=vid)
    supersede.mark_superseded(db, vault_id=vid, relpath="wiki/concepts/old.md", by_slug="new")
    first = page.read_text(encoding="utf-8")
    supersede.mark_superseded(db, vault_id=vid, relpath="wiki/concepts/old.md", by_slug="new")
    assert page.read_text(encoding="utf-8") == first


def test_mark_superseded_missing_page_raises(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError):
        supersede.mark_superseded(db, vault_id=vid, relpath="wiki/concepts/nope.md", by_slug="x")
