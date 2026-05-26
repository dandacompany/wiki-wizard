#!/usr/bin/env bash
# Fake claude CLI for OMW dispatch integration tests.
# Accepts a subset of claude's flags; writes deterministic output.
#
# Usage (mirrors real claude non-interactive shape):
#   claude [--dangerously-skip-permissions] --model MODEL
#          --append-system-prompt BODY -p TASK [--output-format FORMAT]
#
# Environment:
#   OMW_FAKE_OUTPUT_PATH   if set, write output here instead of stdout
#   OMW_FAKE_FAIL          if set to "1", exit 1 (simulate failure)
#   OMW_FAKE_FLAGS_LOG     if set, append all argv to this file

set -euo pipefail

MODEL=""
PERSONA_BODY=""
TASK_PROMPT=""
SKIP_PERM=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dangerously-skip-permissions) SKIP_PERM=1; shift ;;
    --model) MODEL="$2"; shift 2 ;;
    --append-system-prompt) PERSONA_BODY="$2"; shift 2 ;;
    -p) TASK_PROMPT="$2"; shift 2 ;;
    --output-format) shift 2 ;;   # accepted, ignored
    --version) echo "claude fake 0.0.0"; exit 0 ;;
    *) shift ;;  # ignore unknown flags
  esac
done

# Log flags if requested
if [[ -n "${OMW_FAKE_FLAGS_LOG:-}" ]]; then
  {
    if [[ "$SKIP_PERM" -eq 1 ]]; then echo "--dangerously-skip-permissions"; fi
    echo "model=${MODEL}"
  } >> "$OMW_FAKE_FLAGS_LOG"
fi

# Honour failure injection
if [[ "${OMW_FAKE_FAIL:-0}" == "1" ]]; then
  echo "FAKE-CLAUDE: injected failure" >&2
  exit 1
fi

OUTPUT="FAKE-CLAUDE model=${MODEL} task=${TASK_PROMPT}"

if [[ -n "${OMW_FAKE_OUTPUT_PATH:-}" ]]; then
  mkdir -p "$(dirname "$OMW_FAKE_OUTPUT_PATH")"
  printf '%s\n' "$OUTPUT" > "$OMW_FAKE_OUTPUT_PATH"
fi

printf '%s\n' "$OUTPUT"
exit 0
