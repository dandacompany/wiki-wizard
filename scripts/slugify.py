"""Title-to-slug conversion that preserves Korean characters."""
from __future__ import annotations

import re

# Allow ASCII alphanumerics + Hangul syllables. Everything else becomes a hyphen.
_INVALID = re.compile(r"[^a-z0-9가-힣]+")


def slugify(text: str, *, max_length: int = 80, default: str = "untitled") -> str:
    s = text.strip().lower()
    s = _INVALID.sub("-", s).strip("-")
    if not s:
        return default
    if len(s) > max_length:
        s = s[:max_length].rstrip("-")
    return s


if __name__ == "__main__":
    import sys
    print(slugify(" ".join(sys.argv[1:])))
