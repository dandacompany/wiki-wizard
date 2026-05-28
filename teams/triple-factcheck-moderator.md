---
name: triple-factcheck-moderator
description: >
  Three fact-checker workers on different AI backends (claude, codex, gemini)
  independently verify the same document. A moderator worker reconciles their
  findings via swarm messaging and structured votes for any conflicting claims,
  then synthesizes a single authoritative consensus report.
mode: mixed
swarm: true
stages:
  - parallel:
      - fact-checker
      - fact-checker
      - fact-checker
  - sequential:
      - moderator
timeout_seconds: 1800
workers:
  - persona: fact-checker
    backend_default: claude
    model_hint: most_capable
    swarm_instructions: |
      After completing your full fact-check of the document, publish each
      contested claim to the swarm so the moderator can reconcile:

        python3 -m scripts.swarm publish \
          --topic "claim" \
          --body '{"claim": "<claim text>", "verdict": "<SUPPORTED|DISPUTED|UNVERIFIABLE>", "sources": ["<url-or-citation>"]}'

      Call heartbeat every 30 seconds while working:

        python3 -m scripts.swarm heartbeat \
          --status "verifying claim N of M" \
          --progress <0.0-1.0>

      When you have published all contested claims, send a final heartbeat:

        python3 -m scripts.swarm heartbeat \
          --status "all claims published" \
          --progress 1.0

      You do NOT need to wait for the moderator or other workers.
      Write your individual fact-check report to your assigned output path
      as normal, then exit.

  - persona: fact-checker
    backend_default: codex
    model_hint: most_capable
    swarm_instructions: |
      After completing your full fact-check of the document, publish each
      contested claim to the swarm so the moderator can reconcile:

        python3 -m scripts.swarm publish \
          --topic "claim" \
          --body '{"claim": "<claim text>", "verdict": "<SUPPORTED|DISPUTED|UNVERIFIABLE>", "sources": ["<url-or-citation>"]}'

      Call heartbeat every 30 seconds while working:

        python3 -m scripts.swarm heartbeat \
          --status "verifying claim N of M" \
          --progress <0.0-1.0>

      When you have published all contested claims, send a final heartbeat:

        python3 -m scripts.swarm heartbeat \
          --status "all claims published" \
          --progress 1.0

      You do NOT need to wait for the moderator or other workers.
      Write your individual fact-check report to your assigned output path
      as normal, then exit.

  - persona: fact-checker
    backend_default: gemini
    model_hint: most_capable
    swarm_instructions: |
      After completing your full fact-check of the document, publish each
      contested claim to the swarm so the moderator can reconcile:

        python3 -m scripts.swarm publish \
          --topic "claim" \
          --body '{"claim": "<claim text>", "verdict": "<SUPPORTED|DISPUTED|UNVERIFIABLE>", "sources": ["<url-or-citation>"]}'

      Call heartbeat every 30 seconds while working:

        python3 -m scripts.swarm heartbeat \
          --status "verifying claim N of M" \
          --progress <0.0-1.0>

      When you have published all contested claims, send a final heartbeat:

        python3 -m scripts.swarm heartbeat \
          --status "all claims published" \
          --progress 1.0

      You do NOT need to wait for the moderator or other workers.
      Write your individual fact-check report to your assigned output path
      as normal, then exit.

  - persona: moderator
    backend_default: claude
    model_hint: most_capable
    swarm_instructions: |
      You start AFTER the three fact-checkers have finished (sequential stage).
      Their individual reports are available in the session directory.

      Step 1 - Collect all published claims:

        python3 -m scripts.swarm inbox --topic "claim" --mark-delivered

      You should receive at least one message from each of the three
      fact-checker workers. If fewer than three workers have published,
      check heartbeats to determine if a worker is still running:

        python3 -m scripts.swarm monitor

      Wait up to 5 minutes for stragglers, then proceed with what is
      available. Note any missing workers explicitly.

      Step 2 - Group messages by claim text (normalise whitespace).

      Step 3 - For each claim where verdicts disagree across workers:

        python3 -m scripts.swarm vote-create \
          --proposal "Verdict for: <claim text>" \
          --choices "SUPPORTED,DISPUTED,UNVERIFIABLE" \
          --quorum 3

        # Cast votes on behalf of each worker based on their published verdicts:
        python3 -m scripts.swarm vote --proposal-id <id> --choice <worker-1-verdict>
        # Repeat for each worker's published verdict

        python3 -m scripts.swarm vote-result --proposal-id <id>

      Step 4 - Synthesize the final consensus report using the Moderator
      persona output format (Consensus Table + Dissent Table + Full Synthesis).

      Write the final report to the output path defined in === TASK ===.
      Filename convention: <source-doc>.factcheck-consensus.md
---

# triple-factcheck-moderator team

A two-stage swarm pipeline that produces an authoritative, cross-validated
fact-check consensus report from a single source document.

**Stage 1 (parallel)** — three independent fact-checkers (claude, codex, gemini)
each verify the document simultaneously, publishing every contested claim to
the shared swarm topic `"claim"` as they work.

**Stage 2 (sequential)** — a moderator reads all published claims from the
swarm inbox, groups them by claim text, opens a structured vote for any claim
where the three workers disagree, collects the vote results, and synthesizes
a final **Consensus Table + Dissent Table + Full Synthesis** report.

## Recommended invocation

```
omw team-run triple-factcheck-moderator --on <article.md>
```

## Stages

| Stage | Type       | Workers                                                            | Action                   |
| ----- | ---------- | ------------------------------------------------------------------ | ------------------------ |
| 1     | parallel   | fact-checker (claude), fact-checker (codex), fact-checker (gemini) | independent verification |
| 2     | sequential | moderator (claude)                                                 | consensus synthesis      |

## Swarm message flow

```
fact-checker/claude ──┐
fact-checker/codex  ──┼──▶ topic:"claim"  ──▶ moderator inbox
fact-checker/gemini ──┘                         │
                                                ├─ vote-create (conflicts)
                                                ├─ vote × 3
                                                ├─ vote-result
                                                └─ consensus report
```

## Outputs

- `<source>.claude.factcheck.md` — individual claude report
- `<source>.codex.factcheck.md` — individual codex report
- `<source>.gemini.factcheck.md` — individual gemini report
- `<source>.factcheck-consensus.md` — final moderator consensus (primary output)
- `summary.json` in the dispatch session directory

## Notes

- Expected wall-clock: 20-40 min for a medium article (parallel stage dominates).
- `swarm: true` — all workers share a swarm message bus injected at dispatch time.
- `timeout_seconds: 1800` — 30 min total; moderator waits up to 5 min for stragglers.
- Override backends per worker:
  `omw team-run triple-factcheck-moderator --backend fact-checker=claude`
- Skip permissions for faster CI usage:
  `omw team-run triple-factcheck-moderator --skip-permissions`
