from unittest.mock import patch

import pytest

from scripts import adapters


def test_get_adapter_returns_markdown(tmp_path):
    a = adapters.get_adapter("markdown")
    assert isinstance(a, adapters.MarkdownAdapter)


def test_get_adapter_unknown_type_raises():
    with pytest.raises(adapters.AdapterError):
        adapters.get_adapter("notion")


def test_markdown_link_syntax_uses_standard_markdown():
    a = adapters.MarkdownAdapter()
    assert a.link_syntax("concepts/karpathy") == "[karpathy](./concepts/karpathy.md)"


def test_markdown_is_valid_accepts_existing_dir(markdown_vault_path):
    a = adapters.MarkdownAdapter()
    assert a.is_valid(markdown_vault_path) is True


def test_markdown_is_valid_rejects_nonexistent(tmp_path):
    a = adapters.MarkdownAdapter()
    assert a.is_valid(tmp_path / "missing") is False


def test_markdown_init_vault_memo_mode_creates_inbox_and_trash(tmp_path):
    a = adapters.MarkdownAdapter()
    root = tmp_path / "new-vault"
    a.init_vault(root, mode="memo")
    assert (root / "inbox").is_dir()
    assert (root / ".trash").is_dir()


def test_markdown_init_vault_wiki_mode_creates_three_layers(tmp_path):
    a = adapters.MarkdownAdapter()
    root = tmp_path / "wv"
    a.init_vault(root, mode="wiki")
    assert (root / "raw").is_dir()
    assert (root / "wiki").is_dir()
    assert (root / "wiki" / "index.md").is_file()
    assert (root / "wiki" / "log.md").is_file()


def test_markdown_open_invokes_os_open(tmp_path):
    a = adapters.MarkdownAdapter()
    target = tmp_path / "note.md"
    target.write_text("hi")
    with patch("scripts.adapters.subprocess.run") as run:
        a.open(target)
        assert run.called


def test_markdown_init_vault_unknown_mode_raises(tmp_path):
    a = adapters.MarkdownAdapter()
    with pytest.raises(adapters.AdapterError, match="unknown mode"):
        a.init_vault(tmp_path / "x", mode="invalid")
