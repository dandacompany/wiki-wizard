"""Vault storage adapters. v1 supports markdown and obsidian."""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Protocol


class AdapterError(Exception):
    pass


class VaultAdapter(Protocol):
    def open(self, abs_path: Path) -> None: ...
    def link_syntax(self, target_relpath: str) -> str: ...
    def init_vault(self, root: Path, mode: str) -> None: ...
    def is_valid(self, root: Path) -> bool: ...


def _os_open(target: Path) -> None:
    """Cross-platform 'open this file with the default app'."""
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", str(target)], check=False)
    elif system == "Windows":
        subprocess.run(["cmd", "/c", "start", "", str(target)], check=False, shell=False)
    else:
        subprocess.run(["xdg-open", str(target)], check=False)


_INDEX_TEMPLATE = """---
title: Wiki Index
type: meta
status: meta
---

## Concepts

## Entities

## Summaries
"""

_LOG_TEMPLATE = "# Operation Log\n"


class MarkdownAdapter:
    """Plain-markdown adapter — works with any editor (VS Code, Cursor, etc.)."""

    def open(self, abs_path: Path) -> None:
        _os_open(abs_path)

    def link_syntax(self, target_relpath: str) -> str:
        rel = target_relpath
        if rel.endswith(".md"):
            rel = rel[:-3]
        name = rel.rsplit("/", 1)[-1]
        return f"[{name}](./{rel}.md)"

    def init_vault(self, root: Path, mode: str) -> None:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        (root / ".trash").mkdir(exist_ok=True)
        if mode == "memo":
            (root / "inbox").mkdir(exist_ok=True)
        elif mode == "wiki":
            (root / "raw").mkdir(exist_ok=True)
            wiki = root / "wiki"
            wiki.mkdir(exist_ok=True)
            for sub in ("summaries", "entities", "concepts", "comparisons", "syntheses"):
                (wiki / sub).mkdir(exist_ok=True)
            index_path = wiki / "index.md"
            log_path = wiki / "log.md"
            if not index_path.exists():
                index_path.write_text(_INDEX_TEMPLATE, encoding="utf-8")
            if not log_path.exists():
                log_path.write_text(_LOG_TEMPLATE, encoding="utf-8")
        else:
            raise AdapterError(f"unknown mode: {mode!r}")

    def is_valid(self, root: Path) -> bool:
        return Path(root).is_dir()


def get_adapter(type_: str) -> VaultAdapter:
    if type_ == "markdown":
        return MarkdownAdapter()
    if type_ == "obsidian":
        return ObsidianAdapter()
    raise AdapterError(f"unknown adapter type: {type_!r}")


# Placeholder so Task 10 can extend it.
class ObsidianAdapter(MarkdownAdapter):
    pass
