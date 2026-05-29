"""CLI for scripts.registry: `vaults` subcommand emits JSON list of vaults."""
import json
import os
import subprocess
import sys

from scripts import registry


def _run(args, env_extra):
    return subprocess.run(
        [sys.executable, "-m", "scripts.registry", *args],
        capture_output=True, text=True, env={**os.environ, **env_extra},
    )


def test_vaults_subcommand_emits_json_list(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    db = home / "registry.db"
    registry.init_db(db)
    root = tmp_path / "v"
    root.mkdir()
    registry.add_vault(db, name="alpha", path=root, type_="markdown", mode="memo")
    r = _run(["vaults"], {"OMW_HOME": str(home)})
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert isinstance(data, list) and len(data) == 1
    v = data[0]
    assert v["name"] == "alpha"
    assert v["path"] == str(root)
    assert v["mode"] == "memo"
    assert v["type"] == "markdown"
    assert "id" in v and "is_active" in v


def test_vaults_subcommand_explicit_db_wins(tmp_path):
    db = tmp_path / "custom.db"
    registry.init_db(db)
    root = tmp_path / "v"
    root.mkdir()
    registry.add_vault(db, name="beta", path=root, type_="markdown", mode="wiki")
    r = _run(["vaults", "--db", str(db)], {"OMW_HOME": str(tmp_path / "unused")})
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert [v["name"] for v in data] == ["beta"]
