import json
import threading

import pytest

from scripts import registry, reindex
from scripts import server


@pytest.fixture
def seeded_db(tmp_db, markdown_vault_path):
    """A registry with one markdown vault named 'md', fully indexed."""
    registry.init_db(tmp_db)
    row = registry.add_vault(
        tmp_db, name="md", path=markdown_vault_path,
        type_="markdown", mode="memo",
    )
    reindex.full(tmp_db, vault_id=row["id"])
    return tmp_db


def test_handle_query_returns_hits(seeded_db):
    out = server.handle_query({"text": "Karpathy"}, db_path=seeded_db, default_vault="md")
    assert out["query"] == "Karpathy"
    assert out["vault"] == "md"
    assert out["count"] == len(out["hits"])
    assert out["count"] >= 1
    assert set(out["hits"][0]) == {"relpath", "title", "summary", "tags", "score"}


def test_handle_query_missing_text_raises_400(seeded_db):
    with pytest.raises(server.ServeError) as exc:
        server.handle_query({}, db_path=seeded_db, default_vault="md")
    assert exc.value.status == 400


def test_handle_query_blank_text_raises_400(seeded_db):
    with pytest.raises(server.ServeError) as exc:
        server.handle_query({"text": "   "}, db_path=seeded_db, default_vault="md")
    assert exc.value.status == 400


def test_handle_query_unknown_vault_raises_404(seeded_db):
    with pytest.raises(server.ServeError) as exc:
        server.handle_query({"text": "x", "vault": "nope"}, db_path=seeded_db)
    assert exc.value.status == 404


def test_handle_query_no_active_vault_raises_409(tmp_db):
    registry.init_db(tmp_db)  # registry exists but nothing active
    with pytest.raises(server.ServeError) as exc:
        server.handle_query({"text": "x"}, db_path=tmp_db)
    assert exc.value.status == 409


def test_handle_query_uses_active_vault_when_unpinned(seeded_db):
    registry.set_active(seeded_db, "md")
    out = server.handle_query({"text": "Karpathy"}, db_path=seeded_db)
    assert out["vault"] == "md"


def test_handle_query_clamps_limit_to_max(seeded_db):
    out = server.handle_query(
        {"text": "note", "limit": 999}, db_path=seeded_db, default_vault="md", max_limit=2
    )
    assert len(out["hits"]) <= 2


def test_handle_query_bad_limit_raises_400(seeded_db):
    with pytest.raises(server.ServeError) as exc:
        server.handle_query(
            {"text": "note", "limit": "abc"}, db_path=seeded_db, default_vault="md"
        )
    assert exc.value.status == 400


def test_verify_bearer_accepts_matching_token():
    assert server.verify_bearer("Bearer s3cret", "s3cret") is True


def test_verify_bearer_rejects_wrong_token():
    assert server.verify_bearer("Bearer nope", "s3cret") is False


def test_verify_bearer_rejects_missing_header():
    assert server.verify_bearer(None, "s3cret") is False


def test_verify_bearer_rejects_non_bearer_scheme():
    assert server.verify_bearer("Basic s3cret", "s3cret") is False


def test_verify_bearer_rejects_empty_expected():
    assert server.verify_bearer("Bearer ", "") is False
