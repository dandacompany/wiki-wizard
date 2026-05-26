"""Hot cache: build, write, read, cap."""
from pathlib import Path

import pytest

from scripts import registry, adapters, reindex, hot_cache


@pytest.fixture
def wiki_vault(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    root = tmp_path / "wiki"
    adapters.get_adapter("markdown").init_vault(root, "wiki")
    vault = registry.add_vault(
        tmp_db, name="w", path=root, type_="markdown", mode="wiki"
    )
    registry.set_active(tmp_db, "w")
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, root


def test_build_returns_markdown_with_required_sections(wiki_vault):
    db, vault, root = wiki_vault
    text = hot_cache.build(db)
    assert text.startswith("---\n"), "should start with YAML frontmatter"
    assert "## Active vaults" in text
    assert "## Recent activity" in text
    assert "## Last session summary" in text


def test_build_respects_2000_char_cap(wiki_vault, tmp_path):
    db, vault, root = wiki_vault
    long_summary = "A" * 5000
    text = hot_cache.build(db, last_session_summary=long_summary)
    assert len(text) <= 2000, f"cap violated: {len(text)} chars"


def test_write_persists_to_vault_hot_md(wiki_vault):
    db, vault, root = wiki_vault
    path = hot_cache.write(db)
    expected = root / "wiki" / "hot.md"
    assert path == expected
    assert expected.exists()
    text = expected.read_text(encoding="utf-8")
    assert "## Active vaults" in text


def test_write_uses_root_hot_md_when_memo_mode(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    root = tmp_path / "memo-vault"
    adapters.get_adapter("markdown").init_vault(root, "memo")
    vault = registry.add_vault(
        tmp_db, name="m", path=root, type_="markdown", mode="memo"
    )
    registry.set_active(tmp_db, "m")
    reindex.full(tmp_db, vault_id=vault["id"])

    path = hot_cache.write(tmp_db)
    assert path == root / "hot.md", "memo-mode cache lives at vault root"
    assert path.exists()


def test_write_uses_data_hot_md_when_no_active_vault(tmp_path, tmp_db):
    registry.init_db(tmp_db)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    path = hot_cache.write(tmp_db, data_dir=data_dir)
    assert path == data_dir / "hot.md", "no-vault fallback goes to data/hot.md"
    assert path.exists()


def test_read_returns_text_when_present(wiki_vault):
    db, vault, root = wiki_vault
    hot_cache.write(db)
    text = hot_cache.read(db)
    assert text is not None
    assert "## Active vaults" in text


def test_read_returns_none_when_no_cache(wiki_vault):
    db, vault, root = wiki_vault
    assert hot_cache.read(db) is None


def test_write_is_atomic(wiki_vault):
    """Concurrent writes should not corrupt the file (tempfile + rename)."""
    db, vault, root = wiki_vault
    hot_cache.write(db)
    target = root / "wiki" / "hot.md"
    tmps = list(target.parent.glob("hot.md.*"))
    assert tmps == [], f"stale temp files: {tmps}"


import subprocess
import sys


def test_cli_on_session_start_prints_cache_when_present(wiki_vault, tmp_path):
    db, vault, root = wiki_vault
    hot_cache.write(db)
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.hot_cache", "--on-session-start",
         "--db", str(db)],
        capture_output=True, text=True, check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 0, proc.stderr
    assert "## Active vaults" in proc.stdout


def test_cli_on_session_start_no_cache_exits_zero_silent(wiki_vault):
    db, vault, root = wiki_vault
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.hot_cache", "--on-session-start",
         "--db", str(db)],
        capture_output=True, text=True, check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_cli_on_session_stop_writes_cache_with_stdin_summary(wiki_vault):
    db, vault, root = wiki_vault
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.hot_cache", "--on-session-stop",
         "--db", str(db)],
        input="The user asked me to lint the daily vault and it returned clean.",
        capture_output=True, text=True, check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 0, proc.stderr
    cache = (root / "wiki" / "hot.md").read_text(encoding="utf-8")
    assert "lint the daily vault" in cache


def test_cli_refresh_writes_cache_without_stdin(wiki_vault):
    db, vault, root = wiki_vault
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.hot_cache", "--refresh",
         "--db", str(db)],
        capture_output=True, text=True, check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 0
    assert (root / "wiki" / "hot.md").exists()
