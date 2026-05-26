"""End-to-end integration test for v2.2b review personas + glossary."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _python(*args, cwd=PROJECT_ROOT):
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_fact_checker_files_factcheck_report(tmp_path):
    """fact-checker persona + sibling_suffix produces <stem>.factcheck.md."""
    source = tmp_path / "claim-doc.md"
    source.write_text("Python is interpreted.\nPython was created in 1991.\n",
                      encoding="utf-8")
    report = tmp_path / "report.md"
    report.write_text(
        "# Fact-check report\n\n"
        "| # | Claim | Verdict | Confidence | Sources |\n"
        "|---|-------|---------|------------|---------|\n"
        "| 1 | Python is interpreted | supported | high | wikipedia.org |\n",
        encoding="utf-8",
    )
    r = _python(
        "-m", "scripts.personas", "run", "fact-checker",
        "--file", str(source),
        "--suffix", "factcheck",
        "--output-file", str(report),
    )
    assert r.returncode == 0, r.stderr
    produced = source.with_name("claim-doc.factcheck.md")
    assert produced.exists()
    assert "Fact-check report" in produced.read_text(encoding="utf-8")


def test_terminology_manager_glossary_end_to_end(tmp_path):
    """Glossary lifecycle: init → upsert → list → lint."""
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "page.md").write_text(
        "Andrej Karpathy is a researcher.\n"
        "andrej karpathy spoke at a conference.\n"
        "Karpathy left Tesla.\n",
        encoding="utf-8",
    )

    r = _python("-m", "scripts.glossary", "init", "--vault-root", str(vault))
    assert r.returncode == 0, r.stderr

    r = _python(
        "-m", "scripts.glossary", "upsert",
        "--vault-root", str(vault), "--vault-id", "1",
        "--canonical", "Andrej Karpathy",
        "--alias", "Karpathy",
        "--definition", "AI researcher.",
        "--first-seen-relpath", "wiki/page.md",
    )
    assert r.returncode == 0, r.stderr

    r = _python(
        "-m", "scripts.glossary", "list",
        "--vault-root", str(vault), "--vault-id", "1",
    )
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert len(rows) == 1
    assert rows[0]["canonical"] == "Andrej Karpathy"

    r = _python(
        "-m", "scripts.glossary", "lint",
        "--vault-root", str(vault), "--vault-id", "1",
    )
    assert r.returncode == 0, r.stderr
    inconsistencies = json.loads(r.stdout)
    assert any(f["surface_form"] == "andrej karpathy" for f in inconsistencies)


def test_consistency_checker_persona_stdout(tmp_path):
    """consistency-checker (stdout output) accepts a vault_relpath input."""
    from scripts import registry
    db = tmp_path / "reg.db"
    registry.init_db(db)
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "page.md").write_text("# Page\n", encoding="utf-8")
    registry.add_vault(db, name="test", path=str(vault), type_="markdown", mode="wiki")

    output = tmp_path / "verdicts.json"
    output.write_text(
        json.dumps({
            "mode": "single_doc",
            "verdicts": [],
            "summary": {"confirmed": 0, "nuanced": 0, "false_positive": 0},
        }),
        encoding="utf-8",
    )
    r = _python(
        "-m", "scripts.personas", "run", "consistency-checker",
        "--db", str(db),
        "--vault-id", "1",
        "--vault-relpath", "wiki/page.md",
        "--output-file", str(output),
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["mode"] == "single_doc"
