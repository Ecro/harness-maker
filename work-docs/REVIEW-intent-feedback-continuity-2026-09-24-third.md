---
type: review
task_slug: intent-feedback-continuity
status: CHANGES_REQUESTED
created: 2026-09-24
run_id: 280bd7ceac58
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-feedback-continuity
  computed_at: 2026-09-24T01:50:00Z
---

# Intent feedback continuity: third independent review

## Round 1 summary

Grade **C**: five counted P1 defects. Seven mandatory lenses exercised; coverage reported no blocker. The full non-advisory pytest suite and lint/type checks passed before this review, but they do not cover the five paths below. The approved SPEC, PLAN and real trial were read independently. The live trial remains at two enrolled tasks, collecting/pending, with no user assessments. No commit or task landing occurred.

## Drift findings

No changed path crossed the PLAN's Phase 1–3 scope or its Do not change boundaries. No omitted SPEC scenario or intent-scope drift was identified.

## Consensus findings

| ID | Severity | Lens | Location | Finding |
|---|---|---|---|---|
| cd47b8694d5b61cf | P1 | functionality | intent_trial.py:538 | A later typed acknowledgment certifies an earlier unreviewed first start. |
| a825bbee0a238b73 | P1 | robustness | intent_trial.py:1036 | A source-review inventory with non-string keys crashes the decision command. |
| 730b45dac4de4ba0 | P1 | security | intent_trial.py:845 | Malformed active trial frontmatter can remove landing protection. |
| 86c9b46c2344a0b5 | P1 | concurrency | worktree.py:485 | Supported worktree registration/removal paths bypass the trial fence. |
| 32c555582e06d487 | P1 | concurrency | stage_spans.py:143 | Supported stage-start append can race after the final source check. |

## Weak consensus

None.

## Manual-only findings

Codex finding 10eeb8cbc1eda74c (P1) reports a registered no-start task artifact excluded from population validation. Four accepted Codex P2 findings concern sequential acknowledged extensions, timezone-equivalent tied starts, decision-writer source revalidation, and stale derived Trial presentation after terminal evidence changes. These remain outside the counted C grade but require examination in the repair round. Codex finding 2258f9b4ef73d838 was refuted against SPEC AC-005: a completed cohort is not automatically invalidated by an unrelated artifact edit.

## Disagreements

The tests lens withdrew its initial objection to the already-committed member edit test and its objection to static native evidence after reading the SPEC's bounded captured-run oracle. The security lens withdrew its initial local-CLI impersonation objection because the approved API uses explicitly supplied decision files, without a separate authenticated-host boundary.

## Frozen cross-model findings (round 1)

```json
{
  "frozen_at_round": 1,
  "models": [
    {
      "model": "codex",
      "status": "invoked",
      "reason": null
    }
  ],
  "findings": [
    {
      "id": "2258f9b4ef73d838",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 711,
      "summary": "[P1] 등록 완료 후에도 소스 유효성을 검사해야 합니다. 현재 coverage 검사는 미등록 후보가 있을 때만 실행되어, 기존 증거가 변경되어도 성공 판정이 유지됩니다. 모든 상태 조회와 reconcile에서 검토된 소스의 변경을 확인하고, 충돌이 해결되기 전에는 passed를 반환하지 않도록 수정하세요.",
      "evidence": "세 멤버와 pass 평가가 있는 상태에서 검토된 artifact hash를 변경하면 _coverage()는 source_conflict를 반환하지만 _status()는 outcome='passed', reason='pending', action='none'을 반환한다.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "rejected",
      "oracle_result": "SPEC AC-005 limits changed identity invalidation to affected provisional coverage; a full committed cohort need not be revoked by an unrelated artifact edit.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "10eeb8cbc1eda74c",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 538,
      "summary": "[P1] 발견된 전체 작업의 시작 누락을 검사한 뒤 자동 등록해야 합니다. 등록된 worktree에 시작 기록이 누락된 RESEARCH/SPEC 작업 b가 있고 a에만 start acknowledgment가 있으면, b는 inventory와 gap 검사에서 빠지고 a가 확정됩니다. 이는 승인된 SPEC의 전체 population 및 선행 구간 검증 조건을 충족하지 못합니다. 발견된 작업도 inventory에 포함하고 시작 귀속이 해결될 때까지 등록을 보류하세요.",
      "evidence": "_source_snapshot()은 trial_feedback이 없는 문서를 최초 탐색에서 건너뛰고, starts에 이미 있는 slug의 legacy 문서만 inventory에 추가한다. _coverage()는 그 starts에 acknowledgment가 있는지만 검사한다.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Registered worktree artifacts without a start are omitted from source inventory despite SPEC first-start and preceding interval requirements.",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "f5d0989d6c5e6ac1",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 567,
      "summary": "[P2] 자동 승인된 후속 구간을 다음 확장의 경계로 유지해야 합니다. 현재 조건은 마지막 사용자 검토 목록과 전체 cohort가 같아야 하므로 순차적으로 도착하는 두 번째 후속 작업부터 자동 등록이 막힙니다. 승인된 확장 경계를 보존하고 a→b→c를 서로 다른 invocation에서 등록하는 회귀 테스트를 추가하세요.",
      "evidence": "검토된 cohort=[a]에서 b의 acknowledgment는 acknowledged_extension으로 허용된다. b 등록 후 c의 acknowledgment를 추가하면 ordered_tasks=[a]와 frozen=[a,b]가 달라 source_conflict가 발생한다.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Reviewed ordered_tasks remains [a] as cohort grows to [a,b], so acknowledged c is blocked.",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "832a54168728529c",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 694,
      "summary": "[P2] 동률 시작 검사를 timestamp 문자열 대신 정규화된 시각으로 수행하세요. 같은 순간을 다른 시간대 형식으로 기록하면 현재 검사를 통과하고 slug 순서로 cohort가 확정됩니다. 독립적인 순서 증거나 명시적 source review 없이 동률을 해소해서는 안 됩니다.",
      "evidence": "a='2026-09-22T01:00:00Z', b='2026-09-22T10:00:00+09:00'에 대해 _status()가 order_conflict 대신 awaiting_reconciliation을 반환한다.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Equal instants with different timezone strings evade string-based tie check.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "a50ed78a2415d34d",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 1077,
      "summary": "[P2] decision writer에도 publication 직전 소스 재검증을 적용하세요. lock 대기 중 지원되는 task_create가 worktree를 등록하면 record-decision은 새 소스를 제외한 snapshot으로 결정을 저장하고 readback까지 수행합니다. lock 내부에서 등록 목록을 다시 읽고, 관련 소스와 목적지의 identity가 바뀌면 저장 전에 conflict를 반환해야 합니다.",
      "evidence": "record_decision()은 lock 획득 전에 얻은 roots를 그대로 _read()에 전달하며, _publish() 전 소스 목록·내용 재검증이 없다. reconcile()에 추가된 lock 내부 roots 재검증도 이 경로에는 없다.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "record_decision uses roots acquired before writer fence without lock-internal recheck.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "18c5bf43bf50c53f",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 1169,
      "summary": "[P2] 기존 멤버의 증거 변경도 파생 Trial 표 갱신 조건에 포함하세요. 현재 publication은 membership, source_refs 경로 또는 recovery 상태가 바뀔 때만 실행됩니다. 따라서 정상 closeout 후에도 PLAN의 Terminal과 Collection 표시는 이전 값으로 남습니다. 렌더링 결과의 변경도 감지하되 동일 입력 replay는 무쓰기 상태로 유지하세요.",
      "evidence": "기존 멤버의 동일 artifact에 terminal 이벤트만 추가한 경우, reconcile()은 tasks[a].terminal=True를 반환하지만 _publish()를 호출하지 않고 changed=False로 종료한다.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Terminal evidence changes do not trigger derived body re-render when membership and recovery are unchanged.",
      "status": "pending",
      "invalidation_reason": null
    }
  ]
}
```

