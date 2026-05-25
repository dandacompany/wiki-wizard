# `lint` — check vault health

**Mode:** memo or wiki
**Underlying scripts:** `scripts.lint.check` (always) + `scripts.wiki_lint.check` (wiki only)

## Preconditions

Active vault must exist.

## Flow

1. Determine the active vault's mode:

   ```bash
   python3 -c "
   from pathlib import Path
   from scripts import registry
   db = Path('data/registry.db')
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
   from pathlib import Path
   from scripts import wiki_lint
   db = Path('data/registry.db')
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
