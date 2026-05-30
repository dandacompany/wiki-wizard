# persona-curate-index

Run the **curator** persona to sync + reorder `wiki/index.md`. Reads the
deterministic `index_drift` report first; proposes a full rewritten index on
stdout. Nothing is written until you confirm.

## When to invoke

User says: "update the index", "the TOC is stale", "reorder the wiki index",
"목차 정리해줘".

## Procedure

1. **Show the persona spec** (`personas/curator.md`).
2. **Compute drift** for the active vault:
   ```bash
   python3 -c "
   from scripts.paths import registry_path
   from scripts import links, registry
   import json
   db = registry_path(); vid = registry.get_active(db)['id']
   print(json.dumps(links.index_drift(db, vid)))
   "
   ```
   (Or read `omw lint`'s `links.index_drift`.)
3. **Run the persona** with the drift JSON + the current index.md as input:
   ```bash
   python3 -m scripts.personas run curator \
     --vault-relpath wiki/index.md --vault-id <id> \
     --db "$(python3 -c 'from scripts.paths import registry_path; print(registry_path())')" \
     --output-file /tmp/curate-index-<ts>.md
   ```
   (output_kind stdout — capture the proposed index.)
4. **Show the proposed index.md and ask** to apply (propose → confirm → execute).
5. **On confirm**, write the proposed content to `wiki/index.md` and
   `python3 -m scripts.reindex --vault-id <id>`. Re-run the drift check to confirm
   `missing_from_index`/`dangling_in_index` are now empty.
6. **Report** the result.
