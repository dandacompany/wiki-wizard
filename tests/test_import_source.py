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
