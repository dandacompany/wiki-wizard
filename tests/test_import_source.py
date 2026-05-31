from pathlib import Path

from scripts import registry, reindex
from scripts import import_source as imp


def _vault(tmp_db, tmp_path, name="iv"):
    registry.init_db(tmp_db)
    vroot = tmp_path / name
    (vroot / "wiki").mkdir(parents=True)
    row = registry.add_vault(tmp_db, name=name, path=str(vroot), type_="markdown", mode="wiki")
    return row["id"], vroot


def _src_tree(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / ".obsidian").mkdir()
    (src / ".git").mkdir()
    (src / "a.md").write_text("# A\n[[b]]", encoding="utf-8")
    (src / "sub" / "b.md").write_text("plain b", encoding="utf-8")
    (src / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    (src / ".git" / "cfg").write_text("x", encoding="utf-8")
    return src


def test_import_folder_copies_md_skips_dotdirs(tmp_db, tmp_path):
    vid, vroot = _vault(tmp_db, tmp_path)
    src = _src_tree(tmp_path)
    out = imp.import_folder(tmp_db, vault_id=vid, src_dir=src)
    rels = set(out["imported"])
    assert "raw/import/a.md" in rels
    assert "raw/import/sub/b.md" in rels
    assert not any(".obsidian" in r or ".git" in r for r in rels)
    assert (vroot / "raw" / "import" / "a.md").exists()


def test_import_folder_idempotent(tmp_db, tmp_path):
    vid, vroot = _vault(tmp_db, tmp_path, "iv2")
    src = _src_tree(tmp_path)
    imp.import_folder(tmp_db, vault_id=vid, src_dir=src)
    out2 = imp.import_folder(tmp_db, vault_id=vid, src_dir=src)  # re-run
    assert out2["imported"] == []
    assert set(out2["skipped"]) >= {"raw/import/a.md", "raw/import/sub/b.md"}


def test_import_folder_wiki_layer_adds_stub(tmp_db, tmp_path):
    vid, vroot = _vault(tmp_db, tmp_path, "iv3")
    src = _src_tree(tmp_path)
    imp.import_folder(tmp_db, vault_id=vid, src_dir=src, layer="wiki")
    body = (vroot / "wiki" / "import" / "sub" / "b.md").read_text()
    assert body.startswith("---")
    assert "type: imported" in body
    assert "title: b" in body


def test_import_folder_obsidian_label(tmp_db, tmp_path):
    vid, vroot = _vault(tmp_db, tmp_path, "iv4")
    src = _src_tree(tmp_path)
    out = imp.import_folder(tmp_db, vault_id=vid, src_dir=src, source="obsidian")
    assert "raw/import/a.md" in out["imported"]


def test_blocks_to_markdown_common_types():
    blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title"}]}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello world"}]}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "one"}]}},
        {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "task"}], "checked": True}},
        {"type": "code", "code": {"rich_text": [{"plain_text": "print(1)"}]}},
        {"type": "quote", "quote": {"rich_text": [{"plain_text": "wise"}]}},
    ]
    md = imp._blocks_to_markdown(blocks)
    assert "# Title" in md
    assert "Hello world" in md
    assert "- one" in md
    assert "- [x] task" in md
    assert "```" in md and "print(1)" in md
    assert "> wise" in md


def test_import_notion_mocked(tmp_db, tmp_path, monkeypatch):
    vid, vroot = _vault(tmp_db, tmp_path, "nv")
    def fake_http(url, *, headers=None):
        if url.endswith("/pages/PAGE1"):
            return {"properties": {"Name": {"type": "title",
                    "title": [{"plain_text": "My Page"}]}}}
        if "/blocks/PAGE1/children" in url:
            return {"results": [
                {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "My Page"}]},
                 "has_children": False, "id": "B1"},
                {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "body text"}]},
                 "has_children": False, "id": "B2"},
            ], "has_more": False, "next_cursor": None}
        return {"results": [], "has_more": False, "next_cursor": None}
    monkeypatch.setattr(imp, "_http_get", fake_http)
    out = imp.import_notion(tmp_db, vault_id=vid, token="t", root_id="PAGE1")
    assert any(r.startswith("raw/import/notion/") and r.endswith(".md") for r in out["imported"])
    page = next(vroot.glob("raw/import/notion/*.md"))
    assert "body text" in page.read_text()
