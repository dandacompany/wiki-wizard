"""Persona registry + I/O runtime."""
from pathlib import Path

import pytest

from scripts import personas


def test_list_personas_returns_all_four():
    names = {p["name"] for p in personas.list_personas()}
    assert names == {"translator", "polisher", "summarizer", "scaffolder"}


def test_list_personas_entries_have_required_keys():
    for p in personas.list_personas():
        for key in ("name", "description", "capabilities", "tools",
                    "model_hint", "input_kinds", "output_kind"):
            assert key in p, f"persona {p.get('name')!r} missing {key}"


def test_load_persona_unknown_raises():
    with pytest.raises(personas.PersonaError, match="unknown"):
        personas.load_persona("nonexistent")


def test_load_persona_translator_has_body():
    p = personas.load_persona("translator")
    assert p["name"] == "translator"
    assert p["output_kind"] == "sibling_file"
    assert "body" in p
    assert isinstance(p["body"], str)
    assert len(p["body"]) > 0


def test_load_persona_validates_output_kind():
    """A persona with an invalid output_kind raises PersonaError."""
    bad_text = """---
name: bad-persona
description: x
capabilities: []
tools: []
model_hint: standard
input_kinds: [text]
output_kind: nonsense
---
body
"""
    with pytest.raises(personas.PersonaError, match="output_kind"):
        personas._parse_persona_text(bad_text)


from scripts import registry, adapters, reindex


@pytest.fixture
def wiki_vault(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    root = tmp_path / "wiki"
    adapters.get_adapter("markdown").init_vault(root, "wiki")
    vault = registry.add_vault(
        tmp_db, name="w", path=root, type_="markdown", mode="wiki"
    )
    registry.set_active(tmp_db, "w")
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, root


def test_resolve_input_text_mode():
    content, meta = personas.resolve_input(text="hello world")
    assert content == "hello world"
    assert meta["kind"] == "text"
    assert meta["origin"] is None


def test_resolve_input_file_mode(tmp_path):
    p = tmp_path / "input.md"
    p.write_text("file content", encoding="utf-8")
    content, meta = personas.resolve_input(file_path=p)
    assert content == "file content"
    assert meta["kind"] == "file"
    assert meta["origin"] == p


def test_resolve_input_file_not_found(tmp_path):
    with pytest.raises(personas.PersonaError, match="not found"):
        personas.resolve_input(file_path=tmp_path / "nope.md")


def test_resolve_input_vault_page_mode(wiki_vault):
    db, vault, root = wiki_vault
    page = root / "wiki" / "summaries" / "demo.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("vault page content", encoding="utf-8")
    content, meta = personas.resolve_input(
        vault_relpath="wiki/summaries/demo.md",
        db_path=db, vault_id=vault["id"],
    )
    assert content == "vault page content"
    assert meta["kind"] == "vault_page"
    assert meta["origin"] == page


def test_resolve_input_no_input_raises():
    with pytest.raises(personas.PersonaError, match="no input"):
        personas.resolve_input()


def test_resolve_input_multiple_inputs_raises(tmp_path):
    with pytest.raises(personas.PersonaError, match="exactly one"):
        personas.resolve_input(text="x", file_path=tmp_path / "y.md")


def test_resolve_output_path_sibling_for_translator(wiki_vault):
    db, vault, root = wiki_vault
    src = root / "wiki" / "summaries" / "demo.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("x", encoding="utf-8")
    persona = personas.load_persona("translator")
    path = personas.resolve_output_path(
        persona=persona,
        source_meta={"kind": "vault_page", "origin": src},
        lang="ko",
    )
    assert path == src.with_name("demo.ko.md")


def test_resolve_output_path_sibling_requires_lang(wiki_vault):
    db, vault, root = wiki_vault
    src = root / "wiki" / "summaries" / "demo.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("x", encoding="utf-8")
    persona = personas.load_persona("translator")
    with pytest.raises(personas.PersonaError, match="lang"):
        personas.resolve_output_path(
            persona=persona,
            source_meta={"kind": "vault_page", "origin": src},
        )


def test_resolve_output_path_inplace_for_polisher(tmp_path):
    src = tmp_path / "draft.md"
    src.write_text("x", encoding="utf-8")
    persona = personas.load_persona("polisher")
    path = personas.resolve_output_path(
        persona=persona,
        source_meta={"kind": "file", "origin": src},
    )
    assert path == src


def test_resolve_output_path_new_page_for_scaffolder(wiki_vault):
    db, vault, root = wiki_vault
    persona = personas.load_persona("scaffolder")
    path = personas.resolve_output_path(
        persona=persona,
        source_meta={"kind": "text", "origin": None},
        db_path=db,
        vault_id=vault["id"],
        title="My New Topic",
    )
    assert path == root / "wiki" / "syntheses" / "my-new-topic.md"


def test_resolve_output_path_new_page_requires_title(wiki_vault):
    db, vault, root = wiki_vault
    persona = personas.load_persona("scaffolder")
    with pytest.raises(personas.PersonaError, match="title"):
        personas.resolve_output_path(
            persona=persona,
            source_meta={"kind": "text", "origin": None},
            db_path=db, vault_id=vault["id"],
        )


def test_resolve_output_path_stdout_for_summarizer():
    persona = personas.load_persona("summarizer")
    path = personas.resolve_output_path(
        persona=persona,
        source_meta={"kind": "text", "origin": None},
    )
    assert path is None
