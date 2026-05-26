# persona-consistency

Run the **consistency-checker** persona to surface contradictions
within a doc or across a vault. JSON report to stdout.

## When to invoke

- "check this doc for contradictions"
- "any inconsistencies in my wiki?"
- "이 글에 모순 있어?"
- "위키 안에서 어긋난 부분 찾아줘"

## Inputs

- Single doc mode: `--text`, `--file`, or `--vault-relpath` + `--vault-id`
- Vault-wide mode: `--vault-id` only (no source)

## Procedure

1. **Show the persona spec.** Read `personas/consistency-checker.md`
   so the user sees the judgment categories.

2. **Pick the mode.** If a source was given → single_doc. If only
   `--vault-id` → vault_wide.

3. **For vault-wide mode**, first gather the candidate list:

   ```bash
   python3 -m scripts.wiki_lint --vault-id <id>
   ```

   The output contains `contradiction_candidates` — feed those to
   the persona body's judgment step.

4. **For single-doc mode**, read the source and look for
   contradiction patterns within it (same patterns
   wiki_lint uses: `is X` vs `is not X`, `supports X` vs
   `contradicts X`, etc.).

5. **Apply the persona's judgment.** For each candidate pair,
   classify as `confirmed` / `nuanced` / `false_positive`. Write
   a 1-2 sentence explanation per verdict.

6. **Emit JSON on stdout.** Follow the persona's "Output format"
   exactly. Run via:

   ```bash
   python3 -m scripts.personas run consistency-checker \
     --vault-id <id> \
     --vault-relpath <relpath>   # for single_doc; omit for vault_wide
     --output-file /tmp/consistency-<ts>.json
   ```

   For vault_wide, `--vault-relpath` is required for the runtime
   even if the LLM judges across many pages — pick the most
   relevant index page (e.g. `wiki/index.md`) as the symbolic
   source.

7. **Summarize to the user**: counts per category + the most
   important confirmed contradictions.

## Pitfalls

- **wiki_lint returned [].** Tell user there's nothing to judge.
- **Single-doc mode but doc is < 200 chars.** Probably nothing to
  contradict; tell user.
