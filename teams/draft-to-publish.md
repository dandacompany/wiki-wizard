---
name: draft-to-publish
description: Full publishing pipeline — scaffold → polish → parallel fact-check + consistency review.
mode: mixed
stages:
  - sequential: [scaffolder]
  - sequential: [polisher]
  - parallel: [fact-checker, consistency-checker]
workers:
  - persona: scaffolder
    backend_default: codex
    model_hint: fast
  - persona: polisher
    backend_default: claude
    model_hint: standard
    inputs_from: previous
  - persona: fact-checker
    backend_default: claude
    model_hint: most_capable
    inputs_from: previous
  - persona: consistency-checker
    backend_default: codex
    model_hint: standard
    inputs_from: previous
timeout_seconds: 1800
---

# draft-to-publish team

A three-stage mixed pipeline that takes a raw idea or outline and
produces a publish-ready wiki article.

**Stage 1** — scaffolder structures the content (fast model, codex).
**Stage 2** — polisher improves prose flow (standard model, claude).
**Stage 3** — fact-checker and consistency-checker review in parallel
(most_capable + standard, both reading the polished output).

## Recommended invocation

```
omw team-run draft-to-publish --on <raw-notes.md>
```

## Stages

| Stage | Type       | Workers                           | Source            |
| ----- | ---------- | --------------------------------- | ----------------- |
| 1     | sequential | scaffolder                        | original source   |
| 2     | sequential | polisher                          | scaffolder output |
| 3     | parallel   | fact-checker, consistency-checker | polisher output   |

## Outputs

- `<source>.scaffold.md` or `wiki/syntheses/<slug>.md` (scaffolder, new_page)
- polished document (polisher, inplace)
- `<polished>.factcheck.md` (fact-checker, sibling_suffix)
- consistency report JSON (consistency-checker, stdout)
- `summary.json` in the dispatch session dir

## Notes

- Expected wall-clock: 15-30 min for a medium draft.
- Override backends per worker:
  `omw team-run draft-to-publish --backend scaffolder=gemini`
- Skip permissions for faster CI usage (each backend):
  `omw team-run draft-to-publish --skip-permissions`
