---
name: review-pipeline
description: Three-way review of a draft (facts, consistency, terminology) in parallel.
mode: parallel
workers:
  - persona: fact-checker
    backend_default: claude
    model_hint: most_capable
  - persona: consistency-checker
    backend_default: codex
    model_hint: standard
  - persona: terminology-manager
    backend_default: gemini
    model_hint: standard
timeout_seconds: 900
---

# review-pipeline team

Use when you have a draft you want triple-reviewed before publishing.
All three workers run in parallel; expect ~5-10 min wall-clock on a
medium-sized document.

## Recommended invocation

```
omw team-run review-pipeline --on <draft.md>
```

## Workers

| Worker              | Backend | Model hint   | Output                 |
| ------------------- | ------- | ------------ | ---------------------- |
| fact-checker        | claude  | most_capable | `<draft>.factcheck.md` |
| consistency-checker | codex   | standard     | stdout JSON            |
| terminology-manager | gemini  | standard     | stdout JSON            |

## Outputs

- `<draft>.factcheck.md` — fact-checker findings
- `stdout JSON` — consistency-checker + terminology-manager reports
- `summary.json` in the dispatch session dir

## Notes

- Override any backend at launch: `omw team-run review-pipeline --backend fact-checker=codex`
- For large documents (>5k words) consider increasing timeout:
  `omw team-run review-pipeline --timeout 1800`
