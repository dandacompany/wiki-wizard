# oh-my-wiki — Docker E2E harness (sub-project A)

Validates omw end-to-end by driving a containerized Claude Code (with the omw
skill installed) through a real wiki-construction scenario, then verifying the
actual on-disk / registry effects out-of-band.

## A0 — de-risk spike (run this first)

Before building the full harness, prove the three riskiest assumptions:

1. Claude Code OAuth-logs-in inside a Linux container (uses your Max/Pro
   subscription — no API key, no extra billing).
2. The omw skill is visible to the containerized Claude.
3. Bright Data MCP works from inside the container.

```bash
tests/e2e/a0-spike.sh build      # build the omw-e2e image
tests/e2e/a0-spike.sh shell      # inside: run `claude`, open the login URL on your
                                 # Mac browser, authorize. Creds persist in a volume.
tests/e2e/a0-spike.sh checks     # automated: creds present? skill visible? MCP call works?
```

Notes:

- Auth + skills persist in the `omw-e2e-claude` named volume across runs.
- `OMW_HOME=/work/.omw` inside the container — fully isolated from any real `~/.omw`.
- The Bright Data MCP URL (token inside) is read from the host `~/.claude.json` at
  runtime and passed via `$BRIGHTDATA_MCP_URL`. It is never baked into the image or
  committed.

## Driving model (full harness, A1+)

Hybrid: headless `claude -p --dangerously-skip-permissions --output-format
stream-json` for deterministic verification steps; tmux `capture-pane` snapshots
of a few key interactive scenes (vault-setup, a query answer) for UX evidence.

## Verification

After each omw op, the harness inspects the isolated `OMW_HOME` directly with omw
scripts (registry rows, vault files, `wiki/index.md`, syntheses) to confirm the
skill did what it claimed. Gaps go to `docs/e2e/<date>-...md` as a next-phase
improvement checklist.
