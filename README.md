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

## License

MIT
