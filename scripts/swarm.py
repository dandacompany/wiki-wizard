"""Swarm messaging bus for oh-my-wiki v2.4.

All operations use file I/O only — no sockets, no IPC, no MCP.
Identity is read from environment:
    OMW_SWARM_SESSION_DIR  — path to dispatch session directory
    OMW_SWARM_WORKER_ID    — this worker's id (e.g. "worker-1-fact-checker")
    OMW_SWARM_PEERS        — comma-separated peer worker ids (excludes self)

Exit codes:
    0   — ok
    1   — generic runtime error
    2   — invalid args / missing env
    3   — quorum not reached (vote-result without --wait)
    124 — timeout (rpc --timeout, vote-result --wait)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Environment context
# ---------------------------------------------------------------------------

class SwarmContext:
    """Holds resolved session dir, worker id, and peer list."""

    def __init__(self, session_dir: Path, worker_id: str, peers: list[str]) -> None:
        self.session_dir = session_dir
        self.worker_id = worker_id
        self.peers = peers  # excludes self

    # ---- path helpers ----

    def worker_dir(self, worker_id: str | None = None) -> Path:
        wid = worker_id or self.worker_id
        return self.session_dir / wid

    def inbox_dir(self, worker_id: str | None = None) -> Path:
        return self.worker_dir(worker_id) / "inbox"

    def delivered_dir(self, worker_id: str | None = None) -> Path:
        return self.inbox_dir(worker_id) / ".delivered"

    def messages_dir(self) -> Path:
        return self.session_dir / "messages"

    def proposals_dir(self) -> Path:
        return self.session_dir / "proposals"

    def rpc_dir(self) -> Path:
        return self.session_dir / "rpc"

    def heartbeat_path(self, worker_id: str | None = None) -> Path:
        return self.worker_dir(worker_id) / "heartbeat.json"

    def subscriptions_path(self, worker_id: str | None = None) -> Path:
        return self.worker_dir(worker_id) / "subscriptions.json"


def _load_env_context() -> SwarmContext:
    """Read OMW_SWARM_* env vars and return a SwarmContext.

    Exits with code 2 if SESSION_DIR or WORKER_ID are missing.
    """
    session_dir_raw = os.environ.get("OMW_SWARM_SESSION_DIR", "")
    worker_id = os.environ.get("OMW_SWARM_WORKER_ID", "")
    peers_raw = os.environ.get("OMW_SWARM_PEERS", "")

    if not session_dir_raw:
        print(
            "error: OMW_SWARM_SESSION_DIR is not set. "
            "This command must be run inside a swarm-enabled dispatch worker.",
            file=sys.stderr,
        )
        sys.exit(2)
    if not worker_id:
        print(
            "error: OMW_SWARM_WORKER_ID is not set. "
            "This command must be run inside a swarm-enabled dispatch worker.",
            file=sys.stderr,
        )
        sys.exit(2)

    session_dir = Path(session_dir_raw)
    peers = [p.strip() for p in peers_raw.split(",") if p.strip() and p.strip() != worker_id]

    return SwarmContext(session_dir=session_dir, worker_id=worker_id, peers=peers)


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    """Write JSON to path atomically via temp-file + rename.

    Creates parent directories as needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp-{uuid.uuid4().hex[:8]}")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


# ---------------------------------------------------------------------------
# Message ID generation
# ---------------------------------------------------------------------------

def _new_msg_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    short = uuid.uuid4().hex[:6]
    return f"msg-{ts}-{short}"


# ---------------------------------------------------------------------------
# Content dedup (5-second window)
# ---------------------------------------------------------------------------

_DEDUP_WINDOW_SEC = 5.0


def _content_hash(body: str, to: str) -> str:
    raw = f"{to}|{body}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _is_duplicate(ctx: SwarmContext, content_hash: str) -> bool:
    """Return True if this hash was written by this worker in the last 5s."""
    dedup_dir = ctx.session_dir / ".dedup" / ctx.worker_id
    dedup_dir.mkdir(parents=True, exist_ok=True)
    stamp_path = dedup_dir / f"{content_hash}.json"
    if stamp_path.exists():
        try:
            data = json.loads(stamp_path.read_text(encoding="utf-8"))
            written_at = data.get("written_at", 0.0)
            if time.time() - written_at < _DEDUP_WINDOW_SEC:
                return True
        except Exception:
            pass
    # Not a duplicate — stamp it
    _atomic_write(stamp_path, {"written_at": time.time(), "hash": content_hash})
    return False


