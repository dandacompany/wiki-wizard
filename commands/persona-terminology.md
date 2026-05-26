# persona-terminology

Run the **terminology-manager** persona to build/refresh the
per-vault glossary and surface inconsistent surface forms.

## When to invoke

- "build a glossary for this vault"
- "what terms does my wiki use?"
- "any inconsistent terminology?"
- "용어집 만들어줘"
- "용어가 일관되게 쓰였는지 확인해줘"

## Inputs

- `--vault-id <id>` (required)
- Optional: `--vault-relpath <relpath>` to scope ingestion to a
  single page on this run (otherwise scan all wiki/ pages)

## Procedure

1. **Show the persona spec.** Read `personas/terminology-manager.md`.

2. **Resolve vault root.** Look up via:

   ```bash
   python3 -m scripts.registry vaults --db data/registry.db
   ```

   to map vault-id → vault path.

3. **List current glossary state.** Run:

   ```bash
   python3 -m scripts.glossary list \
     --vault-root <vault-path> --vault-id <id>
   ```

4. **Scan pages.** Read all `wiki/**/*.md` (or just the targeted
   page if `--vault-relpath` provided). Extract candidate terms
   per the persona's "What counts as a term" rules. Skip terms
   already in the glossary.

5. **Upsert each new term.** For each new term:

   ```bash
   python3 -m scripts.glossary upsert \
     --vault-root <vault-path> --vault-id <id> \
     --canonical "<form>" \
     --alias "<alt1>" --alias "<alt2>" \
     --definition "<one-sentence definition>" \
     --first-seen-relpath "<wiki/path/page.md>"
   ```

6. **Run lint.**

   ```bash
   python3 -m scripts.glossary lint \
     --vault-root <vault-path> --vault-id <id>
   ```

7. **Emit JSON on stdout** following the persona's output
   format. File via:

   ```bash
   python3 -m scripts.personas run terminology-manager \
     --vault-id <id> \
     --vault-relpath wiki/index.md \
     --output-file /tmp/terminology-<ts>.json
   ```

   `wiki/index.md` is a symbolic source — the actual work is
   vault-wide and the output is stdout.

8. **Summarize to the user**: total terms in glossary,
   N added this run, K inconsistencies flagged, top 3
   suggested actions.

## Pitfalls

- **No wiki/ directory** (memo mode vault). Tell user
  terminology-manager is wiki-mode specific.
- **Tens of thousands of candidates.** Cap at ~50 new terms per
  run; tell user to re-run.
- **`.oh-my-wiki/glossary.db` already exists.** Fine — that's
  the steady state. Just keep upserting.
