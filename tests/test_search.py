import pytest

from scripts import registry, reindex, search


@pytest.fixture
def indexed_markdown(tmp_db, markdown_vault_path):
    registry.init_db(tmp_db)
    row = registry.add_vault(
        tmp_db, name="md", path=markdown_vault_path,
        type_="markdown", mode="memo",
    )
    reindex.full(tmp_db, vault_id=row["id"])
    return tmp_db, row["id"]


def test_search_returns_title_match_first(indexed_markdown):
    db, vid = indexed_markdown
    hits = search.query(db, vault_id=vid, query="Karpathy", limit=5)
    assert hits[0]["relpath"].endswith("karpathy-llm-wiki.md")


def test_search_matches_tag(indexed_markdown):
    db, vid = indexed_markdown
    hits = search.query(db, vault_id=vid, query="zettelkasten", limit=5)
    assert any("zettelkasten" in h["relpath"] for h in hits)


def test_search_matches_summary(indexed_markdown):
    db, vid = indexed_markdown
    hits = search.query(db, vault_id=vid, query="Vannevar Bush", limit=5)
    assert any("memex-history" in h["relpath"] for h in hits)


def test_search_returns_empty_on_no_match(indexed_markdown):
    db, vid = indexed_markdown
    hits = search.query(db, vault_id=vid, query="quantum dishwasher", limit=5)
    assert hits == []


def test_search_respects_limit(indexed_markdown):
    db, vid = indexed_markdown
    hits = search.query(db, vault_id=vid, query="note", limit=2)
    assert len(hits) <= 2
