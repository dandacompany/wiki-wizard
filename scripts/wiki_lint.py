"""Wiki-mode structural lint: orphan/missing/empty/dangling checks."""
from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from scripts import registry

ORPHAN_GRACE_DAYS = 7

# Matches [[target]] or [[target|alias]] — captures the target slug
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")

# v2.0 candidate detection
STALE_CLAIM_AGE_DAYS = 180
STALE_CLAIM_PHRASES = ("currently", "as of", "the latest")
CONTRADICTION_PAIRS = [
    ("is faster", "is not faster"),
    ("supports", "contradicts"),
    ("is", "is not"),
    ("can", "cannot"),
]
# Matches [text](./path.md) — captures relpath (without ./ prefix)
_MDLINK_RE = re.compile(r"\[[^\]]+\]\(\./([^)]+\.md)\)")


def check(db_path: Path, *, vault_id: int) -> dict:
    """Return wiki structural lint report. Read-only."""
    conn = registry.connect(db_path)
    try:
        row = conn.execute(
            "SELECT path FROM vaults WHERE id = ?", (vault_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise registry.VaultError(f"unknown vault_id={vault_id}")
    root = Path(row["path"])

    pages = _scan_pages(root)
    return {
        "vault_id": vault_id,
        "vault_path": str(root),
        "orphan_pages":     _orphan_pages(pages),
        "missing_concepts": _missing_concepts(pages, root),
        "empty_data":       _empty_data(pages),
        "dangling_links":   _dangling_links(pages, root),
        # v2.0 additions:
        "contradiction_candidates": _contradiction_candidates(pages),
        "stale_claim_candidates":   _stale_claim_candidates(pages),
        "link_bidirectionality_gaps": [],   # Task 14
        "terminology_drift_candidates": [], # Task 14
    }


def _scan_pages(root: Path) -> list[tuple[str, str, float]]:
    """Return [(relpath, body, mtime), ...] for wiki/* notes (excluding index/log)."""
    out = []
    wiki_dir = root / "wiki"
    if not wiki_dir.is_dir():
        return out
    for p in sorted(wiki_dir.rglob("*.md")):
        if ".trash" in p.parts:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if rel in {"wiki/index.md", "wiki/log.md"}:
            continue
        text = p.read_text(encoding="utf-8")
        out.append((rel, text, p.stat().st_mtime))
    return out


def _slug_from_relpath(relpath: str) -> str:
    """wiki/entities/karpathy.md -> karpathy"""
    name = relpath.rsplit("/", 1)[-1]
    return name[:-3] if name.endswith(".md") else name


def _inbound_link_counts(pages: list[tuple[str, str, float]]) -> Counter:
    counter: Counter[str] = Counter()
    for _rel, body, _mt in pages:
        for m in _WIKILINK_RE.finditer(body):
            counter[m.group(1).strip()] += 1
        for m in _MDLINK_RE.finditer(body):
            target = m.group(1)
            counter[_slug_from_relpath(target)] += 1
    return counter


def _orphan_pages(pages: list[tuple[str, str, float]]) -> list[dict]:
    inbound = _inbound_link_counts(pages)
    now = time.time()
    out = []
    for rel, _body, mt in pages:
        slug = _slug_from_relpath(rel)
        if inbound.get(slug, 0) > 0:
            continue
        age_days = int((now - mt) / 86400)
        if age_days < ORPHAN_GRACE_DAYS:
            continue
        out.append({"relpath": rel, "age_days": age_days})
    return out


def _existing_slugs(root: Path) -> set[str]:
    """Slugs that DO have a page under wiki/entities/ or wiki/concepts/."""
    out: set[str] = set()
    for sub in ("entities", "concepts"):
        d = root / "wiki" / sub
        if not d.is_dir():
            continue
        for p in d.glob("*.md"):
            out.add(p.stem)
    return out


def _missing_concepts(
    pages: list[tuple[str, str, float]],
    root: Path,
    threshold: int = 2,
) -> list[dict]:
    existing = _existing_slugs(root)
    referenced_by: dict[str, list[str]] = defaultdict(list)
    for rel, body, _mt in pages:
        seen_in_this_page: set[str] = set()
        for m in _WIKILINK_RE.finditer(body):
            tgt = m.group(1).strip()
            if tgt in seen_in_this_page:
                continue
            seen_in_this_page.add(tgt)
            if tgt not in existing:
                referenced_by[tgt].append(rel)
    out = []
    for title, refs in sorted(referenced_by.items()):
        if len(refs) >= threshold:
            out.append({"title": title, "referenced_by": refs})
    return out


EMPTY_BODY_THRESHOLD = 50  # chars after stripping frontmatter and whitespace
PLACEHOLDER_TOKENS = ("TBD", "TODO")


def _strip_frontmatter(text: str) -> str:
    """Return body after `---\\n…\\n---\\n` if present."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            return text[end + 5:]
    return text


def _empty_data(pages: list[tuple[str, str, float]]) -> list[dict]:
    out = []
    for rel, text, _mt in pages:
        body = _strip_frontmatter(text).strip()
        if len(body) < EMPTY_BODY_THRESHOLD:
            out.append({"relpath": rel, "reason": f"body<{EMPTY_BODY_THRESHOLD}chars"})
            continue
        non_blank_lines = [ln for ln in body.split("\n") if ln.strip()]
        if not non_blank_lines:
            out.append({"relpath": rel, "reason": "no_non_blank_lines"})
            continue
        placeholder_lines = sum(
            1 for ln in non_blank_lines
            if any(tok in ln for tok in PLACEHOLDER_TOKENS)
        )
        if placeholder_lines / len(non_blank_lines) > 0.5:
            out.append({"relpath": rel, "reason": "majority_placeholders"})
    return out


def _dangling_links(
    pages: list[tuple[str, str, float]],
    root: Path,
) -> list[dict]:
    """Detect [text](./relpath.md) links whose target file doesn't exist (under wiki/)."""
    out = []
    wiki_dir = root / "wiki"
    for rel, body, _mt in pages:
        for m in _MDLINK_RE.finditer(body):
            target_rel = m.group(1)
            target_path = wiki_dir / target_rel
            if not target_path.exists():
                out.append({"source": rel, "target": target_rel})
    return out


def _contradiction_candidates(
    pages: list[tuple[str, str, float]],
) -> list[dict]:
    """For every pair of pages that share at least one wikilink target,
    flag them as a candidate if their bodies contain opposing-verb pairs.
    Final verdict is LLM-judged in commands/lint.md."""
    targets_by_page: dict[str, set[str]] = {}
    bodies_by_page: dict[str, str] = {}
    for rel, body, _mt in pages:
        targets_by_page[rel] = {m.group(1).strip() for m in _WIKILINK_RE.finditer(body)}
        bodies_by_page[rel] = body.lower()

    out: list[dict] = []
    relpaths = sorted(targets_by_page.keys())
    for i, a in enumerate(relpaths):
        for b in relpaths[i + 1:]:
            shared = targets_by_page[a] & targets_by_page[b]
            if not shared:
                continue
            body_a = bodies_by_page[a]
            body_b = bodies_by_page[b]
            for pos, neg in CONTRADICTION_PAIRS:
                if (pos in body_a and neg in body_b) or (neg in body_a and pos in body_b):
                    for entity in sorted(shared):
                        out.append({
                            "page_a": a,
                            "page_b": b,
                            "shared_entity": entity,
                            "lexicon_pair": [pos, neg],
                            "verdict": "candidate",
                        })
                    break
    return out


def _stale_claim_candidates(
    pages: list[tuple[str, str, float]],
) -> list[dict]:
    now = time.time()
    out: list[dict] = []
    for rel, body, mt in pages:
        age_days = int((now - mt) / 86400)
        if age_days < STALE_CLAIM_AGE_DAYS:
            continue
        body_lc = body.lower()
        for phrase in STALE_CLAIM_PHRASES:
            if phrase in body_lc:
                out.append({
                    "relpath": rel,
                    "claim_phrase": phrase,
                    "age_days": age_days,
                    "verdict": "candidate",
                })
                break
    return out
