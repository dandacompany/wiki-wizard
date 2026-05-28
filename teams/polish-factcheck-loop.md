---
name: polish-factcheck-loop
description: >
  An iterative refinement pipeline. A scaffolder produces an initial draft;
  a polisher refines it and sends it to a fact-checker via swarm RPC for
  review. The polisher loops (up to max_iterations times) until the
  fact-checker confirms the draft is clean. Useful for high-stakes content
  where accuracy must be verified interactively before finalising.
mode: sequential
swarm: true
max_iterations: 3
timeout_seconds: 2400
workers:
  - persona: scaffolder
    backend_default: codex
    model_hint: fast
    # No swarm_instructions — scaffolder does not coordinate.
    # It simply produces the first draft and exits normally.

  - persona: polisher
    backend_default: claude
    model_hint: standard
    inputs_from: previous
    swarm_instructions: |
      You receive the scaffolder's draft via inputs_from: previous.

      Polish the draft as your persona instructs. Then enter a review loop:

      LOOP (up to max_iterations times — the team is configured for 3):

        Step A - Send draft to the fact-checker for review via RPC:

          python3 -m scripts.swarm rpc \
            --to worker-3-fact-checker \
            --body "review draft at $(cat OMW_OUTPUT_PATH)" \
            --timeout 600

          Save the response text as RPC_RESPONSE.

        Step B - Check response:

          If RPC_RESPONSE starts with "OK":
            Exit loop. Finalize. Write to your output path. Exit.

          If RPC_RESPONSE starts with "issues found:":
            Read the issues listed. Revise accordingly.
            Heartbeat with current iteration progress:

              python3 -m scripts.swarm heartbeat \
                --status "revision N/3 complete, re-submitting" \
                --progress <fraction>

            Continue to next iteration.

      After max_iterations are exhausted without "OK":
        Write a note at the top of the final draft:
          NOTE: Fact-checker flagged issues after 3 revision rounds.
                Review the following before publishing: <final issues>
        Write the draft to your output path and exit.

      Heartbeat after each major step.

  - persona: fact-checker
    backend_default: gemini
    model_hint: most_capable
    swarm_instructions: |
      You act as a blocking fact-check service in this team.

      Wait for RPC requests from the polisher by polling your inbox:

        python3 -m scripts.swarm inbox \
          --unread-only \
          --mark-delivered

      Poll every 10 seconds until a message arrives with a correlation_id
      (indicating an RPC request).

      For each request received:

        1. Read the draft path from the message body.
        2. Fact-check the draft thoroughly (all factual claims, dates,
           statistics, attributions).
        3. Respond via rpc-respond with your verdict:

           If clean:
             python3 -m scripts.swarm rpc-respond \
               --rpc-id <correlation_id from message> \
               --body "OK"

           If issues found:
             python3 -m scripts.swarm rpc-respond \
               --rpc-id <correlation_id from message> \
               --body "issues found: <bulleted list of issues>"

        4. Heartbeat:
             python3 -m scripts.swarm heartbeat \
               --status "review N complete, responded OK|issues" \
               --progress <fraction>

      After responding "OK" (or after no new requests arrive within
      120 seconds following your last response), exit.
---

# polish-factcheck-loop team

An iterative refinement pipeline that drives a draft through sequential
polish–verify cycles until the fact-checker signals the content is clean,
or the maximum iteration budget is exhausted.

**Stage 1** — scaffolder (codex/fast) produces the raw initial draft and exits.

**Stage 2** — polisher (claude/standard) receives the draft via
`inputs_from: previous`, refines it, then enters a synchronous RPC loop
with the fact-checker: it sends the draft via `swarm rpc`, waits for the
response, and either finalises ("OK") or revises and re-submits ("issues
found: …") for up to `max_iterations=3` rounds.

**Stage 3** — fact-checker (gemini/most_capable) polls its inbox for RPC
requests, performs a thorough fact-check, and responds via `rpc-respond`
with "OK" or a bulleted list of issues.

## Recommended invocation

```
omw team-run polish-factcheck-loop --on <article.md>
```

## Stages

| Stage | Worker       | Backend | Action                                        |
| ----- | ------------ | ------- | --------------------------------------------- |
| 1     | scaffolder   | codex   | Produce initial draft, exit                   |
| 2     | polisher     | claude  | Polish + RPC loop (up to 3 iterations)        |
| 3     | fact-checker | gemini  | Fact-check on demand, respond via rpc-respond |

## Swarm message flow

```
scaffolder ──▶ [initial draft written to output path]
                    │
                    ▼ (inputs_from: previous)
polisher ──── refine ──▶ swarm rpc ──▶ fact-checker inbox
                              │              │
                         wait…          fact-check
                              │              │
                     swarm rpc-respond ◀─────┘
                              │
               ┌──────────────┴──────────────┐
           "OK" exit                  "issues found:" → revise, repeat
```

## Outputs

- `<source>.polished.md` — final polished draft (primary output)
- Swarm RPC messages are transient and not written to disk

## Notes

- `max_iterations: 3` — polisher makes up to 3 revision rounds before
  adding a NOTE header and finalising with remaining issues listed.
- `swarm: true` — polisher and fact-checker share a swarm message bus.
- `timeout_seconds: 2400` — 40 min total (allows generous fact-check time).
- `inputs_from: previous` on polisher — automatically receives scaffolder output.
- Override backends: `omw team-run polish-factcheck-loop --backend polisher=codex`
- Skip permissions for CI: `omw team-run polish-factcheck-loop --skip-permissions`
