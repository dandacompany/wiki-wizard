# tests/test_review.py
import pytest

from scripts import review


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
