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
