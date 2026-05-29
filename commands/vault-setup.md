# `vault-setup` — register a new vault

**Underlying script:** `scripts.registry.add_vault` + `scripts.adapters.get_adapter(...).init_vault`

## Flow

1. Ask the user for:
   - **name** (unique short identifier, e.g. `daily`, `research`)
   - **location** (AskUserQuestion, 3 options):
     - **Global default (recommended)** — stored at `~/.omw/vaults/<name>`,
       reachable from any working directory. Resolve with
       `scripts.paths.default_vault_root(name)`.
     - **Project-local** — stored at `<cwd>/.omw/<name>`. Resolve with
       `scripts.paths.project_vault_root(name)`. Still registered in the global
       registry, so it remains visible everywhere.
     - **Custom path** — prompt for an absolute path (legacy behavior).
   - **mode**: `memo` or `wiki` (AskUserQuestion 2 options)
   - **type**: `markdown` or `obsidian` (AskUserQuestion 2 options)

   If **Project-local** is chosen and `<cwd>` is inside a git repo
   (`git rev-parse --is-inside-work-tree` succeeds), offer to append `.omw/`
   to the repo's `.gitignore` so vault content is not accidentally committed.

2. Show a summary and confirm.

3. On confirm, run:

```python
from pathlib import Path
from scripts import registry, adapters, reindex
from scripts.paths import registry_path, ensure_home, default_vault_root, project_vault_root
ensure_home()
db = registry_path()
# root is one of: default_vault_root('<name>') | project_vault_root('<name>') | Path('<custom-abs-path>')
root = Path('<resolved-location>')
root.mkdir(parents=True, exist_ok=True)
adapters.get_adapter('<type>', vault_name='<name>').init_vault(root, '<mode>')
vault = registry.add_vault(db, name='<name>', path=root, type_='<type>', mode='<mode>')
registry.set_active(db, '<name>')
reindex.full(db, vault_id=vault['id'])
print(dict(vault))
```

4. Confirm to the user: vault registered, set active, indexed N notes.

## Post-conditions

- New row in `vaults` table; `is_active = 1` (others demoted).
- Folder scaffolded: `inbox/` for memo; `raw/`, `wiki/{summaries,entities,concepts,comparisons,syntheses}/`, `wiki/index.md`, `wiki/log.md` for wiki. `.trash/` always.
- Initial `reindex.full` runs (idempotent on an empty vault — count = 0).

## Error handling

- Name collision → registry raises `VaultError`. Re-prompt with a different name.
- Path collision → same error, different message. Re-prompt or suggest `vault-import-memo` if it's an existing memo folder.
- Wrong type for environment (e.g., obsidian without Obsidian installed) → still register; warn the user that `open` will fail.
