# persona-memo-curate

Run the **memo-curator** persona over a memo vault. Prints JSON proposals
(promote / retag / categorize) to stdout — no files change until you confirm.

## When to invoke

User says: "tidy my memos", "what memos should become wiki pages?", "메모 정리해줘".

## Inputs you need

- A memo page (`--vault-relpath <relpath> --vault-id <id>`) or a pasted digest (`--text`).

## Procedure

1. **Show the persona spec** (`personas/memo-curator.md`).
2. **Run the persona** to produce proposals:
   ```bash
   python3 -m scripts.personas run memo-curator \
     --vault-relpath <relpath> --vault-id <id> \
     --db "$(python3 -c 'from scripts.paths import registry_path; print(registry_path())')" \
     --output-file /tmp/memo-curate-<ts>.json
   ```
3. **Show proposals and ask** which to apply (propose → confirm → execute).
4. **On confirm**, perform the deterministic promotion (e.g. `ingest` the memo
   into the wiki vault) and `python3 -m scripts.reindex --vault-id <id>`.
5. **Report** what was promoted/retagged.
