---
generated_by: harness-maker
harness_maker_version: 0.52.3
generated_at: '2026-01-01T00:00:00+00:00'
source_template: memory/session-readme.md.j2
provenance: official
---
# Session Logs — Production preset

> 이 디렉토리는 **compaction 체크포인트만** 날짜별로 보관합니다.
> `flush_session` PreCompact hook 이 컨텍스트 압축 시 자동 생성합니다 (편집 금지).

## 파일 구조

```
.claude/memory/session/
└── YYYY-MM-DD.md    ← 하루 1파일. 여러 세션이 동일 날짜 파일에 누적.
```

## 항목 형식

```markdown
## [checkpoint:compaction] <label> | HH:MM UTC | stage:<name>
Context compaction fired. Progress snapshotted to `<checkpoint-ref>`.
```

**category 값:**
- `checkpoint:compaction` — flush_session hook 이 컨텍스트 압축 시 자동 생성 (편집 금지).
  중단된 세션을 mid-stage 에서 재개하기 위한 신호.

> 결정·설계 노트는 이 티어가 아니라 `wiki.md` / `failures.md` (retrieval-indexed) 와
> PLAN ADR 에 기록됩니다 — 세션 티어는 더 이상 decision 저널이 아닙니다.

## 로딩 정책

`/hm:execute` 시작 시에만 로딩:
1. **Hot tier (checkpoint only)** — 오늘 날짜 세션 로그에서 `checkpoint:compaction`
   엔트리만 확인 (interrupted-session 재개용). legacy `[decision:*]` 블록은 무시.

<!-- @hm:user:extensions -->
<!-- @hm:/user:extensions -->
