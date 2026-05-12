---
generated_by: harness-maker
harness_maker_version: 0.11.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: memory/session-readme.md.j2
provenance: official
---
# Session Logs — Production preset

> 이 디렉토리는 autoloop 세션 로그를 날짜별로 보관합니다.
> `flush_session` PreCompact hook 과 wrapup 스테이지가 자동 생성합니다.

## 파일 구조

```
.claude/memory/session/
└── YYYY-MM-DD.md    ← 하루 1파일. 여러 세션이 동일 날짜 파일에 누적.
```

## 항목 형식

```markdown
## [<category>:<slug>] <description> | HH:MM UTC | stage:<name>
<non-obvious 결정 또는 관찰 — 왜 이 방향인지, 어떤 제약이 있었는지>
```

**category 값:**
- `decision` — 아키텍처·설계 결정
- `blocker` — 진행 중단 이유 + 해결 방법
- `anomaly` — 이상하지만 진행한 것 (왜 진행했는지 기록)
- `checkpoint:compaction` — flush_session hook 이 자동 생성 (편집 금지)

## 로딩 정책

각 스테이지(research / execute / review) 시작 시:
1. **Hot tier** — 오늘 날짜 세션 로그 전문 로딩 (exists? read : skip)
2. **Warm tier** — `.claude/memory/failures.md` 첫 60줄 skim
3. **Warm tier** — `.claude/memory/wiki.md` 첫 60줄 skim

<!-- @hm:user:extensions -->
<!-- @hm:/user:extensions -->