# ---------------------------------------------------------------------------
# cmd: inbox
# ---------------------------------------------------------------------------

def _read_inbox_messages(ctx: SwarmContext, include_delivered: bool = False) -> list[dict]:
    """Scan inbox dir, return list of message dicts sorted by sent_at."""
    inbox = ctx.inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)

    messages: list[dict] = []

    # Unread: direct children of inbox/ (excluding .delivered/)
    for f in inbox.iterdir():
        if f.is_dir():
            continue
        if not f.suffix == ".json":
            continue
        try:
            messages.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass

    if include_delivered:
        delivered = ctx.delivered_dir()
        if delivered.exists():
            for f in delivered.iterdir():
                if f.suffix == ".json":
                    try:
                        msg = json.loads(f.read_text(encoding="utf-8"))
                        msg.setdefault("_delivered", True)
                        messages.append(msg)
                    except Exception:
                        pass

    # Sort by sent_at ascending (lexicographic on ISO timestamps works)
    messages.sort(key=lambda m: m.get("sent_at", ""))
    return messages


def cmd_inbox(ctx: SwarmContext, args: argparse.Namespace) -> int:
    """Read messages from this worker's inbox."""
    # --unread-only: only unread (not delivered); default: only unread too
    msgs = _read_inbox_messages(ctx, include_delivered=False)

    # Topic filter
    if args.topic:
        msgs = [m for m in msgs if m.get("topic") == args.topic]

    if args.mark_delivered:
        delivered_dir = ctx.delivered_dir()
        delivered_dir.mkdir(parents=True, exist_ok=True)
        inbox = ctx.inbox_dir()
        for msg in msgs:
            msg_id = msg.get("msg_id", "")
            src = inbox / f"{msg_id}.json"
            dst = delivered_dir / f"{msg_id}.json"
            if src.exists():
                src.replace(dst)

    print(json.dumps(msgs, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Internal: write message + deliver to inbox(es)
# ---------------------------------------------------------------------------

def _write_message(
    ctx: SwarmContext,
    to: str,
    body: str,
    *,
    topic: str = "",
    correlation_id: str = "",
) -> dict[str, Any]:
    """Write canonical message envelope + copy to recipient inbox.

    Returns the envelope dict (includes msg_id, sent_at).
    """
    msg_id = _new_msg_id()
    envelope: dict[str, Any] = {
        "msg_id": msg_id,
        "from": ctx.worker_id,
        "to": to,
        "body": body,
        "sent_at": _now_iso(),
    }
    if topic:
        envelope["topic"] = topic
    if correlation_id:
        envelope["correlation_id"] = correlation_id

    # 1. Canonical store
    canonical_path = ctx.messages_dir() / f"{msg_id}.json"
    _atomic_write(canonical_path, envelope)

    # 2. Inbox copy (only for point-to-point)
    if to != "*":
        inbox_path = ctx.inbox_dir(to) / f"{msg_id}.json"
        _atomic_write(inbox_path, envelope)

    return envelope


def cmd_send(ctx: SwarmContext, args: argparse.Namespace) -> int:
    if not args.to or args.to == "*":
        print(
            "error: --to must specify a single worker id. "
            "Use 'broadcast' to send to all peers.",
            file=sys.stderr,
        )
        return 1
    chash = _content_hash(args.body, args.to)
    if _is_duplicate(ctx, chash):
        print(json.dumps({"msg_id": None, "skipped": "duplicate", "hash": chash}))
        return 0
    envelope = _write_message(
        ctx, args.to, args.body,
        topic=args.topic or "",
        correlation_id=args.correlation_id or "",
    )
    print(json.dumps({"msg_id": envelope["msg_id"], "delivered_at": envelope["sent_at"]}))
    return 0


def cmd_publish(ctx: SwarmContext, args: argparse.Namespace) -> int:
    """Publish = broadcast with a mandatory --topic."""
    # Delegate entirely to cmd_broadcast — args.topic is already set by argparse
    return cmd_broadcast(ctx, args)


def cmd_broadcast(ctx: SwarmContext, args: argparse.Namespace) -> int:
    chash = _content_hash(args.body, "*")
    if _is_duplicate(ctx, chash):
        print(json.dumps({"msg_id": None, "skipped": "duplicate", "recipients": []}))
        return 0
    # Write canonical envelope with to="*"
    msg_id = _new_msg_id()
    envelope: dict[str, Any] = {
        "msg_id": msg_id,
        "from": ctx.worker_id,
        "to": "*",
        "body": args.body,
        "sent_at": _now_iso(),
    }
    if args.topic:
        envelope["topic"] = args.topic
    canonical_path = ctx.messages_dir() / f"{msg_id}.json"
    _atomic_write(canonical_path, envelope)
    # Deliver to each peer's inbox (ctx.peers already excludes self)
    for peer in ctx.peers:
        inbox_path = ctx.inbox_dir(peer) / f"{msg_id}.json"
        _atomic_write(inbox_path, envelope)
    print(json.dumps({"msg_id": msg_id, "recipients": ctx.peers}))
    return 0


# ---------------------------------------------------------------------------
# cmd: subscribe
# ---------------------------------------------------------------------------

def cmd_subscribe(ctx: SwarmContext, args: argparse.Namespace) -> int:
    """Record topic subscription in subscriptions.json (advisory only)."""
    subs_path = ctx.subscriptions_path()
    # Read existing or start fresh
    if subs_path.exists():
        try:
            existing = json.loads(subs_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    else:
        existing = {}

    topics: list[str] = existing.get("topics", [])
    if args.topic not in topics:
        topics.append(args.topic)

    _atomic_write(subs_path, {
        "worker_id": ctx.worker_id,
        "topics": topics,
        "updated_at": _now_iso(),
    })
    print(json.dumps({"subscribed": args.topic, "all_topics": topics}))
    return 0


# ---------------------------------------------------------------------------
# cmd: heartbeat
# ---------------------------------------------------------------------------

def cmd_heartbeat(ctx: SwarmContext, args: argparse.Namespace) -> int:
    hb_path = ctx.heartbeat_path()
    _atomic_write(hb_path, {
        "worker_id": ctx.worker_id,
        "ts": _now_iso(),
        "status": args.status,
        "progress": float(args.progress) if args.progress is not None else None,
    })
    print(json.dumps({"updated": True, "worker_id": ctx.worker_id}))
    return 0


# ---------------------------------------------------------------------------
# cmd: monitor
# ---------------------------------------------------------------------------

_ALIVE_THRESHOLD_SEC = 30


def _count_inbox_unread(ctx: SwarmContext, worker_id: str) -> int:
    inbox = ctx.inbox_dir(worker_id)
    if not inbox.exists():
        return 0
    return sum(
        1 for f in inbox.iterdir()
        if f.suffix == ".json" and not f.is_dir()
    )


def _is_alive(ts_iso: str) -> bool:
    """Return True if ts_iso is within the last 30 seconds."""
    try:
        # Parse ISO timestamp (with trailing Z or microseconds+Z)
        ts_iso_clean = ts_iso.rstrip("Z").replace("T", " ")
        dt = datetime.fromisoformat(ts_iso_clean).replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - dt).total_seconds()
        return age < _ALIVE_THRESHOLD_SEC
    except Exception:
        return False


def _build_dashboard(ctx: SwarmContext) -> dict[str, Any]:
    """Aggregate all workers' heartbeats + inbox counts into a dashboard dict."""
    workers: list[dict] = []
    session_dir = ctx.session_dir

    # Discover worker dirs (any subdir matching "worker-*")
    if session_dir.exists():
        for child in sorted(session_dir.iterdir()):
            if not child.is_dir():
                continue
            if not child.name.startswith("worker-"):
                continue
            wid = child.name
            hb_path = child / "heartbeat.json"
            hb: dict | None = None
            if hb_path.exists():
                try:
                    hb = json.loads(hb_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            alive = _is_alive(hb["ts"]) if hb and "ts" in hb else False
            workers.append({
                "worker_id": wid,
                "heartbeat": hb,
                "inbox_unread": _count_inbox_unread(ctx, wid),
                "alive": alive,
            })

    # Count canonical messages
    messages_dir = ctx.messages_dir()
    messages_total = (
        sum(1 for f in messages_dir.glob("*.json")) if messages_dir.exists() else 0
    )

    # Count active proposals
    proposals_dir = ctx.proposals_dir()
    active_proposals = 0
    if proposals_dir.exists():
        for prop in proposals_dir.iterdir():
            if prop.is_dir():
                active_proposals += 1

    # Count pending RPCs (request.json exists, response.json does not)
    rpc_dir = ctx.rpc_dir()
    pending_rpcs = 0
    if rpc_dir.exists():
        for rpc in rpc_dir.iterdir():
            if rpc.is_dir():
                if (rpc / "request.json").exists() and not (rpc / "response.json").exists():
                    pending_rpcs += 1

    return {
        "session": str(ctx.session_dir),
        "polled_at": _now_iso(),
        "workers": workers,
        "messages_total": messages_total,
        "active_proposals": active_proposals,
        "pending_rpcs": pending_rpcs,
    }


def cmd_monitor(ctx: SwarmContext, args: argparse.Namespace) -> int:
    if args.watch:
        interval = float(getattr(args, "interval", 2))
        try:
            while True:
                dashboard = _build_dashboard(ctx)
                print(json.dumps(dashboard))
                sys.stdout.flush()
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
        return 0

    dashboard = _build_dashboard(ctx)
    print(json.dumps(dashboard, indent=2))
    return 0


# ---------------------------------------------------------------------------
# cmd: rpc
# ---------------------------------------------------------------------------

_RPC_POLL_INTERVAL = 0.5  # seconds


def _new_rpc_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    short = uuid.uuid4().hex[:6]
    return f"rpc-{ts}-{short}"


def cmd_rpc(ctx: SwarmContext, args: argparse.Namespace) -> int:
    rpc_id = _new_rpc_id()
    timeout = float(getattr(args, "timeout", 60))

    # 1. Write request.json
    rpc_dir = ctx.rpc_dir() / rpc_id
    request_data: dict[str, Any] = {
        "rpc_id": rpc_id,
        "from": ctx.worker_id,
        "to": args.to,
        "body": args.body,
        "sent_at": _now_iso(),
    }
    _atomic_write(rpc_dir / "request.json", request_data)

    # 2. Deliver to recipient inbox with correlation_id
    _write_message(
        ctx, args.to, args.body,
        topic="",
        correlation_id=rpc_id,
    )

    # 3. Poll for response.json
    response_path = rpc_dir / "response.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if response_path.exists():
            try:
                resp = json.loads(response_path.read_text(encoding="utf-8"))
                print(json.dumps(resp))
                return 0
            except Exception:
                pass
        time.sleep(_RPC_POLL_INTERVAL)

    # Timeout
    print(
        f"error: rpc timeout after {timeout}s waiting for response to {rpc_id}",
        file=sys.stderr,
    )
    return 124


# ---------------------------------------------------------------------------
# cmd: rpc-respond
# ---------------------------------------------------------------------------

def cmd_rpc_respond(ctx: SwarmContext, args: argparse.Namespace) -> int:
    rpc_id = args.rpc_id
    rpc_dir = ctx.rpc_dir() / rpc_id
    request_path = rpc_dir / "request.json"

    if not request_path.exists():
        print(
            f"error: rpc request not found: {request_path}",
            file=sys.stderr,
        )
        return 1

    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"error: could not read request.json: {exc}", file=sys.stderr)
        return 1

    # Validate that this RPC was addressed to us
    expected_to = request.get("to", "")
    if expected_to != ctx.worker_id:
        print(
            f"error: this RPC ({rpc_id}) is addressed to {expected_to!r}, "
            f"but this worker is {ctx.worker_id!r}. Cannot respond to another worker's RPC.",
            file=sys.stderr,
        )
        return 1

    response_data = {
        "rpc_id": rpc_id,
        "from": ctx.worker_id,
        "to": request.get("from", ""),
        "body": args.body,
        "responded_at": _now_iso(),
    }
    _atomic_write(rpc_dir / "response.json", response_data)
    print(json.dumps({"responded": True, "rpc_id": rpc_id}))
    return 0


# ---------------------------------------------------------------------------
# cmd: vote-create
# ---------------------------------------------------------------------------

def _new_prop_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    short = uuid.uuid4().hex[:6]
    return f"prop-{ts}-{short}"


def cmd_vote_create(ctx: SwarmContext, args: argparse.Namespace) -> int:
    prop_id = _new_prop_id()
    choices_raw = getattr(args, "choices", "") or ""
    choices = [c.strip() for c in choices_raw.split(",") if c.strip()] if choices_raw else []

    # Quorum default = number of peers (all workers except initiator)
    quorum = int(getattr(args, "quorum", 0) or 0)
    if quorum <= 0:
        quorum = len(ctx.peers)

    proposal_data: dict[str, Any] = {
        "proposal_id": prop_id,
        "proposal_text": args.proposal,
        "choices": choices,  # empty = free-form
        "quorum": quorum,
        "created_by": ctx.worker_id,
        "created_at": _now_iso(),
    }
    prop_dir = ctx.proposals_dir() / prop_id
    _atomic_write(prop_dir / "proposal.json", proposal_data)
    print(json.dumps({"proposal_id": prop_id, "quorum": quorum}))
    return 0


# ---------------------------------------------------------------------------
# cmd: vote
# ---------------------------------------------------------------------------

def cmd_vote(ctx: SwarmContext, args: argparse.Namespace) -> int:
    prop_id = args.proposal_id
    prop_dir = ctx.proposals_dir() / prop_id
    proposal_path = prop_dir / "proposal.json"

    if not proposal_path.exists():
        print(f"error: proposal not found: {prop_id}", file=sys.stderr)
        return 1

    vote_data = {
        "worker_id": ctx.worker_id,
        "choice": args.choice,
        "voted_at": _now_iso(),
    }
    vote_file = prop_dir / f"vote-{ctx.worker_id}.json"
    _atomic_write(vote_file, vote_data)
    print(json.dumps({"voted": True, "proposal_id": prop_id, "choice": args.choice}))
    return 0


# ---------------------------------------------------------------------------
# cmd: vote-result
# ---------------------------------------------------------------------------

_VOTE_POLL_INTERVAL = 0.5  # seconds


def _tally_votes(prop_dir: Path, proposal_data: dict) -> dict[str, Any]:
    """Read all vote-*.json files, compute tally, winner, dissenters."""
    tally: dict[str, int] = {}
    all_votes: list[dict] = []

    for vote_file in prop_dir.glob("vote-*.json"):
        try:
            vd = json.loads(vote_file.read_text(encoding="utf-8"))
            choice = vd.get("choice", "")
            tally[choice] = tally.get(choice, 0) + 1
            all_votes.append(vd)
        except Exception:
            pass

    # Determine winner: simple majority; tie-break by lexicographic order
    winner = ""
    if tally:
        max_votes = max(tally.values())
        candidates = sorted(
            (choice for choice, count in tally.items() if count == max_votes)
        )
        winner = candidates[0]  # lex-first among tied leaders

    # Dissenters = workers whose choice != winner
    dissenters = [
        {"worker_id": v["worker_id"], "choice": v["choice"]}
        for v in all_votes
        if v.get("choice") != winner
    ]

    quorum = proposal_data.get("quorum", 0)
    votes_received = len(all_votes)

    return {
        "proposal_id": proposal_data["proposal_id"],
        "proposal_text": proposal_data.get("proposal_text", ""),
        "tally": tally,
        "winner": winner,
        "dissenters": dissenters,
        "quorum": quorum,
        "votes_received": votes_received,
        "quorum_reached": votes_received >= quorum,
    }


def cmd_vote_result(ctx: SwarmContext, args: argparse.Namespace) -> int:
    prop_id = args.proposal_id
    prop_dir = ctx.proposals_dir() / prop_id
    proposal_path = prop_dir / "proposal.json"

    if not proposal_path.exists():
        print(f"error: proposal not found: {prop_id}", file=sys.stderr)
        return 1

    proposal_data = json.loads(proposal_path.read_text(encoding="utf-8"))
    wait = getattr(args, "wait", False)
    timeout = float(getattr(args, "timeout", 60))

    if wait:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = _tally_votes(prop_dir, proposal_data)
            if result["quorum_reached"]:
                print(json.dumps(result, indent=2))
                return 0
            time.sleep(_VOTE_POLL_INTERVAL)
        # Timeout while waiting for quorum
        result = _tally_votes(prop_dir, proposal_data)
        print(json.dumps(result, indent=2))
        return 124

    result = _tally_votes(prop_dir, proposal_data)
    if not result["quorum_reached"]:
        print(json.dumps(result, indent=2))
        return 3

    print(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3 -m scripts.swarm",
        description="oh-my-wiki swarm messaging bus",
    )
    sub = p.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # inbox
    inbox_p = sub.add_parser("inbox", help="Read messages from this worker's inbox")
    inbox_p.add_argument("--topic", default="", help="Filter by topic")
    inbox_p.add_argument("--unread-only", action="store_true", dest="unread_only",
                         help="Only return messages not yet marked delivered")
    inbox_p.add_argument("--mark-delivered", action="store_true", dest="mark_delivered",
                         help="Move returned messages to .delivered/ after reading")

    # send
    send_p = sub.add_parser("send", help="Send a message to a specific peer")
    send_p.add_argument("--to", required=True, help="Recipient worker id")
    send_p.add_argument("--body", required=True, help="Message body (text or JSON string)")
    send_p.add_argument("--topic", default="", help="Optional topic tag")
    send_p.add_argument("--correlation-id", default="", dest="correlation_id",
                        help="Correlation id for RPC pairing")

    # broadcast
    bc_p = sub.add_parser("broadcast", help="Send a message to all peers")
    bc_p.add_argument("--body", required=True, help="Message body")
    bc_p.add_argument("--topic", default="", help="Optional topic tag")

    # publish
    pub_p = sub.add_parser("publish", help="Broadcast with a mandatory topic tag (alias for broadcast --topic)")
    pub_p.add_argument("--topic", required=True, help="Topic name (required)")
    pub_p.add_argument("--body", required=True, help="Message body")

    # subscribe
    sub_p = sub.add_parser("subscribe", help="Record topic subscription (advisory)")
    sub_p.add_argument("--topic", required=True, help="Topic to subscribe to")

    # heartbeat
    hb_p = sub.add_parser("heartbeat", help="Update this worker's heartbeat status")
    hb_p.add_argument("--status", required=True, help="Status text")
    hb_p.add_argument("--progress", default=None, type=float,
                      help="Progress fraction 0.0–1.0 (optional)")

    # monitor
    mon_p = sub.add_parser("monitor", help="Aggregate dashboard of all worker states")
    mon_p.add_argument("--watch", action="store_true", help="Poll continuously")
    mon_p.add_argument("--interval", type=float, default=2.0,
                       help="Poll interval in seconds (with --watch)")

    # rpc
    rpc_p = sub.add_parser("rpc", help="Send a synchronous RPC request and wait for response")
    rpc_p.add_argument("--to", required=True, help="Recipient worker id")
    rpc_p.add_argument("--body", required=True, help="Request body")
    rpc_p.add_argument("--timeout", type=float, default=60.0,
                       help="Seconds to wait for response (default 60)")

    # rpc-respond
    rpcr_p = sub.add_parser("rpc-respond", help="Write a response to an incoming RPC request")
    rpcr_p.add_argument("--rpc-id", required=True, dest="rpc_id", help="RPC id to respond to")
    rpcr_p.add_argument("--body", required=True, help="Response body")

    # vote-create
    vc_p = sub.add_parser("vote-create", help="Create a new vote proposal")
    vc_p.add_argument("--proposal", required=True, help="Proposal text")
    vc_p.add_argument("--choices", default="",
                      help="Comma-separated list of allowed choices (empty = free-form)")
    vc_p.add_argument("--quorum", type=int, default=0,
                      help="Min votes needed (default = peer count)")

    # vote
    v_p = sub.add_parser("vote", help="Cast a vote on a proposal")
    v_p.add_argument("--proposal-id", required=True, dest="proposal_id")
    v_p.add_argument("--choice", required=True)

    # vote-result
    vr_p = sub.add_parser("vote-result", help="Get the current tally for a proposal")
    vr_p.add_argument("--proposal-id", required=True, dest="proposal_id")
    vr_p.add_argument("--wait", action="store_true",
                      help="Block until quorum is reached")
    vr_p.add_argument("--timeout", type=float, default=60.0,
                      help="Max seconds to wait with --wait (default 60)")

    return p


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand is None:
        parser.print_help(sys.stderr)
        return 2

    ctx = _load_env_context()

    if args.subcommand == "inbox":
        return cmd_inbox(ctx, args)
    elif args.subcommand == "send":
        return cmd_send(ctx, args)
    elif args.subcommand == "broadcast":
        return cmd_broadcast(ctx, args)
    elif args.subcommand == "publish":
        return cmd_publish(ctx, args)
    elif args.subcommand == "subscribe":
        return cmd_subscribe(ctx, args)
    elif args.subcommand == "heartbeat":
        return cmd_heartbeat(ctx, args)
    elif args.subcommand == "monitor":
        return cmd_monitor(ctx, args)
    elif args.subcommand == "rpc":
        return cmd_rpc(ctx, args)
    elif args.subcommand == "rpc-respond":
        return cmd_rpc_respond(ctx, args)
    elif args.subcommand == "vote-create":
        return cmd_vote_create(ctx, args)
    elif args.subcommand == "vote":
        return cmd_vote(ctx, args)
    elif args.subcommand == "vote-result":
        return cmd_vote_result(ctx, args)

    # Subcommands implemented in later tasks — placeholder exit
    print(
        f"error: subcommand '{args.subcommand}' is not yet implemented in this build.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
