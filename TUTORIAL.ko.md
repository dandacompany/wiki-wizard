# oh-my-wiki 사용 튜토리얼

Claude Code 나 Codex CLI 에서 oh-my-wiki 를 어떻게 사용하는지 실전 예제로 보여드립니다.
모든 대화는 실제 동작을 그대로 옮긴 것이고, 한국어 트리거와 영어 트리거 모두 사용할 수 있습니다.

> **표기 규약**
>
> - `> 사용자:` 는 당신이 채팅창에 입력하는 텍스트입니다.
> - `< Claude:` 는 oh-my-wiki 가 실행되어 돌려주는 응답입니다.
> - `$` 로 시작하는 줄은 내부적으로 실행되는 Python 호출입니다. 참고용이며 직접 칠 필요는 없습니다.

---

## 0. 설치 확인

새 컴퓨터에서는 한 줄 설치를 권장합니다.

```bash
git clone https://github.com/dandacompany/oh-my-wiki
cd oh-my-wiki
bash bin/install.sh --dev
```

이 스크립트가 Python 의존성, 두 개의 스킬 symlink (`oh-my-wiki` 와 `omw`), pytest 검증까지 모두 처리합니다.
플래그와 수동 설치 경로는 [README](./README.md) 를 참고하세요.
설치가 끝나면 새 Claude Code 세션 어디서든 트리거를 사용할 수 있습니다.
헬스 체크는 이렇게 해보세요.

```
> 사용자: 위키 상태 확인해줘

< Claude: [oh-my-wiki 디스패처 실행]
$ python3 -m scripts.wizard status

{
  "vault_count": 0,
  "active": null,
  "needs": "setup",
  "vaults": []
}

등록된 vault가 없습니다. 새 vault를 만들까요?
1. memo 모드 (가볍게 메모 캡처)
2. wiki 모드 (Karpathy 스타일 지식 위키)
3. 기존 /memo 폴더 가져오기
4. 취소
```

설치 직후라면 `needs: setup` 이 반환됩니다.
사용할 수 있는 트리거 문구는 다음과 같습니다.

- 영어: "open my wiki", "set up a new vault", "ingest this", "what does my wiki say about X", "omw", "use omw", "/omw"
- 한국어: "위키 열어줘", "새 vault 만들어줘", "이거 정리해줘", "위키에 물어봐", "오엠더블유", "오엠더블유 켜줘"

**단축 별칭**: `omw` (또는 `/omw`) 만 입력해도 `oh-my-wiki` 와 똑같이 동작합니다.
`omw` 스킬은 표준 디스패처로 즉시 위임하는 얇은 별칭 스킬입니다.

---

## 시나리오 1: memo vault 첫 설정과 첫 메모 작성

가장 간단한 흐름입니다.
일상 메모를 빠르게 캡처할 때 씁니다.

### 1.1 vault 생성

```
> 사용자: 새 memo vault 만들어줘. 이름은 daily, 경로는 ~/notes/daily

< Claude: vault-setup 명령어 실행하겠습니다.

  - 이름: daily
  - 경로: /Users/you/notes/daily
  - 모드: memo
  - 타입: markdown (Obsidian 사용 안 함)

진행할까요? [Yes / No]

> 사용자: yes

< Claude:
$ adapters.get_adapter('markdown').init_vault(/Users/you/notes/daily, 'memo')
$ registry.add_vault(name='daily', ...)
$ registry.set_active('daily')
$ reindex.full(vault_id=1) → 0 notes

✅ vault 'daily' 등록 완료. 활성 vault로 설정됨.
   생성된 폴더 구조:
   ~/notes/daily/
   ├── inbox/
   └── .trash/
```

### 1.2 paste 로 첫 메모 캡처 (긴 텍스트)

가장 자주 쓰는 패턴입니다.
어떤 글이든 통째로 paste 하면 oh-my-wiki 가 제목과 태그, 폴더를 자동으로 제안합니다.

