"""Writing-agent persona framework.

Personas live at personas/<role>.md with YAML frontmatter that declares
the persona's name, description, capabilities, required tools, model hint,
input kinds, and output kind. The body is the prompt template the LLM
follows when invoked.

This module never calls an LLM. It loads + validates persona definitions
and provides deterministic I/O (resolve input, resolve output path, write
output). The LLM does the cognitive work via commands/persona-<role>.md.
"""
from __future__ import annotations

from pathlib import Path

from scripts import frontmatter

PERSONAS_ROOT = Path(__file__).resolve().parents[1] / "personas"

VALID_OUTPUT_KINDS = {"sibling_file", "inplace", "new_page", "stdout"}
VALID_MODEL_HINTS = {"fast", "standard", "most_capable"}
REQUIRED_FRONTMATTER_KEYS = (
    "name", "description", "capabilities", "tools",
    "model_hint", "input_kinds", "output_kind",
)


class PersonaError(Exception):
    """Raised for unknown persona, invalid frontmatter, missing input, etc."""


def _parse_persona_text(text: str) -> dict:
    """Internal: parse a persona markdown file's text into a spec dict."""
    try:
        meta, body = frontmatter.parse(text)
    except frontmatter.FrontmatterError as exc:
        raise PersonaError(f"malformed frontmatter: {exc}") from exc
    for key in REQUIRED_FRONTMATTER_KEYS:
        if key not in meta:
            raise PersonaError(f"missing required key in frontmatter: {key!r}")
    if meta["output_kind"] not in VALID_OUTPUT_KINDS:
        raise PersonaError(
            f"invalid output_kind: {meta['output_kind']!r} "
            f"(valid: {sorted(VALID_OUTPUT_KINDS)})"
        )
    if meta["model_hint"] not in VALID_MODEL_HINTS:
        raise PersonaError(
            f"invalid model_hint: {meta['model_hint']!r} "
            f"(valid: {sorted(VALID_MODEL_HINTS)})"
        )
    if not isinstance(meta["capabilities"], list):
        raise PersonaError("capabilities must be a list")
    if not isinstance(meta["tools"], list):
        raise PersonaError("tools must be a list")
    if not isinstance(meta["input_kinds"], list) or not meta["input_kinds"]:
        raise PersonaError("input_kinds must be a non-empty list")
    spec = dict(meta)
    spec["body"] = body
    return spec


def list_personas() -> list[dict]:
    """Return [{name, description, capabilities, tools, model_hint,
    input_kinds, output_kind}, ...] for every persona under personas/."""
    out = []
    if not PERSONAS_ROOT.is_dir():
        return out
    for md in sorted(PERSONAS_ROOT.glob("*.md")):
        try:
            spec = _parse_persona_text(md.read_text(encoding="utf-8"))
        except PersonaError:
            continue
        entry = {k: spec[k] for k in REQUIRED_FRONTMATTER_KEYS}
        out.append(entry)
    return out


def load_persona(name: str) -> dict:
    """Return the full persona spec (frontmatter dict + 'body' key)."""
    target = PERSONAS_ROOT / f"{name}.md"
    if not target.exists():
        raise PersonaError(f"unknown persona: {name!r}")
    return _parse_persona_text(target.read_text(encoding="utf-8"))
