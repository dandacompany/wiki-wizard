# oh-my-wiki (OMW)

[![CI](https://github.com/dandacompany/oh-my-wiki/actions/workflows/ci.yml/badge.svg)](https://github.com/dandacompany/oh-my-wiki/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-6C5CE7)](https://github.com/dandacompany/oh-my-wiki#install)
[![skillsmp](https://img.shields.io/badge/skills.sh-oh--my--wiki-1abc9c)](https://skills.sh/)

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

## Writing personas (v2.2a)

Four reusable writing-agent personas live at `personas/<role>.md`. Each declares input/output contracts; the LLM follows the persona body when invoked, then the runtime files the output.

| Persona        | Op                  | Output                                            |
| -------------- | ------------------- | ------------------------------------------------- |
| **translator** | `persona-translate` | `<base>.<lang>.md` sibling                        |
| **polisher**   | `persona-polish`    | inplace (with `.trash/` backup)                   |
| **summarizer** | `persona-summarize` | stdout JSON (one_line / one_paragraph / detailed) |
| **scaffolder** | `persona-scaffold`  | `wiki/syntheses/<slug>.md` (draft status)         |

```text
"translate wiki/summaries/karpathy.md to Korean"
"polish this paragraph in Korean"
"summarize wiki/summaries/karpathy.md"
"scaffold an outline for: how attention enables parallel training"
```

CLI for manual control:

```bash
python3 -m scripts.personas list
python3 -m scripts.personas show translator
python3 -m scripts.personas run translator \
  --vault-relpath wiki/summaries/karpathy.md \
  --lang ko \
  --output-file ./translated.md
```

Persona definitions are plain markdown; add your own under `personas/` and they appear in `list` automatically (must pass the frontmatter schema).

## Review personas (v2.2b)

Three review personas lift drafts from "drafted" to "shippable":

- **fact-checker** — decomposes a doc into atomic claims, verifies each
  via Bright Data MCP web search, writes a sibling report at
  `<page>.factcheck.md` with verdict + confidence + sources per claim.
- **consistency-checker** — judges contradictions found by `wiki_lint`
  (single-doc or vault-wide) as `confirmed` / `nuanced` /
  `false_positive`. JSON to stdout.
- **terminology-manager** — extracts canonical terms with aliases and
  definitions into a per-vault glossary at
  `<vault>/.oh-my-wiki/glossary.db`. Flags inconsistent surface forms.
  JSON to stdout.

### Invoke

```text
fact-check this draft
check this for contradictions
build a glossary for my vault
```

### Glossary CLI

```bash
python3 -m scripts.glossary list --vault-root <vault> --vault-id 1
python3 -m scripts.glossary upsert --vault-root <vault> --vault-id 1 \
    --canonical "LLM" --alias "Large Language Model" --definition "..."
python3 -m scripts.glossary lint --vault-root <vault> --vault-id 1
```

## Dispatch + Teams (v2.3)

v2.3 adds a **dispatch runtime** that spawns persona workers into separate
tmux panes, each running its own AI backend (claude / codex / gemini / opencode).

**Prerequisites:** tmux >= 3.0 installed; at least one backend CLI authenticated.

### Example invocations

**Single dispatch** — send one persona to one backend:

```
> dispatch the fact-checker to review draft.md using codex
```

oh-my-wiki asks which model, whether to skip permissions, then runs:
`python3 -m scripts.dispatch --persona fact-checker --source draft.md --backend codex --model gpt-5-high`

**Explicit team** — name workers and backends inline:

```
> run a team: fact-checker on claude, consistency-checker on codex, on draft.md
```

**Template-based team** — use a shipped template:

```
> omw team-run review-pipeline --on draft.md
```

Spawns 3 parallel workers (fact-checker/claude, consistency-checker/codex,
terminology-manager/gemini). Leader waits for all done.json sentinels, then
reports output paths and durations.

### Form factors

| Form factor               | How to invoke                          | When to use            |
| ------------------------- | -------------------------------------- | ---------------------- |
| In-skill (default)        | Works within Claude Code automatically | Most users             |
| CLI shim (`omw-dispatch`) | `bin/omw-dispatch` on PATH             | Scripting / CI         |
| Docker                    | `docker/docker-compose.yml`            | Full backend isolation |

### Shipped team templates

| Template               | Mode       | Workers                                                                                     |
| ---------------------- | ---------- | ------------------------------------------------------------------------------------------- |
| `review-pipeline`      | parallel   | fact-checker (claude) + consistency-checker (codex) + terminology-manager (gemini)          |
| `translation-pipeline` | sequential | translator (claude) -> polisher (gemini)                                                    |
| `draft-to-publish`     | mixed      | scaffolder (codex) -> polisher (claude) -> [fact-checker + consistency-checker] in parallel |

## Swarm protocol (v2.4)

Workers can now talk to each other during execution via a file-based message
bus (`scripts/swarm.py`). No sockets, no MCP — pure file I/O accessible from
any backend CLI.

### Invocation examples

**Triple fact-check with moderator consensus**

```
omw team-run triple-factcheck-moderator on my-draft.md
```

Three fact-checker workers (claude / codex / gemini) each verify the document
independently and publish their findings to `topic: claim`. A moderator worker
reads all three, initiates a vote on contested claims, and writes a consensus
report with a dissent table.

**Polish + fact-check loop**

```
omw team-run polish-factcheck-loop on my-draft.md
```

A scaffolder produces an initial draft; a polisher refines it and sends it to
a fact-checker via swarm RPC. The fact-checker responds "OK" or "issues found:
...". The polisher iterates up to `max_iterations` (default: 3) times before
finalizing.

**Multi-perspective synthesis**

```
omw team-run perspective-synthesis-team on my-topic.md
```

Three perspective-writers draft the same topic from beginner, expert, and
skeptic viewpoints in parallel. A moderator weaves the three drafts into a
single layered document with `[for: audience]` annotations.

**Live swarm dashboard**

```
omw swarm-monitor
```

Or during any swarm-team dispatch, from your leader session, call
`omw swarm-monitor` to see a real-time table of worker heartbeats, inbox
depths, alive status, and session-wide message/vote/RPC counters.

### Swarm primitives

Workers coordinate via `python3 -m scripts.swarm <op>`:

| Op                                     | Purpose                                         |
| -------------------------------------- | ----------------------------------------------- |
| `send`                                 | Direct message to one peer                      |
| `broadcast`                            | Message all peers                               |
| `publish`                              | Tagged broadcast (alias with `--topic`)         |
| `inbox`                                | Read messages (filter by topic / unread)        |
| `heartbeat`                            | Update worker status (visible to `monitor`)     |
| `monitor`                              | Dashboard: all worker states + session counters |
| `rpc` / `rpc-respond`                  | Synchronous request–response with timeout       |
| `vote-create` / `vote` / `vote-result` | Majority-vote consensus                         |

Swarm activates only for teams with `swarm: true` in their manifest.
Existing teams (`swarm: false` default) are unaffected.

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
