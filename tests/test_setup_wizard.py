"""omw setup wizard — non-interactive contract."""
import yaml

from scripts import omw_cli, registry
from scripts.paths import omw_home, registry_path


def test_noninteractive_setup_creates_vault_and_config(capsys):
    rc = omw_cli.main([
        "setup", "--noninteractive",
        "--name", "first", "--mode", "wiki", "--type", "markdown", "--location", "global",
    ])
    assert rc == 0
    vaults = registry.list_vaults(registry_path())
    assert [v["name"] for v in vaults] == ["first"]
    cfg = omw_home() / "config.yaml"
    assert cfg.is_file()
    data = yaml.safe_load(cfg.read_text())
    assert data["default_vault"] == "first" and data["version"] == 1


def test_noninteractive_setup_idempotent(capsys):
    omw_cli.main(["setup", "--noninteractive", "--name", "first"])
    rc = omw_cli.main(["setup", "--noninteractive", "--name", "first"])  # re-run
    assert rc == 0
    assert len(registry.list_vaults(registry_path())) == 1


def test_doctor_reports_state(capsys):
    omw_cli.main(["setup", "--noninteractive", "--name", "first"])
    rc = omw_cli.main(["doctor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "registry" in out.lower() and "first" in out


def test_setup_search_noninteractive_writes_config_and_secret(monkeypatch):
    from scripts import config, omw_cli
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    rc = omw_cli.main(["setup", "search", "--noninteractive",
                       "--provider", "brave", "--api-key", "sk-1"])
    assert rc == 0
    assert config.load_config()["search"]["provider"] == "brave"
    assert config.load_config()["search"]["enabled"] is True
    assert config.read_secret("BRAVE_API_KEY") == "sk-1"


def test_setup_search_defer_records_disabled(monkeypatch):
    from scripts import config, omw_cli
    rc = omw_cli.main(["setup", "search", "--noninteractive", "--provider", "tavily"])
    assert rc == 0
    cfg = config.load_config()
    assert cfg["search"]["provider"] == "tavily" and cfg["search"]["enabled"] is False


def test_setup_search_brightdata_needs_key_and_zone(monkeypatch):
    from scripts import config, omw_cli
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHTDATA_ZONE", raising=False)
    omw_cli.main(["setup", "search", "--noninteractive", "--provider", "brightdata", "--api-key", "K"])
    assert config.load_config()["search"]["enabled"] is False   # zone 없음
    omw_cli.main(["setup", "search", "--noninteractive", "--provider", "brightdata", "--api-key", "K", "--zone", "Z"])
    assert config.load_config()["search"]["enabled"] is True
    assert config.read_secret("BRIGHTDATA_API_KEY") == "K" and config.read_secret("BRIGHTDATA_ZONE") == "Z"


def test_vault_setup_preserves_search_config(monkeypatch):
    from scripts import config, omw_cli
    omw_cli.main(["setup", "search", "--noninteractive", "--provider", "brave", "--api-key", "k"])
    omw_cli.main(["setup", "--noninteractive", "--name", "v1"])
    cfg = config.load_config()
    assert cfg["search"]["provider"] == "brave" and cfg["default_vault"] == "v1"


def test_setup_serve_with_token_writes_env():
    from scripts import setup_wizard, config
    from scripts.paths import omw_home
    rc = setup_wizard.setup_serve(token="abc123")
    assert rc == 0
    assert config.read_secret("OMW_SERVE_TOKEN") == "abc123"
    mode = (omw_home() / ".env").stat().st_mode & 0o777
    assert mode == 0o600


def test_setup_serve_generate_token_writes_random():
    from scripts import setup_wizard, config
    rc = setup_wizard.setup_serve(generate_token=True)
    assert rc == 0
    tok = config.read_secret("OMW_SERVE_TOKEN")
    assert tok and len(tok) >= 20


def test_setup_serve_without_token_or_flag_errors(capsys):
    from scripts import setup_wizard
    rc = setup_wizard.setup_serve()
    assert rc == 1
    assert "token" in capsys.readouterr().err.lower()


def test_setup_personas_records_config_and_exports(tmp_path):
    from scripts import setup_wizard, config, persona_export
    rc = setup_wizard.setup_personas(
        enabled=["researcher", "curator"], main="researcher",
        hosts=["claude", "codex", "gemini"], base_dir=tmp_path,
    )
    assert rc == 0
    cfg = config.load_config()
    assert cfg["personas"]["enabled"] == ["researcher", "curator"]
    assert cfg["personas"]["main"] == "researcher"
    for f in persona_export.HOST_FILES.values():
        assert "<!-- omw-personas:start -->" in (tmp_path / f).read_text()


def test_setup_personas_unknown_name_errors(tmp_path, capsys):
    from scripts import setup_wizard
    rc = setup_wizard.setup_personas(enabled=["nonesuch"], base_dir=tmp_path)
    assert rc == 1
    assert "nonesuch" in capsys.readouterr().err


def test_setup_personas_defaults_main_to_orchestrator(tmp_path):
    from scripts import setup_wizard, config
    rc = setup_wizard.setup_personas(base_dir=tmp_path, hosts=["claude"])
    assert rc == 0
    assert config.load_config()["personas"]["main"] == "operations-orchestrator"
