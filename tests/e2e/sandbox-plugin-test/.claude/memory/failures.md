---
generated_by: harness-maker
harness_maker_version: 0.5.6
generated_at: '2026-01-01T00:00:00+00:00'
source_template: memory/failures.ko.md.j2
provenance: official
---
# Failures Log — Production preset

> 이 프로젝트에서 반복된 실수 / 함정을 기록합니다. wrapup 스테이지가 자동 추가합니다.
>
> **검색:** `rg -F "[fail:" .claude/memory/failures.md`
>
> **형식:**
> ```
> ## [fail:<category>] <slug> | <YYYY-MM-DD> | count:<N>
> <재현 조건 + 원인 + 해결책 한 단락>
> ```
> - `category`: import / test / render / hook / lint / type / runtime / design / other
> - `count`: 동일 실수 반복 시 헤딩만 업데이트 (중복 섹션 금지)
> - count ≥ 3 이면 wrapup 이 `.claude/memory/pending-proposals.md` 에 개선 제안 추가

---

(아직 기록된 실패 없음)
