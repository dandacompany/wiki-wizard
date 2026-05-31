from scripts import fts, registry, reindex
from scripts import search_index


def _vault(tmp_path, monkeypatch):
    monkeypatch.setenv("OMW_HOME", str(tmp_path / ".omw"))
    db = tmp_path / "r.db"
    registry.init_db(db)
    root = tmp_path / "v"
    (root / "wiki" / "concepts").mkdir(parents=True)
    v = registry.add_vault(db, name="v", path=root, type_="markdown", mode="wiki")
    return db, root, v["id"]


def test_query_finds_body_only_term_via_fts(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    (root / "wiki" / "concepts" / "a.md").write_text(
        "---\ntitle: Alpha\ndate: 2026-01-01\ntype: concept\ntags: [x]\n---\nthe quick brown fox\n",
        encoding="utf-8")
    reindex.full(db, vault_id=vid)
    hits = search_index.query(db, vault_id=vid, query="fox", limit=5)  # body-only term
    assert any(h["relpath"] == "wiki/concepts/a.md" for h in hits)


def test_query_falls_back_without_fts5(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    (root / "wiki" / "concepts" / "a.md").write_text(
        "---\ntitle: Alpha Fox\ndate: 2026-01-01\ntype: concept\ntags: [x]\n---\nbody\n",
        encoding="utf-8")
    reindex.full(db, vault_id=vid)
    monkeypatch.setattr(fts, "fts5_available", lambda: False)
    hits = search_index.query(db, vault_id=vid, query="fox", limit=5)  # token path
    assert any(h["relpath"] == "wiki/concepts/a.md" for h in hits)
    assert set(hits[0]) >= {"relpath", "title", "summary", "tags", "score"}
