# `vault-list` — show all registered vaults

**Underlying script:** `scripts.registry.list_vaults` (+ per-vault note counts)

## Flow

1. Run:

```bash
python3 -c "
from pathlib import Path
from scripts import registry
db = Path('data/registry.db')
vaults = registry.list_vaults(db)
conn = registry.connect(db)
try:
    for v in vaults:
        n = conn.execute('SELECT COUNT(*) FROM notes WHERE vault_id = ?', (v['id'],)).fetchone()[0]
        marker = '*' if v['is_active'] else ' '
        print(f\"{marker} {v['name']:20s} {v['mode']:5s} {v['type']:10s} {n:5d} notes  {v['path']}\")
finally:
    conn.close()
"
```

2. Render to the user. The `*` marks the active vault.

## Post-conditions

- Read-only.

## Error handling

- No vaults registered → tell the user to run `vault-setup` or `vault-import-memo`.
