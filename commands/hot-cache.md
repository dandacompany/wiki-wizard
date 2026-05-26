# `hot-cache` — inspect or refresh the session continuity cache

**Underlying script:** `scripts.hot_cache`

The hot cache is a short markdown file that lives next to each vault. It carries the recent context a Claude Code session needs to pick up where the last session left off — active vaults, recently touched pages, and a one-paragraph summary of the previous session.

By default the cache is read automatically at SessionStart and refreshed at SessionStop (see `hooks/hooks.json`). The `hot-cache` op exists for manual inspection or forced refresh.

## Flow

### View the current cache

```bash
python3 -m scripts.hot_cache --on-session-start --db data/registry.db
```

Prints the cache text to stdout. Silent (exit 0) if no cache exists yet.

### Force a refresh (no session summary)

```bash
python3 -m scripts.hot_cache --refresh --db data/registry.db
```

Rebuilds the cache from the current registry state (no last-session-summary, just vaults + recent activity).

### Refresh with a session summary

```bash
echo "User worked on the research vault. Ingested 3 papers and ran lint." \
  | python3 -m scripts.hot_cache --on-session-stop --db data/registry.db
```

Same as `--refresh` but pipes a summary in on stdin. The hooks call this form at SessionStop with a summary that Claude Code generates from the just-completed conversation.

## Post-conditions

- A file at one of three locations exists:
  - `<active_vault>/wiki/hot.md` when the active vault is wiki-mode
  - `<active_vault>/hot.md` when memo-mode or any other non-wiki mode
  - `data/hot.md` when no active vault
- File is at most 2000 characters (cap enforced; summary is truncated first if needed).
- File contains three sections: `## Active vaults`, `## Recent activity (last 10 pages)`, `## Last session summary`.

## Error handling

- Cache file already locked by another process → atomic-write via tempfile + rename avoids corruption.
- Missing data directory when no active vault → script creates `data/` automatically.
- DB missing or unreadable → script exits non-zero with a clear stderr message. Hooks ignore the failure (non-blocking) so Claude Code is never blocked by hot-cache problems.
