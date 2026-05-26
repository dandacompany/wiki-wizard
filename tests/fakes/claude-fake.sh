#!/usr/bin/env bash
# Fake claude CLI for OMW dispatch integration tests.
# Accepts a subset of claude's flags; writes deterministic output.
#
# Usage (mirrors real claude non-interactive shape):
#   claude [--dangerously-skip-permissions] --model MODEL
#          --append-system-prompt BODY -p TASK [--output-format FORMAT]
#
# Environment:
#   OMW_FAKE_OUTPUT_PATH  if set, write output here instead of stdout

set -euo pipefail

MODEL=""
PERSONA_BODY=""
TASK_PROMPT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dangerously-skip-permissions) shift ;;
    --model) MODEL="$2"; shift 2 ;;
    --append-system-prompt) PERSONA_BODY="$2"; shift 2 ;;
    -p) TASK_PROMPT="$2"; shift 2 ;;
    --output-format) shift 2 ;;   # accepted, ignored
    --version) echo "claude fake 0.0.0"; exit 0 ;;
    *) shift ;;  # ignore unknown flags
  esac
done

OUTPUT="FAKE-CLAUDE model=${MODEL} task=${TASK_PROMPT}"

if [[ -n "${OMW_FAKE_OUTPUT_PATH:-}" ]]; then
  mkdir -p "$(dirname "$OMW_FAKE_OUTPUT_PATH")"
  printf '%s\n' "$OUTPUT" > "$OMW_FAKE_OUTPUT_PATH"
fi

printf '%s\n' "$OUTPUT"
exit 0
