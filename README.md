# oh-my-wiki (OMW)

A Karpathy-style LLM Wiki skill that captures sources, builds a structured wiki out of them, and answers queries with proper citations.

**Status:** v1 (Plans A + B + C) is complete. The skill is production-ready for single-user workflows. v2 is in progress — see [docs/superpowers/specs/2026-05-25-oh-my-wiki-v2-master-design.md](./docs/superpowers/specs/2026-05-25-oh-my-wiki-v2-master-design.md) for the phased roadmap.

**Short alias:** `OMW` (lowercase `omw`). Both `oh-my-wiki` and `omw` register as skills and respond to the same trigger phrases. Use whichever is more convenient.

**Tutorial:** Walk through real Claude Code and Codex dialogs in [TUTORIAL.md](./TUTORIAL.md) (English) or [TUTORIAL.ko.md](./TUTORIAL.ko.md) (한국어).

<!-- TODO: record ingest demo GIF and add: ![ingest demo](docs/demos/ingest.gif) -->

## Why

Memos rot, but wikis compound. oh-my-wiki implements the workflow Karpathy laid out in his "LLM Wiki" Gist. Every source becomes a `raw/` snapshot, a `wiki/summaries/` page, and 10 to 15 entity and concept page touches. Queries pull from this structured wiki rather than a flat file dump, so answers can cite specific pages. The act of querying tends to produce new syntheses, which file themselves back into the wiki and close the loop.

## Architecture

```
SKILL.md dispatcher → commands/<op>.md (LLM procedure) → scripts/<op>.py (deterministic I/O)
                                                       └─ registry.py → data/registry.db (sqlite)
                                                       └─ adapters.py → filesystem (markdown / obsidian)
```

The skill exposes 11 user-facing ops:

| Mode   | Ops                                                                               |
| ------ | --------------------------------------------------------------------------------- |
| Vault  | `vault-setup` · `vault-use` · `vault-list` · `vault-forget` · `vault-import-memo` |
| memo   | `create` · `find` · `open` · `edit` · `move` · `delete`                           |
| wiki   | `ingest` · `query`                                                                |
| Common | `lint`                                                                            |

## Install

### Via Claude Code plugin marketplace (recommended)

In any Claude Code session:

```
/plugin marketplace add dandacompany/oh-my-wiki
/plugin install oh-my-wiki@oh-my-wiki-marketplace
```

This wires the skill + hooks + commands in one shot. Update later with `/plugin marketplace update oh-my-wiki-marketplace`.

### Via clone + bin/install.sh (developers, Codex CLI users)

```bash
git clone https://github.com/dandacompany/oh-my-wiki
cd oh-my-wiki
bash bin/install.sh --dev
```

The installer:

1. Checks for Python 3.10+.
2. Runs `pip install -e ".[dev]"` (drop `--dev` to skip pytest/ruff).
3. Creates `~/.claude/skills/oh-my-wiki` and `~/.claude/skills/omw` symlinks (idempotent).
4. Runs `pytest -q` to verify the install on your machine.
5. Prints next steps and trigger phrases.

It is safe to re-run. Use `--force` to replace pre-existing symlinks without a prompt, and `--no-test` to skip the verification step. Run `bash bin/install.sh --help` for all flags.

After installation, both `oh-my-wiki` and `omw` appear in the Claude Code skill list and resolve to the same dispatcher.

### Uninstall

```bash
bash bin/uninstall.sh           # remove symlinks (keep pip package)
bash bin/uninstall.sh --pip     # also pip uninstall oh-my-wiki
```

Your vaults and `data/registry.db` are never touched.

### Manual install (advanced)

If you prefer to wire things yourself:

```bash
pip install -e ".[dev]"
ln -s "$PWD" ~/.claude/skills/oh-my-wiki
ln -s "$PWD/omw" ~/.claude/skills/omw
pytest -v
```

## Quick start (memo vault)

```text
"vault-setup name=daily path=~/notes/daily mode=memo type=markdown"
"<paste long content>"                  # → create proposes title/folder/tags
"find karpathy"
"open inbox/karpathy-llm-wiki.md"
"lint"
```

## Quick start (wiki vault)

```text
"vault-setup name=research path=~/notes/research mode=wiki type=markdown"
"ingest <paste of the article body>"    # → 7-step ingest flow
"ingest ~/Downloads/paper.pdf"          # → pypdf extraction + same flow
"query how does X relate to Y?"         # → cited answer, optional file-back
"lint"                                  # → common + 4 wiki structural checks
```

