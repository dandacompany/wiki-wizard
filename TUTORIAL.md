# wiki-wizard Usage Tutorial

This is a hands-on tutorial for using wiki-wizard inside Claude Code or Codex CLI. Every dialog below reflects actual runtime behavior, and both English and Korean trigger phrases work.

> **Korean version**: [TUTORIAL.ko.md](./TUTORIAL.ko.md)

> **Notation**
>
> - `> You:` is what you type into the chat.
> - `< Claude:` is what wiki-wizard responds with.
> - `$` lines are Python calls executed internally. They are for reference; you never need to type them yourself.

---

## 0. Verify the install

See the [README](./README.md) for install instructions. Once the skill is linked, the trigger works in any new Claude Code session. Here is a quick health check.

```
> You: check the wiki status

< Claude: [wiki-wizard dispatcher invoked]
$ python3 -m scripts.wizard status

{
  "vault_count": 0,
  "active": null,
  "needs": "setup",
  "vaults": []
}

No vaults registered. Want to create one?
1. memo mode (lightweight note capture)
2. wiki mode (Karpathy-style knowledge wiki)
3. import an existing /memo folder
4. cancel
```

A fresh install returns `needs: setup`. The trigger phrases you can use are:

- English: "open my wiki", "set up a new vault", "ingest this", "what does my wiki say about X"
- Korean: "위키 열어줘", "새 vault 만들어줘", "이거 정리해줘", "위키에 물어봐"

---

## Scenario 1: First memo vault and first memo

This is the simplest workflow — use it to capture day-to-day notes quickly.

### 1.1 Create the vault

```
> You: create a new memo vault named "daily" at ~/notes/daily

< Claude: Running vault-setup with:

  - name: daily
  - path: /Users/you/notes/daily
  - mode: memo
  - type: markdown (no Obsidian)

Proceed? [Yes / No]

> You: yes

< Claude:
$ adapters.get_adapter('markdown').init_vault(/Users/you/notes/daily, 'memo')
$ registry.add_vault(name='daily', ...)
$ registry.set_active('daily')
$ reindex.full(vault_id=1) → 0 notes

✅ vault 'daily' registered and set active.
   Scaffolded:
   ~/notes/daily/
   ├── inbox/
   └── .trash/
```

### 1.2 Capture a memo by pasting (long-form)

This is the most common pattern. Paste any content and wiki-wizard proposes a title, tags, and folder for you.

```
> You: save this for me

Karpathy calls the LLM Wiki a "compounding knowledge artifact". Every source
gets saved verbatim to raw/, a summary lands at wiki/summaries/, and the
entities and concepts that appeared get their own pages. 10-15 page touches
per ingest is normal. Memos rot; structured wikis accumulate value over time.

< Claude: Long paste detected (368 chars) — proceeding with memo-mode hybrid create.
LLM proposes metadata from the body:

  - title: "Karpathy LLM Wiki — compounding knowledge"
  - slug: karpathy-llm-wiki-compounding-knowledge (auto-generated)
  - folder: inbox/
  - tags: [karpathy, llm, wiki, knowledge-management]
  - type: note
  - date: 2026-05-25

Save as-is?
1. Accept
2. Edit field
3. Cancel

> You: 1

< Claude:
$ memo_ops.write(vault_id=1, title='Karpathy LLM Wiki — compounding knowledge',
                 body='Karpathy calls the LLM Wiki...', folder='inbox',
                 tags=['karpathy','llm','wiki','knowledge-management'],
                 type_='note', date_str='2026-05-25')

✅ Saved:
   inbox/karpathy-llm-wiki-compounding-knowledge.md
```

### 1.3 Prompt-driven (short memo)

When the pasted body is under 200 characters, the wizard automatically switches to prompt mode.

```
> You: I want to write a quick memo

< Claude: Short input — using prompt mode.

What's the title?

> You: cut slack triage time by 30 minutes

< Claude: Folder? (default: inbox/)
1. inbox/
2. enter another folder

> You: 1

< Claude: Enter the body (multi-line OK, end with a blank line):

> You: Goal: shave 30 min off the daily mail+slack triage. Mute notifications, block focus time, batch replies.

< Claude: Suggested tags: [productivity, slack, workflow]
Save?

> You: ok

✅ inbox/cut-slack-triage-time-by-30-minutes.md
```

