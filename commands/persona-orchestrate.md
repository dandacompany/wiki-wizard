# persona-orchestrate

Plan and run a **multi-step** content-operations request via the
**operations-orchestrator** persona. The orchestrator proposes a plan; you show
it, confirm, then execute each step. Single-op requests should use their direct
trigger instead (see SKILL.md).

## When to invoke

A request that spans **multiple lifecycle stages**, names **≥2 ops**, or is a
**broad multi-step goal** — e.g. "research X, fact-check it, and organize it into
the wiki", "이 주제 조사해서 검증하고 위키에 정리해줘", "plan this", "전체적으로 처리해줘",
"워크플로 짜줘".

## Procedure

1. **Show the persona spec** (`personas/operations-orchestrator.md`) so the user
   knows it plans only.
2. **Run the orchestrator** to get the plan:
   ```bash
   python3 -m scripts.personas run operations-orchestrator \
     --text "<the user's request>" --output-file /tmp/orchestrate-<ts>.json
   ```
   (output_kind stdout — capture the JSON plan.)
3. **Show the plan** to the user as a numbered list (each stage: lifecycle · step ·
   why), surface any `notes` caveats, and **confirm the overall plan** before running.
4. **Execute step by step, in order.** For each stage:
   - `kind: persona` → load that persona's command and run it, using this map:
     researcher→`persona-research`, source-curator→`persona-source-curate`,
     memo-curator→`persona-memo-curate`, wiki-librarian→`persona-librarian`,
     curator→`persona-curate-index`, wiki-auditor→`persona-audit`,
     fact-checker→`persona-factcheck`, polisher→`persona-polish`,
     summarizer→`persona-summarize`, translator→`persona-translate`,
     scaffolder→`persona-scaffold`, consistency-checker→`persona-consistency`,
     terminology-manager→`persona-terminology`.
   - `kind: team` → run it via `commands/team-run.md`
     (`python3 -m scripts.team run <team> ...`).
   - Honor each step's own **propose → confirm → execute** (destructive/external
     steps confirm inside their own command). If the user declines a step, **stop**
     and report progress so far.
5. **Report** what ran, what each step produced, and any skipped/declined steps.