```
> 사용자: 다음 내용 저장해줘

Karpathy는 LLM Wiki를 "compounding knowledge artifact"라고 부른다.
모든 출처는 raw/에 원본 그대로 저장하고, wiki/summaries/에 요약을
쓴 다음, 등장한 인물·개념을 별도 페이지로 분리한다. 한 번 ingest할
때마다 10-15개 페이지가 함께 갱신되는 게 정상이다. 메모는 썩지만
구조화된 위키는 시간이 갈수록 가치가 누적된다.

< Claude: 긴 텍스트 paste 감지 (368자) — memo-mode hybrid create로 진행.
LLM이 본문에서 메타데이터 제안:

  - title: "Karpathy LLM Wiki — compounding knowledge"
  - slug: karpathy-llm-wiki-compounding-knowledge (자동 생성)
  - folder: inbox/
  - tags: [karpathy, llm, wiki, knowledge-management]
  - type: note
  - date: 2026-05-25

이대로 저장할까요?
1. Accept (그대로 저장)
2. Edit (필드 수정)
3. Cancel

> 사용자: 1

< Claude:
$ memo_ops.write(vault_id=1, title='Karpathy LLM Wiki — compounding knowledge',
                 body='Karpathy는 LLM Wiki를...', folder='inbox',
                 tags=['karpathy','llm','wiki','knowledge-management'],
                 type_='note', date_str='2026-05-25')

✅ 저장 완료:
   inbox/karpathy-llm-wiki-compounding-knowledge.md
```

### 1.3 prompt 방식 (짧은 메모)

paste 한 본문이 200 자보다 짧으면 자동으로 prompt 모드로 전환됩니다.

```
> 사용자: 메모 하나 만들어줘

< Claude: 짧은 입력 — prompt 모드.

제목을 알려주세요:

> 사용자: 슬랙 정리 시간 30분 줄이기

< Claude: 폴더는? (기본: inbox/)
1. inbox/
2. 다른 폴더 입력

> 사용자: 1

< Claude: 본문을 입력하세요 (멀티라인 가능, 빈 줄로 종료):

> 사용자: 메일/슬랙 통합 트리지 시간 30분 단축이 목표. 알림 끄기, 시간 블록 지정, 답장 batch.

< Claude: 제안 태그: [productivity, slack, workflow]
저장할까요?

> 사용자: ok

✅ inbox/slack-jeongri-sigan-30bun-jul-igi.md
```

> **참고**: 한글 제목은 slugify 가 한글 음절을 그대로 보존합니다 (`가-힣` 허용).
> 영문 슬러그를 쓰고 싶다면 제목을 영문으로 입력하거나, `edit` 으로 slug 만 따로 바꾸세요.

### 1.4 메모 검색

```
> 사용자: karpathy 관련 메모 찾아줘

< Claude:
$ search.query(vault_id=1, query='karpathy', limit=5)

검색 결과 (상위 1개):

# | score | relpath                                                 | title
1 | 8.5   | inbox/karpathy-llm-wiki-compounding-knowledge.md        | Karpathy LLM Wiki — compounding knowledge

어떻게 할까요?
1. 1번 열기 (open)
2. 다른 키워드로 다시 검색
3. 종료

> 사용자: 1

< Claude:
$ adapters.get_adapter('markdown').open(~/notes/daily/inbox/karpathy-llm-wiki-compounding-knowledge.md)
→ macOS의 기본 .md 핸들러로 열림 (VS Code, Obsidian 등 설정에 따라)

✅ 열었습니다.
```

### 1.5 메모 수정 (frontmatter 1필드)

```
> 사용자: 방금 그 메모에 "deep-work" 태그 추가해줘

< Claude: 검색으로 메모 위치 확인했습니다:
   inbox/karpathy-llm-wiki-compounding-knowledge.md

현재 tags: [karpathy, llm, wiki, knowledge-management]
새 tags: [karpathy, llm, wiki, knowledge-management, deep-work]

> 사용자: yes

< Claude:
$ memo_ops.edit_meta(vault_id=1,
                     relpath='inbox/karpathy-llm-wiki-compounding-knowledge.md',
                     key='tags',
                     value=['karpathy','llm','wiki','knowledge-management','deep-work'])

✅ tags 필드 갱신 완료.
```

### 1.6 메모 정리 (move + delete)

