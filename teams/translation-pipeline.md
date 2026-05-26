---
name: translation-pipeline
description: Translate a document then polish the translation for natural target-language flow.
mode: sequential
workers:
  - persona: translator
    backend_default: claude
    model_hint: standard
    args:
      lang: required
  - persona: polisher
    backend_default: gemini
    model_hint: standard
    inputs_from: previous
timeout_seconds: 1200
---

# translation-pipeline team

A two-step sequential pipeline: translate first, then polish.
The polisher receives the translator's output file as its source
(`inputs_from: previous`), so it works on the translated text rather
than the original.

## Required argument

Supply `--lang <target>` at launch — e.g. `--lang ko` for Korean.

## Recommended invocation

```
omw team-run translation-pipeline --on <source.md> --lang ko
```

## Workers

| Step | Worker     | Backend | Input             |
| ---- | ---------- | ------- | ----------------- |
| 1    | translator | claude  | original source   |
| 2    | polisher   | gemini  | translator output |

## Outputs

- `<source>.<lang>.md` — translated document (translator, sibling_file output)
- polished in-place by polisher (`inplace` output_kind)
- `summary.json` in the dispatch session dir

## Notes

- Override backends: `omw team-run translation-pipeline --backend translator=gemini`
- The polisher uses `inplace` output — it overwrites the translated file.
  A backup is written to the dispatch session dir automatically.
