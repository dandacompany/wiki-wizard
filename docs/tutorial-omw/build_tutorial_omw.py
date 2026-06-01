#!/usr/bin/env python3
"""Self-contained static HTML tutorial builder for oh-my-wiki (Korean, v3 focused showcase).

Single-file: HEAD (full <head> + <style>), esc(), render_section(), SECTIONS, body(), main().
All command blocks and outputs are copied verbatim from TUTORIAL.ko.md (accuracy-reviewed v3).
Personal OMW_HOME paths are shown as ~/.omw.
"""
import html
import pathlib

BASE = pathlib.Path(__file__).resolve().parent
OUT = BASE / "tutorial-omw.html"

# ─────────────────────────────────────────────────────────────────────────────
# HEAD — full <head> + <style> (sand / stone / moss earth palette)
# ─────────────────────────────────────────────────────────────────────────────
HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>oh-my-wiki v3 — 따라 하는 위키 셋업</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;700;900&family=Noto+Sans+KR:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --sand:#d4c4a8;
  --stone-100:#f5f3ee; --stone-200:#e8e3d9;
  --stone-400:#a89876; --stone-500:#8a7a58;
  --stone-700:#5a4e38; --stone-800:#3e3526;
  --stone-900:#1f1a10;
  --moss:#6b7d4f; --cream:#fafaf7;
  --code-bg-a:#13171b; --code-bg-b:#0e1114;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:'Noto Sans KR',sans-serif;
  font-weight:400; font-size:15.5px; line-height:1.8;
  color:var(--stone-800);
  background:var(--stone-100);
  -webkit-font-smoothing:antialiased;
}
a{color:var(--moss);text-decoration:none;border-bottom:1px solid rgba(107,125,79,.35)}
a:hover{border-bottom-color:var(--moss)}
.container{max-width:880px;margin:0 auto;padding:0 28px}
code{font-family:'JetBrains Mono',monospace;font-size:.92em;
  background:var(--stone-200);color:var(--stone-700);
  padding:1px 6px;border-radius:4px}

/* ── hero ── */
.hero{
  background:
    linear-gradient(180deg, var(--stone-200) 0%, var(--stone-100) 100%);
  border-bottom:1px solid var(--stone-200);
  padding:78px 0 56px;
}
.hero-inner{max-width:880px;margin:0 auto;padding:0 28px}
.hero-badge{
  display:inline-block;font-family:'JetBrains Mono',monospace;font-weight:500;
  font-size:11.5px;letter-spacing:.4px;text-transform:uppercase;
  color:var(--stone-500);background:var(--cream);
  border:1px solid var(--sand);border-radius:999px;
  padding:5px 13px;margin-bottom:22px;
}
.hero h1{
  font-family:'Noto Serif KR',serif;font-weight:900;
  font-size:clamp(34px,5vw,48px);line-height:1.18;
  color:var(--stone-900);letter-spacing:-.5px;
}
.hero .tagline{
  margin-top:18px;font-size:16px;line-height:1.8;color:var(--stone-700);
  max-width:640px;
}
.meta-grid{
  margin-top:34px;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0;
  border:1px solid var(--stone-200);border-radius:8px;overflow:hidden;
  background:var(--cream);
}
.meta-grid div{padding:14px 18px;border-right:1px solid var(--stone-200);border-bottom:1px solid var(--stone-200)}
.meta-grid dt{
  font-family:'JetBrains Mono',monospace;font-weight:500;
  font-size:11px;letter-spacing:.4px;text-transform:uppercase;color:var(--stone-400);
}
.meta-grid dd{margin-top:5px;font-size:14px;color:var(--stone-800);font-weight:500}

/* ── top nav / TOC ── */
nav.toc{
  position:sticky;top:0;z-index:20;
  background:rgba(245,243,238,.94);backdrop-filter:saturate(120%);
  border-bottom:1px solid var(--stone-200);
}
nav.toc .toc-inner{
  max-width:880px;margin:0 auto;padding:11px 28px;
  display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;
}
nav.toc a{
  font-family:'JetBrains Mono',monospace;font-weight:500;
  font-size:11px;letter-spacing:.3px;text-transform:uppercase;
  color:var(--stone-500);border-bottom:none;
}
nav.toc a:hover{color:var(--moss)}
nav.toc .tag{color:var(--stone-400);font-weight:700;margin-right:4px}

/* ── overview ── */
#overview{padding:60px 0 8px}
#overview .lede{font-size:16.5px;line-height:1.85;color:var(--stone-700);max-width:680px}

/* ── section rhythm ── */
section{padding:68px 0;border-top:1px solid var(--stone-200)}
.section-num{
  font-family:'JetBrains Mono',monospace;font-weight:500;
  font-size:12px;letter-spacing:4px;text-transform:uppercase;color:var(--stone-400);
  margin-bottom:14px;
}
h2{
  font-family:'Noto Serif KR',serif;font-weight:700;
  font-size:clamp(22px,3vw,30px);line-height:1.3;
  color:var(--stone-900);letter-spacing:-.3px;
}
p.lede{margin-top:16px;font-size:16px;line-height:1.82;color:var(--stone-700);max-width:680px}
p.lede + .block,p.lede + .design,p.lede + .note,p.lede + .callout{margin-top:30px}
.block-label{
  font-family:'JetBrains Mono',monospace;font-weight:500;
  font-size:11.5px;letter-spacing:.5px;text-transform:uppercase;color:var(--stone-500);
  margin:30px 0 9px;
}
.prose{margin-top:14px;font-size:15px;line-height:1.82;color:var(--stone-700)}
.prose + .block-label{margin-top:24px}

