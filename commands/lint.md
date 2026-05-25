# `lint` — check vault health

**Mode:** memo or wiki
**Underlying script:** `scripts.lint.check`

## Preconditions

Active vault must exist.

## Flow

1. Call:

```bash
python3 -m scripts.lint --vault-id <id>
```

2. Parse the JSON report. Render to the user as three sections:
   - **Frontmatter issues** — group by `issue` (malformed_yaml, missing_field:X, tags_not_list, invalid_type).
   - **Drift — missing files** — registry rows pointing to deleted files.
   - **Drift — mtime mismatch** — files edited outside wiki-wizard.

3. If `auto_fix_hints` is non-empty, list each hint as a suggested next action. Do NOT auto-apply fixes in Plan B; just print the hint.

## Post-conditions

- No state mutation. Read-only report.

## Error handling

- Active vault is None → suggest `vault-use`.