> **Note**: The slugifier preserves Hangul syllables (`가-힣` is allowed). If you want a readable English slug for a Korean title, either write the title in English up front, or use `edit` to change just the slug afterward.

### 1.4 Find a memo

```
> You: find a memo about karpathy

< Claude:
$ search.query(vault_id=1, query='karpathy', limit=5)

Top 1 hit:

# | score | relpath                                                 | title
1 | 8.5   | inbox/karpathy-llm-wiki-compounding-knowledge.md        | Karpathy LLM Wiki — compounding knowledge

Next?
1. open #1
2. search again with different terms
3. stop

> You: 1

< Claude:
$ adapters.get_adapter('markdown').open(~/notes/daily/inbox/karpathy-llm-wiki-compounding-knowledge.md)
→ opens via the macOS default .md handler (VS Code, Obsidian, etc.)

✅ Opened.
```

### 1.5 Edit a memo (single frontmatter field)

```
> You: add a "deep-work" tag to that memo

< Claude: Located the memo via search:
   inbox/karpathy-llm-wiki-compounding-knowledge.md

Current tags: [karpathy, llm, wiki, knowledge-management]
New tags:     [karpathy, llm, wiki, knowledge-management, deep-work]

> You: yes

< Claude:
$ memo_ops.edit_meta(vault_id=1,
                     relpath='inbox/karpathy-llm-wiki-compounding-knowledge.md',
                     key='tags',
                     value=['karpathy','llm','wiki','knowledge-management','deep-work'])

✅ tags field updated.
```

### 1.6 Organize (move + delete)

```
> You: move the slack memo to an archive folder

< Claude:
$ search.query(query='slack') → 1 hit
$ memo_ops.move(relpath='inbox/cut-slack-...md', dest_folder='archive')

archive/ didn't exist — created it.
✅ Moved: inbox/cut-slack-...md → archive/cut-slack-...md

> You: delete the karpathy memo

< Claude: Located:
   inbox/karpathy-llm-wiki-compounding-knowledge.md

Soft delete (move to .trash/, recoverable) or hard delete (permanent)?

> You: soft

< Claude:
$ memo_ops.delete(relpath='...', hard=False)

✅ Moved: .trash/20260525-145012-345678-karpathy-llm-wiki-compounding-knowledge.md
   To restore, move the file back to inbox/.
```

---

## Scenario 2: Wiki vault, ingest, and query (the Karpathy workflow)

This is wiki-wizard's core use case. Each source flows through five steps: save the raw original, write a summary page, split out the entity and concept pages it mentions, and finally update the index.

### 2.1 Create the wiki vault

```
> You: make a wiki vault called "research" at ~/notes/research using obsidian

< Claude:
$ adapters.get_adapter('obsidian', vault_name='research').init_vault(...)
$ registry.add_vault(name='research', type_='obsidian', mode='wiki')
$ registry.set_active('research')
$ reindex.full → 2 notes (index.md + log.md auto-created)

✅ wiki vault 'research' registered.
   ~/notes/research/
   ├── raw/                  (verbatim source bytes)
   ├── wiki/
   │   ├── summaries/        (summary pages)
   │   ├── entities/         (people, orgs, papers)
   │   ├── concepts/         (ideas, techniques)
   │   ├── comparisons/      (comparison pages)
   │   ├── syntheses/        (auto-filled by query file-back)
   │   ├── index.md          (auto-maintained TOC)
   │   └── log.md            (operation log)
   └── .trash/
```

### 2.2 Ingest by paste (text source)

