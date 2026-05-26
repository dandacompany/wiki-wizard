#!/usr/bin/env bash
# Fake gemini CLI for OMW dispatch integration tests.
# Shape: gemini --model MODEL --system BODY -p TASK

set -euo pipefail

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

OUTPUT="FAKE-GEMINI model=${MODEL} task=${TASK_PROMPT}"

if [[ -n "${OMW_FAKE_OUTPUT_PATH:-}" ]]; then
  mkdir -p "$(dirname "$OMW_FAKE_OUTPUT_PATH")"
  printf '%s\n' "$OUTPUT" > "$OMW_FAKE_OUTPUT_PATH"
fi

printf '%s\n' "$OUTPUT"
exit 0
