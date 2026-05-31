"""Tests for scripts.glossary — per-vault sqlite glossary runtime."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts import glossary


def test_open_db_creates_file_and_schema(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = glossary.open_db(vault)
    assert db_path == vault / ".oh-my-wiki" / "glossary.db"
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='terms'"
        ).fetchall()
        assert len(rows) == 1
        cols = {row[1] for row in conn.execute("PRAGMA table_info(terms)")}
        assert {"id", "vault_id", "canonical", "aliases", "definition",
                "first_seen_relpath", "last_updated"} <= cols
    finally:
        conn.close()


def test_open_db_is_idempotent(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db1 = glossary.open_db(vault)
    db2 = glossary.open_db(vault)
    assert db1 == db2
    assert db1.exists()


def test_open_db_creates_parent_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    assert not (vault / ".oh-my-wiki").exists()
    glossary.open_db(vault)
    assert (vault / ".oh-my-wiki").is_dir()


def test_glossary_error_is_exception():
    assert issubclass(glossary.GlossaryError, Exception)


def test_upsert_term_inserts(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db = glossary.open_db(vault)
    term_id = glossary.upsert_term(
        db, vault_id=1,
        canonical="Andrej Karpathy",
        aliases=["karpathy", "Karpathy", "andrej karpathy"],
        definition="Former Tesla AI director.",
        first_seen_relpath="wiki/entities/karpathy.md",
    )
    assert term_id > 0
    row = glossary.get_term(db, vault_id=1, canonical="Andrej Karpathy")
    assert row["canonical"] == "Andrej Karpathy"
    assert row["aliases"] == ["karpathy", "Karpathy", "andrej karpathy"]
    assert row["definition"] == "Former Tesla AI director."
    assert row["first_seen_relpath"] == "wiki/entities/karpathy.md"


def test_upsert_term_updates_existing(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db = glossary.open_db(vault)
    glossary.upsert_term(db, vault_id=1, canonical="LLM",
                         aliases=["llm"], definition="Large Language Model.")
    glossary.upsert_term(db, vault_id=1, canonical="LLM",
                         aliases=["llm", "LLMs"], definition="A neural net trained on text.")
    row = glossary.get_term(db, vault_id=1, canonical="LLM")
    assert row["aliases"] == ["llm", "LLMs"]
    assert row["definition"] == "A neural net trained on text."
    rows = glossary.list_terms(db, vault_id=1)
    assert len(rows) == 1  # update, not duplicate


def test_get_term_returns_none_on_miss(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db = glossary.open_db(vault)
    assert glossary.get_term(db, vault_id=1, canonical="Nope") is None


def test_list_terms_empty(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db = glossary.open_db(vault)
    assert glossary.list_terms(db, vault_id=1) == []


def test_list_terms_ordered_by_canonical(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db = glossary.open_db(vault)
    for c in ["Zed", "Alpha", "Mid"]:
        glossary.upsert_term(db, vault_id=1, canonical=c, aliases=[])
    rows = glossary.list_terms(db, vault_id=1)
    assert [r["canonical"] for r in rows] == ["Alpha", "Mid", "Zed"]


def test_list_terms_scoped_by_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db = glossary.open_db(vault)
    glossary.upsert_term(db, vault_id=1, canonical="A", aliases=[])
    glossary.upsert_term(db, vault_id=2, canonical="B", aliases=[])
    assert [r["canonical"] for r in glossary.list_terms(db, vault_id=1)] == ["A"]
    assert [r["canonical"] for r in glossary.list_terms(db, vault_id=2)] == ["B"]


def test_find_inconsistencies_flags_unknown_variant(tmp_path):
    vault = tmp_path / "vault"
    (vault / "wiki" / "entities").mkdir(parents=True)
    (vault / "wiki" / "entities" / "karpathy.md").write_text(
        "# Karpathy\nAndrej Karpathy worked at Tesla.\n", encoding="utf-8",
    )
    (vault / "wiki" / "entities" / "tesla.md").write_text(
        "# Tesla\nKarpathy led Autopilot. Andrej karpathy is a researcher.\n",
        encoding="utf-8",
    )
    db = glossary.open_db(vault)
    glossary.upsert_term(
        db, vault_id=1,
        canonical="Andrej Karpathy",
        aliases=["Karpathy"],  # "andrej karpathy" (lowercase) is NOT a known alias
    )
    inconsistencies = glossary.find_inconsistencies(
        db, vault_id=1, vault_root=vault,
    )
    assert len(inconsistencies) == 1
    flag = inconsistencies[0]
    assert flag["canonical"] == "Andrej Karpathy"
    assert flag["surface_form"] == "Andrej karpathy"
    assert "wiki/entities/tesla.md" in flag["found_in"]


def test_find_inconsistencies_clean_vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "page.md").write_text(
        "Andrej Karpathy and Karpathy both used.\n", encoding="utf-8",
    )
    db = glossary.open_db(vault)
    glossary.upsert_term(
        db, vault_id=1,
        canonical="Andrej Karpathy",
        aliases=["Karpathy"],
    )
    assert glossary.find_inconsistencies(db, vault_id=1, vault_root=vault) == []


def test_find_inconsistencies_skips_glossary_db_dir(tmp_path):
    """Should not scan inside .oh-my-wiki/."""
    vault = tmp_path / "vault"
    vault.mkdir()
    db = glossary.open_db(vault)  # creates .oh-my-wiki/
    # No markdown files at all
    glossary.upsert_term(db, vault_id=1, canonical="Foo", aliases=["foo"])
    assert glossary.find_inconsistencies(db, vault_id=1, vault_root=vault) == []


def test_korean_canonical_matches_surface_with_josa(tmp_path):
    """_build_variant_pattern must match canonical + Korean josa (was missed with \\b)."""
    pat = glossary._build_variant_pattern("카르파시", [])
    assert pat.search("카르파시가 논문을 썼다"), "josa '가' should match"
    assert pat.search("카르파시의 연구"), "josa '의' should match"
    # name inside a compound should not match
    assert not pat.search("카르파시나무"), "compound should not match"


def test_find_inconsistencies_ignores_korean_josa_inflection(tmp_path):
    """A josa-inflected form of the canonical is NOT a real inconsistency."""
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "page.md").write_text(
        "카르파시가 이것을 썼다. 카르파시의 연구.\n", encoding="utf-8",
    )
    db = glossary.open_db(vault)
    glossary.upsert_term(db, vault_id=1, canonical="카르파시", aliases=[])
    # name-part of every match equals the canonical → nothing flagged
    assert glossary.find_inconsistencies(db, vault_id=1, vault_root=vault) == []


import json as _json
import subprocess
import sys


def _run_cli(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "scripts.glossary", *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_init(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    project_root = Path(__file__).resolve().parents[1]
    r = _run_cli("init", "--vault-root", str(vault), cwd=project_root)
    assert r.returncode == 0, r.stderr
    assert (vault / ".oh-my-wiki" / "glossary.db").exists()


def test_cli_upsert_list_show(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    project_root = Path(__file__).resolve().parents[1]
    _run_cli("init", "--vault-root", str(vault), cwd=project_root)
    r = _run_cli(
        "upsert",
        "--vault-root", str(vault),
        "--vault-id", "1",
        "--canonical", "Karpathy",
        "--alias", "karpathy", "--alias", "AK",
        "--definition", "Researcher",
        cwd=project_root,
    )
    assert r.returncode == 0, r.stderr

    r = _run_cli("list", "--vault-root", str(vault), "--vault-id", "1",
                 cwd=project_root)
    assert r.returncode == 0, r.stderr
    data = _json.loads(r.stdout)
    assert len(data) == 1
    assert data[0]["canonical"] == "Karpathy"
    assert data[0]["aliases"] == ["karpathy", "AK"]

    r = _run_cli("show", "--vault-root", str(vault), "--vault-id", "1",
                 "--canonical", "Karpathy", cwd=project_root)
    assert r.returncode == 0, r.stderr
    data = _json.loads(r.stdout)
    assert data["definition"] == "Researcher"


def test_cli_show_miss_returns_2(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    project_root = Path(__file__).resolve().parents[1]
    _run_cli("init", "--vault-root", str(vault), cwd=project_root)
    r = _run_cli("show", "--vault-root", str(vault), "--vault-id", "1",
                 "--canonical", "Nope", cwd=project_root)
    assert r.returncode == 2
    assert "not found" in r.stderr.lower()


def test_cli_lint(tmp_path):
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "page.md").write_text(
        "Karpathy and karpathy and KARPATHY.\n", encoding="utf-8",
    )
    project_root = Path(__file__).resolve().parents[1]
    _run_cli("init", "--vault-root", str(vault), cwd=project_root)
    _run_cli("upsert", "--vault-root", str(vault), "--vault-id", "1",
             "--canonical", "Karpathy", "--alias", "karpathy", cwd=project_root)
    r = _run_cli("lint", "--vault-root", str(vault), "--vault-id", "1",
                 cwd=project_root)
    assert r.returncode == 0, r.stderr
    data = _json.loads(r.stdout)
    # KARPATHY (uppercase) is not in aliases, so should be flagged
    assert any(f["surface_form"] == "KARPATHY" for f in data)
