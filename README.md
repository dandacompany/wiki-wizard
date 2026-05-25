# wiki-wizard

> Karpathy-style LLM Wiki as a multi-vault Agent Skill, with a Socratic setup wizard.

**Status:** Plan A (Foundation) complete. Commands and adapters extend in Plans B and C.

## Concept

An LLM agent that maintains a persistent, interlinked Markdown wiki for you. Instead of re-deriving answers from raw sources every time, it compiles them into a knowledge base that compounds. Inspired by [Andrej Karpathy's LLM Wiki gist (2026-04)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Two modes per vault:

- **memo-mode** — lightweight note-taking (Obsidian-friendly).
- **wiki-mode** — Karpathy's `raw/` + `wiki/` + `index.md` + `log.md` structure with `ingest`, `query`, and `lint`.

## Install

```bash
skills add dandacompany/dante-skills@wiki-wizard -g -y --copy -a claude-code
```

(Available after Plan C ships.)

## Quick start

(Filled in during Plan C.)

## Architecture

See `references/architecture.md` for the three-layer design and adapter contract.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e ".[dev]"
pytest
```

## Plan B — Vault management + memo-mode ops

After Plan A's foundation, Plan B adds:

- **Vault management** — `vault-setup`, `vault-use`, `vault-list`, `vault-forget`, `vault-import-memo`
- **memo-mode ops** — `create`, `find`, `open`, `edit`, `move`, `delete`
- **Common health** — `lint` (frontmatter validity + sqlite↔disk drift)

### Quick start

```
# 1. Set up a fresh memo vault
# (in Claude Code with this skill loaded)
"vault-setup name=daily path=~/notes/daily mode=memo type=markdown"

# 2. Capture a memo by pasting content
"<paste long content>"
# → wizard proposes title/folder/tags, you confirm.

# 3. Find it later
"find karpathy"

# 4. Open in your editor
"open inbox/karpathy-llm-wiki.md"

# 5. Check vault health
"lint"
```

### Migrating an existing /memo folder

```
"vault-import-memo path=/Volumes/DanteStorage/Obsidian/memo name=legacy"
```

The skill registers the folder, then offers a **dry-run** of frontmatter normalization (adds missing `type`/`date`/`tags`, converts string tags to lists). Pre-images are backed up to `.trash/` before any change.

### What's not in Plan B

`ingest`, `query`, and wiki-mode-specific lint checks land in Plan C.

## License

MIT
