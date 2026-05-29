# `persona-scaffold` — generate an outline + section placeholders

**Underlying scripts:** `scripts.personas` (load, run) + `scripts.reindex`
**Persona:** `personas/scaffolder.md`

## Preconditions

Active vault must be wiki-mode (the runtime files to `wiki/syntheses/`).

## Flow

### Step 1 — Get inputs

1. **Title** — required.
2. **Topic description** — short paragraph on what the page will cover.
3. **Sections** — number of `## Section` headings (default 5).

### Step 2 — Show persona

```bash
python3 -m scripts.personas show scaffolder
```

### Step 3 — Generate scaffold

Apply the persona's output-shape rules. Produce a markdown document with:

- Frontmatter (`title`, `date`, `type: synthesis`, `tags`, `status: draft`)
- `# <title>` heading matching frontmatter
- One-sentence framing line
- N section headings inferred from the topic
- Inline HTML comment prompts per section
- References section last (empty bullet)

Write to a temp file:

```bash
tmp_out=$(mktemp /tmp/scaffold.XXXXXX.md)
cat > "$tmp_out" <<'SCAFFOLD'
<the scaffold markdown>
SCAFFOLD
```

### Step 4 — File via runtime (new_page)

```bash
python3 -m scripts.personas run scaffolder \
  --vault-id <id> \
  --text "<topic description>" \
  --title "<page title>" \
  --output-file "$tmp_out"
```

The script writes to `wiki/syntheses/<slug>.md` where `<slug>` comes from the title.

### Step 5 — Reindex

```bash
python3 -c "
from scripts.paths import registry_path
from scripts import reindex, registry
db = registry_path()
vault = registry.get_active(db)
reindex.incremental(db, vault_id=vault['id'])
"
```

### Step 6 — Report

Tell the user the relpath of the new scaffold page. Suggest:

- `open <relpath>` — start filling in the sections.
- `lint` — verify the page is correctly marked `status: draft` (so it doesn't appear as orphan).