/* ── code block (dark terminal card) ── */
.block.code{
  background:linear-gradient(160deg,var(--code-bg-a),var(--code-bg-b));
  border:1px solid #20262c;border-radius:10px;overflow:hidden;
  box-shadow:0 1px 2px rgba(31,26,16,.06),0 8px 24px rgba(31,26,16,.05);
}
.block.code .bar{
  display:flex;align-items:center;gap:7px;
  padding:11px 15px;border-bottom:1px solid #20262c;background:rgba(255,255,255,.015);
}
.block.code .dot{width:11px;height:11px;border-radius:50%}
.dot.r{background:#ff5f56}.dot.y{background:#ffbd2e}.dot.g{background:#27c93f}
.block.code .bar-label{
  margin-left:8px;font-family:'JetBrains Mono',monospace;font-size:11px;
  letter-spacing:.3px;color:#5d6873;text-transform:lowercase;
}
.block.code pre{
  margin:0;padding:17px 19px;overflow-x:auto;
  font-family:'JetBrains Mono',monospace;font-size:13px;line-height:1.85;
  color:#cdd6df;
}
.block.code pre .c-cmd{color:#9ad08f}
.block.code pre .c-flag{color:#e0c275}
.block.code pre .c-key{color:#82aaff}
.block.code pre .c-str{color:#c3e88d}
.block.code pre .c-cmt{color:#5d6873}

/* ── design block ── */
.design{
  background:var(--cream);border:1px solid var(--stone-200);border-radius:12px;
  padding:26px 28px 28px;
}
.design .goal{
  display:flex;gap:10px;align-items:flex-start;
  font-family:'Noto Serif KR',serif;font-weight:700;font-size:18px;line-height:1.5;
  color:var(--stone-900);padding-bottom:20px;border-bottom:1px solid var(--stone-200);
}
.design .goal .ico{font-size:18px;line-height:1.5}
.design .sub-label{
  font-family:'JetBrains Mono',monospace;font-weight:500;
  font-size:11px;letter-spacing:.5px;text-transform:uppercase;color:var(--stone-400);
  margin:22px 0 12px;display:flex;align-items:center;gap:7px;
}
.principles{display:grid;gap:10px}
.principles .pr{
  display:flex;gap:13px;align-items:flex-start;
  font-size:14.5px;line-height:1.7;color:var(--stone-700);
}
.principles .pr .n{
  flex:0 0 auto;width:23px;height:23px;border-radius:6px;
  background:var(--moss);color:#fff;
  font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:500;
  display:flex;align-items:center;justify-content:center;margin-top:1px;
}
.components{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.components .cmp{
  background:var(--stone-100);border:1px solid var(--stone-200);border-radius:9px;
  padding:17px 18px;
}
.components .cmp .ico{font-size:22px;display:block;margin-bottom:9px}
.components .cmp .nm{
  font-family:'JetBrains Mono',monospace;font-weight:500;font-size:13px;
  color:var(--stone-900);margin-bottom:6px;
}
.components .cmp .ds{font-size:13.5px;line-height:1.65;color:var(--stone-600,#6b6150)}

/* ── note (cream memo, moss left border) ── */
.note{
  background:var(--cream);border:1px solid var(--stone-200);
  border-left:3px solid var(--moss);border-radius:0 9px 9px 0;
  padding:18px 22px;font-size:14.5px;line-height:1.72;color:var(--stone-700);
}
.note strong{color:var(--stone-900);font-weight:700}
.note .star{color:var(--moss);font-weight:700}
.note ul{margin:8px 0 0 2px;padding:0;list-style:none}
.note li{position:relative;padding-left:18px;margin-top:5px}
.note li::before{content:"·";position:absolute;left:4px;color:var(--moss);font-weight:700}

/* ── callout (after block) ── */
.callout{
  margin-top:18px;background:var(--cream);
  border-left:3px solid var(--moss);border-radius:0 8px 8px 0;
  padding:14px 20px;font-size:14px;line-height:1.7;color:var(--stone-700);
}
.callout strong{color:var(--stone-900)}

/* ── ref table ── */
.ref-table{
  margin-top:24px;width:100%;border-collapse:collapse;
  border:1px solid var(--stone-200);border-radius:8px;overflow:hidden;font-size:13.5px;
}
.ref-table th,.ref-table td{
  text-align:left;padding:9px 14px;border-bottom:1px solid var(--stone-200);
  vertical-align:top;
}
.ref-table th{
  font-family:'JetBrains Mono',monospace;font-weight:500;font-size:11px;
  letter-spacing:.4px;text-transform:uppercase;color:var(--stone-400);
  background:var(--cream);
}
.ref-table td code{background:var(--stone-100)}
.ref-table tr:last-child td{border-bottom:none}

/* ── footer ── */
footer{
  border-top:1px solid var(--stone-200);background:var(--stone-200);
  padding:46px 0;margin-top:8px;
}
footer .container{font-size:13.5px;color:var(--stone-500);line-height:1.8}
footer a{color:var(--stone-700)}
footer .links{margin-top:10px;display:flex;flex-wrap:wrap;gap:18px}
footer .links a{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.3px}

@media(max-width:640px){
  .components{grid-template-columns:1fr}
  .hero{padding:54px 0 40px}
}
</style>
</head>
"""


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def esc(s: str) -> str:
    return html.escape(s, quote=False)


def render_block(cmd: dict) -> str:
    """Render one block: kind = code (default) | design | note."""
    kind = cmd.get("kind", "code")
    label = cmd.get("label", "")
    label_html = f'<div class="block-label">{esc(label)}</div>' if label else ""

    if kind == "design":
        d = cmd["design"]
        goal = (
            f'<div class="goal"><span class="ico">🎯</span><span>{esc(d["goal"])}</span></div>'
        )
        princ = ""
        if d.get("principles"):
            items = "".join(
                f'<div class="pr"><span class="n">{i}</span><span>{esc(p)}</span></div>'
                for i, p in enumerate(d["principles"], 1)
            )
            princ = (
                '<div class="sub-label">📏 PRINCIPLES</div>'
                f'<div class="principles">{items}</div>'
            )
        comps = ""
        if d.get("components"):
            cards = "".join(
                f'<div class="cmp"><span class="ico">{esc(ico)}</span>'
                f'<div class="nm">{esc(nm)}</div><div class="ds">{esc(ds)}</div></div>'
                for ico, nm, ds in d["components"]
            )
            comps = (
                '<div class="sub-label">🧱 COMPONENTS</div>'
                f'<div class="components">{cards}</div>'
            )
        return f'{label_html}<div class="design">{goal}{princ}{comps}</div>'

    if kind == "note":
        return f'{label_html}<div class="note">{cmd["text"]}</div>'

    # default: code (dark terminal card)
    text = esc(cmd.get("text", ""))
    bar_label = cmd.get("bar", "terminal")
    return (
        f'{label_html}<div class="block code">'
        f'<div class="bar"><span class="dot r"></span><span class="dot y"></span>'
        f'<span class="dot g"></span><span class="bar-label">{esc(bar_label)}</span></div>'
        f"<pre>{text}</pre></div>"
    )


def render_section(s: dict) -> str:
    parts = [
        f'<section id="step-{s["num"]}">',
        '<div class="container">',
        f'<div class="section-num">{esc(s["num"])}</div>',
        f'<h2>{esc(s["title"])}</h2>',
    ]
    if s.get("lede"):
        parts.append(f'<p class="lede">{s["lede"]}</p>')
    for cmd in s.get("commands", []):
        if cmd.get("prose"):
            parts.append(f'<div class="prose">{cmd["prose"]}</div>')
        parts.append(render_block(cmd))
        if cmd.get("callout"):
            parts.append(f'<div class="callout">{cmd["callout"]}</div>')
    if s.get("after"):
        parts.append(s["after"])
    parts.append("</div></section>")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# SECTIONS — Korean focused showcase, verbatim command blocks from TUTORIAL.ko.md
# ─────────────────────────────────────────────────────────────────────────────
SECTIONS: list[dict] = [
    dict(
        num="STEP 01",
        title="설치",
        lede="환경에 맞는 경로 하나를 골라 설치합니다. 어떤 경로든 끝나면 "
        "<code>omw doctor</code>로 연결 상태를 확인합니다.",
        commands=[
            {
                "label": "PATH A — Skills CLI (Claude Code 권장)",
                "bar": "bash",
                "text": "skills add dandacompany/oh-my-wiki@oh-my-wiki -g -y --copy -a claude-code",
                "callout": "스킬을 <code>~/.claude/skills/</code>에 설치하고 "
                "<code>oh-my-wiki</code>와 단축 별칭 <code>omw</code> 스킬 이름을 함께 등록합니다.",
            },
            {
                "label": "PATH B — Claude Code 플러그인 마켓플레이스",
                "bar": "claude code",
                "text": "/plugin marketplace add dandacompany/oh-my-wiki\n"
                "/plugin install oh-my-wiki@oh-my-wiki-marketplace",
                "callout": "이후 업데이트는 "
                "<code>/plugin marketplace update oh-my-wiki-marketplace</code>로 진행합니다.",
            },
            {
                "label": "PATH C — git clone + install script (Codex CLI · 개발자)",
                "bar": "bash",
                "text": "git clone https://github.com/dandacompany/oh-my-wiki\n"
                "cd oh-my-wiki\n"
                "bash bin/install.sh",
                "callout": "인스톨러가 Python 3.10+ 확인, "
                "<code>pip install -e \".\"</code>, "
                "<code>~/.claude/skills/oh-my-wiki</code>·<code>omw</code> symlink 생성(멱등성), "
                "<code>pytest -q</code> 검증을 수행합니다. 재실행해도 안전하며, "
                "<code>--force</code>로 프롬프트 없이 교체합니다.",
            },
            {
                "label": "설치 확인 — omw doctor",
                "bar": "terminal",
                "text": "omw doctor",
            },
            {
                "label": "성공하면 보이는 것 (vault가 있을 때)",
                "bar": "output",
                "text": "omw home:   ~/.omw  ok\n"
                "registry:   ~/.omw/registry.db  ok\n"
                "  * demo (wiki/markdown) ~/.omw/vaults/demo",
                "callout": "새 머신에서 <code>omw setup</code> 전이라면 "
                "<code>missing (run: omw setup)</code>으로 표시됩니다. "
                "<code>doctor</code>는 각 컴포넌트를 찾으면 <code>ok</code>를, 없으면 무엇이 빠졌는지 보고합니다.",
            },
        ],
    ),
    dict(
        num="STEP 02",
        title="첫 위키",
        lede="설정 마법사로 첫 vault를 만들고, 상태와 lint로 깨끗한 시작점을 확인합니다.",
        commands=[
            {
                "label": "설정 마법사 실행",
                "bar": "terminal",
                "text": "omw setup",
                "callout": "첫 vault, 검색 provider, TTS, persona를 구성하는 대화형 마법사입니다. "
                "기본값을 그대로 받아들이면 빠르게 시작합니다. 이후 "
                "<code>omw setup vault</code>·<code>omw setup personas</code>로 개별 섹션을 다시 조정합니다.",
            },
            {
                "label": "상태 확인 — omw status",
                "bar": "terminal",
                "text": "omw status",
            },
            {
                "label": "성공하면 보이는 것 (깨끗한 머신)",
                "bar": "json",
                "text": "{\n"
                '  "vault_count": 0,\n'
                '  "active": null,\n'
                '  "needs": "setup",\n'
                '  "vaults": []\n'
                "}",
                "callout": "<code>needs: \"setup\"</code>은 깨끗한 머신의 정상 화면입니다. "
                "소스 트리에서 실행하면 <code>data/registry.db</code> 때문에 "
                "<code>needs</code>가 <code>\"migrate\"</code>로 표시되며, 이는 개발 트리에서만 나타납니다.",
            },
            {
                "label": "첫 vault 만들기",
                "bar": "terminal",
                "text": "omw vault create demo --mode wiki",
            },
            {
                "label": "성공하면 보이는 것",
                "bar": "json",
                "text": "{\n"
                '  "created": "demo",\n'
                '  "path": "~/.omw/vaults/demo",\n'
                '  "mode": "wiki",\n'
                '  "type": "markdown"\n'
                "}",
            },
            {
                "label": "활성 상태 확인 — omw vault list",
                "bar": "json",
                "text": "[\n"
                "  {\n"
                '    "name": "demo",\n'
                '    "path": "~/.omw/vaults/demo",\n'
                '    "mode": "wiki",\n'
                '    "type": "markdown",\n'
                '    "is_active": true\n'
                "  }\n"
                "]",
            },
            {
                "label": "노트 추가 (Claude / Codex / Gemini 세션에서)",
                "bar": "ai session",
                "text": "ingest this\n\n"
                'Andrej Karpathy calls the LLM Wiki a "compounding knowledge artifact". Every\n'
                "source gets saved verbatim to raw/, a summary lands at wiki/summaries/, and\n"
                "the entities and concepts that appeared get their own pages. 10–15 page touches\n"
                "per ingest is normal.",
                "callout": "스킬이 제목, slug, 태그, 저장 위치를 제안합니다. 확인하면 저장됩니다.",
            },
            {
                "label": "lint 검사 — omw lint",
                "bar": "terminal",
                "text": "omw lint",
            },
            {
                "label": "성공하면 보이는 것 (문제 없는 vault)",
                "bar": "json",
                "text": "{\n"
                '  "vault_id": 1,\n'
                '  "vault_path": "~/.omw/vaults/demo",\n'
                '  "frontmatter_issues": [],\n'
                '  "drift": { "missing_files": [], "mtime_drift": [] },\n'
                '  "links": {\n'
                '    "broken": [],\n'
                '    "orphans": [],\n'
                '    "index_drift": { "missing_from_index": [], "dangling_in_index": [] },\n'
                '    "contradictions": [],\n'
                '    "supersedes": [],\n'
                '    "superseded_unmarked": [],\n'
                '    "link_suggestions": []\n'
                "  },\n"
                '  "auto_fix_hints": []\n'
                "}",
            },
            {
                "kind": "note",
                "text": "<span class='star'>★ 읽는 법</span> — "
                "<strong>frontmatter_issues: []</strong>는 모든 페이지가 필수 필드 검사를 통과했다는 뜻입니다."
                "<ul>"
                "<li><strong>links</strong> 키들(broken·orphans·index_drift·contradictions·supersedes·"
                "superseded_unmarked·link_suggestions)은 vault의 구조 건강 상태를 알려줍니다.</li>"
                "<li><strong>drift</strong>는 디스크에 있지만 인덱스에 없는 파일을 보고합니다.</li>"
                "<li><strong>auto_fix_hints</strong>는 문제가 발견될 때 실행 가능한 해결 방법을 제시합니다.</li>"
                "</ul>",
            },
        ],
    ),
    dict(
        num="STEP 03",
        title="페이지 규약 (스키마)",
        lede="13개 내장 페이지 타입이 각 타입에 필요한 필드와 허용값을 정의합니다. "
        "타입을 나열하고, entity 타입을 자세히 확인합니다.",
        commands=[
            {
                "label": "타입 나열 — omw schema list",
                "bar": "terminal",
                "text": "omw schema list",
            },
            {
                "label": "13개 타입",
                "bar": "output",
                "text": "article, book, comparison, concept, doc, entity, link, meta, note,\n"
                "paper, summary, synthesis, video",
                "callout": "각 항목은 <code>type</code>, <code>required_fields</code>, "
                "<code>required_sections</code>, <code>field_types</code>, "
                "<code>allowed_values</code>를 가진 스키마 객체입니다.",
            },
            {
                "label": "entity 타입 상세 — omw schema show entity",
                "bar": "terminal",
                "text": "omw schema show entity",
            },
            {
                "label": "성공하면 보이는 것",
                "bar": "json",
                "text": "{\n"
                '  "type": "entity",\n'
                '  "required_fields": ["title", "date", "type", "tags"],\n'
                '  "required_sections": ["## Summary"],\n'
                '  "field_types": {\n'
                '    "tags": "list",\n'
                '    "title": "str",\n'
                '    "date": "str",\n'
                '    "review": "dict",\n'
                '    "aliases": "list"\n'
                "  },\n"
                '  "allowed_values": {\n'
                '    "confidence": ["high", "medium", "low"],\n'
                '    "status": ["draft", "inbox", "processed", "raw", "superseded", "meta"]\n'
                "  }\n"
                "}",
                "callout": "모든 entity 페이지는 본문에 <code>## Summary</code> 섹션이 있어야 합니다. "
                "<code>confidence</code>는 high·medium·low를, <code>status</code>는 "
                "<code>allowed_values</code> 목록값을 허용합니다.",
            },
            {
                "label": "vault별 스키마 오버라이드",
                "bar": "tree",
                "text": "~/.omw/vaults/demo/\n"
                "└── schemas/\n"
                "    └── entity.yml   ← overrides the built-in entity schema for this vault only",
                "callout": "<code>&lt;vault&gt;/schemas/</code>의 파일이 패키지 루트의 내장 "
                "<code>schemas/</code>보다 우선합니다. 공유 기본값을 건드리지 않고 특정 프로젝트에 "
                "커스텀 타입을 추가하거나 필드 규칙을 강화합니다.",
            },
        ],
    ),
    dict(
        num="STEP 04",
        title="신뢰도와 대체",
        lede="페이지는 근거의 충분함을 나타내는 <code>confidence</code>(high·medium·low)를 가집니다. "
        "더 나은 페이지로 대체할 때는 삭제하지 않고 <code>superseded</code>로 표시해 감사 추적을 보존합니다.",
        commands=[
            {
                "label": "old-method.md를 llm-wiki로 supersede",
                "bar": "terminal",
                "text": "omw supersede wiki/concepts/old-method.md --by llm-wiki",
            },
            {
                "label": "성공하면 보이는 것",
                "bar": "json",
                "text": "{\n"
                '  "relpath": "wiki/concepts/old-method.md",\n'
                '  "status": "superseded",\n'
                '  "superseded_by": "llm-wiki"\n'
                "}",
            },
            {
                "label": "old-method.md에 작성되는 frontmatter",
                "bar": "yaml",
                "text": "status: superseded\n"
                "superseded_by: llm-wiki",
                "callout": "<code>omw lint</code>는 본문에 \"outdated\"·\"replaced\"로 비공식 설명되어 "
                "있지만 이 필드가 없는 페이지를 <code>superseded_unmarked</code> 키 아래에 표시합니다.",
            },
        ],
    ),
    dict(
        num="STEP 05",
        title="리뷰 주기",
        lede="모든 페이지는 frontmatter의 <code>review:</code> 블록으로 다음 재평가 일정을 지정합니다. "
        "간격은 confidence를 따릅니다. high → 90일, medium → 30일, low → 7일.",
        commands=[
            {
                "label": "llm-wiki.md (high-confidence) review 완료 처리",
                "bar": "terminal",
                "text": "omw review done wiki/concepts/llm-wiki.md --grade pass --today 2026-06-01",
            },
            {
                "label": "성공하면 보이는 것",
                "bar": "json",
                "text": "{\n"
                '  "relpath": "wiki/concepts/llm-wiki.md",\n'
                '  "review": { "last": "2026-06-01", "due": "2026-08-30", "interval_days": 90 }\n'
                "}",
                "callout": "<code>high</code> confidence → 90일 간격 → 만료일 <code>2026-08-30</code>.",
            },
            {
                "label": "review 대상 조회 (미래 날짜 시뮬레이션)",
                "bar": "terminal",
                "text": "omw review due --today 2026-09-01",
                "callout": "<code>{relpath, due, interval_days, confidence}</code> 목록이 반환됩니다. "
                "<code>review:</code> 블록이 없는 페이지는 <code>due: null</code>로 표시되며 가장 앞에 정렬됩니다. "
                "한 번도 검토되지 않았으므로 주의가 필요합니다.",
            },
        ],
    ),
    dict(
        num="STEP 06",
        title="전문 검색 & 메신저 API",
        lede="vault 검색은 SQLite FTS5(BM25)로 동작합니다. 세션에서 자연어로 묻거나, "
        "<code>omw serve</code>로 로컬 읽기 전용 HTTP API를 띄워 <code>POST /query</code>로 가져옵니다.",
        commands=[
            {
                "label": "vault 인덱싱 방식",
                "bar": "fts5",
                "text": "title + summary + tags + body  →  SQLite FTS5 (BM25)\n"
                "FTS5 미지원 시  →  토큰 스코어 기반 자동 폴백",
                "callout": "세션에서 \"내 위키에서 X에 대해 뭐라고 해?\"라고 말하면 스킬이 FTS5로 검색하고 "
                "LLM이 결과를 재순위 매깁니다. <code>omw serve</code>는 서버에 LLM 없이 검색만 수행합니다.",
            },
            {
                "label": "인증 토큰 생성 (~/.omw/.env에 OMW_SERVE_TOKEN으로 저장)",
                "bar": "terminal",
                "text": "omw setup serve --generate-token",
            },
            {
                "label": "서버 시작 — omw serve",
                "bar": "terminal",
                "text": "omw serve",
                "callout": "서버는 <code>http://127.0.0.1:8765</code>(localhost 전용)에서 실행됩니다. "
                "<code>POST /query</code>는 인증 필요, <code>GET /health</code>는 인증 불필요, "
                "<code>GET /query</code>는 405를 반환합니다.",
            },
            {
                "label": "curl — health(인증 없음) + query(POST + bearer)",
                "bar": "bash",
                "text": "# health (no auth)\n"
                "curl -s http://127.0.0.1:8765/health\n\n"
                "# query (POST + bearer token)\n"
                "curl -s -X POST http://127.0.0.1:8765/query \\\n"
                '  -H "Authorization: Bearer $OMW_SERVE_TOKEN" \\\n'
                '  -H "Content-Type: application/json" \\\n'
                '  -d \'{"text": "compounding knowledge", "limit": 5}\'',
                "callout": "전체 요청/응답 JSON 형식과 Slack·Telegram·Discord 어댑터 스케치는 "
                "<code>references/messenger-api.md</code>에 있습니다.",
            },
            {
                "kind": "note",
                "text": "<span class='star'>★ 구분</span> — "
                "<strong>omw search</strong>는 별개입니다. 외부 provider"
                "(brave·tavily·exa·firecrawl·brightdata)를 통한 <strong>웹 검색</strong>이며, "
                "vault 내부를 검색하지 않습니다. provider 미설정 시 "
                "<code>omw setup search</code>를 실행합니다.",
            },
        ],
    ),
    dict(
        num="STEP 07",
        title="엔티티 자동 링크",
        lede="개념 페이지가 엔티티를 언급하면서 링크를 걸지 않는 경우, "
        "oh-my-wiki가 링크 없는 언급을 감지하고 자동으로 wikilink를 삽입합니다.",
        commands=[
            {
                "label": "링크 없는 언급 감지 — omw links suggest",
                "bar": "terminal",
                "text": "omw links suggest",
            },
            {
                "label": "성공하면 보이는 것 (2건)",
                "bar": "json",
                "text": "[\n"
                "  {\n"
                '    "src_relpath": "wiki/concepts/llm-wiki.md",\n'
                '    "target_slug": "andrej-karpathy",\n'
                '    "target_relpath": "wiki/entities/andrej-karpathy.md",\n'
                '    "mention": "Andrej Karpathy",\n'
                '    "position": 145\n'
                "  },\n"
                "  {\n"
                '    "src_relpath": "wiki/entities/andrej-karpathy.md",\n'
                '    "target_slug": "llm-wiki",\n'
                '    "target_relpath": "wiki/concepts/llm-wiki.md",\n'
                '    "mention": "LLM Wiki",\n'
                '    "position": 88\n'
                "  }\n"
                "]",
                "callout": "<code>llm-wiki.md</code> 위치 145에서 \"Andrej Karpathy\"가, "
                "<code>andrej-karpathy.md</code> 위치 88에서 \"LLM Wiki\"가 wikilink 없이 언급됩니다. "
                "두 경우 모두 vault에 일치하는 페이지가 존재합니다.",
            },
            {
                "label": "링크 삽입 — omw links link",
                "bar": "terminal",
                "text": "omw links link wiki/concepts/llm-wiki.md --to andrej-karpathy",
            },
            {
                "label": "성공하면 보이는 것",
                "bar": "json",
                "text": "{\n"
                '  "relpath": "wiki/concepts/llm-wiki.md",\n'
                '  "target_slug": "andrej-karpathy",\n'
                '  "mention": "Andrej Karpathy",\n'
                '  "inserted": "[[andrej-karpathy|Andrej Karpathy]]"\n'
                "}",
                "callout": "해당 언급을 <code>[[andrej-karpathy|Andrej Karpathy]]</code>로 제자리에서 재작성합니다.",
            },
            {
                "kind": "note",
                "text": "<span class='star'>★ 한국어 조사 매칭</span> — "
                "본문에 <strong>안드레이 카르파시가 이 방법을 제안했다.</strong>처럼 조사 "
                "<code>가</code>가 이름에 붙어 있어도, <code>omw links suggest</code>가 "
                "<code>안드레이 카르파시가</code>를 <code>안드레이 카르파시</code> slug와 매칭하고, "
                "<code>omw links link</code>는 다음처럼 삽입합니다."
                "<ul>"
                "<li><code>[[…|안드레이 카르파시]]가 이 방법을 제안했다.</code></li>"
                "</ul>"
                "조사는 wikilink 괄호 밖에 남고, 표시 텍스트는 조사 없는 표준 이름입니다.",
            },
        ],
    ),
    dict(
        num="STEP 08",
        title="인라인 필드",
        lede="페이지 본문에 Dataview 스타일 인라인 필드 <code>key:: value</code>를 넣으면 "
        "frontmatter와 함께 파싱·저장·인덱싱됩니다.",
        commands=[
            {
                "label": "본문 인라인 필드 예시",
                "bar": "markdown",
                "text": "owner:: dante\n"
                "status:: draft\n"
                "uses:: [[llm-wiki]]",
            },
            {
                "label": "전체 필드 확인 — omw fields",
                "bar": "terminal",
                "text": "omw fields wiki/concepts/llm-wiki.md",
            },
            {
                "label": "성공하면 보이는 것",
                "bar": "json",
                "text": "{\n"
                '  "relpath": "wiki/concepts/llm-wiki.md",\n'
                '  "frontmatter": {\n'
                '    "title": "LLM Wiki",\n'
                '    "date": "2026-06-01",\n'
                '    "type": "concept",\n'
                '    "tags": ["method"]\n'
                "  },\n"
                '  "inline": { "owner": ["dante"], "status": ["draft"] }\n'
                "}",
                "callout": "wikilink를 참조하는 관계 키(<code>uses</code>, <code>contradicts</code>, "
                "<code>supersedes</code>)는 frontmatter <code>relations:</code>와 동일하게 "
                "타입드 엣지 그래프에 반영됩니다.",
            },
        ],
    ),
    dict(
        num="STEP 09",
        title="페르소나 (세션 내, 자연어)",
        lede="여덟 가지 writing persona를 Claude Code / Codex / Gemini 세션에서 자연어로 호출합니다. "
        "별도 커맨드 없이 입력 내용에 따라 스킬이 적절한 persona로 라우팅합니다.",
        commands=[
            {
                "label": "Researcher — in your Claude session, say:",
                "bar": "ai session",
                "text": "autoresearch how does the LLM Wiki pattern compare to Zettelkasten?",
                "callout": "질문을 주장 단위로 분해하고, 주장별 최대 3라운드 검색 후 confidence 태그를 부여하며, "
                "synthesis 초안을 작성해 저장 전에 확인을 요청합니다. → "
                "<code>wiki/syntheses/&lt;slug&gt;.md</code>",
            },
            {
                "label": "Fact-checker — in your Claude session, say:",
                "bar": "ai session",
                "text": "fact-check wiki/concepts/llm-wiki.md",
                "callout": "초안을 원자 단위 주장으로 분해해 웹 검색으로 검증하고, 판정 표"
                "(supported·contradicted·partial·unverifiable)를 "
                "<code>&lt;page&gt;.factcheck.md</code>에 작성합니다.",
            },
            {
                "label": "Curator — in your Claude session, say:",
                "bar": "ai session",
                "text": "curate my wiki — what pages are most in need of attention?",
                "callout": "공백, 고립 페이지, 구조적 취약점을 검토하고 유지 관리 계획을 제안합니다(세션 내).",
            },
            {
                "label": "Wiki-auditor — in your Claude session, say:",
                "bar": "ai session",
                "text": "check my wiki for contradictions\n"
                "build a glossary for my vault",
                "callout": "전체 일관성 검사를 실행합니다. 모순, 용어 표류, 오래된 주장을 점검합니다.",
            },
            {
                "kind": "note",
                "text": "<span class='star'>★ 공통 모델</span> — "
                "모든 persona는 <strong>제안 → 확인 → 실행</strong>을 따릅니다. "
                "파일을 읽고, 제안 초안을 작성하고, 무엇이 변경될지 보여준 다음 작성합니다. "
                "전체 목록(translator·polisher·summarizer·scaffolder 포함)은 아래 레퍼런스에 있습니다.",
            },
        ],
    ),
    dict(
        num="레퍼런스",
        title="마무리 / 다음 단계",
        lede="전체 6부 레퍼런스는 영어·한국어 튜토리얼에 있습니다. "
        "13개 CLI 서브커맨드는 결정론 ops를, 추론 작업은 AI 세션을 사용합니다.",
        commands=[
            {
                "after_marker": True,  # marker; rendered via section 'after'
            },
        ],
        after="""<table class="ref-table">
<tr><th>서브커맨드</th><th>한 줄 설명</th></tr>
<tr><td><code>omw status</code></td><td>레지스트리 상태 표시: vault 수, 활성 vault, needs 코드</td></tr>
<tr><td><code>omw vault</code></td><td>Vault 관리: create · list · use · forget</td></tr>
<tr><td><code>omw lint</code></td><td>결정론 vault 건강 검사 (frontmatter + links + drift)</td></tr>
<tr><td><code>omw search</code></td><td>설정된 외부 provider를 통한 웹 검색 (brave/tavily/exa/…)</td></tr>
<tr><td><code>omw serve</code></td><td>로컬 읽기 전용 HTTP 쿼리 API 시작 (포트 8765)</td></tr>
<tr><td><code>omw schema</code></td><td>페이지 타입 스키마 표시: list · show &lt;type&gt;</td></tr>
<tr><td><code>omw supersede</code></td><td>페이지를 status: superseded + superseded_by: &lt;slug&gt;로 표시</td></tr>
<tr><td><code>omw review</code></td><td>간격 반복 대기열: due · done</td></tr>
<tr><td><code>omw links</code></td><td>엔티티 자동 링크: suggest · link</td></tr>
<tr><td><code>omw fields</code></td><td>페이지의 frontmatter + 인라인 key:: value 필드 표시</td></tr>
<tr><td><code>omw import</code></td><td>폴더 / Obsidian vault / Notion export 가져오기</td></tr>
<tr><td><code>omw setup</code></td><td>대화형 마법사: vault · 검색 · persona · TTS</td></tr>
<tr><td><code>omw doctor</code></td><td>omw 설정 + 설치 건강 상태 검증</td></tr>
</table>
<div class="callout" style="margin-top:24px">
추론 작업(<code>ingest</code> · <code>query</code> · <code>find</code> · <code>edit</code> ·
<code>autoresearch</code> · persona)은 <strong>Claude / Codex / Gemini 세션</strong>에서 자연어로 사용합니다.
전체 레퍼런스: <a href="../../TUTORIAL.md">TUTORIAL.md (EN)</a> ·
<a href="../../TUTORIAL.ko.md">TUTORIAL.ko.md (KO)</a>.
</div>""",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# body + main
# ─────────────────────────────────────────────────────────────────────────────
OVERVIEW_DESIGN = {
    "goal": "omw를 두 표면으로 쓴다.",
    "principles": [
        "페르소나는 제안, 결정론 명령이 실행 (propose → confirm → execute).",
        "어떤 AI 호스트(Claude Code · Codex · Gemini)에서도 동일한 SKILL.md, 동일한 트리거 문구.",
        "모든 파일 변경은 감사 가능 — 추론은 투명하게, 출력은 결정론으로.",
    ],
    "components": [
        (
            "⌨️",
            "omw CLI",
            "결정론 ops — 설치·셋업·vault·lint·schema·supersede·review·links·fields·serve·doctor",
        ),
        (
            "💬",
            "omw 스킬",
            "세션 내 자연어 추론 — ingest·query·autoresearch·페르소나",
        ),
    ],
}


def body() -> str:
    toc_links = "\n".join(
        f'<a href="#step-{s["num"]}"><span class="tag">{esc(s["num"])}</span>{esc(s["title"])}</a>'
        for s in SECTIONS
    )
    sections_html = "\n\n".join(render_section(s) for s in SECTIONS)
    overview_block = render_block({"kind": "design", "design": OVERVIEW_DESIGN})
    return f"""<body>
<header class="hero">
  <div class="hero-inner">
    <span class="hero-badge">oh-my-wiki · v3 · 한국어</span>
    <h1>AI 코딩 에이전트로 운영하는<br>host-universal LLM 위키</h1>
    <p class="tagline">Claude Code · Codex · Gemini 세션에서 자연어로 위키를 키우고,
    <code>omw</code> CLI로 결정론 작업을 실행합니다. 모든 명령과 출력은 실제 v3 실행 결과 그대로입니다.</p>
    <dl class="meta-grid">
      <div><dt>표면</dt><dd>omw CLI + omw 스킬</dd></div>
      <div><dt>호스트</dt><dd>Claude Code · Codex · Gemini</dd></div>
      <div><dt>모델</dt><dd>propose → confirm → execute</dd></div>
      <div><dt>CLI 서브커맨드</dt><dd>13개</dd></div>
    </dl>
  </div>
</header>

<nav class="toc"><div class="toc-inner">
{toc_links}
</div></nav>

<main>
<section id="overview">
  <div class="container">
    <div class="section-num">OVERVIEW</div>
    <h2>두 표면 모델</h2>
    <p class="lede">oh-my-wiki는 Andrej Karpathy의 "LLM Wiki" 워크플로를 구현합니다.
    모든 소스는 raw 스냅샷, 요약 페이지, 10–15개의 엔티티·개념 페이지 터치로 이어지고,
    쿼리는 구조화된 위키에서 출처를 인용해 답합니다. 인터페이스는 정확히 두 개입니다.</p>
    {overview_block}
  </div>
</section>

{sections_html}
</main>

<footer>
  <div class="container">
    oh-my-wiki — host-universal LLM 위키 · MIT License<br>
    모든 커맨드 블록과 출력은 v3 CLI 실행 결과(TUTORIAL.ko.md)에서 가져왔습니다.
    <div class="links">
      <a href="../../TUTORIAL.ko.md">TUTORIAL.ko.md</a>
      <a href="../../TUTORIAL.md">TUTORIAL.md (EN)</a>
      <a href="https://github.com/dandacompany/oh-my-wiki">github.com/dandacompany/oh-my-wiki</a>
      <a href="https://github.com/dandacompany/oh-my-wiki/issues">issues</a>
    </div>
  </div>
</footer>
</body>
</html>
"""


def main():
    OUT.write_text(HEAD + body(), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
