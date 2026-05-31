# tests/test_entity_link.py
import pytest

from scripts import entity_link, frontmatter, registry, reindex


def _vault(tmp_path, monkeypatch):
    monkeypatch.setenv("OMW_HOME", str(tmp_path / ".omw"))
    db = tmp_path / "r.db"
    registry.init_db(db)
    root = tmp_path / "v"
    (root / "wiki" / "entities").mkdir(parents=True)
    v = registry.add_vault(db, name="v", path=root, type_="markdown", mode="wiki")
    return db, root, v["id"]


def _page(root, name, frontmatter_body):
    (root / "wiki" / "entities" / name).write_text(frontmatter_body, encoding="utf-8")


def test_name_pattern_matches_multiword_and_alias():
    pat = entity_link._name_pattern(["Andrej Karpathy", "Karpathy"])
    assert pat.search("met andrej karpathy today")     # multi-word, case-insensitive
    assert pat.search("per Karpathy's blog")            # alias
    assert not pat.search("nanocarp")                   # word-boundary


def test_suggest_finds_unlinked_title_mention(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "karpathy.md", "---\ntitle: Andrej Karpathy\ndate: 2026-01-01\ntype: entity\ntags: [p]\n---\n## Summary\nresearcher\n")
    _page(root, "tdd.md", "---\ntitle: TDD\ndate: 2026-01-01\ntype: concept\ntags: [m]\n---\n## Summary\nAndrej Karpathy wrote about this.\n")
    reindex.full(db, vault_id=vid)
    sugg = entity_link.suggest_links(db, vault_id=vid)
    pairs = {(s["src_relpath"], s["target_slug"]) for s in sugg}
    assert ("wiki/entities/tdd.md", "karpathy") in pairs


def test_suggest_excludes_already_linked_and_self(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "karpathy.md", "---\ntitle: Andrej Karpathy\ndate: 2026-01-01\ntype: entity\ntags: [p]\n---\n## Summary\nAndrej Karpathy is me.\n")
    _page(root, "tdd.md", "---\ntitle: TDD\ndate: 2026-01-01\ntype: concept\ntags: [m]\n---\n## Summary\nSee [[karpathy]] — Andrej Karpathy.\n")
    reindex.full(db, vault_id=vid)
    sugg = entity_link.suggest_links(db, vault_id=vid)
    pairs = {(s["src_relpath"], s["target_slug"]) for s in sugg}
    assert ("wiki/entities/tdd.md", "karpathy") not in pairs   # already linked in page
    assert ("wiki/entities/karpathy.md", "karpathy") not in pairs  # self


def test_suggest_excludes_mention_inside_existing_link(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "karpathy.md", "---\ntitle: Karpathy\ndate: 2026-01-01\ntype: entity\ntags: [p]\n---\n## Summary\nx\n")
    _page(root, "tdd.md", "---\ntitle: TDD\ndate: 2026-01-01\ntype: concept\ntags: [m]\n---\n## Summary\n[[karpathy|Karpathy]] only.\n")
    reindex.full(db, vault_id=vid)
    sugg = entity_link.suggest_links(db, vault_id=vid)
    assert ("wiki/entities/tdd.md", "karpathy") not in {(s["src_relpath"], s["target_slug"]) for s in sugg}


def test_apply_link_inserts_wikilink(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "karpathy.md", "---\ntitle: Andrej Karpathy\ndate: 2026-01-01\ntype: entity\ntags: [p]\n---\n## Summary\nx\n")
    _page(root, "tdd.md", "---\ntitle: TDD\ndate: 2026-01-01\ntype: concept\ntags: [m]\n---\n## Summary\nAndrej Karpathy wrote this.\n")
    reindex.full(db, vault_id=vid)
    out = entity_link.apply_link(db, vault_id=vid, relpath="wiki/entities/tdd.md", target_slug="karpathy")
    assert out["inserted"] == "[[karpathy|Andrej Karpathy]]"
    _, body = frontmatter.parse((root / "wiki" / "entities" / "tdd.md").read_text(encoding="utf-8"))
    assert "[[karpathy|Andrej Karpathy]] wrote this." in body


def test_apply_link_plain_when_mention_equals_slug(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "tdd.md", "---\ntitle: TDD\ndate: 2026-01-01\ntype: concept\ntags: [m]\n---\n## Summary\nx\n")
    _page(root, "src.md", "---\ntitle: Src\ndate: 2026-01-01\ntype: concept\ntags: [m]\n---\n## Summary\nI like tdd a lot.\n")
    reindex.full(db, vault_id=vid)
    out = entity_link.apply_link(db, vault_id=vid, relpath="wiki/entities/src.md", target_slug="tdd")
    assert out["inserted"] == "[[tdd]]"  # mention 'tdd' slugs to 'tdd'


def test_apply_link_errors(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "tdd.md", "---\ntitle: TDD\ndate: 2026-01-01\ntype: concept\ntags: [m]\n---\n## Summary\nx\n")
    reindex.full(db, vault_id=vid)
    with pytest.raises(FileNotFoundError):
        entity_link.apply_link(db, vault_id=vid, relpath="wiki/entities/nope.md", target_slug="tdd")
    with pytest.raises(ValueError):
        entity_link.apply_link(db, vault_id=vid, relpath="wiki/entities/tdd.md", target_slug="ghost")
