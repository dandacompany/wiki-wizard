# `vault-import-memo` — register an existing memo folder, optionally migrating frontmatter

**Underlying scripts:** `scripts.registry.add_vault` + `scripts.import_memo.dry_run` / `.apply`

## Flow

### Step 1 — Detect or accept path

1. Probe common candidates in order: `~/Documents/Obsidian/memo`, `~/Documents/memo`, `~/notes/memo`, `~/memo`. If any exists, propose the first match. Otherwise ask the user for the path explicitly.
2. Refuse if the path is already registered (registry raises `VaultError` on path collision).

### Step 2 — Register as memo-mode vault

```bash
python3 -c "
from pathlib import Path
from scripts.paths import registry_path
from scripts import registry, reindex
db = registry_path()
vault = registry.add_vault(
    db, name='<name>', path=Path('<path>'),
    type_='markdown', mode='memo',
)
n = reindex.full(db, vault_id=vault['id'])
print(vault['id'], n)
"
```

Report to the user: registered as `<name>`, N notes indexed.

### Step 3 — Optional dry-run migration

Ask: "Run frontmatter normalization (oh-my-wiki rules)? [Yes / Skip]"

If Yes:

```bash
python3 -c "
import json
from scripts.paths import registry_path
from scripts import import_memo
db = registry_path()
plan = import_memo.dry_run(db, vault_id=<id>)
print(json.dumps(plan['summary']))
print(json.dumps([{'relpath': f['relpath'], 'changes': len(f['changes'])} for f in plan['files'] if f['changes']], indent=2))
"
```

Present the summary (`total`, `needs_changes`, `clean`) and a per-file list of `relpath` + change count.

### Step 4 — Two-step confirm + apply

Confirm: "Apply migration? <N> files will be modified in place. Pre-image of each modified file will be backed up to `.trash/<ts>-pre-import-<safe-name>`. Type 'apply' to proceed."

Require the user to type `apply` exactly. Anything else aborts (registration is kept; files are unchanged).

On confirm:

```bash
python3 -c "
from scripts.paths import registry_path
from scripts import import_memo
db = registry_path()
plan = import_memo.dry_run(db, vault_id=<id>)
result = import_memo.apply(db, vault_id=<id>, plan=plan)
print(result)
"
```

Report: applied N files; skipped M files with malformed YAML (these need manual fix — run `lint`).

## Post-conditions

- Vault registered. If migration applied: changed files have oh-my-wiki-compliant frontmatter; `.trash/` contains pre-image backups.

## Error handling

- Path already registered → tell the user the existing vault name; suggest `vault-list` to inspect.
- Malformed YAML files → reported with `skipped` count; user can run `lint` for details and fix manually, then re-run.
