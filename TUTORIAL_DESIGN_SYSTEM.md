# Tutorial Design System

프로젝트의 정적 HTML 튜토리얼은 하나의 디자인 시스템을 공유한다. **레퍼런스 구현**은
`docs/tutorial-omw/build_tutorial_omw.py` (자체 완결형 빌드 스크립트)다. 새 튜토리얼 variant는
이 문서의 규칙을 따르고, 가능하면 레퍼런스 빌더의 `HEAD`·`render_*`를 `importlib`로 재사용한다.

## 1. 산출물 구조

```
docs/tutorial-<slug>/
├── build_tutorial_<slug>.py    # 선언형 SECTIONS + HEAD/CSS + render_*  (단일 진실원천)
├── tutorial-<slug>.html        # python3 build_tutorial_<slug>.py 산출물 (커밋)
├── assets/                     # (선택) 스크린샷
└── captures/                   # (선택) 재현 가능한 명령 캡처 *.txt
```

빌드: `cd docs/tutorial-<slug> && python3 build_tutorial_<slug>.py` → `Wrote …/tutorial-<slug>.html (N bytes)`.
빌드는 **멱등**이어야 한다(재빌드 후 git 트리 clean). 포매터가 HTML을 건드리면 빌더 출력을 정본으로 다시 커밋한다.

## 2. 컬러 팔레트 (CSS 변수)

```css
:root {
  --sand: #d4c4a8;
  --stone-100: #f5f3ee;
  --stone-200: #e8e3d9;
  --stone-400: #a89876;
  --stone-500: #8a7a58;
  --stone-700: #5a4e38;
  --stone-800: #3e3526;
  --stone-900: #1f1a10;
  --moss: #6b7d4f;
  --cream: #fafaf7;
}
```

- **sand / stone** — 본문·헤더·카드 배경·보더 (따뜻한 어스톤). 본문 텍스트 `--stone-800`, 페이지 배경 `--stone-100`.
- **moss** — 링크, callout 좌측 보더, 강조선 (차분한 초록). 링크 `color:var(--moss)` + 옅은 밑줄.
- **cream** — note/figure 배경의 옅은 톤.
- **다크 톤은 코드 블록 내부에서만** (`#13171b`→`#0e1114` 그라디언트 + 트래픽 라이트 점 3개).

## 3. 타이포그래피

```html
<link
  href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;700;900&family=Noto+Sans+KR:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap"
  rel="stylesheet"
/>
```

| 용도                       | 폰트               | 크기·굵기                                    |
| -------------------------- | ------------------ | -------------------------------------------- |
| h1 · hero                  | Noto Serif KR 900  | `clamp(34px, 5vw, 48px)`                     |
| h2 · 섹션 제목             | Noto Serif KR 700  | `clamp(22px, 3vw, 30px)`                     |
| 본문 (lede·p)              | Noto Sans KR 400   | 14.5–16px, line-height 1.7–1.85              |
| 메타 (`.section-num`·라벨) | JetBrains Mono 500 | 11.5–12px, UPPERCASE, letter-spacing 0.4–4px |
| 코드 본문                  | JetBrains Mono 400 | 13px, line-height 1.85                       |

JetBrains Mono 는 항상 **uppercase + letter-spacing** 과 함께 써 "라벨 톤"을 유지한다.

## 4. 섹션 리듬

```
section { padding: 68px 0; border-top: 1px solid var(--stone-200); }
  ├ .section-num   JetBrains Mono, letter-spacing 4px  (예: "STEP 03")
  ├ h2             Noto Serif KR
  ├ p.lede         핵심 1~2문장
  ├ [blocks]       code | design | note   (commands[] 순서대로)
  └ .callout       (선택) moss 좌측 보더 강조 박스
```

히어로: `badge + h1 + .meta-grid(핵심 사실 셀)`. 그 뒤 `#overview` 인트로 + 스텝 섹션들.

## 5. 블록 kind (3종)

`render_block(cmd)` 는 `cmd["kind"]`(기본 `"code"`)로 분기한다.

| kind          | 용도                                 | 스타일                                                              |
| ------------- | ------------------------------------ | ------------------------------------------------------------------- |
| `code` (기본) | 터미널 로그·복붙 명령·파일/JSON 출력 | 다크 터미널 카드 + 트래픽 라이트 점                                 |
| `design`      | 개념의 "설계 개요" (스텝당 0~1개)    | 🎯 goal + 📏 principles(번호 grid) + 🧱 components(아이콘 2열 grid) |
| `note`        | ★ 관찰·팁·체크리스트 (≤ 5–7줄)       | cream 메모 카드 + moss 좌측 보더                                    |

