from scripts import inline_fields


def test_basic_key_value():
    f = inline_fields.extract_inline_fields("intro\nstatus:: active\nmore")
    assert f == {"status": ["active"]}


def test_list_item_and_lowercase_key():
    f = inline_fields.extract_inline_fields("- Owner:: dante\n* Team:: labs")
    assert f == {"owner": ["dante"], "team": ["labs"]}


def test_multiple_same_key_is_list():
    f = inline_fields.extract_inline_fields("uses:: a\nuses:: b")
    assert f == {"uses": ["a", "b"]}


def test_value_with_wikilink_kept_verbatim():
    f = inline_fields.extract_inline_fields("supersedes:: [[old-page]]")
    assert f == {"supersedes": ["[[old-page]]"]}


def test_line_without_double_colon_ignored():
    f = inline_fields.extract_inline_fields("just a sentence: with one colon")
    assert f == {}


def test_url_not_misparsed():
    f = inline_fields.extract_inline_fields("see https://example.com for more")
    assert f == {}


def test_field_inside_code_fence_ignored():
    body = "real:: yes\n```\ncode:: nope\n```\nafter:: ok"
    f = inline_fields.extract_inline_fields(body)
    assert f == {"real": ["yes"], "after": ["ok"]}
