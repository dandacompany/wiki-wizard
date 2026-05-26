# team — explicit multi-persona team with per-worker backend overrides

## When to invoke

User says: "run a team: fact-checker on claude, polisher on gemini",
"팀 실행: fact-checker claude, consistency-checker codex",
"launch a team of fact-checker and consistency-checker".

Trigger keywords: team, 팀, run a team, 팀 실행, launch team.

## Inputs needed

1. **workers** — list of `<persona>:<backend>` pairs. AskUserQuestion if
   incomplete. Each worker also needs a model (AskUserQuestion per worker,
   filtered by persona's model_hint).
2. **mode** — parallel (default) / sequential. AskUserQuestion if not stated.
3. **source** — common source file for all workers.
4. **form factor** — same one-time AskUserQuestion as dispatch.md.
5. **skip permissions** — per-worker AskUserQuestion (default: No).

## Procedure

```bash
python3 -m scripts.team run \
  --workers "fact-checker:claude:<model>,consistency-checker:codex:<model>" \
  --mode parallel \
  --source <path> \
  [--skip-permissions fact-checker,consistency-checker]
```

## Report to user

Status per worker, output paths, durations, attach hint on error.
Same format as dispatch.md report section.
