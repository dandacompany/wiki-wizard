"""Dataview-style inline `key:: value` field parsing (line-level).

Pure. Fenced ``` code blocks are stripped first so field syntax inside code
examples isn't parsed. Keys are lowercased+stripped; values kept verbatim.
"""
from __future__ import annotations

import re

_FENCE_RE = re.compile(r"^\s*```")
_FIELD_RE = re.compile(r"^\s*(?:[-*]\s+)?([A-Za-z][\w \-]*?)\s*::\s*(.+?)\s*$")


def _strip_code(body: str) -> str:
    """Blank out fenced ``` code blocks (keep line count stable)."""
    out: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def extract_inline_fields(body: str) -> dict[str, list[str]]:
    """Return {key: [value, ...]} for line-level `key:: value` fields."""
    fields: dict[str, list[str]] = {}
    for line in _strip_code(body or "").splitlines():
        m = _FIELD_RE.match(line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        fields.setdefault(key, []).append(m.group(2).strip())
    return fields