```
> You: ingest this

The core of Andrej Karpathy's LLM Wiki Gist: notes are one-way flows, but
wikis are bidirectional graphs. raw/ preserves originals; wiki/ holds the
processed pages. A typical ingest touches 10-15 pages. Two meta files —
index.md (TOC) and log.md (operation log) — carry the wiki's metadata.

< Claude: Starting ingest. wiki-mode confirmed (active: research).

[1/7] Save the raw
$ ingest.save_raw(content='...', ext='md', title='Karpathy LLM Wiki Gist core',
                  date_str='2026-05-25')
→ raw/2026-05-25-karpathy-llm-wiki-gist-core.md

[2/7] Body analysis — proposed pages:

  Summary:
    - karpathy-llm-wiki-gist (one-paragraph summary)

  Entities:
    - andrej-karpathy (patch if exists, create if not)

  Concepts:
    - compounding-knowledge
    - raw-wiki-separation
    - bidirectional-graph
    - meta-files (index/log)

Confirm to proceed (yes/edit/cancel):

> You: yes

< Claude:
[3/7] Write summary page
$ ingest.write_wiki_page(layer='summaries', title='Karpathy LLM Wiki Gist', ...)
→ wiki/summaries/karpathy-llm-wiki-gist.md

[4/7] Write entity/concept pages
$ ingest.write_wiki_page(layer='entities', title='Andrej Karpathy', ...)
$ ingest.write_wiki_page(layer='concepts', title='Compounding Knowledge', ...)
$ ingest.write_wiki_page(layer='concepts', title='Raw Wiki Separation', ...)
$ ingest.write_wiki_page(layer='concepts', title='Bidirectional Graph', ...)
$ ingest.write_wiki_page(layer='concepts', title='Meta Files', ...)

[5/7] Update index
$ ingest.update_index(entries=[
    ('summaries', 'karpathy-llm-wiki-gist', 'Karpathy LLM Wiki Gist core'),
    ('entities', 'andrej-karpathy', 'AI researcher and educator'),
    ('concepts', 'compounding-knowledge', 'Knowledge as compounding artifact'),
    ...
  ])

[6/7] Append log
$ ingest.append_log(op='ingest', title='Karpathy LLM Wiki Gist core')
→ "## [2026-05-25] ingest | Karpathy LLM Wiki Gist core" added to wiki/log.md

[7/7] Reindex
$ reindex.incremental(vault_id=1) → 6 new notes indexed

✅ Ingest complete. 6 pages touched.
   raw: raw/2026-05-25-karpathy-llm-wiki-gist-core.md
   summary: wiki/summaries/karpathy-llm-wiki-gist.md
   entities: 1 (andrej-karpathy)
   concepts: 4 (compounding-knowledge, raw-wiki-separation, bidirectional-graph, meta-files)
```

### 2.3 Ingest a PDF

```
> You: ingest ~/Downloads/attention-is-all-you-need.pdf

< Claude: PDF detected. Extracting text via pypdf and preserving original bytes.

$ pdf_bytes = open('~/Downloads/attention-is-all-you-need.pdf', 'rb').read()
$ ingest.save_raw_pdf(pdf_bytes=..., title='Attention Is All You Need',
                      date_str='2026-05-25')
→ raw/2026-05-25-attention-is-all-you-need.pdf  (bytes preserved verbatim)
→ extracted text: 8721 chars

[2/7] Body analysis — proposed:

  Summary:
    - attention-is-all-you-need (transformer overview)

  Entities:
    - vaswani-et-al (authors)
    - google-brain (affiliation)

  Concepts:
    - self-attention
    - multi-head-attention
    - positional-encoding
    - transformer-architecture

Confirm (yes/edit/cancel):

> You: yes

[3/7~7/7] ... (same flow as above)

✅ Ingest complete. 8 pages touched.
```

> **PDF caveat**: Scanned, image-only PDFs may produce empty extracted text. In that case, paste the body manually and ingest it as text. OCR is out of scope for Plan C.

### 2.4 Query the wiki

