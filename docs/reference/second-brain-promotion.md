# Second Brain 승급 파이프라인 (PLAN-second-brain-promotion)

> Relocated verbatim from `CLAUDE.md` on 2026-09-30 (SPEC-top-issues-2026-09). CLAUDE.md keeps a
> short summary and a link here; this file is the recorded *why*.

## Second Brain 승급 파이프라인 (PLAN-second-brain-promotion)

로컬 `.claude/memory/` 와 Obsidian Second Brain 은 **두 개의 평행 기억 시스템이 아니라 승급 파이프라인**이다:

- **로컬 `.claude/memory/`** = 프로젝트 작업 기억 (wiki/failures/session, 빠르고 풍부, 매 wrapup Step 5.1–5.5 에서 채워짐).
- **Obsidian Second Brain** = 큐레이션된 cross-project durable 지식. wrapup **Step 5.6** 이 자격 있는 로컬 엔트리만 `second_brain promote` 로 승급 (ADR-002).

핵심 계약:
- **Step 5.6 은 advisory 가 아니라 must-evaluate 번호 단계** (ADR-001, 이전 PLAN-second-brain-write-failure ADR-006 의 "Advisory" 결정을 supersede). 매 wrapup 마다 평가 필수 — 기록은 LLM 이 "cross-project durable?" 판정 통과한 것만 (ADR-003). count gate 없음 → synthetic note 없음.
- **`promote_note` / `second_brain promote` 가 안전 레일**: 결정적 파일명 `<type>-<slug>.md` + `project_id`/`hm_source` link-back + 멱등 (같은 `--source-slug` 재승급 = in-place 갱신, 중복 0). Python 이 경로·dedup·네임스페이스 소유, LLM 이 판단·본문 소유 (ADR-004).
- **vault 는 별도 git repo** — 승급 노트는 wrapup 커밋에 포함되지 않음 (vault 자체 sync 가 담당).
- **알려진 한계 (ADR-005)**: 승급은 `/hm:wrapup` 에서만 발동한다. 수동/quick 커밋 위주 워크플로우는 승급이 안 일어난다 — vault 는 wrapup 을 도는 만큼만 채워진다. hook/별도 명령은 의도적으로 안 만듦. Step 5.6 의 `promotion evaluated: N candidates, M promoted` receipt (ADR-006) 가 under-promotion 을 가시화한다.
