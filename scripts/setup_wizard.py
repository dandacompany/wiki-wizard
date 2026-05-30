"""omw setup wizard + doctor.

Non-interactive (flag-driven) is the tested contract. Interactive prompting uses
questionary if available (the `wizard` extra); otherwise it degrades to input().
The first slice writes config.yaml; secrets (search/persona/TTS) come in later slices.
"""
from __future__ import annotations

import json
import sys

import yaml

from scripts import adapters, registry, reindex
from scripts.paths import ensure_home, omw_home, registry_path, resolve_vault_root


def _ensure_vault(name: str, mode: str, type_: str, location: str) -> None:
    ensure_home()
    db = registry_path()
    if not db.exists():
        registry.init_db(db)
    if any(v["name"] == name for v in registry.list_vaults(db)):
        return  # idempotent: vault already registered
    root = resolve_vault_root(name, location)
    root.mkdir(parents=True, exist_ok=True)
    adapters.get_adapter(type_, vault_name=name).init_vault(root, mode)
    vault = registry.add_vault(db, name=name, path=root, type_=type_, mode=mode)
    registry.set_active(db, name)
    reindex.full(db, vault_id=vault["id"])


def _write_config(default_vault: str) -> None:
    cfg = omw_home() / "config.yaml"
    data = {"version": 1, "default_vault": default_vault, "ui": {"language": "ko"}}
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def run(
    *,
    section: str | None = None,
    noninteractive: bool = False,
    name: str = "default",
    mode: str = "wiki",
    type_: str = "markdown",
    location: str = "global",
) -> int:
    interactive = (not noninteractive) and sys.stdin.isatty()
    if interactive:
        return _run_interactive(name, mode, type_, location)
    ensure_home()
    _ensure_vault(name, mode, type_, location)
    _write_config(name)
    print(json.dumps(
        {"setup": "ok", "default_vault": name, "home": str(omw_home())},
        ensure_ascii=False,
    ))
    return 0


def _run_interactive(name: str, mode: str, type_: str, location: str) -> int:
    try:
        import questionary  # type: ignore

        def ask(msg: str, default: str) -> str:
            return questionary.text(msg, default=default).ask() or default
    except Exception:
        def ask(msg: str, default: str) -> str:
            got = input(f"{msg} [{default}]: ").strip()
            return got or default

    name = ask("Vault name", name)
    mode = ask("Mode (memo/wiki)", mode)
    type_ = ask("Type (markdown/obsidian)", type_)
    location = ask("Location (global/project/<abs path>)", location)
    ensure_home()
    _ensure_vault(name, mode, type_, location)
    _write_config(name)
    print(
        f"setup complete — vault '{name}' at {omw_home()}. "
        f"Search/persona/TTS sections: configure later with 'omw setup search' (coming soon)."
    )
    return 0


def doctor() -> int:
    home = omw_home()
    db = registry_path()
    print(f"omw home:   {home}  {'ok' if home.exists() else 'missing (run: omw setup)'}")
    print(f"registry:   {db}  {'ok' if db.exists() else 'missing'}")
    vaults = registry.list_vaults(db) if db.exists() else []
    if vaults:
        for v in vaults:
            mark = "*" if v["is_active"] else " "
            print(f"  {mark} {v['name']} ({v['mode']}/{v['type']}) {v['path']}")
    else:
        print("  no vaults registered — run: omw setup")
    return 0
