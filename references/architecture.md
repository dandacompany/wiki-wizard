# Architecture

oh-my-wiki adapts Andrej Karpathy's "LLM Wiki" proposal (2026-04-04 gist) into a distributable Agent Skill.

## Three layers per vault (Karpathy-faithful)

- **Raw** — immutable source material. LLM reads only.
- **Wiki** — LLM-compiled markdown. Summaries, entity pages, concept pages, comparisons, syntheses. The LLM owns this layer.
- **Schema** — the rules governing how Raw becomes Wiki. In oh-my-wiki this is `SKILL.md` + `commands/*.md`.

memo-only vaults skip Raw and treat topic folders as the only layer (keeps the existing `memo` skill UX).

## Skill-side architecture (Option B)

```
SKILL.md          ← dispatcher (loaded every invocation)
  │
  ├─ scripts/wizard.py status   ← reads registry, returns JSON
  │
  └─ commands/<op>.md           ← one file per operation = per-op schema
        │
        └─ scripts/*.py         ← deterministic I/O
              │
              └─ ~/.omw/registry.db
```

Splitting per-op schemas into their own files is deliberate. It mirrors Karpathy's "schema document" principle and lets the LLM load only the workflow it needs.

## Adapter layer

Storage backends sit behind `adapters.py`. v1 ships two:

- `MarkdownAdapter` — works with any editor; standard markdown links.
- `ObsidianAdapter` — wikilinks (`[[target]]`), `obsidian://` open URI, requires `.obsidian/`.

v2 adds `adapters/` directory shape for `logseq`, `hugo`, etc. The contract is documented in `adapter-spec.md`.
