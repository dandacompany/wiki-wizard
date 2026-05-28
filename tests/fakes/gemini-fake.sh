#!/usr/bin/env bash
# Fake gemini CLI for OMW dispatch integration tests.
# Shape: gemini --model MODEL --system BODY -p TASK
#
# Environment:
#   OMW_FAKE_FAIL  if set to "1", exit 1 (simulate failure)

set -euo pipefail

# ─── Swarm behavior dispatch (for hermetic swarm testing) ───────────────────
if [[ -n "${OMW_FAKE_SWARM_BEHAVIOR:-}" ]]; then
  # shellcheck source=swarm-helper.sh
  source "$(dirname "$0")/swarm-helper.sh"
  swarm_dispatch "$OMW_FAKE_SWARM_BEHAVIOR"
  exit $?
fi
# ────────────────────────────────────────────────────────────────────────────

MODEL=""
PERSONA_BODY=""
TASK_PROMPT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) echo "gemini fake 0.0.0"; exit 0 ;;
    --model) MODEL="$2"; shift 2 ;;
    --system) PERSONA_BODY="$2"; shift 2 ;;
    -p) TASK_PROMPT="$2"; shift 2 ;;
    -*) shift 2 2>/dev/null || shift ;;
    *) shift ;;
  esac
done

# Honour failure injection
if [[ "${OMW_FAKE_FAIL:-0}" == "1" ]]; then
  echo "FAKE-GEMINI: injected failure" >&2
  exit 1
fi

OUTPUT="FAKE-GEMINI model=${MODEL} task=${TASK_PROMPT}"

if [[ -n "${OMW_FAKE_OUTPUT_PATH:-}" ]]; then
  mkdir -p "$(dirname "$OMW_FAKE_OUTPUT_PATH")"
  printf '%s\n' "$OUTPUT" > "$OMW_FAKE_OUTPUT_PATH"
fi

printf '%s\n' "$OUTPUT"
exit 0
