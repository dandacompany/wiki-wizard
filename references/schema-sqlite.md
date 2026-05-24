# sqlite registry — schema notes

File: `data/registry.db`. gitignored. Created on first `wizard.py status` call.

## Tables

| Table | Purpose |
|-------|---------|
| `vaults` | One row per registered vault. `is_active` is database-constrained to a single row via partial unique index. |
| `notes` | Lightweight per-file index. `UNIQUE(vault_id, relpath)` enables upsert. |
| `tags` + `note_tags` | Many-to-many. Tag rows are interned (insert-or-ignore). |
| `schema_migrations` | Records applied migration versions. |

## Field constraints

- `vaults.type ∈ {markdown, obsidian}`
- `vaults.mode ∈ {memo, wiki}`
- `notes.layer ∈ {raw, wiki, memo, meta}`
- `notes.parse_error ∈ {0, 1}` — set to 1 when frontmatter is absent or malformed.

## Active vault invariant

```sql
CREATE UNIQUE INDEX idx_active_vault ON vaults(is_active) WHERE is_active = 1;
```

This pushes the invariant into the database. `set_active()` swaps in a single transaction so the index is never violated.

## Drift recovery

Filesystem and `notes` table can diverge if files are edited outside wiki-wizard. Recovery: `python3 -m scripts.reindex --vault <name>` (added in Plan B's `vault-use` follow-up, or invoke `reindex.full()` directly).

## v1.1 plan — FTS5

Add a virtual table:

```sql
CREATE VIRTUAL TABLE notes_fts USING fts5(
    title, summary, body,
    content='notes', content_rowid='id'
);
```

with triggers keeping it in sync on insert/update/delete.
