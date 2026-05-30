#!/usr/bin/env bash
# Container entrypoint for the omw E2E image.
# Runs at every container start (after volume mounts), so the omw skill lands in
# the (possibly volume-backed) ~/.claude/skills, and the Bright Data MCP gets
# registered when its URL is provided at runtime via $BRIGHTDATA_MCP_URL.
set -euo pipefail

SKILLS_DIR="${HOME}/.claude/skills"

# 1) Install the omw skill (idempotent; --force replaces stale symlinks).
bash /opt/oh-my-wiki/bin/install.sh --force --no-test --skills-dir "${SKILLS_DIR}" \
    >/tmp/omw-install.log 2>&1 || {
        echo "[omw-entrypoint] WARNING: skill install failed; see /tmp/omw-install.log" >&2
    }

# 2) Register Bright Data MCP (remote HTTP transport) if a URL was injected.
#    The token lives inside $BRIGHTDATA_MCP_URL — never baked into the image.
if [ -n "${BRIGHTDATA_MCP_URL:-}" ]; then
    claude mcp add brightdata --scope user --transport http "${BRIGHTDATA_MCP_URL}" \
        >/tmp/omw-mcp.log 2>&1 \
    || claude mcp add --transport http --scope user brightdata "${BRIGHTDATA_MCP_URL}" \
        >>/tmp/omw-mcp.log 2>&1 \
    || echo "[omw-entrypoint] WARNING: brightdata MCP add failed; see /tmp/omw-mcp.log" >&2
fi

exec "$@"