## Migrating an existing /memo folder

```text
"vault-import-memo path=~/Documents/old-notes name=legacy"
```

This registers the folder as a vault and then offers a **dry-run** of frontmatter normalization. Pre-images are backed up to `.trash/` before any file is written.

## What `lint` checks

**Common checks (both modes):**

- Frontmatter validity: the YAML parses, the required `title`, `date`, `type`, and `tags` fields are present, `type` is one of the valid values, and `tags` is a list.
- Drift between sqlite and disk: orphan rows, missing files, and mtime mismatches.

**Wiki-only checks:**

- Orphan pages with no inbound links, past the 7-day grace period.
- Missing concepts: `[[slug]]` referenced by two or more pages, but no page exists for it.
- Empty data: body shorter than 50 characters, or more than half of its non-blank lines are placeholders.
- Dangling markdown links.

## Hot cache (session continuity, v2.0)

Each session, oh-my-wiki reads `<active_vault>/wiki/hot.md` (wiki-mode) or `<active_vault>/hot.md` (memo-mode and other non-wiki modes) at SessionStart and refreshes it at SessionStop. The cache holds:

- Active vaults and their state
- Last 10 touched pages
- One-paragraph summary of the previous session

Cap: 2000 chars. Manual refresh: `python3 -m scripts.hot_cache --refresh`. Manual inspect: `python3 -m scripts.hot_cache --on-session-start`.

The SessionStart and SessionStop bindings live in `hooks/hooks.json` and are non-blocking — if the hook fails, Claude Code keeps going.

## Vault modes (v2.0)

`vault-setup` accepts 7 mode names:

- **memo** — flat `inbox/` for quick capture
- **wiki** — Karpathy three-layer (`raw/` + `wiki/{summaries,entities,concepts,comparisons,syntheses}/`)
- **personal** — `journal/ goals/ people/ health/`
- **book** — `chapters/ characters/ worldbuilding/ outlines/ drafts/`
- **business** — `meetings/ decisions/ clients/ vendors/ processes/`
- **github-codebase** — `modules/ apis/ decisions/ runbooks/ glossary/`
- **website** — `pages/ posts/ assets/ seo/ outlines/`

Every mode also gets `.trash/` for soft deletes and an `index.md` (or `wiki/index.md` + `wiki/log.md` for wiki mode).

## Autoresearch (v2.1)

Turn a question into a multi-round research loop that files the answer back into your wiki.

```text
"autoresearch how does attention enable parallel training compared to RNN?"
```

The skill:

1. Decomposes the question into 3–6 atomic claims.
2. For each claim, invokes Bright Data MCP for search + scrape.
3. Reads returned sources and assigns a confidence tag (high / medium / low).
4. Identifies remaining gaps and runs another round if any (default 3 rounds, hard cap 5).
5. Composes a synthesis page, shows it to you, asks before filing.
6. On approval, writes `wiki/syntheses/<slug>.md`, updates `wiki/index.md`, appends `wiki/log.md`.

Session state lives at `<vault>/.oh-my-wiki/sessions/<ts>-<slug>/` (mission.json, round-\*.json, filed.json). Gitignored — never committed.

CLI for manual control:

```bash
python3 -m scripts.autoresearch init --query "..." --max-rounds 3
python3 -m scripts.autoresearch record --session-dir DIR --round 1 \
  --claims-json '[...]' --gaps-json '[...]'
python3 -m scripts.autoresearch should-stop --session-dir DIR
python3 -m scripts.autoresearch status --session-dir DIR
python3 -m scripts.autoresearch file-back --session-dir DIR \
  --title "..." --body-file ./body.md --citations-json '[...]' \
  --tags-json '[...]' --date 2026-05-26
```

## Storage

- The vault registry lives at `data/registry.db` as a per-user sqlite database (gitignored).
- The note index is regenerated by `scripts/reindex.py` after every mutation.
- Your files stay in the vault path you chose. oh-my-wiki never touches them outside the op you explicitly invoked.

## Development

- `pytest -v` runs all tests.
- `ruff check scripts/ tests/` runs the linter.
- `python3 -m scripts.wizard status` inspects the dispatcher state.
- `python3 -m scripts.lint --vault-id N` runs the health check on a specific vault.

Continuous integration runs on GitHub Actions, across a matrix of Python 3.10, 3.11, and 3.12 on both ubuntu-latest and macos-latest.

## License

Released under the MIT License. See [LICENSE](./LICENSE) for the full text.
