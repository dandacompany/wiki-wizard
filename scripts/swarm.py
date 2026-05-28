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

    # Placeholders for subcommands added in later tasks (argparse must know them
    # to avoid exit-code 2 on unknown subcommand)
    for name in ("heartbeat", "monitor",
                 "rpc", "rpc-respond", "vote-create", "vote", "vote-result"):
        sub.add_parser(name, add_help=False)

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

    # Subcommands implemented in later tasks — placeholder exit
    print(
        f"error: subcommand '{args.subcommand}' is not yet implemented in this build.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
