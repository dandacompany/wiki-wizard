---
name: research-to-wiki
description: >
  Research a topic and turn it into a verified, polished wiki page. researcher
  drafts from web research, source-curator gates the sources, fact-checker
  verifies the claims, and polisher tightens the prose. Sequential — each stage
  consumes the previous stage's output.
mode: sequential
swarm: false
timeout_seconds: 1800
workers:
  - persona: researcher
    backend_default: claude
    model_hint: most_capable
  - persona: source-curator
    backend_default: claude
    model_hint: standard
    inputs_from: previous
  - persona: fact-checker
    backend_default: claude
    model_hint: standard
    inputs_from: previous
  - persona: polisher
    backend_default: claude
    model_hint: standard
    inputs_from: previous
---

## research-to-wiki

A sequential pipeline that takes a topic to a finished wiki page:

1. **researcher** — multi-round research → draft page.
2. **source-curator** — triage the draft's sources (keep/drop).
3. **fact-checker** — verify each claim, tag confidence.
4. **polisher** — tighten prose and structure.

Run with `python3 -m scripts.team run research-to-wiki --text "<topic>"`
(see `commands/team-run.md`). Each stage receives the previous stage's output.
