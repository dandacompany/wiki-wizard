import pytest

from scripts import frontmatter as fm


VALID = """---
title: Hello
date: 2026-05-23
tags: [alpha, beta]
summary: greeting
---

Body text here.
"""


def test_parse_returns_metadata_and_body():
    meta, body = fm.parse(VALID)
    assert meta["title"] == "Hello"
    assert meta["tags"] == ["alpha", "beta"]
    assert body.strip().startswith("Body text")


def test_parse_no_frontmatter_returns_empty_meta():
    meta, body = fm.parse("Just plain text\nno yaml")
    assert meta == {}
    assert "Just plain text" in body


def test_parse_malformed_yaml_raises():
    bad = "---\ntitle: [unterminated\n---\nbody"
    with pytest.raises(fm.FrontmatterError):
        fm.parse(bad)


def test_dump_roundtrip_preserves_tag_list_shape():
    meta, body = fm.parse(VALID)
    out = fm.dump(meta, body)
    meta2, _ = fm.parse(out)
    assert meta2["tags"] == ["alpha", "beta"]


def test_edit_field_preserves_other_fields():
    meta, body = fm.parse(VALID)
    new_text = fm.edit_field(VALID, "status", "archived")
    meta2, body2 = fm.parse(new_text)
    assert meta2["status"] == "archived"
    assert meta2["title"] == meta["title"]
    assert body2.strip() == body.strip()
