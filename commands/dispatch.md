# dispatch — single-persona dispatch to a backend

## When to invoke

User says: "dispatch the fact-checker to check this with codex",
"run the summarizer on draft.md using claude", "디스패치 fact-checker",
"send this to the translator persona on gemini".

Trigger keywords: dispatch, 디스패치, dispatch this, send to persona.

## Inputs needed before calling the backend

1. **persona** — name of the persona. AskUserQuestion if not stated.
   Show list from `python3 -m scripts.personas list` if user is unsure.
2. **source** — file path or vault-relative path.
3. **backend** — claude / codex / gemini / opencode. Run
   `python3 -m scripts.backends detect` to show available + authed backends.
   AskUserQuestion to confirm or override.
4. **model** — run `python3 -m scripts.backends list-models <backend>` filtered
   by persona's `model_hint`. AskUserQuestion with filtered list. Default: top.
5. **form factor** — AskUserQuestion ONCE per session (remembered in
   `.oh-my-wiki/ff.tmp`): 1. In-skill (default) 2. CLI shim 3. Docker
6. **skip permissions** — AskUserQuestion: "Use skip-permissions for this
   worker? (claude: --dangerously-skip-permissions / codex: --yolo /
   gemini: n/a)". Default: No.

## Procedure

```bash
python3 -m scripts.dispatch \
  --persona <name> \
  --source <path> \
  --backend <name> \
  --model <model-id> \
  [--skip-permissions]
```

Wait for exit, then read:

```bash
cat <session_dir>/worker-1-<persona>/done.json
```

## Report to user

- Status (ok / timeout / error)
- Output file path (from `result_path` in done.json)
- Model and duration_seconds
- If status ≠ ok: `tmux attach -t <session_name>` to inspect
