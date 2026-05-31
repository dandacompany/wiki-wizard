"""Build a Korean-josa-aware, case-insensitive name-match regex from a name list.

`\\b name \\b` never fires between Hangul syllables, so a name followed by a josa
(`김단테는`) is missed. This matches `name` + an optional josa + a real boundary,
while preserving Latin word-boundary behavior. No morphological analysis, no dep.
"""
from __future__ import annotations

import re

# Common Korean postpositions (josa), longest-first. The trailing boundary check
# disambiguates, so ordering is a minor optimization, not a correctness requirement.
_JOSA = (
    "으로서", "으로써", "에게서", "한테서", "에서", "으론", "으로", "에게",
    "한테", "까지", "부터", "처럼", "보다", "마다", "조차", "마저", "밖에",
    "이나", "이라", "이며", "이고", "이란", "이든", "는", "은", "이", "가",
    "을", "를", "와", "과", "의", "에", "도", "만", "로", "나", "라", "며",
    "고", "란", "든", "께",
)
_JOSA_ALT = "|".join(sorted(_JOSA, key=len, reverse=True))


def build_name_pattern(names) -> re.Pattern | None:
    """Alternation over `names` (multi-word → flexible `\\s+`), longest-first,
    case-insensitive, wrapped with Korean-josa-aware boundaries. None if empty."""
    parts: list[str] = []
    for n in sorted({str(x).strip() for x in (names or []) if x and str(x).strip()},
                    key=len, reverse=True):
        toks = n.split()
        if toks:
            parts.append(r"\s+".join(re.escape(t) for t in toks))
    if not parts:
        return None
    body = "|".join(parts)
    pattern = rf"(?<![\w가-힣])(?P<name>{body})(?:{_JOSA_ALT})?(?![\w가-힣])"
    return re.compile(pattern, re.IGNORECASE)
