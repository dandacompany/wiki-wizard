"""End-to-end v2.2a scenario: each persona's CLI run produces the expected
filing behavior using pre-canned 'LLM output' files."""
from pathlib import Path
import json
import subprocess
import sys

import pytest

from scripts import adapters, registry, reindex


REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _run(*args, cwd=REPO_ROOT):
    return subprocess.run(
        [sys.executable, "-m", "scripts.personas", *args],
        capture_output=True, text=True, check=False, cwd=cwd,
    )


def test_e2e_translator_files_sibling(wiki_vault, tmp_path):
    db, vault, root = wiki_vault
    src = root / "wiki" / "summaries" / "demo.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\ntitle: Demo\n---\nbody", encoding="utf-8")
    out = tmp_path / "translated.md"
    out.write_text("---\ntitle: 데모\n---\n번역", encoding="utf-8")
    proc = _run("run", "translator",
                "--db", str(db),
                "--vault-id", str(vault["id"]),
                "--vault-relpath", "wiki/summaries/demo.md",
                "--lang", "ko",
                "--output-file", str(out))
    assert proc.returncode == 0, proc.stderr
    assert (root / "wiki" / "summaries" / "demo.ko.md").exists()


def test_e2e_polisher_overwrites_with_backup(wiki_vault, tmp_path):
    db, vault, root = wiki_vault
    src = root / "wiki" / "summaries" / "draft.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("original", encoding="utf-8")
    out = tmp_path / "polished.md"
    out.write_text("polished", encoding="utf-8")
    backup_dir = root / ".trash"
    proc = _run("run", "polisher",
                "--db", str(db),
                "--vault-id", str(vault["id"]),
                "--vault-relpath", "wiki/summaries/draft.md",
                "--output-file", str(out),
                "--backup-dir", str(backup_dir))
    assert proc.returncode == 0, proc.stderr
    assert src.read_text(encoding="utf-8") == "polished"
    backups = list(backup_dir.glob("*draft*.md"))
    assert backups and backups[0].read_text(encoding="utf-8") == "original"


def test_e2e_summarizer_stdout_only(tmp_path):
    out = tmp_path / "summary.json"
    summary = {"one_line": "x", "one_paragraph": "y", "detailed": "z"}
    out.write_text(json.dumps(summary), encoding="utf-8")
    proc = _run("run", "summarizer",
                "--text", "body",
                "--output-file", str(out))
    assert proc.returncode == 0, proc.stderr
    assert "one_line" in proc.stdout


def test_e2e_scaffolder_files_new_page(wiki_vault, tmp_path):
    db, vault, root = wiki_vault
    out = tmp_path / "scaffold.md"
    out.write_text(
        "---\ntitle: My Outline\ntype: synthesis\nstatus: draft\n---\n## Section 1\n",
        encoding="utf-8",
    )
    proc = _run("run", "scaffolder",
                "--db", str(db),
                "--vault-id", str(vault["id"]),
                "--text", "outline a topic",
                "--title", "My Outline",
                "--output-file", str(out))
    assert proc.returncode == 0, proc.stderr
    final = (root / "wiki" / "syntheses" / "my-outline.md")
    assert final.exists()
    assert "My Outline" in final.read_text(encoding="utf-8")


def test_e2e_personas_listed_and_show_returns_full_spec():
    proc = _run("list")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    names = {p["name"] for p in data}
    assert names == {"translator", "polisher", "summarizer", "scaffolder"}

    proc = _run("show", "translator")
    assert proc.returncode == 0
    spec = json.loads(proc.stdout)
    assert spec["name"] == "translator"
    assert "body" in spec
    assert "Translator persona" in spec["body"] or "translator" in spec["body"].lower()
