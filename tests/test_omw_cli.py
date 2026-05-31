"""User-facing omw CLI."""
import json
import os
import stat
from pathlib import Path

import pytest

from scripts import omw_cli, registry
from scripts.paths import registry_path


def _run(argv):
    return omw_cli.main(argv)


def _seed_vault(tmp_path, name="v1"):
    from scripts.paths import ensure_home
    ensure_home()
    db = registry_path()
    root = tmp_path / name
    root.mkdir()
    registry.init_db(db)
    registry.add_vault(db, name=name, path=root, type_="markdown", mode="wiki")
    return db


def test_status_emits_setup_when_empty(capsys, monkeypatch):
    monkeypatch.setattr("scripts.paths.legacy_registry_candidates", lambda: [])
    assert _run(["status"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["needs"] == "setup" and out["vault_count"] == 0


def test_status_surfaces_migrate_when_legacy_present(tmp_path, capsys, monkeypatch):
    # legacy registry exists, global one absent → omw status must report migrate,
    # and must NOT mask it by creating the global registry first.
    legacy = tmp_path / "legacy" / "registry.db"
    legacy.parent.mkdir(parents=True)
    registry.init_db(legacy)
    root = tmp_path / "c"
    root.mkdir()
    registry.add_vault(legacy, name="old", path=root, type_="markdown", mode="memo")
    monkeypatch.setattr("scripts.paths.legacy_registry_candidates", lambda: [legacy])
    assert _run(["status"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["needs"] == "migrate"
    assert not registry_path().exists()   # status must not have created/masked it


def test_vault_list_empty(capsys):
    assert _run(["vault", "list"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_vault_list_shows_seeded(tmp_path, capsys):
    _seed_vault(tmp_path, "v1")
    assert _run(["vault", "list"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [v["name"] for v in data] == ["v1"]
    assert data[0]["mode"] == "wiki" and "is_active" in data[0]


def test_vault_create_global_default(capsys):
    assert _run(["vault", "create", "ai-agents", "--mode", "wiki", "--type", "markdown"]) == 0
    rows = registry.list_vaults(registry_path())
    assert [v["name"] for v in rows] == ["ai-agents"]
    v = rows[0]
    assert v["mode"] == "wiki" and v["type"] == "markdown" and bool(v["is_active"])
    root = Path(v["path"])
    assert (root / "wiki" / "entities").is_dir()
    assert (root / "wiki" / "index.md").is_file()


def test_vault_create_duplicate_errors(capsys):
    assert _run(["vault", "create", "dup"]) == 0
    capsys.readouterr()  # drain first create output
    assert _run(["vault", "create", "dup"]) == 1
    assert "already registered" in capsys.readouterr().err


def test_vault_create_project_location(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert _run(["vault", "create", "p", "--location", "project"]) == 0
    v = registry.list_vaults(registry_path())[0]
    assert Path(v["path"]) == (tmp_path / ".omw" / "p")


def test_vault_use_switches_active(capsys):
    _run(["vault", "create", "a"])
    _run(["vault", "create", "b"])
    assert _run(["vault", "use", "a"]) == 0
    active = [v["name"] for v in registry.list_vaults(registry_path()) if v["is_active"]]
    assert active == ["a"]


def test_vault_use_unknown_errors(tmp_path, capsys):
    # Registry exists but the requested vault does not → VaultError "not found".
    _seed_vault(tmp_path, "exists")
    assert _run(["vault", "use", "nope"]) == 1
    assert "not found" in capsys.readouterr().err


def test_vault_use_no_registry_errors(capsys):
    assert _run(["vault", "use", "nope"]) == 1
    assert "no registry" in capsys.readouterr().err


def test_vault_forget_removes_row_keeps_files(capsys):
    _run(["vault", "create", "gone"])
    path = Path([v["path"] for v in registry.list_vaults(registry_path())][0])
    assert _run(["vault", "forget", "gone"]) == 0
    assert registry.list_vaults(registry_path()) == []
    assert path.is_dir()


def test_lint_active_vault_returns_report(capsys):
    _run(["vault", "create", "lv", "--mode", "wiki"])
    capsys.readouterr()  # drain vault create output
    assert _run(["lint"]) == 0
    assert isinstance(json.loads(capsys.readouterr().out), dict)


def test_lint_no_active_errors(tmp_path, capsys):
    # Registry exists with a vault but none active → "no active vault".
    _seed_vault(tmp_path, "lv")  # add_vault leaves is_active = 0
    assert _run(["lint"]) == 1
    assert "no active vault" in capsys.readouterr().err


def test_lint_no_registry_errors(capsys):
    assert _run(["lint"]) == 1
    assert "no registry" in capsys.readouterr().err


def test_lint_vault_flag_no_registry_errors(capsys):
    assert _run(["lint", "--vault", "foo"]) == 1
    assert "no registry" in capsys.readouterr().err


@pytest.mark.parametrize("op", ["ingest", "query", "autoresearch", "persona-polish"])
def test_agentic_op_bridges_to_claude(op, capsys):
    assert _run([op]) == 0
    out = capsys.readouterr().out
    assert "Claude" in out and op in out
    db = registry_path()
    assert (not db.exists()) or registry.list_vaults(db) == []


def test_setup_tts_via_cli(monkeypatch):
    from scripts import omw_cli, config
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    rc = omw_cli.main(["setup", "tts", "--provider", "elevenlabs",
                       "--voice-id", "V9", "--api-key", "K9"])
    assert rc == 0
    assert config.read_secret("ELEVENLABS_API_KEY") == "K9"
    assert config.load_config()["tts"]["enabled"] is True


def test_installer_is_executable_and_valid():
    p = Path(__file__).resolve().parents[1] / "bin" / "omw-install.sh"
    assert p.is_file()
    assert os.stat(p).st_mode & stat.S_IXUSR, "omw-install.sh must be executable"
    text = p.read_text()
    assert "omw setup" in text                 # auto-launches the wizard
    assert "pipx install" in text or "pip install" in text


def test_omw_search_returns_json(capsys, monkeypatch):
    import scripts.search as _search
    monkeypatch.setattr(_search, "search",
                        lambda q, *, provider=None, limit=10: [{"title": "T", "url": "u", "snippet": "s"}])
    assert _run(["search", "ai agents", "--limit", "3"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"title": "T", "url": "u", "snippet": "s"}]


def test_omw_search_unconfigured_errors(capsys):
    rc = _run(["search", "q"])
    assert rc == 1
    assert "omw setup search" in capsys.readouterr().err


def test_serve_help_exits_zero():
    import pytest
    with pytest.raises(SystemExit) as exc:
        omw_cli.main(["serve", "--help"])
    assert exc.value.code == 0


def test_serve_without_token_exits_1(monkeypatch, capsys):
    monkeypatch.delenv("OMW_SERVE_TOKEN", raising=False)
    # autouse OMW_HOME isolation guarantees no ~/.omw/.env token exists
    rc = omw_cli.main(["serve"])
    assert rc == 1
    assert "OMW_SERVE_TOKEN" in capsys.readouterr().err


def test_setup_serve_via_cli_writes_token():
    from scripts import omw_cli, config
    rc = omw_cli.main(["setup", "serve", "--token", "xyz789"])
    assert rc == 0
    assert config.read_secret("OMW_SERVE_TOKEN") == "xyz789"


def test_setup_personas_via_cli(tmp_path):
    from scripts import omw_cli, config
    rc = omw_cli.main([
        "setup", "personas", "--enable", "researcher,curator",
        "--main", "curator", "--host", "claude", "--base-dir", str(tmp_path),
    ])
    assert rc == 0
    assert config.load_config()["personas"]["main"] == "curator"
    assert (tmp_path / "CLAUDE.md").exists()


def test_setup_no_section_noninteractive_creates_vault(tmp_path, monkeypatch):
    from scripts import omw_cli, registry
    from scripts.paths import registry_path
    rc = omw_cli.main(["setup", "--noninteractive", "--name", "wiz"])
    assert rc == 0
    names = {v["name"] for v in registry.list_vaults(registry_path())}
    assert "wiz" in names


def test_setup_no_section_interactive_calls_run_all(monkeypatch):
    from scripts import omw_cli, setup_wizard
    called = {}
    monkeypatch.setattr(setup_wizard.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(setup_wizard, "run_all", lambda **k: called.setdefault("ran", True) or 0)
    rc = omw_cli.main(["setup"])
    assert rc == 0 and called.get("ran") is True
