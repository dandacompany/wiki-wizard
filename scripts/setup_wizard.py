"""omw setup wizard + doctor.

Non-interactive (flag-driven) is the tested contract. Interactive prompting uses
questionary if available (the `wizard` extra); otherwise it degrades to input().
The first slice writes config.yaml; secrets (search/persona/TTS) come in later slices.
"""
from __future__ import annotations

import json
import secrets
import sys

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
    # Merge (not overwrite) so a previously-configured search section survives.
    from scripts import config
    config.set_config("version", 1)
    config.set_config("default_vault", default_vault)
    config.set_config("ui.language", "ko")


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


#: provider -> ordered list of (field, env var) the wizard must write.
#: Multi-secret providers (e.g. brightdata) are only enabled once ALL are present.
_PROVIDER_SECRETS = {
    "brave":      [("api_key", "BRAVE_API_KEY")],
    "tavily":     [("api_key", "TAVILY_API_KEY")],
    "exa":        [("api_key", "EXA_API_KEY")],
    "firecrawl":  [("api_key", "FIRECRAWL_API_KEY")],
    "brightdata": [("api_key", "BRIGHTDATA_API_KEY"), ("zone", "BRIGHTDATA_ZONE")],
}


def setup_search(*, noninteractive: bool = False, provider: str | None = None,
                 api_key: str | None = None, zone: str | None = None) -> int:
    from scripts import config
    interactive = (not noninteractive) and sys.stdin.isatty()
    if interactive:
        try:
            import questionary  # type: ignore
            provider = questionary.select(
                "Search provider", choices=list(_PROVIDER_SECRETS) + ["skip"]).ask() or "skip"
        except Exception:
            provider = input(f"Search provider {list(_PROVIDER_SECRETS)} [skip]: ").strip() or "skip"
    if not provider or provider == "skip":
        print("search setup skipped — re-run `omw setup search` anytime.")
        return 0
    if provider not in _PROVIDER_SECRETS:
        print(f"error: unknown provider {provider!r}; choose from {list(_PROVIDER_SECRETS)}",
              file=sys.stderr)
        return 1
    supplied = {"api_key": api_key, "zone": zone}
    all_present = True
    for field, env_var in _PROVIDER_SECRETS[provider]:
        val = supplied.get(field)
        if interactive and not val:
            try:
                import questionary  # type: ignore
                val = questionary.password(f"{field} (blank to defer)").ask() or None
            except Exception:
                val = input(f"{field} (blank to defer): ").strip() or None
        if val:
            config.set_secret(env_var, val)
        else:
            all_present = False
    config.set_config("search.provider", provider)
    config.set_config("search.enabled", all_present)
    if all_present:
        print(f"✓ search provider '{provider}' configured.")
    else:
        print(f"recorded provider '{provider}' — add missing key(s) with "
              f"`omw setup search --provider {provider} --api-key <key>` "
              f"(brightdata also needs --zone).")
    return 0


def setup_personas(*, enabled: list[str] | None = None, main: str | None = None,
                   hosts: list[str] | None = None, base_dir=None,
                   noninteractive: bool = False) -> int:
    """Record the enabled persona roster + main, and export to host instruction files."""
    from pathlib import Path
    from scripts import config, personas, persona_export
    specs = personas.list_personas()
    all_names = [p["name"] for p in specs]
    descriptions = {p["name"]: p.get("description", "") for p in specs}
    if enabled is None:
        enabled = list(all_names)
    unknown = [n for n in enabled if n not in all_names]
    if unknown:
        print(f"error: unknown persona(s): {unknown}", file=sys.stderr)
        return 1
    if main is None:
        main = "operations-orchestrator" if "operations-orchestrator" in enabled \
            else (enabled[0] if enabled else None)
    if main is not None and main not in enabled:
        print(f"error: main persona {main!r} not in enabled set", file=sys.stderr)
        return 1
    if hosts is None:
        hosts = list(persona_export.HOST_FILES)
    base = Path(base_dir) if base_dir else Path.cwd()
    config.set_config("personas.enabled", enabled)
    config.set_config("personas.main", main)
    written = persona_export.export_personas(
        enabled=enabled, main=main, descriptions=descriptions,
        base_dir=base, hosts=hosts,
    )
    print(f"✓ personas: {len(enabled)} enabled, main={main}; "
          f"exported to {', '.join(p.name for p in written)}")
    return 0


def setup_tts(*, provider: str | None = None, voice_id: str | None = None,
              api_key: str | None = None, noninteractive: bool = False) -> int:
    """Configure a TTS provider + voice. Key -> ~/.omw/.env (0600). Mirrors setup_search."""
    from scripts import config
    provider = provider or "elevenlabs"
    if api_key:
        config.set_secret(f"{provider.upper()}_API_KEY", api_key)
    config.set_config("tts.provider", provider)
    config.set_config("tts.voice_id", voice_id)
    enabled = bool(api_key and voice_id)
    config.set_config("tts.enabled", enabled)
    if enabled:
        print(f"✓ tts provider '{provider}' configured (voice {voice_id}).")
    else:
        print(f"tts provider '{provider}' recorded — provide --api-key + --voice-id to enable.")
    return 0


def setup_serve(*, token: str | None = None, generate_token: bool = False) -> int:
    """Configure OMW_SERVE_TOKEN in ~/.omw/.env (0600)."""
    from scripts import config
    if generate_token:
        token = secrets.token_urlsafe(32)
    if not token:
        print("error: provide --token <t> or --generate-token", file=sys.stderr)
        return 1
    config.set_secret("OMW_SERVE_TOKEN", token)
    print(f"✓ serve token configured ({len(token)} chars). Start with: omw serve")
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
