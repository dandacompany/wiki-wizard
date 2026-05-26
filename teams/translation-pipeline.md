---
name: translation-pipeline
description: >
  Sequential translation pipeline: translator runs first, then the polisher
  refines the translator's output.
mode: sequential
timeout_seconds: 900
workers:
  - persona: translator
    backend_default: claude
    model_hint: standard
  - persona: polisher
    backend_default: claude
    model_hint: standard
    inputs_from: previous
---

# translation-pipeline

Two-stage sequential pipeline for high-quality translation:

1. **translator** — translates the source document to the target language.
2. **polisher** — receives the translator's output (`inputs_from: previous`)
   and refines grammar, style, and fluency.

Workers run one after the other; the polisher receives the translator's output
file as its source document.
