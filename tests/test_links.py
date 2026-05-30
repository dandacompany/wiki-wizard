from scripts import registry


def test_links_table_exists_after_init_db(tmp_db):
    registry.init_db(tmp_db)
    conn = registry.connect(tmp_db)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='links'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_init_db_idempotent_with_links(tmp_db):
    registry.init_db(tmp_db)
    registry.init_db(tmp_db)  # must not raise (IF NOT EXISTS)
    conn = registry.connect(tmp_db)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(links)")}
    finally:
        conn.close()
    assert cols == {"id", "vault_id", "src_note_id", "dst_slug",
                    "dst_note_id", "link_type", "position"}


from scripts import links


def test_extract_wikilink_simple():
    assert links.extract_links("see [[attention]] here") == [("attention", "wikilink", 0)]


def test_extract_wikilink_alias_and_heading():
    assert links.extract_links("[[attn|Attention]] and [[topic#sec]]") == [
        ("attn", "wikilink", 0),
        ("topic", "wikilink", 1),
    ]


def test_extract_markdown_internal_link():
    assert links.extract_links("[x](concepts/attn.md)") == [("attn", "markdown", 0)]


def test_extract_ignores_external_and_fragment_and_non_md():
    body = "[a](https://e.com) [b](mailto:x@y.z) [c](#sec) [d](img.png)"
    assert links.extract_links(body) == []


def test_extract_preserves_document_order_across_kinds():
    body = "[md](a.md) then [[wiki]] then [md2](b.md)"
    assert links.extract_links(body) == [
        ("a", "markdown", 0),
        ("wiki", "wikilink", 1),
        ("b", "markdown", 2),
    ]


def test_extract_skips_empty_targets():
    assert links.extract_links("[[ ]] and [x]()") == []
