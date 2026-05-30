"""Persona registry + I/O runtime."""
from pathlib import Path

import pytest

from scripts import personas


def test_list_personas_returns_all_four():
    names = {p["name"] for p in personas.list_personas()}
    # v2.2a core 4; v2.2b adds more — use superset check so new personas don't break this
    assert {"translator", "polisher", "summarizer", "scaffolder"} <= names


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


from datetime import datetime


def test_write_output_sibling_creates_file(wiki_vault):
    db, vault, root = wiki_vault
    src = root / "wiki" / "summaries" / "demo.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\ntitle: Demo\n---\nbody", encoding="utf-8")
    persona = personas.load_persona("translator")
    out_path = personas.resolve_output_path(
        persona=persona,
        source_meta={"kind": "vault_page", "origin": src},
        lang="ko",
    )
    result = personas.write_output(
        persona=persona,
        target_path=out_path,
        content="---\ntitle: 데모\n---\n번역된 본문",
        source_meta={"kind": "vault_page", "origin": src},
    )
    assert result == out_path
    assert out_path.exists()
    assert "번역된 본문" in out_path.read_text(encoding="utf-8")


def test_write_output_inplace_backs_up_original(tmp_path):
    src = tmp_path / "draft.md"
    src.write_text("original prose", encoding="utf-8")
    backup_dir = tmp_path / ".trash"
    persona = personas.load_persona("polisher")
    result = personas.write_output(
        persona=persona,
        target_path=src,
        content="polished prose",
        source_meta={"kind": "file", "origin": src},
        backup_dir=backup_dir,
    )
    assert result == src
    assert src.read_text(encoding="utf-8") == "polished prose"
    backups = list(backup_dir.glob("*draft*.md"))
    assert backups, "expected at least one backup file"
    assert backups[0].read_text(encoding="utf-8") == "original prose"


def test_write_output_inplace_skips_backup_when_no_backup_dir(tmp_path):
    src = tmp_path / "draft.md"
    src.write_text("original", encoding="utf-8")
    persona = personas.load_persona("polisher")
    result = personas.write_output(
        persona=persona,
        target_path=src,
        content="updated",
        source_meta={"kind": "file", "origin": src},
        backup_dir=None,
    )
    assert result == src
    assert src.read_text(encoding="utf-8") == "updated"


def test_write_output_new_page_writes_to_wiki_syntheses(wiki_vault):
    db, vault, root = wiki_vault
    persona = personas.load_persona("scaffolder")
    out_path = personas.resolve_output_path(
        persona=persona,
        source_meta={"kind": "text", "origin": None},
        db_path=db, vault_id=vault["id"],
        title="My Outline",
    )
    result = personas.write_output(
        persona=persona,
        target_path=out_path,
        content="---\ntitle: My Outline\ntype: synthesis\n---\n## Section 1\n## Section 2\n",
        source_meta={"kind": "text", "origin": None},
    )
    assert result == out_path
    assert out_path.exists()
    assert out_path == root / "wiki" / "syntheses" / "my-outline.md"


def test_write_output_stdout_returns_none(tmp_path):
    persona = personas.load_persona("summarizer")
    result = personas.write_output(
        persona=persona,
        target_path=None,
        content="some output",
        source_meta={"kind": "text", "origin": None},
    )
    assert result is None


import subprocess
import sys
import json as _json


def test_cli_list_returns_4_personas():
    REPO_ROOT = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.personas", "list"],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    data = _json.loads(proc.stdout)
    names = {p["name"] for p in data}
    # v2.2a core 4; v2.2b adds more — use superset check so new personas don't break this
    assert {"translator", "polisher", "summarizer", "scaffolder"} <= names


def test_cli_show_returns_persona_spec():
    REPO_ROOT = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.personas", "show", "translator"],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    data = _json.loads(proc.stdout)
    assert data["name"] == "translator"
    assert "body" in data


def test_cli_run_translator_sibling_file(wiki_vault, tmp_path):
    db, vault, root = wiki_vault
    REPO_ROOT = Path(__file__).resolve().parents[1]
    src = root / "wiki" / "summaries" / "demo.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\ntitle: Demo\n---\nEnglish body", encoding="utf-8")
    out = tmp_path / "translated.md"
    out.write_text("---\ntitle: 데모\n---\n한국어 본문", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable, "-m", "scripts.personas", "run", "translator",
            "--db", str(db),
            "--vault-id", str(vault["id"]),
            "--vault-relpath", "wiki/summaries/demo.md",
            "--lang", "ko",
            "--output-file", str(out),
        ],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    final_path = proc.stdout.strip()
    assert final_path.endswith("demo.ko.md")
    written = Path(final_path)
    assert written.exists()
    assert "한국어 본문" in written.read_text(encoding="utf-8")


def test_cli_run_summarizer_stdout(tmp_path):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    out = tmp_path / "summary.json"
    out.write_text(
        '{"one_line":"x","one_paragraph":"y","detailed":"z"}',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable, "-m", "scripts.personas", "run", "summarizer",
            "--text", "some body",
            "--output-file", str(out),
        ],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "one_line" in proc.stdout


def test_researcher_persona_loads():
    p = personas.load_persona("researcher")
    assert p["output_kind"] == "new_page"
    assert p["input_kinds"] == ["text"]
    assert p["tools"] == []          # search via abstraction, NOT hardcoded MCP
    assert p["body"].strip()