```
> 사용자: 슬랙 메모를 archive 폴더로 옮겨

< Claude:
$ search.query(query='슬랙') → 1 hit
$ memo_ops.move(relpath='inbox/slack-...md', dest_folder='archive')

archive/ 폴더가 없어서 자동 생성했습니다.
✅ 이동: inbox/slack-...md → archive/slack-...md

> 사용자: karpathy 메모는 삭제해줘

< Claude: 메모 위치 확인:
   inbox/karpathy-llm-wiki-compounding-knowledge.md

soft delete (.trash/로 이동, 복구 가능) 또는 hard delete (영구 삭제)?

> 사용자: soft

< Claude:
$ memo_ops.delete(relpath='...', hard=False)

✅ 이동: .trash/20260525-145012-345678-karpathy-llm-wiki-compounding-knowledge.md
   복구하려면 파일을 inbox/로 다시 옮기세요.
```

---

## 시나리오 2: wiki vault 에서 ingest 와 query (Karpathy 흐름)

oh-my-wiki 의 핵심 사용 사례입니다.
출처 한 건을 받으면 먼저 raw 폴더에 원본을 저장하고, 그 다음에 요약 페이지를 만듭니다.
이어서 본문에 등장한 엔티티와 개념을 별도 페이지로 분리하고, 마지막으로 인덱스를 갱신합니다.

### 2.1 wiki vault 생성

```
> 사용자: research라는 wiki vault 만들어줘. ~/notes/research, obsidian 사용

< Claude:
$ adapters.get_adapter('obsidian', vault_name='research').init_vault(...)
$ registry.add_vault(name='research', type_='obsidian', mode='wiki')
$ registry.set_active('research')
$ reindex.full → 2 notes (index.md + log.md 자동 생성)

✅ wiki vault 'research' 등록.
   ~/notes/research/
   ├── raw/                  (원본 출처)
   ├── wiki/
   │   ├── summaries/        (요약)
   │   ├── entities/         (인물·조직·논문)
   │   ├── concepts/         (아이디어·기법)
   │   ├── comparisons/      (비교)
   │   ├── syntheses/        (질의 후 자동 생성)
   │   ├── index.md          (자동 목차)
   │   └── log.md            (운영 로그)
   └── .trash/
```

### 2.2 paste 로 ingest (텍스트 출처)

```
> 사용자: 이거 정리해줘

Andrej Karpathy의 LLM Wiki Gist 핵심: 메모는 단방향 흐름이지만
위키는 양방향 그래프다. raw/는 원본 보존, wiki/는 가공된 페이지.
각 ingest는 평균 10-15개 페이지를 갱신해야 정상이다. 두 가지 메타
파일 — index.md(목차)와 log.md(운영 로그) — 가 위키의 메타데이터다.

< Claude: ingest 시작. wiki-mode 확인됨 (active: research).

[1/7] raw 저장
$ ingest.save_raw(content='...', ext='md', title='Karpathy LLM Wiki Gist 핵심',
                  date_str='2026-05-25')
→ raw/2026-05-25-karpathy-llm-wiki-gist-haegsim.md

[2/7] 본문 분석 — 다음 페이지들을 제안합니다:

  Summary:
    - karpathy-llm-wiki-gist (one-paragraph 요약)

  Entities:
    - andrej-karpathy (이미 존재하면 patch, 없으면 신규)

  Concepts:
    - compounding-knowledge (지식 누적)
    - raw-wiki-separation (raw/wiki 분리 원칙)
    - bidirectional-graph (양방향 그래프)
    - meta-files (index/log)

확인하면 진행 (yes/edit/cancel):

> 사용자: yes

< Claude:
[3/7] 요약 페이지 작성
$ ingest.write_wiki_page(layer='summaries', title='Karpathy LLM Wiki Gist', ...)
→ wiki/summaries/karpathy-llm-wiki-gist.md

[4/7] 엔티티/개념 페이지 작성
$ ingest.write_wiki_page(layer='entities', title='Andrej Karpathy', ...)
$ ingest.write_wiki_page(layer='concepts', title='Compounding Knowledge', ...)
$ ingest.write_wiki_page(layer='concepts', title='Raw Wiki Separation', ...)
$ ingest.write_wiki_page(layer='concepts', title='Bidirectional Graph', ...)
$ ingest.write_wiki_page(layer='concepts', title='Meta Files', ...)

[5/7] 인덱스 갱신
$ ingest.update_index(entries=[
    ('summaries', 'karpathy-llm-wiki-gist', 'Karpathy LLM Wiki Gist 핵심'),
    ('entities', 'andrej-karpathy', 'AI researcher and educator'),
    ('concepts', 'compounding-knowledge', '지식 누적 모델'),
    ...
  ])

[6/7] 로그 추가
$ ingest.append_log(op='ingest', title='Karpathy LLM Wiki Gist 핵심')
→ wiki/log.md에 "## [2026-05-25] ingest | Karpathy LLM Wiki Gist 핵심" 추가

[7/7] reindex
$ reindex.incremental(vault_id=1) → 6 new notes indexed

✅ Ingest 완료. 6개 페이지 갱신.
   raw: raw/2026-05-25-karpathy-llm-wiki-gist-haegsim.md
   summary: wiki/summaries/karpathy-llm-wiki-gist.md
   entities: 1 (andrej-karpathy)
   concepts: 4 (compounding-knowledge, raw-wiki-separation, bidirectional-graph, meta-files)
```

