"""Each CLI module resolves its --db default to the global registry, not cwd."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module,args", [
    # Each arg-set reaches the module's db_path resolution + a registry connect
    # (subcommand modules use the subcommand whose handler touches the db).
    ("scripts.lint", ["--vault-id", "1"]),
    ("scripts.autoresearch", ["init", "--query", "x"]),
    ("scripts.hot_cache", ["--on-session-start"]),
    ("scripts.memo_ops", ["write", "--title", "t", "--date", "2026-01-01"]),
    ("scripts.personas", ["run", "polisher",
                          "--vault-relpath", "p/x.md", "--vault-id", "1",
                          "--output-file", "out.txt"]),
])
def test_db_default_does_not_touch_cwd_data_registry(monkeypatch, tmp_path, module, args):
    """With no --db, the module must NOT create/read ./data/registry.db in cwd.

    We pre-create the cwd-relative data/ directory so SQLite *could* create the
    file there — then assert it was NOT created, proving the module resolved its
    default via registry_path() (OMW_HOME) instead.
    """
    home = tmp_path / "home"
    # Pre-create data/ so SQLite can write there if the default isn't fixed.
    (tmp_path / "data").mkdir()
    r = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=tmp_path, capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "OMW_HOME": str(home)},
    )
    # No cwd-relative data/registry.db should be created as a side effect.
    assert not (tmp_path / "data" / "registry.db").exists(), (
        f"{module} created a cwd-relative data/registry.db — default not resolved via paths.\n"
        f"stdout: {r.stdout!r}\nstderr: {r.stderr!r}"
    )
