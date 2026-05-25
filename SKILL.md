---
name: oh-my-wiki
description: Karpathy-style LLM Wiki with multi-vault sqlite registry and Socratic wizard. Manages multiple knowledge vaults (markdown or Obsidian). On invocation, infers user intent from registry state — first-time users get a setup wizard, returning users go straight to operations. Supports memo-mode (lightweight notes) and wiki-mode (Karpathy's raw/wiki/index/log pattern with ingest/query/lint). Trigger phrases — English "open my wiki", "ingest this", "find a note about X", "what does my wiki say about X"; Korean "위키 열어줘", "이거 정리해줘", "X 관련 노트 찾아줘", "위키에 물어봐". Also fires when the user pastes long-form content and asks to save it.
---

# oh-my-wiki

A storage-agnostic LLM Wiki skill. Implements Andrej Karpathy's three-layer pattern (Raw / Wiki / Schema) with hybrid `memo-only` and `wiki-mode` per vault. Operations live in `commands/*.md`. Deterministic I/O lives in `scripts/*.py`. State lives in `data/registry.db`.

## Plan A + B complete

Plan A delivered the dispatcher and foundation scripts. Plan B added vault management (`vault-setup`, `vault-use`, `vault-list`, `vault-forget`, `vault-import-memo`) and all memo-mode ops (`create`, `find`, `open`, `edit`, `move`, `delete`, `lint`). Plan C will add wiki-mode ops (`ingest`, `query`) and wiki-mode-specific lint checks.

## Step 1 — Read registry state

Always invoke this before doing anything else:

```bash
python3 -m scripts.wizard status
```

Parse the JSON output. Fields:

- `vault_count` (int)
- `active` (`null` or `{name, path, type, mode}`)
- `needs` (`"setup"` | `"select"` | `"op"`)
- `vaults` (array of `{name, mode}`)

## Step 2 — Route by `needs`

| `needs`    | Action                                                                                                                          |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `"setup"`  | Load `commands/vault-setup.md`.                                                                                                 |
| `"select"` | Load `commands/vault-use.md`.                                                                                                   |
| `"op"`     | Inspect the user's input. If it names an op explicitly, load that op's `commands/<op>.md`. Otherwise run the Op Wizard (below). |

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

| Keyword (EN / KO)                   | Op                  |
| ----------------------------------- | ------------------- |
| "ingest", "정리", "흡수"            | `ingest`            |
| "query", "물어봐", "찾아봐"         | `query`             |
| "find", "검색", "찾아줘"            | `find`              |
| "open", "열어줘"                    | `open`              |
| "edit", "수정", "편집"              | `edit`              |
| "move", "이동", "옮겨"              | `move`              |
| "delete", "삭제", "지워"            | `delete`            |
| "lint", "점검", "정리하기"          | `lint`              |
| "setup", "새 vault", "vault 만들기" | `vault-setup`       |
| "use", "vault 전환", "vault 바꿔"   | `vault-use`         |
| "list", "vault 목록"                | `vault-list`        |
| "forget", "vault 제거"              | `vault-forget`      |
| "import memo", "memo 가져오기"      | `vault-import-memo` |

## Pasted content heuristic

If the user pastes ≥ 200 characters without naming an op:

- `active.mode == "memo"` → suggest `create`
- `active.mode == "wiki"` → suggest `ingest`

Always confirm before writing. Show the proposed slug + destination first.

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
