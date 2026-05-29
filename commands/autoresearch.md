# `autoresearch` — multi-round web research with file-back

**Mode:** wiki (rejected on memo vaults)
**Underlying script:** `scripts.autoresearch` (subcommands: init / record / should-stop / status / file-back)
**External tools used:** Bright Data MCP (`mcp__brightdata__search_engine`, `mcp__brightdata__scrape_as_markdown`) per CLAUDE.md.

## Preconditions

Active vault must be wiki-mode. Run `python3 -m scripts.wizard status` first. If active vault is memo-mode, suggest `vault-use <wiki-vault>` or `vault-setup` to create one.

If Bright Data MCP is unavailable, fall back to user-pasted source content for each claim.

## Flow

### Step 1 — Initialize the session

Get the user's research question. Then:

```bash
python3 -m scripts.autoresearch init \
  --query "<the user's question>"
```

Parse the JSON output:

```json
{
  "session_id": "20260526-204500-...",
  "session_dir": "/.../sessions/...",
  "max_rounds": 3
}
```

Tell the user: "Session started: <session_id>. Up to <max_rounds> rounds."

### Step 2 — Round loop

For `round_num` in 1, 2, ... up to `max_rounds`:

**(a) Decompose.** For round 1, break the original query into 3–6 atomic claims (testable statements). For round 2+, focus on `gaps_remaining` from the previous round.

**(b) Search.** For each claim, invoke Bright Data MCP:

```text
mcp__brightdata__search_engine(query=..., engine="google")
mcp__brightdata__scrape_as_markdown(url=...)   # for deep reads
```

If multiple claims share search terms, batch via `mcp__brightdata__search_engine_batch`.

**(c) Read + judge.** For each claim, read the returned sources and decide a confidence tag:

- **high** — multiple independent reputable sources agree
- **medium** — single strong source or multiple weak sources agreeing
- **low** — conflicting sources, weak source only, or no source found

**(d) Detect gaps.** Identify gaps that need another round (claims you could not resolve, follow-up questions raised by sources, contradicting evidence to reconcile). Plain-English strings.

**(e) Record the round:**

```bash
python3 -m scripts.autoresearch record \
  --session-dir <session_dir> \
  --round <round_num> \
  --claims-json '[{"claim":"...","confidence":"high","sources":["..."]}, ...]' \
  --gaps-json '["...", "..."]' \
  --notes "<optional free-form notes for self/next round>"
```

**(f) Check stop:**

```bash
python3 -m scripts.autoresearch should-stop --session-dir <session_dir>
```

If `{"stop": true, ...}` → break loop. Otherwise continue to round_num+1.

### Step 3 — Compose synthesis

Read all `round-*.json` files. Compose a synthesis page:

- **Title** — a short noun phrase summarizing the answer
- **Body** — ordered narrative answer with inline citations like `[per-claim summary](source-url)`; group claims by topic; explicitly note any `low`-confidence claims as "uncertain"
- **Tags** — 2–5 nouns
- **Citations list** — flat array of all source URLs/strings used

Show the draft to the user. Ask: "File this synthesis to wiki/syntheses/? [Yes / No / Edit]". On "Edit", revise. On "No", stop without filing (session dir still persists for replay). On "Yes" → Step 4.

### Step 4 — File back

Write the body to a temp file (to avoid CLI length issues):

```bash
tmp_body=$(mktemp)
cat > "$tmp_body" <<'BODY'
<the synthesis body>
BODY
```

Then:

```bash
python3 -m scripts.autoresearch file-back \
  --session-dir <session_dir> \
  --title "<synthesis title>" \
  --body-file "$tmp_body" \
  --citations-json '["url1", "url2", ...]' \
  --tags-json '["tag1", "tag2"]' \
  --date 2026-05-26
```

Output is the synthesis page relpath (e.g. `wiki/syntheses/why-attention-beats-rnn.md`).

Run incremental reindex so search picks up the new page:

```bash
python3 -c "
from scripts.paths import registry_path
from scripts import reindex, registry
db = registry_path()
vault = registry.get_active(db)
reindex.incremental(db, vault_id=vault['id'])
"
```

### Step 5 — Report

Tell the user:

- The synthesis page relpath
- Rounds completed and stop reason
- Confidence breakdown (high/medium/low counts)
- Optional next steps: `lint` to check vault health; `find <topic>` to verify the page surfaces in search; `ingest` if new sources discovered during research warrant their own raw entries.

## Post-conditions

- A new file at `wiki/syntheses/<slug>.md` with valid frontmatter (`type: synthesis`, `citations: [...]`).
- `wiki/index.md` updated with a new entry under `## Syntheses`.
- `wiki/log.md` appended with `## [YYYY-MM-DD] autoresearch | <title>`.
- Session dir at `.oh-my-wiki/sessions/<session_id>/` with `mission.json`, `round-*.json`, `filed.json` (replayable audit trail).

## Error handling

- Active vault is memo-mode → init raises `VaultError`. Suggest `vault-use <wiki-vault>` or `vault-setup`.
- Bright Data MCP unavailable → fall back to asking the user to paste source content for each claim.
- User aborts on the "File this?" prompt → leave the session dir intact (it's small JSON; useful for later resume). Do not call file-back.
- File-back called twice on the same session → idempotent; returns the prior relpath without re-writing.
