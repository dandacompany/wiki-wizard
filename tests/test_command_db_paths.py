"""No command file may hardcode the legacy cwd-relative registry path."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMMANDS = REPO / "commands"


def test_no_legacy_data_registry_db_literal():
    offenders = []
    for md in COMMANDS.glob("*.md"):
        text = md.read_text(encoding="utf-8")
        if "data/registry.db" in text:
            offenders.append(md.name)
    assert not offenders, (
        f"these command files still hardcode data/registry.db: {offenders}. "
        f"Use scripts.paths.registry_path() in snippets, omit --db on CLI calls."
    )


def test_inline_snippets_import_registry_path():
    """Any command snippet that builds a db Path must import registry_path."""
    offenders = []
    for md in COMMANDS.glob("*.md"):
        text = md.read_text(encoding="utf-8")
        if "registry_path()" in text and "from scripts.paths import registry_path" not in text:
            offenders.append(md.name)
    assert not offenders, f"these use registry_path() without importing it: {offenders}"
