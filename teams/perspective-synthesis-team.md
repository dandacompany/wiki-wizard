---
name: perspective-synthesis-team
description: >
  A multi-audience drafting team. Three perspective-writer workers draft the
  same topic from different editorial standpoints (beginner, expert, skeptic)
  in parallel. A moderator worker then weaves the three drafts into a single
  layered piece that serves all three audiences — marking sections with
  [for: beginner|expert|skeptic] annotations so readers can self-route.
  Useful for tutorials, deep-dives, and marketing+technical hybrid content.
mode: mixed
swarm: true
stages:
  - parallel: [perspective-writer, perspective-writer, perspective-writer]
  - sequential: [moderator]
timeout_seconds: 1500
workers:
  - persona: perspective-writer
    backend_default: claude
    model_hint: standard
    args:
      perspective: beginner
    swarm_instructions: |
      Your perspective is: BEGINNER.
      Assume the reader has no domain knowledge. Explain using analogies,
      motivating examples, and simple vocabulary. Avoid jargon unless you
      define it on first use.

      When your draft section is ready, publish it to the swarm so the
      moderator can collect it:

        python3 -m scripts.swarm publish \
          --topic "perspective-draft" \
          --body "$(cat <your_output_path>)"

      Heartbeat at start and after publishing:

        python3 -m scripts.swarm heartbeat --status "beginner draft published" --progress 1.0

  - persona: perspective-writer
    backend_default: codex
    model_hint: standard
    args:
      perspective: expert
    swarm_instructions: |
      Your perspective is: EXPERT.
      Assume the reader has solid domain knowledge. Focus on depth, edge
      cases, nuance, and implementation detail. Reference specifications
      or research where relevant. Don't over-explain basics.

      When your draft section is ready, publish it:

        python3 -m scripts.swarm publish \
          --topic "perspective-draft" \
          --body "$(cat <your_output_path>)"

      Heartbeat at start and after publishing:

        python3 -m scripts.swarm heartbeat --status "expert draft published" --progress 1.0

  - persona: perspective-writer
    backend_default: gemini
    model_hint: standard
    args:
      perspective: skeptic
    swarm_instructions: |
      Your perspective is: SKEPTIC.
      Surface limitations, failure modes, caveats, and what the mainstream
      narrative gets wrong. Ask "what could go wrong?" and "what is the cost
      most people overlook?". Be fair — acknowledge strengths — but don't
      soft-pedal problems.

      When your draft section is ready, publish it:

        python3 -m scripts.swarm publish \
          --topic "perspective-draft" \
          --body "$(cat <your_output_path>)"

      Heartbeat at start and after publishing:

        python3 -m scripts.swarm heartbeat --status "skeptic draft published" --progress 1.0

  - persona: moderator
    backend_default: claude
    model_hint: most_capable
    swarm_instructions: |
      You will receive three drafts — beginner, expert, and skeptic — via
      the swarm. Your job is to weave them into one layered final piece.

      Step 1 — Collect all three drafts:

        Poll inbox until three messages arrive on topic "perspective-draft":

          python3 -m scripts.swarm inbox \
            --topic "perspective-draft" \
            --unread-only \
            --mark-delivered

        Repeat every 10 seconds until inbox returns exactly 3 messages.
        Heartbeat while waiting:

          python3 -m scripts.swarm heartbeat --status "waiting for drafts (N/3 received)" --progress <N/3>

      Step 2 — Synthesize:

        For each conceptual section in the source topic, locate the same
        idea across the three drafts. Choose ONE of:
          (a) Interleave: present each framing in subsections, labelled
              [for: beginner], [for: expert], [for: skeptic].
          (b) Weave: choose the strongest framing as the main text; absorb
              the others' best lines as parenthetical insights or callout boxes.

        Produce a final document that serves all three audiences. Use
        [for: beginner|expert|skeptic] annotations on sections that are
        strongly audience-targeted.

      Step 3 — Write output:

        Write the synthesized piece to your output path and exit normally.

        Final heartbeat:

          python3 -m scripts.swarm heartbeat --status "synthesis complete" --progress 1.0
---

## About this team

`perspective-synthesis-team` runs **three perspective-writer workers in parallel**
then passes their combined drafts to a **moderator** that synthesises them into
a single layered document.

### When to use

- Tutorials that must serve beginners AND experts without boring one or losing the other.
- Product write-ups that need to acknowledge sceptical readers without alienating enthusiasts.
- Deep-dives where you want the "practitioner's" view interleaved with the theoretical framing.

### Monitoring while running

Once dispatched, watch live progress with:

```
omw swarm-monitor
```

Or from the leader pane:

```bash
python3 -m scripts.swarm monitor --session <dispatch-session-dir>
```

Each perspective-writer heartbeats after publishing its draft; the moderator
heartbeats while waiting and again when synthesis is complete.

### Output

The moderator's output is written to the standard `result` path for `worker-4-moderator`.
Sections are annotated `[for: beginner]`, `[for: expert]`, `[for: skeptic]`
where the framing is audience-specific.
