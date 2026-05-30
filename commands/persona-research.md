# persona-research

Run the **researcher** persona on a topic — produces a new wiki page draft
under `wiki/syntheses/`.

## When to invoke

User says: "research <topic>", "build a wiki page on <topic>", "<주제> 조사해서 위키로", etc.

## Inputs you need

- The topic (text) → `--text "<topic>"`.
- An active wiki-mode vault (`omw status`); the page is filed there.

## Procedure

1. **Show the persona spec.** Read `personas/researcher.md`; tell the user search
   uses MCP (in-session) or `omw search` (headless) and that output is a new page.
2. **Confirm the active vault** is wiki-mode (`omw status`). If memo-mode, suggest
   `omw vault use <wiki-vault>`.
3. **Research.** Follow the persona body: decompose → search (MCP or `omw search`)
   → read + confidence-tag → note gaps. (If a multi-round audit trail is wanted,
   the existing `commands/autoresearch.md` flow may be used to drive the rounds.)
4. **Draft** the page (title/body/tags/citations) to a temp file
   `/tmp/research-<ts>.md`.
5. **File as a new page:**
   ```bash
   python3 -m scripts.personas run researcher \
     --text "<topic>" --title "<page title>" \
     --vault-id <id> --db "$(python3 -c 'from scripts.paths import registry_path; print(registry_path())')" \
     --output-file /tmp/research-<ts>.md
   ```
   It writes `wiki/syntheses/<slug>.md`.
6. **Reindex:** `python3 -m scripts.reindex --vault-id <id>`.
7. **Report** the page relpath + confidence breakdown + suggested next step
   (`fact-check this`, or run the `research-to-wiki` team).
