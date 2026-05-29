# `persona-translate` — translate via the translator persona

**Underlying scripts:** `scripts.personas` (subcommands: load, run) + `scripts.reindex` after vault writes.
**Persona:** `personas/translator.md`

## Preconditions

Active vault optional. If translating a vault page, active vault must exist (any mode).

## Flow

### Step 1 — Get inputs

Ask the user for:

1. **Source** — paste text, file path, or vault relpath (e.g. `wiki/summaries/foo.md`).
2. **Target language** — `ko`, `en`, `ja`, etc. (ISO 639-1 code).

### Step 2 — Load the persona

```bash
python3 -m scripts.personas show translator
```

Read the persona body — it has 8 rules. Follow them exactly.

### Step 3 — Translate

Apply the persona rules to the source content. Output ONLY the translated markdown — no preamble, no fences around it.

Write your translation to a temp file:

```bash
tmp_out=$(mktemp /tmp/translated.XXXXXX.md)
cat > "$tmp_out" <<'TRANSLATION'
<your translated markdown here>
TRANSLATION
```

### Step 4 — File via runtime

For a vault page:

```bash
python3 -m scripts.personas run translator \
  --vault-id <id> \
  --vault-relpath <relpath> \
  --lang <target-lang> \
  --output-file "$tmp_out"
```

For a local file:

```bash
python3 -m scripts.personas run translator \
  --file <input-path> \
  --lang <target-lang> \
  --output-file "$tmp_out"
```

The script files the translation to `<source-stem>.<lang>.md` next to the source.

### Step 5 — Reindex (vault pages only)

```bash
python3 -c "
from scripts.paths import registry_path
from scripts import reindex, registry
db = registry_path()
vault = registry.get_active(db)
if vault is not None:
    reindex.incremental(db, vault_id=vault['id'])
"
```

### Step 6 — Report

Tell the user the final relpath of the translated file and offer next steps (`find` to verify search picks it up; `persona-polish` if the translation needs smoothing).

## Error handling

- Source missing → re-prompt for path / paste.
- Invalid `--lang` (e.g. unsupported) → script does not validate; the LLM should refuse before writing if the language is gibberish.
- Vault page not under wiki/ → still works; sibling file is created in the same directory.
