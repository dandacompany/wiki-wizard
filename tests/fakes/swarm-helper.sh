#!/usr/bin/env bash
# tests/fakes/swarm-helper.sh — shared swarm behavior library for fake backends.
#
# Sourced by claude-fake.sh, codex-fake.sh, gemini-fake.sh.
# Dispatch happens in each fake's main body via:
#   if [[ -n "${OMW_FAKE_SWARM_BEHAVIOR:-}" ]]; then
#     source "$(dirname "$0")/swarm-helper.sh"
#     swarm_dispatch "$OMW_FAKE_SWARM_BEHAVIOR"
#     exit $?
#   fi

SWARM="python3 -m scripts.swarm"

# ─── behavior: publish-claim ─────────────────────────────────────────────────
# Publishes a canned claim message to topic "claim" then exits.
_behavior_publish_claim() {
  local claim_body
  claim_body=$(cat <<'JSON'
{"claim": "Python was created in 1991", "verdict": "supported", "sources": ["python.org/history"]}
JSON
  )
  $SWARM publish --topic "claim" --body "$claim_body"
  $SWARM heartbeat --status "claim published" --progress 1.0
}

# ─── behavior: read-and-vote ─────────────────────────────────────────────────
# Reads inbox for a vote proposal and casts a vote.
_behavior_read_and_vote() {
  local proposal_id="${OMW_FAKE_PROPOSAL_ID:-prop-001}"
  $SWARM vote --proposal-id "$proposal_id" --choice "1991"
  $SWARM heartbeat --status "voted on $proposal_id" --progress 1.0
}

# ─── behavior: rpc-request ───────────────────────────────────────────────────
# Sends an RPC to OMW_FAKE_RPC_TARGET (default: worker-test-2) and prints response.
_behavior_rpc_request() {
  local target="${OMW_FAKE_RPC_TARGET:-worker-test-2}"
  $SWARM rpc --to "$target" --body "review draft at /tmp/fake-draft.md" --timeout 10 || true
}

# ─── behavior: rpc-respond ───────────────────────────────────────────────────
# Responds to an existing RPC request identified by OMW_FAKE_RPC_ID.
_behavior_rpc_respond() {
  local rpc_id="${OMW_FAKE_RPC_ID:-rpc-test-001}"
  $SWARM rpc-respond --rpc-id "$rpc_id" --body "OK"
  $SWARM heartbeat --status "rpc response sent for $rpc_id" --progress 1.0
}

# ─── behavior: perspective-publish ──────────────────────────────────────────
# Publishes a canned perspective draft to topic "perspective-draft".
_behavior_perspective_publish() {
  local draft="[Fake perspective draft from ${OMW_SWARM_WORKER_ID:-worker-unknown}]"
  $SWARM publish --topic "perspective-draft" --body "$draft"
  $SWARM heartbeat --status "perspective draft published" --progress 1.0
}

# ─── behavior: moderator-synthesize ─────────────────────────────────────────
# Reads perspective-draft inbox and writes a canned synthesis (no actual LLM).
_behavior_moderator_synthesize() {
  # Read inbox (mark delivered so counts are accurate in tests)
  $SWARM inbox --topic "perspective-draft" --mark-delivered > /tmp/swarm-fake-inbox.json 2>&1 || true
  $SWARM heartbeat --status "synthesis complete (fake)" --progress 1.0
  echo "[Fake moderator synthesis output]"
}

# ─── dispatcher ─────────────────────────────────────────────────────────────
swarm_dispatch() {
  local behavior="${1:-}"
  case "$behavior" in
    publish-claim)         _behavior_publish_claim ;;
    read-and-vote)         _behavior_read_and_vote ;;
    rpc-request)           _behavior_rpc_request ;;
    rpc-respond)           _behavior_rpc_respond ;;
    perspective-publish)   _behavior_perspective_publish ;;
    moderator-synthesize)  _behavior_moderator_synthesize ;;
    *)
      echo "swarm-helper: unknown behavior '${behavior}'" >&2
      return 1
      ;;
  esac
}
