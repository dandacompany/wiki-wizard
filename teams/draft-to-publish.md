---
name: draft-to-publish
description: >
  Mixed-mode pipeline: parallel review in stage 1, sequential polish in
  stage 2, final summary in stage 3.
mode: mixed
timeout_seconds: 1200
stages:
  - name: parallel-review
    mode: parallel
    workers:
      - persona: fact-checker
        backend_default: claude
        model_hint: most_capable
      - persona: consistency-checker
        backend_default: claude
        model_hint: standard
  - name: polish
    mode: sequential
    workers:
      - persona: polisher
        backend_default: claude
        model_hint: standard
        inputs_from: previous
  - name: summarize
    mode: parallel
    workers:
      - persona: summarizer
        backend_default: gemini
        model_hint: fast
workers:
  - persona: fact-checker
    backend_default: claude
    model_hint: most_capable
  - persona: consistency-checker
    backend_default: claude
    model_hint: standard
  - persona: polisher
    backend_default: claude
    model_hint: standard
    inputs_from: previous
  - persona: summarizer
    backend_default: gemini
    model_hint: fast
---

# draft-to-publish

Three-stage mixed pipeline that takes a draft document to a publish-ready state:

**Stage 1 — parallel-review:** fact-checker and consistency-checker run concurrently.

**Stage 2 — polish:** polisher refines the document after reviews complete.

**Stage 3 — summarize:** summarizer produces a final summary of the polished document.
