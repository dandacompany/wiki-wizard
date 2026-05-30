# persona-librarian

Run the **wiki-librarian** persona to propose structural fixes (cross-links,
orphan resolution, merges). Reads the F#1 link graph first; prints JSON
proposals to stdout. No file changes until you confirm.

## When to invoke

User says: "tidy the wiki structure", "what's orphaned?", "suggest cross-links",
"위키 구조 정리해줘".

## Procedure

1. **Show the persona spec** (`personas/wiki-librarian.md`).
2. **Gather the deterministic link graph** for the active vault:
   ```bash
   python3 -c "
   from scripts.paths import registry_path
   from scripts import links, registry
   import json
   db = registry_path(); vid = registry.get_active(db)['id']
   print(json.dumps({'orphans': links.orphans(db, vid), 'graph': links.graph(db, vid)}))
   "
   ```
   (If that one-liner is awkward, run `omw lint` and read its `links` section, which
   already contains `orphans`/`broken`.)
3. **Run the persona** with that JSON as input text:
   ```bash
   python3 -m scripts.personas run wiki-librarian \
     --text "<the links JSON + any focus note>" \
     --output-file /tmp/librarian-<ts>.json
   ```
4. **Show proposals and ask** which to apply (propose → confirm → execute).
5. **On confirm**, apply the chosen edits (add the `[[link]]`/markdown link, move
   a page to `.trash` for archive, etc.) and `python3 -m scripts.reindex --vault-id <id>`.
6. **Report** what changed.
