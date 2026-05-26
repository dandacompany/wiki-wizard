#!/usr/bin/env bash
# Fake opencode CLI for OMW dispatch integration tests.
# Shape: opencode run --model MODEL --system BODY TASK
#
# Environment:
#   OMW_FAKE_FAIL  if set to "1", exit 1 (simulate failure)

set -euo pipefail

SUBCOMMAND=""
MODEL=""
PERSONA_BODY=""
TASK_PROMPT=""

if [[ "${1:-}" == "run" || "${1:-}" == "--version" ]]; then
  SUBCOMMAND="$1"; shift
fi

if [[ "$SUBCOMMAND" == "--version" ]]; then
  echo "opencode fake 0.0.0"; exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) echo "opencode fake 0.0.0"; exit 0 ;;
    --model) MODEL="$2"; shift 2 ;;
    --system) PERSONA_BODY="$2"; shift 2 ;;
    -*) shift 2 2>/dev/null || shift ;;
    *) TASK_PROMPT="$1"; shift ;;
  esac
done

# Honour failure injection
if [[ "${OMW_FAKE_FAIL:-0}" == "1" ]]; then
  echo "FAKE-OPENCODE: injected failure" >&2
  exit 1
fi

OUTPUT="FAKE-OPENCODE model=${MODEL} task=${TASK_PROMPT}"

if [[ -n "${OMW_FAKE_OUTPUT_PATH:-}" ]]; then
  mkdir -p "$(dirname "$OMW_FAKE_OUTPUT_PATH")"
  printf '%s\n' "$OUTPUT" > "$OMW_FAKE_OUTPUT_PATH"
fi

printf '%s\n' "$OUTPUT"
exit 0