### 2.3 PDF ingest

```
> 사용자: ~/Downloads/attention-is-all-you-need.pdf 정리해줘

< Claude: PDF 파일 감지. pypdf로 텍스트 추출 + 원본 보존.

$ pdf_bytes = open('~/Downloads/attention-is-all-you-need.pdf', 'rb').read()
$ ingest.save_raw_pdf(pdf_bytes=..., title='Attention Is All You Need',
                      date_str='2026-05-25')
→ raw/2026-05-25-attention-is-all-you-need.pdf  (원본 바이트 그대로)
→ 추출된 텍스트: 8721자

[2/7] 본문 분석 — 제안:

  Summary:
    - attention-is-all-you-need (transformer 핵심)

  Entities:
    - vaswani-et-al (저자)
    - google-brain (소속)

  Concepts:
    - self-attention
    - multi-head-attention
    - positional-encoding
    - transformer-architecture

확인 (yes/edit/cancel):

> 사용자: yes

[3/7~7/7] ... (동일 흐름)

✅ Ingest 완료. 8개 페이지 갱신.
```

> **PDF 주의**: 스캔된 이미지 PDF 는 텍스트 추출이 비어 있을 수 있습니다.
> 이 경우 본문을 직접 paste 해서 ingest 하세요.
> OCR 은 Plan C 범위 밖입니다.

### 2.4 query 로 위키에 묻기

```
> 사용자: attention 매커니즘이 왜 RNN보다 빠른지 위키에 물어봐

< Claude:
$ search.query(vault_id=1, query='attention RNN', limit=5)

검색 결과 (상위 3개):
1. wiki/summaries/attention-is-all-you-need.md      (score 7.5)
2. wiki/concepts/self-attention.md                  (score 5.0)
3. wiki/concepts/transformer-architecture.md        (score 3.5)

[페이지들을 읽고 답변 합성 중...]

답변:
─────────────────────────────────────
Attention은 RNN의 시퀀셜 의존성을 끊고 병렬화가 가능하기 때문에 빠릅니다.
RNN은 hidden state h_t가 h_{t-1}에 의존하므로 시퀀스를 한 토큰씩 순차
처리해야 하지만, self-attention은 모든 토큰 쌍 간의 관계를 동시에
계산합니다 [summaries/attention-is-all-you-need](wiki/summaries/attention-is-all-you-need.md).

특히 multi-head attention은 행렬곱 한 번으로 모든 토큰의
context vector를 계산하므로 GPU에서 매우 효율적입니다
[concepts/self-attention](wiki/concepts/self-attention.md).

다만 시퀀스 길이 N에 대해 O(N²) 메모리가 필요한 trade-off가 있어,
긴 문서에는 별도 기법(sparse attention 등)이 필요합니다.
─────────────────────────────────────

이 답변을 wiki/syntheses/에 저장할까요? (새 페이지로 file-back) [Yes / No]

> 사용자: yes

< Claude:
$ query.write_synthesis(title='왜 Attention이 RNN보다 빠른가',
                        body='Attention은 RNN의 시퀀셜 의존성을...',
                        citations=['wiki/summaries/attention-is-all-you-need.md',
                                   'wiki/concepts/self-attention.md'],
                        tags=['attention','rnn','transformer'])
→ wiki/syntheses/wae-attention-i-rnn-boda-bareungga.md

$ ingest.update_index(entries=[('syntheses', '...', '왜 Attention이 RNN보다 빠른가')])
$ ingest.append_log(op='synthesis', title='왜 Attention이 RNN보다 빠른가')
$ reindex.incremental

✅ Synthesis 페이지 저장됨. 이제 위키에 답변이 포함되었습니다.
   다음 검색에서 이 페이지가 출처로 나옵니다.
```

