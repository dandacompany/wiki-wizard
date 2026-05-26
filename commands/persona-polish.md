# `persona-polish` — polish prose via the polisher persona

**Underlying scripts:** `scripts.personas` (load, run)
**Persona:** `personas/polisher.md`

## Preconditions

None. Works on text, files, and vault pages.

## Flow

### Step 1 — Get inputs

1. **Source** — paste, file path, or vault relpath.
2. **`--lang`** — `ko` or `en`. Determines style profile (korean-prose-polish patterns vs Strunk-and-White-ish defaults).

### Step 2 — Show persona

```bash
python3 -m scripts.personas show polisher
```

Read the body — it has language-specific style profiles.

### Step 3 — Polish

Apply the profile to the source. Preserve meaning, tone, facts, frontmatter, headings, code blocks, links, numbers, dates, names, technical terms.

Write your polished version to a temp file:

```bash
tmp_out=$(mktemp /tmp/polished.XXXXXX.md)
cat > "$tmp_out" <<'POLISHED'
<polished markdown>
POLISHED
```

### Step 4 — File via runtime (inplace overwrite + backup)

For a vault page (backup to vault's `.trash/`):

```bash
python3 -m scripts.personas run polisher \
  --db data/registry.db \
  --vault-id <id> \
  --vault-relpath <relpath> \
  --output-file "$tmp_out" \
  --backup-dir <vault-root>/.trash
```

For a local file (backup somewhere of the user's choice or skip with no `--backup-dir`):

```bash
python3 -m scripts.personas run polisher \
  --file <input-path> \
  --output-file "$tmp_out" \
  --backup-dir <path-to-backups>
```

### Step 5 — Reindex (vault pages only)

```bash
python3 -c "
from pathlib import Path
from scripts import reindex, registry
db = Path('data/registry.db')
vault = registry.get_active(db)
if vault is not None:
    reindex.incremental(db, vault_id=vault['id'])
"
```

### Step 6 — Report

Tell the user which file was polished and where the backup of the original lives. Offer to diff if they want to see what changed.

## Error handling

- Source missing → re-prompt.
- Author wants to revert → original is at the backup path (no special op needed).
