---
name: live-monitor
description: >
  Documentation-only template. Explains how to monitor ANY swarm team in
  real time using commands/swarm-monitor.md and the swarm heartbeat
  primitive. Does not define workers — wrap your actual team template and
  call swarm-monitor from the leader session while it runs.
workers: []
---

## live-monitor: Real-time swarm dashboard

`live-monitor` is not a runnable team on its own. It is a **reference template**
that documents the monitoring pattern applicable to any swarm team (those with
`swarm: true` in their manifest).

### How monitoring works

Every swarm-aware worker is expected to call:

```bash
python3 -m scripts.swarm heartbeat \
  --status "<human-readable progress description>" \
  --progress <0.0-1.0>
```

periodically (typically once per major step). The heartbeat overwrites
`<session>/worker-<id>/heartbeat.json` with the latest status + timestamp.

The leader (or any interested party) then reads aggregated state with:

```bash
python3 -m scripts.swarm monitor --session <dispatch-session-dir>
```

which returns a JSON dashboard showing, for each worker:

- latest heartbeat status + timestamp
- number of unread inbox messages
- whether the worker is considered "alive" (heartbeat age < 30 s)

Plus session-wide counters: total messages, active vote proposals, pending RPCs.

### Invoking from the LLM leader session

Use the `commands/swarm-monitor.md` procedure from your leader Claude Code
window. It guides you to:

1. Detect the active dispatch session (or ask the user for its path).
2. Run `python3 -m scripts.swarm monitor --session <dir>`.
3. Render the JSON output as a readable table.
4. Optionally loop with `--watch` until you interrupt or the session ends.

```
omw swarm-monitor
```

### Adding monitoring to your own team

1. In your team manifest, set `swarm: true`.
2. In each worker's `swarm_instructions`, add a heartbeat call after every
   major step.
3. Optionally, subscribe workers to topics they care about so `monitor` can
   show topic-level activity:

   ```bash
   python3 -m scripts.swarm subscribe --topic "claim"
   ```

4. While the team runs, call `omw swarm-monitor` from your leader session.

### Heartbeat frequency guidelines

| Scenario                     | Frequency                             |
| ---------------------------- | ------------------------------------- |
| Short sub-task (< 30 s)      | Once at start, once at end            |
| Medium task (30 s – 5 min)   | Every 30 s                            |
| Long research task (> 5 min) | Every 60 s, + at each major milestone |
| Waiting for RPC / vote       | Every poll cycle                      |

Workers that don't heartbeat for > 30 s are marked `"alive": false` in the
monitor dashboard — useful for detecting hung workers early.