바로 이 흐름이 Karpathy 가 말한 "loop closes" 입니다.
질문이 새 페이지가 되어 위키에 누적되는 거죠.

---

## 시나리오 3: 기존 /memo 폴더 가져오기

이미 Obsidian 이나 일반 markdown 으로 메모를 쌓아둔 경우에 사용합니다.

```
> 사용자: vault-import-memo 실행해줘. 경로는 ~/Documents/old-notes

< Claude:
[1단계] 경로 확인
✅ ~/Documents/old-notes 존재 확인.

[2단계] memo-mode vault로 등록
$ registry.add_vault(name='legacy', path='/Volumes/...', type_='markdown', mode='memo')
$ reindex.full → 247 notes indexed

✅ 'legacy'라는 이름으로 등록됨.

[3단계] frontmatter 정규화 제안 (dry-run)

$ import_memo.dry_run(vault_id=2)

  요약:
    총 파일: 247
    변경 필요: 89
    이미 정상: 158

  변경 필요 파일 예시 (처음 10개):
    - 2025-08-meeting-notes.md           (changes: 2)  ← missing type, missing tags
    - article-clip.md                    (changes: 1)  ← tags string→list
    - random-thought.md                  (changes: 3)  ← missing date/type/tags
    ...

마이그레이션을 적용할까요?
89개 파일이 in-place 수정되고, 원본은 .trash/<ts>-pre-import-*.md로
백업됩니다. 진행하려면 'apply'를 정확히 입력하세요:

> 사용자: apply

< Claude:
$ import_memo.apply(vault_id=2, plan=...)

  적용: 89 파일
  스킵: 0 (malformed YAML 없음)
  백업 timestamp: 20260525-150823-456789

✅ 마이그레이션 완료. 모든 파일이 oh-my-wiki frontmatter 규약
   (title/date/type/tags 필수)을 따릅니다. 문제 발생 시
   .trash/20260525-150823-456789-pre-import-*.md에서 복구 가능.
```

---

## 시나리오 4: 정기 헬스 체크 (lint)

vault 의 무결성을 점검합니다.
활성 vault 가 memo-mode 인지 wiki-mode 인지에 따라 자동으로 분기합니다.

### 4.1 memo vault lint

```
> 사용자: daily vault lint해줘

< Claude: 'daily'는 memo-mode → 공통 체크만 수행.

$ lint.check(vault_id=1)

📋 공통 점검
─────────────────────────────────────

✅ Frontmatter 이슈: 없음 (모두 정상)

⚠️  Drift — missing files (1)
   - inbox/old-note.md (registry에는 있으나 디스크에 없음)

✅ Drift — mtime mismatch: 없음

자동 수정 힌트:
  - 누락 파일: orphan 행을 삭제하거나 파일을 복구하세요.
    수동: registry.delete_note(vault_id=1, relpath='inbox/old-note.md')

> 사용자: orphan 행 삭제해줘

< Claude:
$ registry.delete_note(vault_id=1, relpath='inbox/old-note.md')
✅ 정리됨.
```

### 4.2 wiki vault lint

