# Autoloop Pattern Reference

> 본 문서는 vault `/autoloop` 명령 (`/mnt/c/Users/euncheol.ro/Documents/obsidian-vault/.claude/commands/autoloop.md`) 에서 발췌·정리한 핵심 패턴.
> Phase 6 의 `/hm:loop` (사용자 하네스용 autoloop) 구현 시 참고. cross-filesystem 의존 제거 + 자족적 reference.

## Per-Phase 5-Stage Pipeline

각 phase 는 다음 5 stage 를 순차 진행:

```
Phase N
  Stage 1: Research Detection (URL/marker/unknown-lib 자동 감지)
  Stage 2: Plan Validation (3x parallel, 2/3 consensus, max 2 rounds)
  Stage 3: Execute (CODER → TESTER 루프, max N retries with error context)
  Stage 4: Review (5-8 reviewers, 2/3 consensus, auto-fix P0-P2)
  Stage 5: Wrapup (git commit "autoloop({project}): phase N - {name}")
  ↓
Phase N+1
```

## Document Sharding (DD#3)

각 sub-agent 는 최소 컨텍스트만:

| Section | Included? | 이유 |
|---|---|---|
| Section 2 (Technical Constitution) | Always | 코드 스타일·boundaries |
| Section 3 (Architecture) | Always | 시스템 디자인·data model·APIs |
| Current Phase block ONLY | Per-phase | 현재 phase task 만 (scope creep 방지) |
| Research Context | If triggered | Stage 1 결과 |
| All Other Phases | Never | 미래 phase 누출 차단 |
| Section 1 (Vision) | Never | 구현 무관 |
| Section 5 (Final Acceptance) | Final pass only | 마지막 검증에만 |
| Section 6 (Risks) | Never | orchestrator 만 |

## Context Isolation (DD#4)

- 각 phase 는 별도 sub-agent invocation (fresh context window)
- State handoff 는 디스크 (`.claude-progress.json`) + git history
- Sub-agent 는 progress file 읽지 않음 — 구현·검증만

## 2/3 Consensus Algorithm (Plan Validation + Code Review)

**Step A — Surface Matching:** 두 finding 이 candidate 인 조건: ≥2 일치 (file, line range ±10, category). transitive closure 로 group.

**Step B — Conclusion Alignment:** group 안에서 CONCLUDE step 비교. 같은 risk/impact 인지 검증.

**Step C — Consensus Decision:**
```
if agent_count >= 2 AND conclusions_aligned:
    tier = "strong" if agent_count == 3 else "standard"  # 자동 fix 가능
elif agent_count >= 2 AND NOT aligned:
    tier = "weak"  # manual review, no auto-fix
else:
    DROP  # single agent = noise
```

## Adaptive Reviewer Selection (DD#9)

**항상 spawn (5):**
- 3x code-reviewer (parallel, OBSERVE→TRACE→INFER→CONCLUDE)
- 1x performance-reviewer
- 1x walkthrough-reviewer

**조건부 (0-3):**
- side-effect-reviewer: public 함수 시그니처 변경 시
- concurrency-reviewer: async/await/thread/mutex/lock 포함 시
- test-quality-reviewer: test 파일 수정 시

## Autonomous Decision Protocol (DD#8)

**모든 결정은 autoloop 안에서 자율** — AskUserQuestion 호출 금지.

| 상황 | 자율 행동 | 로그 필요? |
|---|---|---|
| Hash mismatch on resume | Auto-continue with new spec, 완료 phase 보존 | Yes, human_review_needed=true |
| Plan NEEDS_REVISION | Validator 의 revised text 자동 적용 | Yes |
| Plan MAJOR_REVISION (round 1) | Auto-revise + re-validate | Yes |
| Plan MAJOR_REVISION (round 2) | 진행 + human_review_needed=true | Yes |
| Review grade D/F | 진행, human_review_needed flag | Yes |
| Phase blocked (max retries) | HALT autoloop, blocker 기록 | Yes |
| Final verification fails | 보고만, HALT 안 함 | Yes |

## State File Schema (`.claude-progress.json`)

```json
{
  "spec_file": "...",
  "spec_hash": "<SHA-256>",
  "input_mode": "TECH_SPEC",
  "project": "harness-maker",
  "repo_path": "/home/noel/harness-maker",
  "started": "<ISO-8601>",
  "current_phase": 1,
  "total_phases": 10,
  "phases": [
    {
      "id": 1,
      "name": "Project Scaffold + ...",
      "status": "pending|in_progress|retrying|completed|blocked",
      "started_at": null,
      "completed_at": null,
      "commit_hash": null,
      "iterations": 0,
      "stages": {
        "research":         { "status": "pending", "reason": null },
        "plan_validation":  { "status": "pending", "result": null, "rounds": 0 },
        "execute":          { "status": "pending", "iterations": 0 },
        "review":           { "status": "pending", "grade": null, "reviewers_spawned": 0 },
        "wrapup":           { "status": "pending", "commit_hash": null }
      },
      "autonomous_decisions": [],
      "verify_result": null,
      "last_error": null
    }
  ],
  "total_iterations": 0,
  "agents_spawned": 0,
  "blockers": [],
  "decision_log": []
}
```

**Atomic write:** `path.tmp` 작성 → `os.rename(tmp, path)`. 인터럽트 시 corrupt 0.

## Error Handling

| Error | Autonomous Action |
|---|---|
| project-name missing | ERROR + STOP |
| TECH_SPEC.md absent | ERROR + STOP |
| Section 0 malformed | ERROR + STOP |
| Phase parse fail | ERROR + STOP |
| Verify script absent (TECH_SPEC mode) | TESTER-only fallback, 로그 |
| CODER outputs PHASE_BLOCKED | 즉시 HALT |
| Phase fails max retries | HALT 모든 후속 phase |
| Review grade D/F | 진행, human_review_needed |
| Hash mismatch on resume | Auto-continue, 로그 |
| Global iter cap | HALT |
| Final verify fails | 보고, HALT 안 함 |
| Agent malformed JSON | N-1 agent 로 진행 |

## 우리 `/hm:loop` 가 모방할 부분

- **5-stage pipeline** (research → plan-validate → execute → review → wrapup)
- **Document sharding** — atomic stage 별 prompt fragment + workflow 별 fused prompt
- **Adaptive reviewer selection** — Conditional Router (Phase 5) 와 통합
- **Atomic state writes** — `.claude/observability/loop-state.json`
- **Autonomous decision protocol** — `--dry-run` 외 모든 결정 자율, log 기록

## 차이점 (`/hm:loop` 특유)

- vault autoloop 은 vault 안에서 실행 → repo 타깃. `/hm:loop` 은 user 프로젝트 안에서 실행 → 같은 repo.
- vault autoloop 은 TECH_SPEC.md 기반. `/hm:loop` 은 사용자 자연어 goal + workflow 기반.
- vault autoloop 은 phase-based. `/hm:loop` 은 feature-based (parse_goal → feature_list).
- 권한 분리 적용: `/hm:loop` 의 worker 는 executor agent (write-in-worktree only).
- 보안 게이트 통합: 매 iter wrapup 직전 verify-before-completion (보안 high finding 0건 체크).
