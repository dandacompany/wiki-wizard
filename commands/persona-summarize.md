# `persona-summarize` — produce a 3-tier summary via the summarizer persona

**Underlying scripts:** `scripts.personas` (load, run)
**Persona:** `personas/summarizer.md`

## Preconditions

None. Works on text, files, and vault pages.

## Flow

### Step 1 — Get inputs

1. **Source** — paste, file path, or vault relpath.

### Step 2 — Show persona

```bash
python3 -m scripts.personas show summarizer
```

Read the body — output is JSON with three keys.

### Step 3 — Summarize

Apply the persona's per-tier rules. Output a single JSON object:

```json
{
  "one_line": "...",
  "one_paragraph": "...",
  "detailed": "..."
}
```

Write to a temp file:

```bash
tmp_out=$(mktemp /tmp/summary.XXXXXX.json)
cat > "$tmp_out" <<'JSON'
{"one_line": "...", "one_paragraph": "...", "detailed": "..."}
JSON
```

### Step 4 — Run via runtime (stdout)

```bash
python3 -m scripts.personas run summarizer \
  --text "<source body>" \
  --output-file "$tmp_out"
```

The script echoes the JSON to stdout. No file is written to the vault.

### Step 5 — Render to the user

Pretty-print the three tiers. Offer next steps:

- "File as a synthesis page?" → call `persona-scaffold` or `query` to file the `detailed` tier.
- "Translate?" → call `persona-translate` on the summary.
