---
name: oh-my-wiki
description: Karpathy-style LLM Wiki with multi-vault sqlite registry and Socratic wizard. Also addressable by the short alias OMW. Manages multiple knowledge vaults (markdown or Obsidian). On invocation, infers user intent from registry state — first-time users get a setup wizard, returning users go straight to operations. Supports memo-mode (lightweight notes) and wiki-mode (Karpathy's raw/wiki/index/log pattern with ingest/query/lint). Trigger phrases — English "open my wiki", "ingest this", "find a note about X", "what does my wiki say about X", "omw", "use omw", "/omw"; Korean "위키 열어줘", "이거 정리해줘", "X 관련 노트 찾아줘", "위키에 물어봐", "오엠더블유", "오엠더블유 켜줘". Also fires when the user pastes long-form content and asks to save it.
---

# oh-my-wiki (OMW)

A storage-agnostic LLM Wiki skill. Implements Andrej Karpathy's three-layer pattern (Raw / Wiki / Schema) with hybrid `memo-only` and `wiki-mode` per vault. Operations live in `commands/*.md`. Deterministic I/O lives in `scripts/*.py`. State lives in the global registry `~/.omw/registry.db` (override the root with `OMW_HOME`). Vault content lives at each vault's registered path.

**Short alias:** `OMW` (lowercase `omw`). Both `oh-my-wiki` and `omw` resolve to this skill.

## Current status — v1 shipped, v2 in progress

v1 (Plans A + B + C) is complete: dispatcher + foundation scripts, vault management (`vault-setup`, `vault-use`, `vault-list`, `vault-forget`, `vault-import-memo`), memo-mode ops (`create`, `find`, `open`, `edit`, `move`, `delete`), wiki-mode ops (`ingest`, `query`), and the common `lint` op (with wiki-mode structural extensions). 91 pytest tests pass on GitHub Actions matrix (Python 3.10/3.11/3.12 × ubuntu/macos). See `README.md`, `TUTORIAL.md`, `TUTORIAL.ko.md` for usage.

v2 (in progress) adds plugin-marketplace install, session hot cache, 6 vault-setup modes, extended wiki-lint categories, autoresearch, writing-agent personas (translator / polisher / summarizer / scaffolder / fact-checker / consistency-checker / terminology-manager), tmux-based multi-agent orchestration, and a file-based swarm message protocol. See `docs/superpowers/specs/2026-05-25-oh-my-wiki-v2-master-design.md` for the phased roadmap.

## Step 1 — Read registry state

Always invoke this before doing anything else:

> **Command interface — read this first.** omw has exactly two ways to run things,
> and NO standalone script CLIs. Do **not** invent filenames like `omw_db.py`,
> `vault.py`, `cli.py`, or `bootstrap.py` — they do not exist.
>
> 1. **Deterministic ops** (status, vault management, lint, search, serve, schema, supersede): run the
>    `omw` CLI — `omw status`, `omw vault list`, `omw vault create <name> --mode wiki`,
>    `omw vault use <name>`, `omw lint`, `omw schema list`, `omw supersede <relpath> --by <slug>`,
>    `omw serve` (the retrieve-only messenger query API — see `references/messenger-api.md`).
>    Page-type conventions (required frontmatter fields + sections) live in `schemas/<type>.yml`;
>    a vault may override or add types via `<vault>/schemas/` (inspect with `omw schema show <type>`).
>    Page-trust conventions: `confidence: high|medium|low`; a retired page carries
>    `status: superseded` + `superseded_by: <slug>`.
> 2. **Reasoning ops** (ingest, query, autoresearch, personas, …): read the exact
>    procedure in `commands/<op>.md` and run its inline `python3 -c` snippet /
>    `python3 -m scripts.<module>` commands verbatim. Never guess a script path.

```bash
python3 -m scripts.wizard status
```

Parse the JSON output. Fields:

- `vault_count` (int)
- `active` (`null` or `{name, path, type, mode}`)
- `needs` (`"setup"` | `"select"` | `"op"`)
- `vaults` (array of `{name, mode}`)

## Step 2 — Route by `needs`

| `needs`     | Action                                                                                                                          |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `"setup"`   | Load `commands/vault-setup.md`.                                                                                                 |
| `"select"`  | Load `commands/vault-use.md`.                                                                                                   |
| `"migrate"` | Load `commands/migrate.md`.                                                                                                     |
| `"op"`      | Inspect the user's input. If it names an op explicitly, load that op's `commands/<op>.md`. Otherwise run the Op Wizard (below). |

For deterministic vault management you may call the `omw` CLI directly (e.g.
`omw vault list`); for content ops always load `commands/<op>.md` and follow it.

## Step 3 — Op Wizard (when no op specified)

Use `AskUserQuestion` (max 4 options). The option set depends on `active.mode`:

### `memo` mode

1. New memo — paste content
2. Find memo — search
3. Open memo — launch in app
4. Manage — edit / move / delete

### `wiki` mode

1. Ingest — add a new source
2. Query — ask the wiki
3. Find — search existing pages
4. Maintain — lint / edit / delete

## Safety contracts

These hold across all commands. Each `commands/<op>.md` repeats the relevant ones.

- **Destructive ops always confirm**: `delete`, `vault-forget`, `--hard` deletes.
- **`vault-forget` never touches files** — only the registry row.
- **Inferred targets are stated**, then confirmed: "방금 작성한 X 메모 말씀이시죠?"
- **No silent fallbacks**: if a vault path is missing on disk, report it and stop. Don't auto-`forget`.
- **SMB-mounted vaults** (e.g. `/Volumes/...`): use `rsync -rlpt` rather than `cp`. Never `cp -a` on SMB.
- **Recommended option goes first** in any AskUserQuestion list and is suffixed with `(추천)` / `(recommended)`.

## Trigger-phrase routing hint

If the user input matches an op keyword, prefer that op over the wizard:

| Keyword (EN / KO)                                                               | Op                                                              |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| "ingest", "정리", "흡수"                                                        | `ingest`                                                        |
| "query", "물어봐", "찾아봐"                                                     | `query`                                                         |
| "find", "검색", "찾아줘"                                                        | `find`                                                          |
| "open", "열어줘"                                                                | `open`                                                          |
| "edit", "수정", "편집"                                                          | `edit`                                                          |
| "move", "이동", "옮겨"                                                          | `move`                                                          |
| "delete", "삭제", "지워"                                                        | `delete`                                                        |
| "lint", "점검", "정리하기"                                                      | `lint`                                                          |
| "setup", "새 vault", "vault 만들기"                                             | `vault-setup`                                                   |
| "use", "vault 전환", "vault 바꿔"                                               | `vault-use`                                                     |
| "list", "vault 목록"                                                            | `vault-list`                                                    |
| "forget", "vault 제거"                                                          | `vault-forget`                                                  |
| "import memo", "memo 가져오기"                                                  | `vault-import-memo`                                             |
| "autoresearch", "research this", "리서치", "조사"                               | `autoresearch`                                                  |
| "translate", "번역"                                                             | `persona-translate`                                             |
| "polish", "윤문", "다듬어줘"                                                    | `persona-polish`                                                |
| "summarize", "요약"                                                             | `persona-summarize`                                             |
| "scaffold", "초안", "outline"                                                   | `persona-scaffold`                                              |
| "fact-check this" / "팩트체크해줘"                                              | `persona-factcheck`                                             |
| "check for contradictions" / "모순 봐줘"                                        | `persona-consistency`                                           |
| "build a glossary" / "용어집 만들어줘"                                          | `persona-terminology`                                           |
| "omw", "OMW", "/omw", "오엠더블유"                                              | (alias for `oh-my-wiki`; routes through Step 1 wizard normally) |
| "hot-cache", "session cache", "캐시 상태"                                       | `hot-cache`                                                     |
| dispatch / 디스패치 / dispatch this                                             | `commands/dispatch.md`                                          |
| team / 팀 실행 / run a team                                                     | `commands/team.md`                                              |
| team-run / 병렬 검토 / team template                                            | `commands/team-run.md`                                          |
| "monitor the swarm" / "show worker status" / "스웜 모니터" / "워커 상태 보여줘" | `commands/swarm-monitor.md`                                     |
| "orchestrate" / "plan this" / "전체적으로 처리" / "계획 세워줘" / "워크플로"    | `commands/persona-orchestrate.md`                               |

### Hierarchical routing (multi-step requests)

The table above routes **single ops**. If a request spans **multiple lifecycle
stages**, names **≥2 ops**, or is a **broad multi-step goal** (e.g. "research X,
fact-check it, and organize it into the wiki"), route to
`commands/persona-orchestrate.md` instead: the **operations-orchestrator** persona
proposes an execution plan, you confirm it, then execute each step via that step's
own command/team. A single, clearly-named op keeps using its direct trigger above.

## Pasted content heuristic

If the user pastes ≥ 200 characters without naming an op:

- `active.mode == "memo"` → suggest `create`
- `active.mode == "wiki"` → suggest `ingest`

Always confirm before writing. Show the proposed slug + destination first.

`vault-setup` accepts these modes: `memo`, `wiki`, `personal`, `book`, `business`, `github-codebase`, `website`. See README "Vault modes (v2.0)" for the layout each one scaffolds.

## Resources

- `scripts/wizard.py` — status command (this file's entry oracle)
- `scripts/registry.py` — sqlite vault + notes CRUD
- `scripts/adapters.py` — MarkdownAdapter, ObsidianAdapter
- `scripts/reindex.py` — mtime-based incremental indexer
- `scripts/search.py` — weighted natural-language search
- `scripts/frontmatter.py` — safe YAML edits
- `scripts/slugify.py` — title → kebab-case slug
- `references/architecture.md` — three-layer design
- `references/schema-sqlite.md` — DB schema notes
- `references/vault-modes.md` — memo vs wiki behavioral matrix
- `references/wizard-flow.md` — full decision tree
- `references/socratic-dialog.md` — question tone and patterns
- `references/adapter-spec.md` — guide for adding new adapter types
- `references/frontmatter.md` — YAML field definitions
