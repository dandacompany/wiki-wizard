# oh-my-wiki (OMW)

[![CI](https://github.com/dandacompany/oh-my-wiki/actions/workflows/ci.yml/badge.svg)](https://github.com/dandacompany/oh-my-wiki/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-6C5CE7)](https://github.com/dandacompany/oh-my-wiki#install)
[![skillsmp](https://img.shields.io/badge/skills.sh-oh--my--wiki-1abc9c)](https://skills.sh/)

A host-universal LLM-wiki you drive from your AI coding agent (Claude Code / Codex / Gemini).

oh-my-wiki exposes exactly two surfaces. The **`omw` CLI** handles deterministic ops — `omw setup`, `omw vault create`, `omw lint`, `omw schema list`, `omw supersede`, `omw review`, `omw links`, `omw fields`, `omw doctor` — with no LLM required. The **`omw` skill** brings natural-language reasoning inside your AI session: ingest, query, autoresearch, and personas. The model is _personas propose → you confirm → deterministic ops execute_, so every file change is auditable.

**Short alias:** `OMW` (lowercase `omw`). Both `oh-my-wiki` and `omw` register as skills and respond to the same trigger phrases.

**Tutorial:** Walk through real dialogs and verified CLI examples in [TUTORIAL.md](./TUTORIAL.md) (English) or [TUTORIAL.ko.md](./TUTORIAL.ko.md) (한국어).

---

## What's new in v3

- **Schemas** — 13 built-in page types (`omw schema list/show`), with per-vault overrides in `<vault>/schemas/`
- **Confidence + supersede** — `confidence` frontmatter field; `omw supersede` retires old pages cleanly
- **Review queue (SR)** — spaced-repetition via `omw review due` / `omw review done`
- **Web search** — `omw search` queries an external provider (brave/tavily/exa/…); `omw serve` exposes vault FTS5 as a local retrieve-only HTTP API on port 8765
- **Entity-linking** — `omw links suggest` / `omw links link` auto-inserts `[[slug|Name]]` references
- **Inline fields** — `omw fields` reads `key::` inline syntax alongside frontmatter
- **Korean matching** — Korean entity names with josa (`카르파시가`) are suggested and linked correctly

---

## Install

Choose whichever path fits your environment. After any path, run `omw doctor` to confirm everything is wired correctly.

### Path A — Skills CLI (recommended for Claude Code users)

```bash
skills add dandacompany/oh-my-wiki@oh-my-wiki -g -y --copy -a claude-code
```

This installs the skill into `~/.claude/skills/` and registers both the `oh-my-wiki` and `omw` short-alias skill names.

### Path B — Claude Code plugin marketplace

In any Claude Code session:

```
/plugin marketplace add dandacompany/oh-my-wiki
/plugin install oh-my-wiki@oh-my-wiki-marketplace
```

Update later with `/plugin marketplace update oh-my-wiki-marketplace`.

### Path C — git clone + install script (developers, Codex CLI users)

```bash
git clone https://github.com/dandacompany/oh-my-wiki
cd oh-my-wiki
bash bin/install.sh
```

The installer checks for Python 3.10+, pip-installs the package editable, creates `~/.claude/skills/oh-my-wiki` and `~/.claude/skills/omw` symlinks (idempotent), runs `pytest -q` to verify, and prints next steps. Add `--dev` to include pytest/ruff extras. Use `--force` to replace existing symlinks without a prompt; `--no-test` to skip the test step. Run `bash bin/install.sh --help` for all flags.

### Verify the install

```
omw doctor
```

```
omw home:   /Users/you/.omw  ok
registry:   /Users/you/.omw/registry.db  ok
  * demo (wiki/markdown) /Users/you/.omw/vaults/demo
```

---

## Quickstart (~60 seconds)

**Step 1 — Run the setup wizard**

```
omw setup
```

Follow the prompts to configure your first vault, search provider, and persona preferences. Accept the defaults for a fast start.

**Step 2 — Check status**

```
omw status
```

```json
{
  "vault_count": 0,
  "active": null,
  "needs": "setup",
  "vaults": []
}
```

**Step 3 — Create your first vault**

```
omw vault create demo --mode wiki
```

```json
{
  "created": "demo",
  "path": "~/.omw/vaults/demo",
  "mode": "wiki",
  "type": "markdown"
}
```

```
omw vault list
```

```json
[
  {
    "name": "demo",
    "path": "~/.omw/vaults/demo",
    "mode": "wiki",
    "type": "markdown",
    "is_active": true
  }
]
```

**Step 4 — Add a note (in your AI session)**

Open Claude Code (or Codex / Gemini) and say:

```
ingest this

Andrej Karpathy calls the LLM Wiki a "compounding knowledge artifact". Every
source gets saved verbatim to raw/, a summary lands at wiki/summaries/, and
the entities and concepts that appeared get their own pages. 10–15 page touches
per ingest is normal.
```

**Step 5 — Run a lint check**

```
omw lint
```

```json
{
  "vault_id": 1,
  "vault_path": "~/.omw/vaults/demo",
  "frontmatter_issues": [],
  "drift": { "missing_files": [], "mtime_drift": [] },
  "links": {
    "broken": [],
    "orphans": [],
    "index_drift": { "missing_from_index": [], "dangling_in_index": [] },
    "contradictions": [],
    "supersedes": [],
    "superseded_unmarked": [],
    "link_suggestions": []
  },
  "auto_fix_hints": []
}
```

→ Full tutorial: [TUTORIAL.md](TUTORIAL.md) · [한국어](TUTORIAL.ko.md)

---

## Architecture

```
SKILL.md dispatcher → commands/<op>.md (LLM procedure) → scripts/<op>.py (deterministic I/O)
                                                       └─ registry.py → ~/.omw/registry.db (sqlite)
                                                       └─ adapters.py → filesystem (markdown / obsidian)
```

The 13 CLI subcommands:

| Subcommand  | Purpose                                                              |
| ----------- | -------------------------------------------------------------------- |
| `status`    | Show active vault and registry state                                 |
| `vault`     | Create, list, use, forget vaults                                     |
| `lint`      | Structural health check (frontmatter + links)                        |
| `search`    | Web search via the configured external provider (brave/tavily/exa/…) |
| `serve`     | Local retrieve-only HTTP query API (port 8765)                       |
| `schema`    | List / inspect page-type schemas                                     |
| `supersede` | Mark a page superseded by a newer one                                |
| `review`    | Spaced-repetition review queue (due / done)                          |
| `links`     | Suggest and insert `[[slug]]` entity links                           |
| `fields`    | Read frontmatter + inline `key::` fields                             |
| `import`    | Import an existing folder as a vault                                 |
| `setup`     | Interactive setup wizard                                             |
| `doctor`    | Verify install health                                                |

The skill also exposes natural-language ops via your AI session: `ingest`, `query`, `autoresearch`, `find`, `edit`, `move`, `delete`, and persona invocations (`translate`, `polish`, `summarize`, `scaffold`, `fact-check`, `consistency-check`, `build glossary`).

---

## Storage

- The vault registry lives at `~/.omw/registry.db` (override with `OMW_HOME`) as a per-user sqlite database.
- The note index is regenerated by `scripts/reindex.py` after every mutation.
- Your files stay in the vault path you chose. oh-my-wiki never touches them outside the op you explicitly invoked.

---

## Development

- `pytest -v` runs all tests.
- `ruff check scripts/ tests/` runs the linter.
- `python3 -m scripts.wizard status` inspects the dispatcher state.
- `python3 -m scripts.lint --vault-id N` runs the health check on a specific vault.

Continuous integration runs on GitHub Actions, across a matrix of Python 3.10, 3.11, and 3.12 on both ubuntu-latest and macos-latest.

---

## License

Released under the MIT License. See [LICENSE](./LICENSE) for the full text.
