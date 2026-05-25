from pathlib import Path

import pytest

from scripts import registry, adapters, reindex, ingest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def wiki_vault(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    root = tmp_path / "wiki"
    adapters.get_adapter("markdown").init_vault(root, "wiki")
    vault = registry.add_vault(
        tmp_db, name="w", path=root, type_="markdown", mode="wiki"
    )
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, root


def test_save_raw_md(wiki_vault):
    db, vault, root = wiki_vault
    rel = ingest.save_raw(
        db, vault_id=vault["id"],
        content="# Heading\n\nbody",
        ext="md", title="My Source", date_str="2026-05-25",
    )
    assert rel == "raw/2026-05-25-my-source.md"
    text = (root / rel).read_text(encoding="utf-8")
    assert text == "# Heading\n\nbody"


def test_save_raw_txt(wiki_vault):
    db, vault, root = wiki_vault
    rel = ingest.save_raw(
        db, vault_id=vault["id"],
        content="plain text",
        ext="txt", title="A Note", date_str="2026-05-25",
    )
    assert rel == "raw/2026-05-25-a-note.txt"
    assert (root / rel).read_text(encoding="utf-8") == "plain text"


def test_save_raw_collision(wiki_vault):
    db, vault, root = wiki_vault
    ingest.save_raw(
        db, vault_id=vault["id"], content="a",
        ext="md", title="dup", date_str="2026-05-25",
    )
    second = ingest.save_raw(
        db, vault_id=vault["id"], content="b",
        ext="md", title="dup", date_str="2026-05-25",
    )
    assert second == "raw/2026-05-25-dup-2.md"


def test_save_raw_pdf_returns_relpath_and_extracted_text(wiki_vault):
    db, vault, root = wiki_vault
    pdf_bytes = (FIXTURES / "tiny.pdf").read_bytes()
    rel, text = ingest.save_raw_pdf(
        db, vault_id=vault["id"],
        pdf_bytes=pdf_bytes,
        title="Tiny", date_str="2026-05-25",
    )
    assert rel == "raw/2026-05-25-tiny.pdf"
    # bytes preserved verbatim
    assert (root / rel).read_bytes() == pdf_bytes
    # text extracted
    assert "PDF FIXTURE" in text
