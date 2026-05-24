"""Entry-router helper. Emits JSON the LLM dispatcher reads."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts import registry

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "registry.db"


def status(db_path: Path) -> dict:
    if not Path(db_path).exists():
        return {"vault_count": 0, "active": None, "needs": "setup"}
    vaults = registry.list_vaults(db_path)
    active = registry.get_active(db_path)
    if not vaults:
        needs = "setup"
    elif active is None:
        needs = "select"
    else:
        needs = "op"
    return {
        "vault_count": len(vaults),
        "active": {
            "name": active["name"],
            "path": active["path"],
            "type": active["type"],
            "mode": active["mode"],
        } if active else None,
        "needs": needs,
        "vaults": [{"name": v["name"], "mode": v["mode"]} for v in vaults],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wizard")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--db", default=str(DEFAULT_DB))
    args = p.parse_args(argv)
    if args.cmd == "status":
        db = Path(args.db)
        if not db.exists():
            db.parent.mkdir(parents=True, exist_ok=True)
            registry.init_db(db)
        print(json.dumps(status(db), ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
