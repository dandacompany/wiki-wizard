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


def resolve_input(
    *,
    text: str | None = None,
    file_path: Path | None = None,
    vault_relpath: str | None = None,
    db_path: Path | None = None,
    vault_id: int | None = None,
) -> tuple[str, dict]:
    """Resolve exactly one input source into (content, source_meta).
    source_meta = {kind, origin} where kind ∈ {text, file, vault_page}.
    """
    provided = sum(
        x is not None for x in (text, file_path, vault_relpath)
    )
    if provided == 0:
        raise PersonaError("no input provided (need text, file_path, or vault_relpath)")
    if provided > 1:
        raise PersonaError("exactly one of text, file_path, vault_relpath required")

    if text is not None:
        return text, {"kind": "text", "origin": None}

    if file_path is not None:
        fp = Path(file_path)
        if not fp.exists():
            raise PersonaError(f"file not found: {fp}")
        return fp.read_text(encoding="utf-8"), {"kind": "file", "origin": fp}

    # vault_relpath
    if db_path is None or vault_id is None:
        raise PersonaError("vault_relpath requires db_path and vault_id")
    from scripts import registry as _registry
    conn = _registry.connect(db_path)
    try:
        row = conn.execute(
            "SELECT path FROM vaults WHERE id = ?", (vault_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise PersonaError(f"unknown vault_id={vault_id}")
    abs_path = Path(row["path"]) / vault_relpath
    if not abs_path.exists():
        raise PersonaError(f"vault page not found: {vault_relpath}")
    return (
        abs_path.read_text(encoding="utf-8"),
        {"kind": "vault_page", "origin": abs_path},
    )


def resolve_output_path(
    *,
    persona: dict,
    source_meta: dict,
    db_path: Path | None = None,
    vault_id: int | None = None,
    lang: str | None = None,
    title: str | None = None,
) -> Path | None:
    """Compute where this persona's output should be filed.
    Returns None for stdout kind."""
    from scripts import slugify as _slugify
    kind = persona["output_kind"]

    if kind == "stdout":
        return None

    if kind == "sibling_file":
        if not lang:
            raise PersonaError("sibling_file output requires lang= argument")
        origin = source_meta.get("origin")
        if origin is None:
            raise PersonaError("sibling_file output requires source with origin path")
        origin = Path(origin)
        stem = origin.stem
        return origin.with_name(f"{stem}.{lang}{origin.suffix}")

    if kind == "inplace":
        origin = source_meta.get("origin")
        if origin is None:
            raise PersonaError("inplace output requires source with origin path")
        return Path(origin)

    if kind == "new_page":
        if not title:
            raise PersonaError("new_page output requires title= argument")
        if db_path is None or vault_id is None:
            raise PersonaError("new_page output requires db_path and vault_id")
        from scripts import registry as _registry
        conn = _registry.connect(db_path)
        try:
            row = conn.execute(
                "SELECT path FROM vaults WHERE id = ?", (vault_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise PersonaError(f"unknown vault_id={vault_id}")
        slug = _slugify.slugify(title)
        return Path(row["path"]) / "wiki" / "syntheses" / f"{slug}.md"

    raise PersonaError(f"unsupported output_kind: {kind!r}")
