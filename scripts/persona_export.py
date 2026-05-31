"""Host-universal persona export.

Advertise the enabled persona roster in each host's instruction file
(CLAUDE.md / AGENTS.md / GEMINI.md) via a symmetric marker block. Deliberately
NOT claude-native `.claude/agents/` — omw is a universal skill (claude/codex/
gemini), so no host's native subagent mechanism is privileged. The host-agnostic
invocation path is the omw skill itself (`commands/persona-*.md`).
"""
from __future__ import annotations

from pathlib import Path

HOST_FILES = {"claude": "CLAUDE.md", "codex": "AGENTS.md", "gemini": "GEMINI.md"}
MARKER = "omw-personas"
_START = f"<!-- {MARKER}:start -->"
_END = f"<!-- {MARKER}:end -->"


def render_block(enabled: list[str], main: str, descriptions: dict[str, str]) -> str:
    """Render the omw-personas marker block (pure; no I/O)."""
    lines = [
        _START,
        "## omw personas (managed by `omw setup personas` — do not edit between markers)",
        "",
        f"Main persona: **{main}**",
        "",
        "Enabled personas:",
    ]
    for name in enabled:
        desc = (descriptions.get(name) or "").strip().replace("\n", " ")
        lines.append(f"- **{name}** — {desc}" if desc else f"- **{name}**")
    lines += [
        "",
        'Invoke any of these via the omw skill — e.g. say "research X", '
        '"audit the wiki", or run a team. Persona definitions live in '
        "`personas/<name>.md`; procedures in `commands/persona-*.md`.",
        _END,
    ]
    return "\n".join(lines)


def upsert_marker(md_path: Path, block: str) -> None:
    """Insert or replace the omw-personas marker region in md_path (idempotent).

    Creates the file if absent; preserves everything outside the markers.
    """
    md_path = Path(md_path)
    text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    if _START in text and _END in text:
        pre = text[: text.index(_START)]
        post = text[text.index(_END) + len(_END):]
        new = pre + block + post
    elif text == "":
        new = block + "\n"
    else:
        sep = "\n" if text.endswith("\n") else "\n\n"
        new = text + sep + block + "\n"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(new, encoding="utf-8")


def export_personas(*, enabled: list[str], main: str, descriptions: dict[str, str],
                    base_dir: Path, hosts: list[str]) -> list[Path]:
    """Write the roster block into each host's instruction file under base_dir."""
    base_dir = Path(base_dir)
    block = render_block(enabled, main, descriptions)
    written: list[Path] = []
    for host in hosts:
        if host not in HOST_FILES:
            raise ValueError(f"unknown host: {host!r} (known: {sorted(HOST_FILES)})")
        path = base_dir / HOST_FILES[host]
        upsert_marker(path, block)
        written.append(path)
    return written
