# team-run — template-based team launch

## When to invoke

User says: "run the review-pipeline on draft.md",
"omw team-run translation-pipeline --lang ja on article.md",
"병렬 검토 review-pipeline으로 해줘", "팀 실행 draft-to-publish".

Trigger keywords: team-run, 팀 실행, run team template, 병렬 검토.

## Inputs needed (resolve in order — spec §4.7)

1. **template name** — list via `python3 -m scripts.team list`. AskUserQuestion
   if not stated.
2. **source** — file path. AskUserQuestion if not stated.
3. **form factor** — one-time AskUserQuestion (same as dispatch.md).
4. **backend overrides** (optional) — AskUserQuestion: "Override any backend?
   Enter `<persona>=<backend>` pairs or press Enter for template defaults."
5. **model per worker** — AskUserQuestion per worker, catalog filtered by hint.
6. **skip permissions per worker** — AskUserQuestion (default: No).
7. **template-specific args** — read frontmatter for `args:` keys marked
   `required`; AskUserQuestion for each (e.g., `lang` for translation-pipeline).

## Procedure

Step 1 — load + show team summary:

```bash
python3 -m scripts.team describe --template <name>
```

Show summary. AskUserQuestion: "Proceed?" (default: yes).

Step 2 — resolve backends:

```bash
python3 -m scripts.backends detect
```

For any worker whose `backend_default` is missing or unauthed:
AskUserQuestion: "Worker <persona> needs <backend> but it is not available.
a) Install/login <backend> b) Use <other> instead c) Skip this worker"

Step 3 — invoke:

```bash
python3 -m scripts.team run \
  --template <name> \
  --source <path> \
  [--backend-overrides "p1=b1,p2=b2"] \
  [--models "p1=model-id,p2=model-id"] \
  [--skip-permissions "p1,p2"] \
  [--args "lang=ja"]
```

Poll progress with `python3 -m scripts.team status --session <id>` every 30s.

## Report to user

For each worker: persona + backend + model, status, output path, duration.
Offer: "Run `tmux attach -t <session>` to inspect any pane. Run
`python3 -m scripts.team shutdown --session <id>` when done."