```
> 사용자: research vault 점검

< Claude: 'research'는 wiki-mode → 공통 + 구조적 체크.

$ lint.check(vault_id=2)
$ wiki_lint.check(vault_id=2)

📋 공통 점검
─────────────────────────────────────
✅ Frontmatter 이슈: 없음
✅ Drift: 없음

📋 wiki 구조 점검
─────────────────────────────────────

⚠️  Orphan pages (2) — 7일 grace 지나고 inbound 링크 없음
   - wiki/concepts/early-stopping.md (age: 14일)
   - wiki/entities/lecun.md (age: 23일)

⚠️  Missing concepts (3) — N≥2개 페이지에서 참조되나 페이지 없음
   - transformer-decoder (referenced by: summaries/attention-is-all-you-need.md,
                                          summaries/gpt-paper.md)
   - layer-normalization (referenced by 4 pages)
   - residual-connection (referenced by 3 pages)

⚠️  Empty data (1)
   - wiki/concepts/dropout.md (reason: body<50chars — "TBD")

✅ Dangling links: 없음

다음 작업 추천:
  - missing concepts 3개를 ingest하거나 페이지 작성
  - dropout.md 본문 채우기
  - orphan 검토 (의도적이면 다른 페이지에서 [[link]] 추가, 아니면 archive)
```

---

## 시나리오 5: 다중 vault 전환

여러 vault 를 함께 운영할 때 쓰는 흐름입니다.

```
> 사용자: vault 목록 보여줘

< Claude:
$ registry.list_vaults() + per-vault note counts

* daily          memo  markdown      12 notes  /Users/you/notes/daily
  research       wiki  obsidian      47 notes  /Users/you/notes/research
  legacy         memo  markdown     247 notes  ~/Documents/old-notes

(* = active)

> 사용자: research로 전환

< Claude:
$ registry.set_active('research')
✅ Active vault: research (wiki, obsidian) at /Users/you/notes/research

> 사용자: legacy vault 등록 제거해줘. 파일은 그대로 두고.

< Claude: 'legacy'를 registry에서 제거합니다.
파일 (247개)은 ~/Documents/old-notes에 그대로 보존됩니다.

확인하려면 vault 이름을 정확히 입력하세요:

> 사용자: legacy

< Claude:
$ registry.forget_vault('legacy')
✅ Registry에서 'legacy' 제거. 파일은 보존됨.
```

---

## 자주 겪는 상황과 대처

### Q. oh-my-wiki 가 자동으로 트리거되지 않을 때

명시적으로 호출하면 됩니다.

```
> 사용자: oh-my-wiki 실행해줘
```

또는 SKILL.md frontmatter 에 정의된 트리거 문구를 직접 쓰세요.

- "open my wiki" 또는 "위키 열어줘"
- "ingest this" 또는 "이거 정리해줘"
- "find a note about X" 또는 "X 관련 노트 찾아줘"

### Q. 활성 vault가 잘못 됐을 때

```
> 사용자: 지금 활성 vault 뭐야?

< Claude:
$ wizard.status
active: { name: 'legacy', mode: 'memo', ... }

> 사용자: research로 바꿔줘

< Claude:
$ registry.set_active('research')
```

### Q. 마이그레이션 후 변경을 되돌리고 싶을 때

`vault-import-memo apply`는 항상 `.trash/<ts>-pre-import-*.md`에 원본을 백업합니다.

```bash
# 수동 복구 (1개 파일)
cp ~/notes/legacy/.trash/20260525-150823-456789-pre-import-2025-08-meeting-notes.md \
   ~/notes/legacy/2025-08-meeting-notes.md
```

전체 되돌리기는 같은 timestamp를 가진 백업 파일들을 한꺼번에 복원하면 됩니다.

### Q. 한국어 PDF 의 텍스트 추출이 깨질 때

pypdf 는 일부 한글 인코딩 처리가 약합니다.
우회 방법은 두 가지입니다.

1. macOS 미리보기에서 PDF 를 열고 텍스트를 복사한 다음, 직접 paste 해서 ingest 하세요.
2. OCR 이 필요한 스캔 PDF 는 `paddleocr` 스킬을 따로 불러 텍스트를 뽑은 뒤 paste 하세요.

### Q. Obsidian 이 켜져 있지 않아 open 이 실패할 때

`obsidian://open?vault=...&file=...` URI 가 macOS 에서 거부됩니다.
해결 방법은 두 가지입니다.

1. Obsidian 앱을 먼저 실행한 다음 다시 open 하세요.
2. vault 를 markdown 타입으로 등록해서 OS 기본 핸들러 (`open` 이나 `xdg-open`) 로 열게 하세요.

