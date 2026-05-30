# persona-audit

Run the **wiki-auditor** persona for a health audit of the active wiki vault.
Reads `lint.check` (incl. links broken/orphans/index_drift); prints a
prioritized audit to stdout. Read-only.

## When to invoke

User says: "audit the wiki", "is my wiki healthy?", "what needs maintenance?",
"위키 점검해줘".

## Procedure

1. **Show the persona spec** (`personas/wiki-auditor.md`).
2. **Run the deterministic lint** for the active vault:
   ```bash
   omw lint
   ```
   (or `python3 -c "from scripts.paths import registry_path; from scripts import lint, registry; import json; db=registry_path(); print(json.dumps(lint.check(db, vault_id=registry.get_active(db)['id'])))"`)
3. **Run the persona** with that lint JSON as input:
   ```bash
   python3 -m scripts.personas run wiki-auditor \
     --text "<lint JSON>" --output-file /tmp/audit-<ts>.md
   ```
4. **Report** the prioritized audit and suggest the `vault-maintenance` team
   (auditor → librarian → curator) to act on it.
