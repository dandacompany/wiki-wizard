# persona-factcheck

Run the **fact-checker** persona over a document. Produces a sibling
markdown report at `<stem>.factcheck.md`.

## When to invoke

User says any of:

- "fact-check this"
- "verify the claims in <page>"
- "check the facts on <doc>"
- "팩트체크해줘"
- "이 글 사실 확인해줘"

## Inputs you need from the user

One of:

- Inline text → use `--text`
- File path → use `--file`
- Vault page → use `--vault-id <id> --vault-relpath <relpath>`

## Procedure

1. **Show the persona spec.** Read `personas/fact-checker.md` and
   show the user the capabilities + output format so they know what
   they're getting.

2. **Identify the source.** Confirm the source (text/file/vault page)
   and the active vault if applicable.

3. **Decompose + verify.** Follow the fact-checker persona body's
   protocol: decompose into atomic claims, call
   `mcp__brightdata__search_engine` per claim (max 3 searches),
   judge verdict + confidence, collect source URLs.

4. **Draft the markdown report** following the persona's "Output
   format" template. Write it to a temp file
   (e.g., `/tmp/factcheck-<timestamp>.md`).

5. **File the report** by running:

   ```bash
   python3 -m scripts.personas run fact-checker \
     --file <source-path>   # or --vault-relpath + --vault-id
     --suffix factcheck \
     --output-file /tmp/factcheck-<ts>.md
   ```

   The script writes `<stem>.factcheck.md` next to the source.

6. **Reindex if the source is in a vault.** Run:

   ```bash
   python3 -m scripts.reindex --vault-id <id>
   ```

7. **Report to the user.** Print the report path + a 3-line summary
   (supported / contradicted / unverifiable counts).

## Common pitfalls

- **Source is `--text` (no origin).** sibling_suffix needs an
  origin path. If user gave only text, write the report to a
  filename they specify or to `/tmp/`. Don't try to file it
  back to a vault that wasn't named.
- **MCP not available.** If `mcp__brightdata__search_engine` is
  unavailable, tell the user and offer to run with reduced rigor
  (mark every claim "unverifiable — search unavailable").
- **Source is huge (1000+ claims candidates).** Ask the user to
  scope (a section, a heading) before burning the search budget.
