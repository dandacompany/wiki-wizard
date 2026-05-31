# tests/test_review.py
import pytest

from scripts import frontmatter, registry, reindex, review


def test_tier_defaults_to_medium():
    assert review.tier("high") == 90
    assert review.tier("medium") == 30
    assert review.tier("low") == 7
    assert review.tier(None) == 30
    assert review.tier("bogus") == 30


def test_next_interval_pass_first_uses_tier():
    assert review.next_interval(None, "pass", "high") == 90
    assert review.next_interval(0, "pass", "low") == 7


def test_next_interval_pass_doubles_capped():
    assert review.next_interval(30, "pass", "medium") == 60
    assert review.next_interval(300, "pass", "high") == 365  # capped


def test_next_interval_needs_work_resets_to_tier():
    assert review.next_interval(300, "needs-work", "low") == 7
    assert review.next_interval(10, "needs-work", "high") == 90


def test_next_interval_bad_grade_raises():
    with pytest.raises(ValueError):
        review.next_interval(30, "maybe", "high")


def test_schedule_fields_date_math():
    out = review.schedule_fields("2026-01-01", 30)
    assert out == {"last": "2026-01-01", "due": "2026-01-31", "interval_days": 30}


# ---------------------------------------------------------------------------
# Vault I/O tests (Task 2)
# ---------------------------------------------------------------------------


def _vault(tmp_path, monkeypatch):
    monkeypatch.setenv("OMW_HOME", str(tmp_path / ".omw"))
    db = tmp_path / "registry.db"
    registry.init_db(db)
    root = tmp_path / "vault"
    (root / "wiki" / "concepts").mkdir(parents=True)
    v = registry.add_vault(db, name="v", path=root, type_="markdown", mode="wiki")
    return db, root, v["id"]


def _page(root, name, body_meta):
    (root / "wiki" / "concepts" / name).write_text(body_meta, encoding="utf-8")


def test_due_pages_overdue_and_unscheduled(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "overdue.md",
          "---\ntitle: O\ntype: concept\nreview: {last: 2025-01-01, due: 2026-01-01, interval_days: 30}\n---\nx\n")
    _page(root, "future.md",
          "---\ntitle: F\ntype: concept\nreview: {last: 2026-05-01, due: 2099-01-01, interval_days: 30}\n---\nx\n")
    _page(root, "fresh.md", "---\ntitle: N\ntype: concept\n---\nx\n")  # unscheduled
    reindex.full(db, vault_id=vid)
    due = {r["relpath"] for r in review.due_pages(db, vault_id=vid, today="2026-05-31")}
    assert "wiki/concepts/overdue.md" in due
    assert "wiki/concepts/fresh.md" in due       # unscheduled → due
    assert "wiki/concepts/future.md" not in due  # future → not due


def test_due_pages_scheduled_only_excludes_unscheduled(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "fresh.md", "---\ntitle: N\ntype: concept\n---\nx\n")
    reindex.full(db, vault_id=vid)
    due = review.due_pages(db, vault_id=vid, today="2026-05-31", include_unscheduled=False)
    assert due == []


def test_reschedule_writes_review_block(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    _page(root, "p.md", "---\ntitle: P\ntype: concept\nconfidence: high\n---\nbody\n")
    reindex.full(db, vault_id=vid)
    out = review.reschedule(db, vault_id=vid, relpath="wiki/concepts/p.md",
                            grade="pass", today="2026-05-31")
    assert out["review"]["interval_days"] == 90        # high tier, first pass
    assert out["review"]["due"] == "2026-08-29"         # 2026-05-31 + 90d
    meta, _ = frontmatter.parse((root / "wiki" / "concepts" / "p.md").read_text(encoding="utf-8"))
    assert meta["review"]["due"] == "2026-08-29"


def test_reschedule_missing_page_raises(tmp_path, monkeypatch):
    db, root, vid = _vault(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError):
        review.reschedule(db, vault_id=vid, relpath="wiki/concepts/nope.md",
                          grade="pass", today="2026-05-31")
