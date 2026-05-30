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
