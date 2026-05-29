# `query` — ask the wiki

**Mode:** memo or wiki (search works for both)
**Underlying scripts:** `scripts.search.query` (Plan A) + `scripts.query.write_synthesis` (Plan C, wiki only)

## Preconditions

Active vault must exist.

## Flow

1. **Take a query string from the user.**

2. **Run the search.**

   ```bash
   python3 -c "
   import json
   from scripts.paths import registry_path
   from scripts import search, registry
   db = registry_path()
   vault = registry.get_active(db)
   hits = search.query(db, vault_id=vault['id'], query='<query>', limit=5)
   print(json.dumps(hits, ensure_ascii=False, indent=2))
   "
   ```

3. **Read each hit's full file** to draft an answer with inline citations like `[summaries/tdd-paper](wiki/summaries/tdd-paper.md)`. Use absolute paths from `vault.path` to read.

4. **Present the answer.** Show the answer + citation list.

5. **Offer to file the answer back** (wiki-mode only). Ask: "File this as a new synthesis page? [Yes / No]". If Yes:

   ```bash
   python3 -c "
   from scripts.paths import registry_path
   from scripts import query, ingest, registry
   db = registry_path()
   vault = registry.get_active(db)
   rel = query.write_synthesis(
       db, vault_id=vault['id'],
       title='<synthesis title>',
       body='<answer body, lightly edited for standalone reading>',
       citations=['<rel1>', '<rel2>'],
       tags=['<t1>','<t2>'],
       date_str='2026-05-25',
   )
   ingest.update_index(
       db, vault_id=vault['id'],
       entries=[('syntheses', '<slug>', '<oneliner>')],
   )
   ingest.append_log(
       db, vault_id=vault['id'],
       op='synthesis', title='<synthesis title>', date_str='2026-05-25',
   )
   print(rel)
   "
   ```

6. **Reindex** if a synthesis was filed:

   ```bash
   python3 -c "
   from scripts.paths import registry_path
   from scripts import reindex, registry
   db = registry_path()
   vault = registry.get_active(db)
   reindex.incremental(db, vault_id=vault['id'])
   "
   ```

## Post-conditions

- Read-only unless the user opted to file a synthesis.
- If filed: new page under `wiki/syntheses/`, updated `wiki/index.md` and `wiki/log.md`.

## Error handling

- Zero hits → suggest relaxing terms or running `lint` (index drift).
- Memo-mode vault → file-back is wiki-only; still show the answer + citations.
