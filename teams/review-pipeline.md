---
name: review-pipeline
description: >
  Parallel review team: fact-checker, consistency-checker, and summarizer
  run concurrently and each produce a sibling output file.
mode: parallel
timeout_seconds: 600
workers:
  - persona: fact-checker
    backend_default: claude
    model_hint: most_capable
  - persona: consistency-checker
    backend_default: claude
    model_hint: standard
  - persona: summarizer
    backend_default: gemini
    model_hint: fast
---

# review-pipeline

Run three reviewers in parallel against the same source document:

1. **fact-checker** — decomposes claims, verifies via web search, writes `<stem>.factcheck.md`
2. **consistency-checker** — audits internal consistency, writes `<stem>.consistency.md`
3. **summarizer** — produces a concise summary, writes `<stem>.summary.md`

All three workers start simultaneously and produce independent sibling files.
The dispatch session is closed once all three `done.json` sentinels appear.
