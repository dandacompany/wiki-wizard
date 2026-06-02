"""Logseq adapter — logseq:// URL scheme (no token needed)."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from scripts.viewers.base import VaultRef, Viewer, quote_value

_CONFIG_EDN = "{:preferred-format :markdown}\n"


class LogseqViewer(Viewer):
    name = "logseq"
    supports_search = False  # Logseq has no search URL scheme

    def available(self) -> bool:
        if sys.platform == "darwin":
            return Path("/Applications/Logseq.app").exists() or shutil.which("logseq") is not None
        return shutil.which("logseq") is not None or True

    def open_vault(self, vault: VaultRef) -> str:
        return f"logseq://graph/{quote_value(vault.name)}"

    def open_page(self, vault: VaultRef, relpath: str) -> str:
        stem = Path(relpath).stem
        return f"logseq://graph/{quote_value(vault.name)}?page={quote_value(stem)}"

    def search(self, vault: VaultRef, query: str) -> str:
        # No search URL scheme — open the graph; caller prints a hint (supports_search=False).
        return self.open_vault(vault)

    def scaffold_config(self, vault: VaultRef) -> tuple[list[Path], list[str]]:
        cfg = vault.root / "logseq"
        cfg.mkdir(parents=True, exist_ok=True)
        edn = cfg / "config.edn"
        written: list[Path] = []
        if not edn.is_file():
            edn.write_text(_CONFIG_EDN, encoding="utf-8")
            written.append(edn)
        hints = ["Logseq에서 이 폴더를 graph로 추가하세요: Logseq → Add a graph → 이 볼트 폴더 선택."]
        return written, hints
