# Adapter spec (v2 contract)

v1 ships two adapters in a single `scripts/adapters.py`. v2 will split them into `scripts/adapters/`. To add a new adapter:

## Interface

```python
class VaultAdapter(Protocol):
    def open(self, abs_path: Path) -> None: ...
    def link_syntax(self, target_relpath: str) -> str: ...
    def init_vault(self, root: Path, mode: str) -> None: ...
    def is_valid(self, root: Path) -> bool: ...
```

## Required behavior

- `init_vault(mode="memo")` creates `inbox/` and `.trash/`.
- `init_vault(mode="wiki")` creates `raw/`, `wiki/` with sub-folders, plus `wiki/index.md` and `wiki/log.md`.
- `is_valid()` returns True only when the directory looks like a vault of this type (e.g. ObsidianAdapter requires `.obsidian/`).
- `link_syntax()` returns the canonical link form for cross-references (markdown link / wikilink / other).
- `open()` launches the file in the app most natural for the storage type. Fall back to the OS default if the dedicated app is unavailable.

## Registration

Until v2 splits the file, add a new adapter as a sibling class and extend `get_adapter()`:

```python
def get_adapter(type_: str, *, vault_name=None) -> VaultAdapter:
    if type_ == "markdown": return MarkdownAdapter()
    if type_ == "obsidian": return ObsidianAdapter(vault_name=vault_name)
    if type_ == "logseq":   return LogseqAdapter()
    raise AdapterError(...)
```

Add a CHECK constraint update to `schema.sql` and ship a migration when v2 lands.
