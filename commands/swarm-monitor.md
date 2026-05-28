---
name: swarm-monitor
description: >
  Display the real-time status of a running swarm dispatch session.
  Shows each worker's latest heartbeat, inbox queue depth, alive status,
  and session-wide counters (total messages, active proposals, pending RPCs).
triggers:
  en:
    - "monitor the swarm"
    - "show worker status"
    - "swarm dashboard"
    - "check swarm progress"
    - "what are the workers doing"
    - "show swarm heartbeats"
  ko:
    - "스웜 모니터"
    - "워커 상태 보여줘"
    - "스웜 대시보드"
    - "워커 진행 상황"
    - "스웜 모니터링"
requires: [swarm-enabled dispatch session running or path known]
---

## swarm-monitor — Procedure

### Step 1: Locate the active dispatch session

**Auto-detect:** Check whether any `dispatch-sessions/` directories exist
under the current vault's `.oh-my-wiki/` folder and have been modified within
the last 10 minutes:

```bash
ls -t .oh-my-wiki/dispatch-sessions/ | head -5
```

If exactly one recent session is found, use it. If multiple or none are found,
proceed to the prompt below.

**Prompt the user if needed:**

> Which dispatch session would you like to monitor?
> Please provide the path to the session directory, e.g.:
> `.oh-my-wiki/dispatch-sessions/2026-05-27-xxx-triple-factcheck/`

Store the resolved path as `SESSION_DIR`.

---

### Step 2: Run the monitor command

```bash
python3 -m scripts.swarm monitor --session "$SESSION_DIR"
```

The command prints a JSON object. Capture the output.

---

### Step 3: Render as a table

Parse the JSON and display a compact status table. Example format:

```
Swarm Monitor  —  Session: 2026-05-27-xxx-triple-factcheck
Polled at: 2026-05-27T09:31:05Z

Worker                       Status                         Progress  Alive  Inbox
worker-1-fact-checker        verifying claim 3 of 7         43 %      ✓      0
worker-2-fact-checker        published 4 claims             100 %     ✓      0
worker-3-fact-checker        verifying claim 1 of 7         14 %      ✓      2
worker-4-moderator           waiting for fact-checkers      —         ✓      4

Session totals — Messages: 17  |  Active proposals: 1  |  Pending RPCs: 0
```

Use plain-text table formatting (no markdown tables required — a monospace
`str.ljust()` style output is fine).

Mark `Alive` as `✓` when `"alive": true` in the JSON; mark as `✗ (stale)` when
`"alive": false` (heartbeat older than 30 s). If no heartbeat is present for a
worker, show `— (no heartbeat yet)`.

---

### Step 4: Offer to watch (optional)

Ask the user:

> Would you like to watch for updates? (y / n)
> If yes, how many seconds between refreshes? (default: 5)
> Maximum watch duration in minutes? (default: 10)

If the user says yes, run the monitor in a loop:

```bash
# Watch loop — cap at MAX_DURATION minutes
INTERVAL=5          # seconds between polls (user-provided or default)
MAX_DURATION=600    # seconds total (user-provided * 60 or default)
ELAPSED=0

while [ $ELAPSED -lt $MAX_DURATION ]; do
  python3 -m scripts.swarm monitor --session "$SESSION_DIR"
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
done

echo "Monitor stopped after ${MAX_DURATION}s. Re-run swarm-monitor to resume."
```

**Important:** Always cap the watch loop. Do NOT run `--watch` indefinitely.
If the user wants continuous monitoring, instruct them to run the above in a
dedicated terminal pane rather than through the LLM session.

---

### Step 5: Interpret and report

After one poll (or after stopping the watch loop), summarize in natural language:

- How many workers are alive vs. stale.
- Any workers with a large inbox backlog (unread > 5 is notable).
- Active vote proposals (if any) — what they're deciding.
- Pending RPC calls (if any) — potential bottleneck.
- Overall assessment: "all workers healthy and progressing", "worker-3 appears
  stalled (last heartbeat Xs ago)", etc.

If a worker is marked `alive: false`, suggest:

> worker-N has not sent a heartbeat in over 30 s. You may want to check its
> tmux pane for errors: `omw pane-log worker-N` or inspect
> `<session>/worker-N/pane.log`.
