# `lint` — check vault health

**Mode:** memo or wiki
**Underlying scripts:** `scripts.lint.check` (always) + `scripts.wiki_lint.check` (wiki only)

## Preconditions

Active vault must exist.

## Flow

1. Determine the active vault's mode:

   ```bash
   python3 -c "
   from scripts.paths import registry_path
   from scripts import registry
   db = registry_path()
   vault = registry.get_active(db)
   print(vault['mode'], vault['id'])
   "
   ```

2. Always run the common report:

   ```bash
   python3 -m scripts.lint --vault-id <id>
   ```

3. If `vault.mode == "wiki"`, also run the wiki-structural report:

   ```bash
   python3 -c "
   import json
   from scripts.paths import registry_path
   from scripts import wiki_lint
   db = registry_path()
   report = wiki_lint.check(db, vault_id=<id>)
   print(json.dumps(report, ensure_ascii=False, indent=2))
   "
   ```

4. Render to the user:

   **Common (always):**
   - **Frontmatter issues** — grouped by `issue` (malformed_yaml, missing_field:X, tags_not_list, invalid_type)
   - **Drift — missing files** — registry rows for deleted files
   - **Drift — mtime mismatch** — files edited outside oh-my-wiki

   **Wiki structural (wiki-mode only):**
   - **Orphan pages** — wiki pages older than 7 days with no inbound links
   - **Missing concepts** — `[[slug]]` referenced by ≥2 pages but no page at `wiki/entities/<slug>.md` or `wiki/concepts/<slug>.md`
   - **Empty data** — wiki pages with <50 char body OR >50% placeholder lines
   - **Dangling links** — markdown links `[text](./path.md)` pointing to non-existent files

5. If `auto_fix_hints` from the common report is non-empty, list each hint. Do NOT auto-apply fixes in Plan C; print them as suggestions.

## Post-conditions

- Read-only.

## Error handling

- Active vault is None → suggest `vault-use`.
- `wiki_lint` on a memo-mode vault is skipped (not an error — the dispatcher uses mode to gate it).

### v2.0 candidate categories (LLM-judged where indicated)

When `vault.mode == "wiki"`, the structural report from `wiki_lint.check` now includes four additional candidate categories. Two are deterministic; two require a final LLM judgment.

**Deterministic (render as-is):**

- **Link bidirectionality gaps** — page A links to B, B does not link back, and both A and B live in the same `entities/` or `concepts/` layer. Render as a list of `(source → target)` pairs.
- **Terminology drift candidates** — two existing slugs with similarity ≥ 0.85 are referenced from the same source page. Render slug pairs with similarity and the co-referencing page(s).

**LLM-judged (the script emits _candidates_; you decide the verdict):**

- **Contradiction candidates** — two pages share an entity reference and contain opposing-verb lexicon (`is faster` ↔ `is not faster`, etc.). For each candidate, read both pages and decide:
  - `confirmed` — they do contradict; recommend the user reconcile
  - `nuanced` — same claim under different conditions, not a real contradiction
  - `false_positive` — the lexicon hit was coincidental

  Render with your verdict + a one-sentence explanation.

- **Stale claim candidates** — pages older than 180 days containing phrases like `currently`, `as of`, or `the latest`. For each candidate, decide:
  - `likely_stale` — the time-sensitive phrasing is outdated; suggest the user re-verify
  - `still_valid` — the claim happens to still hold
  - `false_positive` — the phrase isn't actually a time-sensitive claim

  Render with your verdict + a one-sentence explanation.

Do NOT auto-edit pages in v2.0. Print verdicts as suggestions; let the user apply fixes via `edit` or `ingest`.

## Notes for v2.1+

Per-vault autoresearch sessions are stored under `<vault>/.oh-my-wiki/sessions/<ts>-<slug>/` and are gitignored by default. `lint` does not currently inspect or clean them — see `python3 -m scripts.autoresearch status --session-dir <DIR>` for one-off inspection.