## Review iteration summary

| Iteration | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 (initial) | C | — | 5 counted P1 | — |
| 2 | A provisional | 5 P1 fixes; targeted tests and Ruff/mypy passed | 0 counted P1, 1 unverified manual P1 | 0 |
| confirm-1 | C | read-only; 7/7 lenses | 4 new P1 | 4 P1, 3 test P2 |
| confirmation repair | A provisional | 4 P1 fixes; targeted tests and manual scenario replays passed | pending confirm-2 | 0 |
| confirm-2 | B | read-only; 7/7 lenses | 1 new P1 | 1 P1, 4 test P2 |

## Round 2 repair and confirmation

Round 2 fixed the five initial P1 paths: first-start acknowledgment matching, malformed decision inventory validation, trial PLAN protection, supported worktree registration/removal fencing, and stage-ledger append fencing. The measured churn ratio was 0.0471 (3 files), below the 0.30 selective re-review threshold; the CLI reason was `churn 0.05 < 0.30`. No reviewer was selectively re-dispatched. The five findings transitioned pending → resolved after targeted verification. The cross-model registered-artifact P1 remained manual-only, so a letter A could not be treated as risk closure.

The required confirm-1 freeze was `0b992a20f9228ab6d47d05890785e09961dc04ad` over review base `cdc6a7181c5ffa2e6b350c22077f92055778b87b`. The coverage CLI exercised all seven lenses with no blocker. It found four new P1s: a registered task artifact with no start is absent from the population; a second sequential acknowledged extension is blocked; malformed `trial :` metadata escapes landing protection; and supported task refresh can rebase trial source artifacts outside the fence. The first corroborates frozen Codex finding `10eeb8cbc1eda74c`; the second raises frozen P2 `f5d0989d6c5e6ac1` to P1 on the approved cross-session path. Three test-lens P2s identify missing regression oracles for first-start matching, malformed YAML landing, and stage append contention. Confirm-1 failed; no edit was made during the pass.

The single permitted confirmation repair added registered worktree artifact detection before cohort enrollment, retained the reviewed prefix across later acknowledged members, protected malformed trial PLANs using both current and committed trial markers, and fenced task refresh rebase/abort. Manual independent temporary-repository scenarios returned `source_incomplete` with empty cohort for a registered no-start task, enrolled reviewed `a` then acknowledged `b` and `c` across calls, and retained protection for malformed `trial :` frontmatter. Targeted pytest, Ruff and mypy passed. Confirm-2 is required before a final verdict; the three test-oracle P2s and other accepted cross-model P2s remain recorded.

## Final bounded confirmation result

Confirm-2 froze `078f9259eea5ed8028936cb0858b54db132dbc5c` over the same review base. All seven mandatory lenses returned, with no coverage blocker. The security lens found one new P1 at `intent_trial.py:863`: a parseable working-copy edit can remove both typed `trial` and legacy `Activation` markers while the committed PLAN is still an active trial. `active_trials()` checks committed content only on parse error, so supported landing can lose that path's protection. Four test-lens P2s identify missing automated oracles for the registered no-start artifact, second extension, malformed YAML, and refresh fence. The bounded second confirmation cannot initiate a third repair/pass in this run.

Final grade: **B**, below the configured A threshold. Status: **CHANGES_REQUESTED**; `human_review_needed: true`. Exit reason: dirty confirm-2. The nine applied P1 fixes passed targeted tests and manual scenarios; the newly reported protection path remains unresolved. The full non-advisory suite was started after the confirmation repair and its result is recorded in the next execution checkpoint. No commit or task landing occurred.
