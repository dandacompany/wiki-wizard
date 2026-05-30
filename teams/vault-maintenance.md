---
name: vault-maintenance
description: >
  Diagnose then repair a wiki vault. wiki-auditor produces a prioritized health
  report, wiki-librarian proposes structural fixes (cross-links, orphans,
  merges), and curator re-syncs and reorders wiki/index.md. Sequential — each
  stage builds on the previous one's findings. All stages PROPOSE; the human
  confirms each apply.
mode: sequential
swarm: false
timeout_seconds: 1500
workers:
  - persona: wiki-auditor
    backend_default: claude
    model_hint: standard
  - persona: wiki-librarian
    backend_default: claude
    model_hint: standard
    inputs_from: previous
  - persona: curator
    backend_default: claude
    model_hint: standard
    inputs_from: previous
---

## vault-maintenance

A sequential maintenance pass:

1. **wiki-auditor** — health audit (broken links, orphans, index drift, staleness).
2. **wiki-librarian** — propose structural fixes from the audit.
3. **curator** — re-sync + reorder `wiki/index.md`.

Every stage only PROPOSES (stdout); apply each change with confirmation
(propose → confirm → execute). Run with
`python3 -m scripts.team run vault-maintenance --vault-id <id>`.