```
> 사용자: vault-setup name=temp path=... mode=memo type=markdown
```

### Q. 세션 사이의 컨텍스트는 어떻게 유지되나요? (v2.0)

세션이 끝날 때 활성 vault 옆에 작은 `hot.md` 캐시 파일을 씁니다.
다음 세션 시작 시 이 파일을 읽어 와서 다시 설명할 필요가 없게 됩니다.

- wiki-mode vault: `<vault>/wiki/hot.md`
- memo-mode 와 기타 mode: `<vault>/hot.md`

캡은 2000자입니다.
캡 초과 시 요약 부분이 먼저 잘립니다.
강제 갱신은 `python3 -m scripts.hot_cache --refresh` 명령으로 가능합니다.
조회는 `python3 -m scripts.hot_cache --on-session-start` 명령입니다.

### Q. 어떤 vault mode가 있나요? (v2.0)

`vault-setup` 은 `memo`, `wiki` (또는 `research`), `personal`, `book`, `business`, `github-codebase`, `website` 를 받습니다.
각각 다른 폴더 구조를 만듭니다.
자세한 레이아웃은 README 의 "Vault modes (v2.0)" 섹션에 있습니다.

### Q. autoresearch 는 어떻게 동작하나요? (v2.1)

`autoresearch <질문>` 을 입력하면 기본 3 라운드 (설정 가능, 최대 5) 의 흐름이 돕니다.

1. 질문을 여러 개의 atomic claim 으로 쪼갭니다.
2. claim 마다 Bright Data MCP 로 웹 검색을 합니다.
3. 출처 품질에 따라 high / medium / low confidence 태그를 답니다.
4. 다음 라운드가 필요한 gap 을 식별합니다.

남은 gap 이 없거나 라운드 예산을 모두 쓰면 종합 답변 (synthesis) 초안을 작성한 다음, 저장 여부를 물어봅니다.
승인 시 `wiki/syntheses/<slug>.md` 로 저장됩니다.
세션 전체 (라운드별 claim · 출처 · gap) 는 `<vault>/.oh-my-wiki/sessions/<ts>-<slug>/` 아래에 audit + replay 용으로 보존됩니다.

과거 세션 조회: `python3 -m scripts.autoresearch status --session-dir <DIR>`.

수동으로 답을 작성해서 저장만 하고 싶다면 기존 `query` op 가 그대로 동작합니다.
`autoresearch` 는 순수 추가 기능입니다.

### Q. writing persona 는 무엇인가요? (v2.2a)

글쓰기 작업을 위한 재사용 가능한 에이전트 페르소나 4종입니다.

- **translator** (`persona-translate`) — 구조를 보존하면서 다국어로 번역합니다. 결과는 원본 옆에 `<base>.<lang>.md` 형식으로 저장됩니다.
- **polisher** (`persona-polish`) — 어색한 문장을 다듬습니다. `--lang ko` 는 korean-prose-polish 패턴을 적용합니다 (em-dash 제거, 문장 끝 콜론 제거 등). 원본을 덮어쓰며, 이전 버전은 `.trash/` 에 백업됩니다.
- **summarizer** (`persona-summarize`) — 1줄 / 1문단 / 상세 3단 요약을 JSON 으로 반환합니다. 표준출력 전용입니다.
- **scaffolder** (`persona-scaffold`) — 새 wiki 페이지의 outline + 섹션 자리표시자를 생성합니다 (`status: draft`, `wiki/syntheses/<slug>.md` 에 저장).

각 페르소나는 `personas/<role>.md` 파일이며 YAML frontmatter 로 입출력 contract 를 선언합니다.
설치된 페르소나 목록 조회: `python3 -m scripts.personas list`
특정 페르소나의 전체 프롬프트 확인: `python3 -m scripts.personas show <name>`

### Q. 초안을 마무리하는 중인데, 발행 전에 사실 확인을 하고 싶어요.

**"이 초안 팩트체크해줘"** 또는 **"fact-check this"** 라고 요청해 보세요.
fact-checker 페르소나가 초안을 원자 단위 주장으로 쪼개고, 주장마다
웹 검색을 돌려서 검증한 다음, `<원본>.factcheck.md` 파일로 옆에 리포트를
남깁니다.
리포트에는 주장 표(근거 있음 / 반박됨 / 부분 일치 / 검증 불가) 와 출처 URL 이
들어 있습니다.

