# `vault-setup` — register a new vault

**Underlying script:** `scripts.registry.add_vault` + `scripts.adapters.get_adapter(...).init_vault`

## Flow

1. Ask the user for:
   - **name** (unique short identifier, e.g. `daily`, `research`)
   - **path** (absolute path; offer to create the directory if missing)
   - **mode**: `memo` or `wiki` (AskUserQuestion 2 options)
   - **type**: `markdown` or `obsidian` (AskUserQuestion 2 options)

2. Show a summary and confirm.

3. On confirm, run:

```bash
python3 -c "
from pathlib import Path
from scripts import registry, adapters, reindex
db = Path('data/registry.db')
root = Path('<path>')
root.mkdir(parents=True, exist_ok=True)
adapters.get_adapter('<type>', vault_name='<name>').init_vault(root, '<mode>')
vault = registry.add_vault(
    db, name='<name>', path=root, type_='<type>', mode='<mode>',
)
registry.set_active(db, '<name>')
reindex.full(db, vault_id=vault['id'])
print(dict(vault))
"
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
