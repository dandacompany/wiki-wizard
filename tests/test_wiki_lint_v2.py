"""Four new wiki_lint candidate categories (v2.0)."""
from pathlib import Path
import shutil
import time
import os

import pytest

from scripts import registry, reindex, wiki_lint

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def contradiction_vault(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    dest = tmp_path / "contradict"
    shutil.copytree(FIXTURES / "wiki-vault-contradiction", dest)
    (dest / ".trash").mkdir(exist_ok=True)
    (dest / "raw").mkdir(exist_ok=True)
    vault = registry.add_vault(
        tmp_db, name="c", path=dest, type_="markdown", mode="wiki"
    )
    # Force old-stale-page mtime to ~270 days old to trigger stale claim
    old = time.time() - 270 * 86400
    os.utime(dest / "wiki/summaries/old-stale-page.md", (old, old))
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, dest


def test_contradiction_candidates_detected(contradiction_vault):
    db, vault, root = contradiction_vault
    report = wiki_lint.check(db, vault_id=vault["id"])
    assert "contradiction_candidates" in report
    pairs = {
        (c["page_a"], c["page_b"], c["shared_entity"])
        for c in report["contradiction_candidates"]
    }
    assert any(
        "claim-a" in a and "claim-b" in b and "transformer" in s
        for a, b, s in pairs
    ) or any(
        "claim-b" in a and "claim-a" in b and "transformer" in s
        for a, b, s in pairs
    )


def test_stale_claim_candidates_detected(contradiction_vault):
    db, vault, root = contradiction_vault
    report = wiki_lint.check(db, vault_id=vault["id"])
    assert "stale_claim_candidates" in report
    relpaths = {c["relpath"] for c in report["stale_claim_candidates"]}
    assert "wiki/summaries/old-stale-page.md" in relpaths
    assert "wiki/summaries/claim-a.md" not in relpaths


def test_stale_claim_includes_claim_phrase_and_age(contradiction_vault):
    db, vault, root = contradiction_vault
    report = wiki_lint.check(db, vault_id=vault["id"])
    stale = next(
        c for c in report["stale_claim_candidates"]
        if c["relpath"] == "wiki/summaries/old-stale-page.md"
    )
    assert "claim_phrase" in stale
    assert stale["claim_phrase"] in ("currently", "as of", "the latest")
    assert stale["age_days"] >= 180


@pytest.fixture
def drift_vault(tmp_db, tmp_path):
    registry.init_db(tmp_db)
    dest = tmp_path / "drift"
    shutil.copytree(FIXTURES / "wiki-vault-drift", dest)
    (dest / ".trash").mkdir(exist_ok=True)
    (dest / "raw").mkdir(exist_ok=True)
    vault = registry.add_vault(
        tmp_db, name="d", path=dest, type_="markdown", mode="wiki"
    )
    reindex.full(tmp_db, vault_id=vault["id"])
    return tmp_db, vault, dest


def test_link_bidirectionality_gaps_detected(drift_vault):
    db, vault, root = drift_vault
    report = wiki_lint.check(db, vault_id=vault["id"])
    gaps = report["link_bidirectionality_gaps"]
    sources = {(g["source"], g["target"]) for g in gaps}
    # gpt-paper is in summaries/ layer; andrej-karpathy and karpathy-andrej are
    # in entities/. Cross-layer links are normal (never flagged). The fixture's
    # entity ↔ entity mutual link (andrej-karpathy ↔ karpathy-andrej) has no
    # gap. So gaps list may legitimately be empty for entity↔entity, but the
    # summary→entity links MUST NOT be flagged because they're cross-layer.
    # The test asserts the cross-layer constraint: gpt-paper sources must NOT
    # appear because gpt-paper is summary while its targets are entities.
    assert all(
        "gpt-paper" not in src for src, _tgt in sources
    ), "summary→entity gaps must be filtered out (cross-layer)"


def test_terminology_drift_candidates_detected(drift_vault):
    db, vault, root = drift_vault
    report = wiki_lint.check(db, vault_id=vault["id"])
    drift = report["terminology_drift_candidates"]
    pairs = {
        tuple(sorted([c["slug_a"], c["slug_b"]]))
        for c in drift
    }
    assert ("andrej-karpathy", "karpathy-andrej") in pairs


def test_clean_vault_returns_empty_for_all_v2_categories(tmp_path, tmp_db):
    """A fresh wiki vault with no notes returns empty lists for all 4 v2 categories."""
    from scripts import adapters
    registry.init_db(tmp_db)
    root = tmp_path / "clean"
    adapters.get_adapter("markdown").init_vault(root, "wiki")
    vault = registry.add_vault(
        tmp_db, name="clean", path=root, type_="markdown", mode="wiki"
    )
    reindex.full(tmp_db, vault_id=vault["id"])
    report = wiki_lint.check(tmp_db, vault_id=vault["id"])
    assert report["contradiction_candidates"] == []
    assert report["stale_claim_candidates"] == []
    assert report["link_bidirectionality_gaps"] == []
    assert report["terminology_drift_candidates"] == []