검색 예산은 주장당 약 3회입니다.
주장이 50개 넘는 큰 초안은 "foo.md 의 API 섹션만 팩트체크해줘" 처럼 범위를
좁히는 게 좋습니다.

### Q. 위키 안에서 페이지끼리 서로 어긋나는 부분을 찾고 싶어요.

**"위키에서 모순 있는지 봐줘"** 라고 요청하세요.
consistency-checker 가 먼저 `wiki_lint` 로 후보 쌍 (예: "X 이다" vs "X 가 아니다")
을 모은 다음, 각 쌍을 `confirmed` (진짜 모순) / `nuanced` (관점·시점이
달라 둘 다 가능) / `false_positive` (오탐) 로 판정합니다.
JSON 형태로 stdout 에 출력합니다.

특정 문서만 보고 싶을 때는 **"이 페이지 안에 모순 있어?"** 라고 물어보세요.

### Q. 같은 개념을 "LLM" 과 "Large Language Model" 로 섞어 써서 정리가 안 돼요.

**"내 위키 용어집 만들어줘"** 라고 요청하세요.
terminology-manager 가 `wiki/` 페이지를 훑어서 표준 형태 (canonical) 와
별칭 (aliases) 을 정리하고, `<vault>/.oh-my-wiki/glossary.db` 에 영구
저장합니다.
별칭에 들어 있지 않은 표기는 inconsistency 로 보고합니다.

저장된 용어집은 언제든 아래 명령으로 살펴볼 수 있습니다.

```bash
python3 -m scripts.glossary list --vault-root <vault> --vault-id 1
```

### Q. v2.0 에서 lint 는 어떤 검사를 새로 합니까?

wiki-mode vault 에서 4가지 구조적 candidate 카테고리가 추가됐습니다.

- **양방향 링크 갭** — A 가 B 를 참조하지만 B 는 A 를 참조하지 않고, 둘 다 같은 `entities/` 나 `concepts/` 안에 있을 때. 결정적 판단.
- **용어 표류 candidate** — 유사도 0.85 이상인 두 slug 가 같은 출처 페이지에서 함께 언급될 때 (예: `andrej-karpathy` 와 `karpathy-andrej`). 결정적 판단.
- **모순 candidate** — 같은 wikilink 대상을 공유하면서 반대 의미 동사를 가진 두 페이지. LLM 이 `confirmed` / `nuanced` / `false_positive` 로 최종 판정합니다.
- **stale claim candidate** — 180일 이상 된 페이지에 `currently`, `as of`, `the latest` 같은 시간 민감 표현이 들어 있을 때. LLM 이 `likely_stale` / `still_valid` / `false_positive` 로 판정합니다.

---

## Codex CLI 에서 사용하기

Claude Code 와 동일합니다.
Codex 가 oh-my-wiki 스킬을 발견하면 같은 트리거로 호출됩니다.
차이가 없는 이유는 SKILL.md frontmatter 의 트리거 문구가 특정 LLM 에 묶이지 않기 때문입니다.

```
$ codex
> 위키 상태 확인해줘
[Codex 가 oh-my-wiki 를 호출하고 동일한 흐름을 진행]
```

다만 Codex 는 Claude Code 보다 자동 트리거가 보수적입니다.
모호한 상황이라면 이렇게 명시적으로 호출하세요.

```
> Use the oh-my-wiki skill to ingest this article: ...
```

---

## 더 알아보기

- **명령어 레퍼런스**: `commands/*.md` (vault-setup, ingest, query, lint 등 12 개)
- **스크립트 API**: `scripts/*.py` (Python 에서 직접 호출 가능. 일부는 CLI 로도 노출됨)
- **설계 문서**: `docs/superpowers/specs/` (로컬에만 두고 GitHub 에는 공개하지 않습니다. 기여자용)
- **테스트**: `pytest -v` (총 91 개 테스트로 모든 동작을 검증합니다)

문제 신고는 https://github.com/dandacompany/oh-my-wiki/issues 에서 받습니다.
