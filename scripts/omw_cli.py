"""User-facing omw CLI: deterministic ops + the setup wizard entrypoint.

The human-facing tool (install + setup + deterministic vault management).
Natural-language work (ingest/query/research/personas) happens inside a Claude
session via the omw skill; the skill may call these deterministic subcommands.
"""
from __future__ import annotations

import argparse
import json
import sys

from scripts import adapters, lint, registry, reindex, wizard
from scripts.paths import ensure_home, registry_path, resolve_vault_root

AGENTIC_OPS = [
    "ingest", "query", "find", "open", "edit", "move", "delete",
    "autoresearch", "persona-translate", "persona-polish", "persona-summarize",
    "persona-scaffold", "persona-factcheck", "persona-consistency",
    "persona-terminology", "dispatch", "team", "team-run", "swarm-monitor",
]


def _cmd_status(args) -> int:
    ensure_home()
    db = registry_path()
    # Compute status BEFORE any init so a pending legacy migration stays visible;
    # only auto-init on the fresh-setup path (mirrors wizard.main()).
    result = wizard.status(db)
    if result["needs"] != "migrate" and not db.exists():
        registry.init_db(db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_vault_list(args) -> int:
    db = registry_path()
    if not db.exists():
        print("[]")
        return 0
    out = [
        {
            "name": v["name"],
            "path": v["path"],
            "mode": v["mode"],
            "type": v["type"],
            "is_active": bool(v["is_active"]),
        }
        for v in registry.list_vaults(db)
    ]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _cmd_vault_create(args) -> int:
    ensure_home()
    db = registry_path()
    registry.init_db(db)
    root = resolve_vault_root(args.name, args.location)
    root.mkdir(parents=True, exist_ok=True)
    adapters.get_adapter(args.type, vault_name=args.name).init_vault(root, args.mode)
    try:
        vault = registry.add_vault(
            db, name=args.name, path=root, type_=args.type, mode=args.mode
        )
    except registry.VaultError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    registry.set_active(db, args.name)
    reindex.full(db, vault_id=vault["id"])
    print(json.dumps(
        {"created": args.name, "path": str(root), "mode": args.mode, "type": args.type},
        ensure_ascii=False,
    ))
    return 0


def _cmd_vault_use(args) -> int:
    db = registry_path()
    if not db.exists():
        print("error: no registry; run `omw status` first", file=sys.stderr)
        return 1
    try:
        registry.set_active(db, args.name)
    except registry.VaultError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"active vault: {args.name}")
    return 0


def _cmd_vault_forget(args) -> int:
    db = registry_path()
    if not db.exists():
        print("error: no registry; run `omw status` first", file=sys.stderr)
        return 1
    try:
        registry.forget_vault(db, args.name)
    except registry.VaultError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"forgot vault: {args.name} (files untouched)")
    return 0


def _cmd_lint(args) -> int:
    db = registry_path()
    if not db.exists():
        print("error: no registry; run `omw status` to set up", file=sys.stderr)
        return 1
    if args.vault:
        match = [v for v in registry.list_vaults(db) if v["name"] == args.vault]
        if not match:
            print(f"error: vault {args.vault!r} not found", file=sys.stderr)
            return 1
        vault_id = match[0]["id"]
    else:
        active = registry.get_active(db)
        if active is None:
            print("error: no active vault; pass --vault <name>", file=sys.stderr)
            return 1
        vault_id = active["id"]
    print(json.dumps(lint.check(db, vault_id=vault_id), ensure_ascii=False, indent=2))
    return 0


def _cmd_search(args) -> int:
    from scripts import search as _search
    try:
        results = _search.search(args.query, provider=args.provider, limit=args.limit)
    except _search.SearchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def _cmd_setup(args) -> int:
    from scripts import setup_wizard
    if args.section == "search":
        return setup_wizard.setup_search(
            noninteractive=args.noninteractive,
            provider=args.provider,
            api_key=args.api_key,
            zone=args.zone,
        )
    return setup_wizard.run(
        section=args.section,
        noninteractive=args.noninteractive,
        name=args.name,
        mode=args.mode,
        type_=args.type,
        location=args.location,
    )


def _cmd_doctor(args) -> int:
    from scripts import setup_wizard
    return setup_wizard.doctor()


def _cmd_agentic(args) -> int:
    op = args.op
    print(
        f"'{op}' needs natural-language reasoning — it is not a deterministic CLI "
        f"command.\nOpen Claude Code and use the omw skill (e.g. say '{op} ...'); "
        f"the skill runs the commands/{op}.md procedure."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="omw",
        description=(
            "oh-my-wiki user CLI — install/setup + deterministic vault ops. "
            "Natural-language work happens in a Claude session via the omw skill."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show registry state as JSON.").set_defaults(
        func=_cmd_status
    )

    pv = sub.add_parser("vault", help="Deterministic vault management.")
    vsub = pv.add_subparsers(dest="vault_cmd", required=True)
    vsub.add_parser("list", help="List vaults as JSON.").set_defaults(func=_cmd_vault_list)

    pc = vsub.add_parser("create", help="Create + register a vault.")
    pc.add_argument("name")
    pc.add_argument("--mode", choices=["memo", "wiki"], default="wiki")
    pc.add_argument("--type", choices=["markdown", "obsidian"], default="markdown")
    pc.add_argument(
        "--location", default="global", help="global | project | <absolute path>"
    )
    pc.set_defaults(func=_cmd_vault_create)

    pu = vsub.add_parser("use", help="Set the active vault.")
    pu.add_argument("name")
    pu.set_defaults(func=_cmd_vault_use)

    pf = vsub.add_parser("forget", help="Remove a vault's registry row (files kept).")
    pf.add_argument("name")
    pf.set_defaults(func=_cmd_vault_forget)

    pl = sub.add_parser("lint", help="Run deterministic lint over a vault.")
    pl.add_argument("--vault", default=None, help="vault name (default: active)")
    pl.set_defaults(func=_cmd_lint)

    psr = sub.add_parser("search", help="Web search via the configured provider.")
    psr.add_argument("query")
    psr.add_argument("--provider", default=None)
    psr.add_argument("--limit", type=int, default=10)
    psr.set_defaults(func=_cmd_search)

    pset = sub.add_parser("setup", help="Interactive setup wizard (run after install).")
    pset.add_argument(
        "section", nargs="?", choices=["vault", "hosts", "search"], default=None
    )
    pset.add_argument(
        "--noninteractive", action="store_true",
        help="create from flags/defaults without prompting",
    )
    pset.add_argument("--name", default="default")
    pset.add_argument("--mode", choices=["memo", "wiki"], default="wiki")
    pset.add_argument("--type", choices=["markdown", "obsidian"], default="markdown")
    pset.add_argument("--location", default="global")
    pset.add_argument("--provider", default=None)
    pset.add_argument("--api-key", dest="api_key", default=None)
    pset.add_argument("--zone", default=None)
    pset.set_defaults(func=_cmd_setup)

    sub.add_parser(
        "doctor", help="Validate omw config + install."
    ).set_defaults(func=_cmd_doctor)

    for op in AGENTIC_OPS:
        ap = sub.add_parser(op, help=f"(needs a Claude session) {op}")
        ap.set_defaults(func=_cmd_agentic, op=op)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
