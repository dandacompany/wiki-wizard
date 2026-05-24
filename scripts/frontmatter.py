"""Safe parse/edit for YAML frontmatter in markdown files."""
from __future__ import annotations

import re

import yaml

FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)


class FrontmatterError(Exception):
    pass


def parse(text: str) -> tuple[dict, str]:
    """Return (metadata, body). Empty dict if no frontmatter present."""
    m = FRONT_RE.match(text)
    if not m:
        return {}, text
    raw_meta, body = m.group(1), m.group(2)
    try:
        meta = yaml.safe_load(raw_meta) or {}
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"malformed YAML frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return meta, body


def dump(meta: dict, body: str) -> str:
    """Serialize back to '---\\n<yaml>\\n---\\n<body>' form."""
    yaml_text = yaml.safe_dump(
        meta,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=None,
    ).rstrip()
    return f"---\n{yaml_text}\n---\n{body.lstrip(chr(10))}" if body else f"---\n{yaml_text}\n---\n"


def edit_field(text: str, key: str, value) -> str:
    """Return new text with metadata[key] = value, preserving body verbatim."""
    meta, body = parse(text)
    meta[key] = value
    return dump(meta, body)