`design` 블록 필수 필드:

```python
{"label": "X. 설계 개요", "kind": "design", "design": {
    "goal": "<한 줄 선언>",
    "principles": ["원칙 1", "원칙 2", ...],          # 번호 grid
    "components": [("⌨️", "이름", "설명"), ...],       # 아이콘 2열 grid (병렬 구성요소)
}}
```

`components`(병렬 카드)와 `layers`(상하 적층) 는 **택일**. 이 프로젝트의 레퍼런스는 `components` 사용.

## 6. SECTIONS 스키마

빌드 스크립트의 핵심은 Python 선언 `SECTIONS: list[dict]`. 각 스텝:

```python
dict(
    num="03",
    title="페이지 규약(스키마)",
    lede="<strong>…</strong> 1~2문장.",
    commands=[
        {"label": "03-1. …", "text": "<복붙 명령/출력>"},               # code (기본)
        {"label": "03-2. 설계 개요", "kind": "design", "design": {...}},
        {"label": "03-3. …", "kind": "note", "text": "★ 관찰 …"},
        {"callout": "<강조 한 줄>"},                                     # .callout
    ],
)
```

- `text` 는 블록 본문(짧은 출력은 인라인 OK). 긴 재현 캡처는 `captures/*.txt` + `read_capture()`.
- 시나리오/스텝이 많으면 탭 UI(`.scenario-tabs`) + 우측 floating TOC(`>1320px`)를 둔다.

## 7. 독자 우선 작성 규칙 (필수 — 빌드 전 자가검증)

튜토리얼은 **독자가 그대로 따라 하는 실행 문서**다. 제작 기록·기획·해설이 아니다.

- **메타 금지**: "이 튜토리얼은 / 이 문서는 / 살펴보세요 / 영상에서는 / 아래에서는 / 제작 / 로드맵" 등 작성자 시점 표현 금지. 주어는 도구·독자 행동으로.
- **독자 행동 문체**: "실행합니다 / 확인합니다 / 복사합니다". lede 1~2문장, note ≤ 5–7줄, 스텝당 블록 3~5개.
- **결과 확인 포함**: 설치·설정 스텝은 "성공하면 보이는 것"(실제 출력)을 항상 함께.
- **복붙 가능**: 명령·코드·JSON은 그대로 실행 가능한 원문. 코드 안 텍스트는 풀어쓰지 않는다.
- **실측만**: 모든 명령 출력은 **라이브로 검증**한 값만 임베드. 지어내기 금지(검증이 실제 버그를 잡는다).

자가검증 sweep:

```bash
rg -n "이 튜토리얼은|이 문서는|살펴보세요|영상에서는|아래에서는|제작 과정|로드맵" docs/tutorial-*/build_tutorial_*.py   # → 0
rg -n "/Users/|/home/|tmp\.[A-Za-z0-9]{6}|Bearer [A-Za-z0-9]{20}" docs/tutorial-*/tutorial-*.html                       # → 0 (마스킹)
```

## 8. 마스킹

원본 캡처는 건드리지 않고 빌더의 `_MASK_PATTERNS`(시크릿)·경로 일반화(`OMW_HOME`→`~/.omw`)에서만 치환한다.
새 시크릿 패턴은 **빌더 + 이 문서 + (있다면) 공용 디자인 스냅샷** 모두에 추가한다.

## 9. 새 variant 만들기

```bash
SRC=docs/tutorial-omw/build_tutorial_omw.py
DST=docs/tutorial-<new>/build_tutorial_<new>.py
mkdir -p docs/tutorial-<new>
cp "$SRC" "$DST"      # BASE/OUT 경로 + SECTIONS 교체, HEAD title 수정
```

또는 `importlib` 로 레퍼런스 빌더의 `HEAD`·`esc`·`render_block`·`render_section` 를 재사용해
디자인 일관성을 자동 확보한다(레퍼런스 CSS 업데이트가 자동 반영; `render_*` 시그니처 변경 시 재검증).

## 완료 기준

- `python3 build_tutorial_<slug>.py` 에러 없이 HTML 생성 + 멱등(재빌드 후 git clean)
- 섹션 번호/제목 매칭, code/design/note 렌더 정상, 한국어 표시 정상
- sweep 0: 시크릿 · 개인 경로 · 메타 표현
- 모든 사용자-facing 문장이 독자 행동·결과 확인·문제 해결 중 하나에 속함
