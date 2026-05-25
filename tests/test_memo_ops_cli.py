"""CLI smoke test for memo_ops via subprocess."""
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import registry


@pytest.fixture
def cli_vault(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    root = tmp_path / "cli-vault"
    root.mkdir()
    (root / "inbox").mkdir()
    (root / ".trash").mkdir()
    vault = registry.add_vault(
        tmp_db, name="c", path=root, type_="markdown", mode="memo"
    )
    registry.set_active(tmp_db, "c")
    return tmp_db, vault, root


def test_memo_ops_write_via_cli(cli_vault, tmp_path):
    db, vault, root = cli_vault
    proc = subprocess.run(
        [
            sys.executable, "-m", "scripts.memo_ops", "write",
            "--db", str(db),
            "--title", "From CLI",
            "--folder", "inbox",
            "--tags", "cli,smoke",
            "--type", "note",
            "--date", "2026-05-25",
        ],
        input="body from stdin",
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    relpath = proc.stdout.strip()
    assert relpath == "inbox/from-cli.md"
    text = (root / relpath).read_text(encoding="utf-8")
    assert "title: From CLI" in text
    assert "body from stdin" in text
