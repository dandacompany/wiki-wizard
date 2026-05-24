# Vault modes

A vault is either `memo` or `wiki` (chosen at `vault-setup` time, stored in `vaults.mode`).

| Aspect | memo-mode | wiki-mode |
|--------|-----------|-----------|
| Directory layout | Topic folders + `inbox/` + `.trash/` | `raw/` + `wiki/` (+ `summaries`, `entities`, `concepts`, `comparisons`, `syntheses`) + `wiki/index.md` + `wiki/log.md` + `.trash/` |
| Ingest concept | Each note is self-contained | New source goes to `raw/`, then LLM updates 10–15 wiki pages |
| Query | Search returns notes | Search reads pages and may file the answer back as a new synthesis |
| Lint | None (Plan A/B) | Contradictions, stale claims, orphans, missing concepts, empty data |
| Best for | Casual note-taking, journaling | Research, deep knowledge bases |

Switching mode after creation is not supported in v1. Workaround: register the same path as a second vault with a different mode (sqlite will refuse the duplicate path — adjust path or create a sibling).