```
> You: ask the wiki why attention is faster than RNN

< Claude:
$ search.query(vault_id=1, query='attention RNN', limit=5)

Top 3 hits:
1. wiki/summaries/attention-is-all-you-need.md      (score 7.5)
2. wiki/concepts/self-attention.md                  (score 5.0)
3. wiki/concepts/transformer-architecture.md        (score 3.5)

[Reading pages and synthesizing answer...]

Answer:
─────────────────────────────────────
Attention is faster than RNN because it breaks the sequential dependency
and enables parallelization. RNNs require hidden state h_t to depend on
h_{t-1}, forcing token-by-token processing, while self-attention computes
all token-pair relationships simultaneously
[summaries/attention-is-all-you-need](wiki/summaries/attention-is-all-you-need.md).

Multi-head attention in particular computes context vectors for every
token in a single matrix multiplication, which is highly efficient on GPUs
[concepts/self-attention](wiki/concepts/self-attention.md).

The trade-off is O(N²) memory for sequence length N — long documents
need separate techniques (sparse attention, etc.).
─────────────────────────────────────

File this answer to wiki/syntheses/ as a new page (file-back)? [Yes / No]

> You: yes

< Claude:
$ query.write_synthesis(title='Why Attention is faster than RNN',
                        body='Attention is faster than RNN because...',
                        citations=['wiki/summaries/attention-is-all-you-need.md',
                                   'wiki/concepts/self-attention.md'],
                        tags=['attention','rnn','transformer'])
→ wiki/syntheses/why-attention-is-faster-than-rnn.md

$ ingest.update_index(entries=[('syntheses', '...', 'Why Attention is faster than RNN')])
$ ingest.append_log(op='synthesis', title='Why Attention is faster than RNN')
$ reindex.incremental

✅ Synthesis page saved. The answer is now part of the wiki.
   Future searches will cite this page.
```

This is exactly what Karpathy means when he says "the loop closes": the question itself becomes a new page in the wiki.

---

## Scenario 3: Import an existing /memo folder

Use this when you already have notes piled up in Obsidian or plain markdown.

```
> You: run vault-import-memo on ~/Documents/old-notes

< Claude:
[Step 1] Path check
✅ ~/Documents/old-notes exists.

[Step 2] Register as memo-mode vault
$ registry.add_vault(name='legacy', path='/Volumes/...', type_='markdown', mode='memo')
$ reindex.full → 247 notes indexed

✅ Registered as 'legacy'.

[Step 3] Propose frontmatter normalization (dry-run)

$ import_memo.dry_run(vault_id=2)

  Summary:
    Total files: 247
    Need changes: 89
    Clean: 158

  Sample of files needing changes (first 10):
    - 2025-08-meeting-notes.md           (changes: 2)  ← missing type, missing tags
    - article-clip.md                    (changes: 1)  ← tags string→list
    - random-thought.md                  (changes: 3)  ← missing date/type/tags
    ...

Apply the migration?
89 files will be modified in place. Pre-images backed up to
.trash/<ts>-pre-import-*.md. Type 'apply' exactly to proceed:

> You: apply

< Claude:
$ import_memo.apply(vault_id=2, plan=...)

  Applied: 89 files
  Skipped: 0 (no malformed YAML)
  Backup timestamp: 20260525-150823-456789

✅ Migration complete. All files now match wiki-wizard frontmatter rules
   (title/date/type/tags required). Recover from
   .trash/20260525-150823-456789-pre-import-*.md if needed.
```

---

## Scenario 4: Routine health check (lint)

`lint` runs an integrity check on the active vault. It dispatches automatically based on the vault's mode — memo-mode runs only the common checks, while wiki-mode adds the structural checks on top.

### 4.1 memo vault lint

```
> You: lint the daily vault

< Claude: 'daily' is memo-mode → common checks only.

$ lint.check(vault_id=1)

📋 Common checks
─────────────────────────────────────

✅ Frontmatter issues: none

⚠️  Drift — missing files (1)
   - inbox/old-note.md (in registry but not on disk)

✅ Drift — mtime mismatch: none

Auto-fix hints:
  - missing files: delete the orphan row or restore the file.
    Manual: registry.delete_note(vault_id=1, relpath='inbox/old-note.md')

> You: delete the orphan row

< Claude:
$ registry.delete_note(vault_id=1, relpath='inbox/old-note.md')
✅ Cleaned up.
```

### 4.2 wiki vault lint

