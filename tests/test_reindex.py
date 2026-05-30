import json
import time

import pytest

from scripts import registry, reindex


@pytest.fixture
def registered_markdown(tmp_db, markdown_vault_path):
    registry.init_db(tmp_db)
    row = registry.add_vault(
        tmp_db, name="md", path=markdown_vault_path,
        type_="markdown", mode="memo",
    )
    return tmp_db, row["id"]


def test_full_reindex_discovers_all_markdown_files(registered_markdown):
    db, vid = registered_markdown
    n_indexed = reindex.full(db, vault_id=vid)
    assert n_indexed == 6  # 5 with frontmatter + 1 without
    notes = registry.list_notes(db, vault_id=vid)
    titles = {n["title"] for n in notes if n["title"]}
    assert "Karpathy LLM Wiki Proposal" in titles


def test_full_reindex_marks_files_without_frontmatter_as_parse_error(registered_markdown):
    db, vid = registered_markdown
    reindex.full(db, vault_id=vid)
    parse_errors = [
        n for n in registry.list_notes(db, vault_id=vid) if n["parse_error"] == 1
    ]
    assert len(parse_errors) == 1
    assert parse_errors[0]["relpath"].endswith("no-frontmatter.md")


def test_incremental_skips_unchanged_files(registered_markdown, monkeypatch):
    db, vid = registered_markdown
    reindex.full(db, vault_id=vid)

    seen = []
    real_upsert = registry.upsert_note

    def spy(*args, **kwargs):
        seen.append(kwargs["relpath"])
        return real_upsert(*args, **kwargs)

    monkeypatch.setattr(registry, "upsert_note", spy)
    reindex.incremental(db, vault_id=vid)
    assert seen == [], "no files changed, so no upserts expected"


def test_incremental_picks_up_new_file(registered_markdown, markdown_vault_path):
    db, vid = registered_markdown
    reindex.full(db, vault_id=vid)
    new_file = markdown_vault_path / "inbox" / "scratch-temp.md"
    new_file.write_text("---\ntitle: Scratch\ntype: note\ntags: []\n---\nbody\n")
    try:
        time.sleep(0.05)
        reindex.incremental(db, vault_id=vid)
        notes = registry.list_notes(db, vault_id=vid)
        relpaths = {n["relpath"] for n in notes}
        assert "inbox/scratch-temp.md" in relpaths
    finally:
        new_file.unlink()


def test_obsidian_vault_layer_classification(tmp_db, obsidian_vault_path):
    registry.init_db(tmp_db)
    row = registry.add_vault(
        tmp_db, name="ob", path=obsidian_vault_path,
        type_="obsidian", mode="wiki",
    )
    reindex.full(tmp_db, vault_id=row["id"])
    layers = {
        n["relpath"]: n["layer"]
        for n in registry.list_notes(tmp_db, vault_id=row["id"])
    }
    assert layers["wiki/index.md"] == "meta"
    assert layers["wiki/log.md"] == "meta"
    assert layers["wiki/concepts/compounding-knowledge.md"] == "wiki"
    assert layers["raw/2026-04-04-llm-wiki-gist.md"] == "raw"


# ---------------------------------------------------------------------------
# CLI entry-point tests
# ---------------------------------------------------------------------------

def _seed_vault(tmp_db, tmp_path, name):
    registry.init_db(tmp_db)
    vroot = tmp_path / name
    (vroot / "wiki").mkdir(parents=True)
    row = registry.add_vault(tmp_db, name=name, path=str(vroot), type_="markdown", mode="wiki")
    (vroot / "wiki" / "a.md").write_text(
        "---\ntitle: a\ntype: concept\ndate: 2026-05-31\ntags: []\n---\n\nbody", encoding="utf-8")
    return row["id"], vroot


def test_reindex_cli_indexes_and_prints_json(tmp_db, tmp_path, capsys):
    vid, _ = _seed_vault(tmp_db, tmp_path, "rv")
    rc = reindex.main(["--vault-id", str(vid), "--db", str(tmp_db)])
    assert rc == 0
    notes = {n["relpath"] for n in registry.list_notes(tmp_db, vault_id=vid)}
    assert "wiki/a.md" in notes
    out = json.loads(capsys.readouterr().out)
    assert out["vault_id"] == vid
    assert out["mode"] == "incremental"
    assert out["indexed"] >= 1


def test_reindex_cli_full_flag(tmp_db, tmp_path, capsys):
    vid, _ = _seed_vault(tmp_db, tmp_path, "rv2")
    rc = reindex.main(["--vault-id", str(vid), "--db", str(tmp_db), "--full"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "full"


def test_reindex_cli_requires_vault_id():
    with pytest.raises(SystemExit):
        reindex.main(["--db", "/tmp/whatever.db"])
