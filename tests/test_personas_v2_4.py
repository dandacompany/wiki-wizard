"""Tests for v2.4 new personas: moderator, perspective-writer."""

from pathlib import Path
import pytest
import yaml

PERSONAS_DIR = Path(__file__).parent.parent / "personas"


def _load_persona(name: str) -> tuple[dict, str]:
    """Parse frontmatter + body from a persona .md file.

    Returns (frontmatter_dict, body_text).
    """
    path = PERSONAS_DIR / f"{name}.md"
    assert path.exists(), f"Persona file not found: {path}"
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---"), f"{name}.md must start with YAML frontmatter"
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{name}.md frontmatter not properly closed"
    fm = yaml.safe_load(parts[1])
    body = parts[2].strip()
    return fm, body


class TestModeratorPersona:
    def test_frontmatter_name_field(self):
        fm, _ = _load_persona("moderator")
        assert fm.get("name") == "moderator"

    def test_frontmatter_model_hint_most_capable(self):
        """Moderator requires most_capable — it synthesizes, not just reads."""
        fm, _ = _load_persona("moderator")
        assert fm.get("model_hint") == "most_capable"

    def test_frontmatter_capabilities_include_synthesize(self):
        fm, _ = _load_persona("moderator")
        caps = fm.get("capabilities", [])
        assert "synthesize" in caps

    def test_body_min_length(self):
        """Persona body should be substantial (>= 50 lines)."""
        _, body = _load_persona("moderator")
        assert len(body.splitlines()) >= 50

    def test_body_contains_inbox_reference(self):
        """Moderator body must reference swarm inbox command."""
        _, body = _load_persona("moderator")
        assert "inbox" in body

    def test_body_contains_synthesize_instruction(self):
        """Moderator body must instruct worker to synthesize."""
        _, body = _load_persona("moderator")
        assert "synthesize" in body.lower() or "synthesis" in body.lower()

    def test_body_contains_vote_create_instruction(self):
        """Moderator body must reference vote-create for conflict resolution."""
        _, body = _load_persona("moderator")
        assert "vote-create" in body or "vote_create" in body


class TestPerspectiveWriterPersona:
    def test_frontmatter_name_field(self):
        fm, _ = _load_persona("perspective-writer")
        assert fm.get("name") == "perspective-writer"

    def test_frontmatter_has_args_perspective(self):
        """perspective-writer must declare `perspective` arg in frontmatter."""
        fm, _ = _load_persona("perspective-writer")
        args = fm.get("args", {})
        assert "perspective" in args, "Missing 'perspective' key in args frontmatter"

    def test_frontmatter_output_kind(self):
        fm, _ = _load_persona("perspective-writer")
        assert fm.get("output_kind") == "stdout"

    def test_body_min_length(self):
        """Persona body should be substantial (>= 50 lines)."""
        _, body = _load_persona("perspective-writer")
        assert len(body.splitlines()) >= 50

    def test_body_contains_perspective_guidance(self):
        """Body must explain how to write from a perspective."""
        _, body = _load_persona("perspective-writer")
        assert "perspective" in body.lower()

    def test_body_contains_audience_examples(self):
        """Body must list audience examples (beginner, expert, etc.)."""
        _, body = _load_persona("perspective-writer")
        assert "beginner" in body.lower()
        assert "expert" in body.lower()

    def test_body_contains_publish_swarm_instruction(self):
        """Body must tell worker to publish draft to swarm."""
        _, body = _load_persona("perspective-writer")
        assert "publish" in body and "perspective-draft" in body
