#!/usr/bin/env bash
# A0 de-risk spike driver for the oh-my-wiki Docker E2E harness.
#
# Validates the three riskiest assumptions before building the full harness:
#   1. Claude Code can OAuth-login inside a Linux container (subscription auth).
#   2. The omw skill is visible to the containerized Claude.
#   3. Bright Data MCP works from inside the container.
#
# Usage:
#   tests/e2e/a0-spike.sh build     # build the image
#   tests/e2e/a0-spike.sh shell     # interactive shell (do `claude` OAuth login here)
#   tests/e2e/a0-spike.sh checks    # run the 3 automated assumption checks
#
# Secrets: the Bright Data MCP URL (contains a token) is read from the host's
# ~/.claude.json at runtime and passed as an env var. It is NEVER written to any
# committed file or echoed.
set -euo pipefail

IMAGE="omw-e2e"
VOLUME="omw-e2e-claude"            # persists /root/.claude (creds + skills) across runs
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

_brightdata_url() {
  # Extract the brightdata MCP URL from the host config without printing it.
  python3 - <<'PY'
import json, pathlib, sys
p = pathlib.Path.home() / ".claude.json"
try:
    d = json.loads(p.read_text())
except Exception:
    sys.exit(0)
def walk(o):
    if isinstance(o, dict):
        for s in o.get("mcpServers", {}).values():
            u = s.get("url", "")
            if "brightdata" in u or "bright" in json.dumps(s).lower():
                print(u); return True
        for v in o.values():
            if walk(v): return True
    return False
walk(d)
PY
}

cmd="${1:-help}"
case "$cmd" in
  build)
    echo "[a0] building ${IMAGE} (context=${REPO_ROOT})..."
    docker build -f "${REPO_ROOT}/tests/e2e/Dockerfile" -t "${IMAGE}" "${REPO_ROOT}"
    echo "[a0] built. Next: tests/e2e/a0-spike.sh shell  (then run 'claude' to log in)"
    ;;
  shell)
    BD_URL="$(_brightdata_url || true)"
    [ -n "${BD_URL}" ] && echo "[a0] Bright Data MCP URL found on host (token hidden)." \
                       || echo "[a0] WARNING: no Bright Data MCP URL on host; MCP check will be skipped."
    echo "[a0] entering container. To authenticate: run 'claude' and follow the login URL."
    docker run --rm -it \
      -v "${VOLUME}:/root/.claude" \
      -e "BRIGHTDATA_MCP_URL=${BD_URL}" \
      "${IMAGE}" bash
    ;;
  checks)
    BD_URL="$(_brightdata_url || true)"
    echo "[a0] running assumption checks (requires you already logged in via 'shell')..."
    docker run --rm -it \
      -v "${VOLUME}:/root/.claude" \
      -e "BRIGHTDATA_MCP_URL=${BD_URL}" \
      "${IMAGE}" bash -lc '
        echo "--- check 1: auth present? ---"
        test -f /root/.claude/.credentials.json && echo "OK creds file present" || echo "FAIL no creds (log in via shell first)"
        echo "--- check 2: omw skill visible? ---"
        ls -l /root/.claude/skills/ 2>/dev/null
        readlink /root/.claude/skills/oh-my-wiki 2>/dev/null && echo "OK omw symlink resolves" || echo "FAIL omw skill missing"
        echo "--- check 2b: claude sees the skill (headless) ---"
        claude -p --dangerously-skip-permissions "List your available skills by name. Is oh-my-wiki (omw) among them? Answer yes/no and list." 2>&1 | tail -20
        echo "--- check 3: Bright Data MCP reachable (headless) ---"
        claude mcp list 2>&1 | tail -10
        claude -p --dangerously-skip-permissions "Use the Bright Data MCP search tool to search '\''latest AI agent frameworks 2026'\'' and return the top 3 result titles." 2>&1 | tail -25
      '
    ;;
  *)
    echo "usage: tests/e2e/a0-spike.sh [build|shell|checks]"; exit 1 ;;
esac