```
> You: check the research vault

< Claude: 'research' is wiki-mode → common + structural checks.

$ lint.check(vault_id=2)
$ wiki_lint.check(vault_id=2)

📋 Common checks
─────────────────────────────────────
✅ Frontmatter issues: none
✅ Drift: none

📋 Wiki structural checks
─────────────────────────────────────

⚠️  Orphan pages (2) — past 7-day grace with no inbound links
   - wiki/concepts/early-stopping.md (age: 14 days)
   - wiki/entities/lecun.md (age: 23 days)

⚠️  Missing concepts (3) — referenced by ≥2 pages but no page exists
   - transformer-decoder (referenced by: summaries/attention-is-all-you-need.md,
                                          summaries/gpt-paper.md)
   - layer-normalization (referenced by 4 pages)
   - residual-connection (referenced by 3 pages)

⚠️  Empty data (1)
   - wiki/concepts/dropout.md (reason: body<50chars — "TBD")

✅ Dangling links: none

Suggested next actions:
  - ingest or write pages for the 3 missing concepts
  - flesh out dropout.md body
  - review orphans (add [[link]] from somewhere, or archive)
```

---

## Scenario 5: Multiple vaults

Use this flow when you run more than one vault side by side.

```
> You: list my vaults

< Claude:
$ registry.list_vaults() + per-vault note counts

* daily          memo  markdown      12 notes  /Users/you/notes/daily
  research       wiki  obsidian      47 notes  /Users/you/notes/research
  legacy         memo  markdown     247 notes  ~/Documents/old-notes

(* = active)

> You: switch to research

< Claude:
$ registry.set_active('research')
✅ Active vault: research (wiki, obsidian) at /Users/you/notes/research

> You: forget the legacy vault but keep the files

< Claude: Removing 'legacy' from the registry.
The 247 files at ~/Documents/old-notes will be preserved.

Type the vault name to confirm:

> You: legacy

< Claude:
$ registry.forget_vault('legacy')
✅ 'legacy' removed from registry. Files preserved.
```

---

## Common situations & how to handle them

### Q. wiki-wizard didn't auto-trigger

Invoke it explicitly:

```
> You: use the wiki-wizard skill
```

Or use one of the trigger phrases defined in SKILL.md frontmatter:

- "open my wiki" or "위키 열어줘"
- "ingest this" or "이거 정리해줘"
- "find a note about X" or "X 관련 노트 찾아줘"

### Q. The active vault is wrong

```
> You: what's my active vault?

< Claude:
$ wizard.status
active: { name: 'legacy', mode: 'memo', ... }

> You: switch to research

< Claude:
$ registry.set_active('research')
```

### Q. Roll back a migration

`vault-import-memo apply` always backs up the pre-image to `.trash/<ts>-pre-import-*.md`.

```bash
# Manual restore (single file)
cp ~/notes/legacy/.trash/20260525-150823-456789-pre-import-2025-08-meeting-notes.md \
   ~/notes/legacy/2025-08-meeting-notes.md
```

To roll back the entire batch, restore every backup with the same timestamp prefix at once.

### Q. PDF extraction garbles Korean (or other CJK)

pypdf is weak with some Hangul encodings. You have two workarounds:

1. Open the PDF in macOS Preview, copy the text, and paste-ingest it manually.
2. For scanned PDFs that need OCR, invoke the separate `paddleocr` skill first, then paste the extracted text.

### Q. Obsidian isn't running and `open` fails

The `obsidian://open?vault=...&file=...` URI is rejected by macOS when the app is closed. You have two options:

1. Launch Obsidian first, then retry `open`.
2. Register the vault as `markdown` type so that OS default handlers (`open` or `xdg-open`) take over.

```
> You: vault-setup name=temp path=... mode=memo type=markdown
```

---

## Using wiki-wizard from Codex CLI

The experience is identical to Claude Code. Once Codex discovers the wiki-wizard skill, the same triggers invoke it. The SKILL.md frontmatter is not tied to any specific LLM, which is why both runtimes behave the same way.

```
$ codex
> check the wiki status
[Codex invokes wiki-wizard, same flow as before]
```

That said, Codex is more conservative than Claude Code about auto-triggering. When in doubt, invoke it explicitly:

```
> Use the wiki-wizard skill to ingest this article: ...
```

---

## More

- **Command reference**: `commands/*.md` covers all 12 ops (vault-setup, ingest, query, lint, and the rest).
- **Script API**: `scripts/*.py` is callable from Python, and a subset is also exposed as a CLI.
- **Design docs**: `docs/superpowers/specs/` is kept local-only and not published. It is intended for contributors.
- **Tests**: `pytest -v` runs all 91 tests, which cover every documented behavior.

Issue tracker: https://github.com/dandacompany/wiki-wizard/issues
