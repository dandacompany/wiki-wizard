"""Viewer registry. get_viewer(name) -> Viewer instance."""
from __future__ import annotations

from scripts.viewers.base import VaultRef, Viewer
from scripts.viewers.logseq import LogseqViewer
from scripts.viewers.obsidian import ObsidianViewer


class UnknownViewer(ValueError):
    pass


_VIEWERS = {"obsidian": ObsidianViewer, "logseq": LogseqViewer}
VIEWER_NAMES = tuple(_VIEWERS)


def get_viewer(name: str) -> Viewer:
    try:
        return _VIEWERS[name]()
    except KeyError:
        raise UnknownViewer(f"unknown viewer {name!r}; choices: {', '.join(VIEWER_NAMES)}")
