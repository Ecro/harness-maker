---
type: review
task_slug: intent-feedback-continuity
status: CHANGES_REQUESTED
created: 2026-09-24
run_id: 159766d7c346
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-feedback-continuity
  computed_at: 2026-09-23T15:33:51.970047Z
---

# Intent feedback continuity review

## Round 1 summary

Grade **C**: eight consensus-passed P1 findings. Seven mandatory lenses were exercised; the coverage CLI reported no missing lenses. The separate Codex voter returned nine findings, all accepted by the PIDA verifier. No code was edited before this round record.

## Drift findings

The 39 execute worktree paths fall within the PLAN phase scopes (collector, CLI, worktree, workflow reference, tests, SPEC and linked evidence). No SPEC scenario lacks a test or captured judgment subject. The base trial runtime update is separately recorded and remains pending field assessment. Intent WORLD-INTENT-CLOSED-LOOP scope and human assessment authority remain intact.

## Consensus findings

| ID | Severity | Lens / voices | Location | Finding |
|---|---|---|---|---|
| `e2c0aa430075695f` | P1 | functionality, codex | `src/harness_maker/intent_trial.py:360` | 승인된 제외 작업이 등록 대상에서 제외되지 않음 |
| `74bafcb7342809fb` | P1 | robustness | `src/harness_maker/worktree.py:5398` | 이미 반영된 브랜치의 시험 변경이 Git에 남지 않음 |
| `3e193405b97d98cd` | P1 | functionality | `src/harness_maker/intent_trial.py:453` | 기한이 지난 관찰 창이 계속 대기 상태로 남음 |
| `ca0161e946314147` | P1 | functionality | `src/harness_maker/intent_trial.py:426` | 등록되지 않은 작업의 평가가 시험 결과를 실패로 바꿈 |
| `79cca9df6521aa61` | P1 | consistency, security | `src/harness_maker/intent_trial.py:50` | 새 Git subprocess 호출에 timeout과 check=True가 없음 |
| `895865e3aa2a8d1e` | P1 | security, codex | `src/harness_maker/intent_trial.py:730` | 문자열 `false`를 수집 승인으로 처리할 수 있음 |
| `2d19a2c748b20c8b` | P1 | security | `src/harness_maker/intent_trial.py:300` | 원본 기록의 task slug가 저장소 밖 파일 읽기로 이어짐 |
| `5ef5a2af635213da` | P1 | concurrency | `src/harness_maker/worktree.py:5436` | 실패한 task_land가 시험 기록을 base index에 남김 |
| `1c04af5c87f10798` | P2 | tests | `tests/integration/test_intent_trial_native_evidence.py:29` | Native evidence is not bound to current stage triggers and execution inputs |

## Weak consensus

None.

## Manual-only findings

| ID | Severity | Source | Location | Finding |
|---|---|---|---|---|
| `a0242a1ee903c0f4` | P1 | codex | `src/harness_maker/intent_trial.py:656` | [P1] 첫 landing 이후 정상적인 trial 변경을 다시 landing할 수 없다. 이전 publication이 현재 HEAD에 반영됐는지 확인하여 새 변경의 base_blob을 현재 HEAD로 갱신해야 한다. 실제 Git으로 연속 두 번의 publish→landing 회귀 테스트를 추가하라. |
| `1e6340632ab42259` | P1 | codex | `src/harness_maker/intent_trial.py:648` | [P1] 첫 publication이 기존 수동 변경까지 runtime 소유 변경으로 인증한다. 최초 receipt 생성 시 원본이 HEAD와 일치하는지 확인하거나 승인된 기계적 delta만 분리해야 한다. 현재 테스트의 'publish 이후 수동 편집'뿐 아니라 'publish 이전 수동 편집'도 검증하라. |
| `3d2e3ecef04cabd8` | P1 | codex | `src/harness_maker/intent_trial.py:322` | [P1] 개별 start 이벤트의 존재를 전체 구간의 coverage 승인으로 취급한다. 누락된 시작이나 수집 실패가 있는 population에서도 cohort가 확정될 수 있다. 모든 발견된 task의 시작 귀속, 구간 경계, 선행 구간 승인 및 unresolved gaps를 검증한 뒤 commitment를 허용하라. |
| `e3c20ecf21b33093` | P1 | codex | `src/harness_maker/intent_trial.py:241` | [P1] activation 필터를 earliest-start 계산보다 먼저 적용해 기존 task의 resume를 새 task로 등록한다. 전체 시작 기록에서 task별 최초 시각을 먼저 구하고 그 결과에 activation 조건을 적용하라. activation 전 시작→activation 후 resume 사례를 추가하라. |
| `adfbc481fc995d2e` | P1 | codex | `src/harness_maker/intent_trial.py:409` | [P1] 새로운 assessment ID가 기존의 확정 실패를 결과 계산에서 지운다. 실패 우선순위는 전체 유효 decision 이력에서 계산하고, 상충하는 후속 판단은 명시적인 정정 규칙 없이는 덮어쓰지 않아야 한다. 서로 다른 ID의 fail→pass 테스트를 추가하라. |
| `6fbd13b4a05b5467` | P2 | codex | `src/harness_maker/intent_trial.py:443` | [P2] 명시적인 source-review로 동률 순서를 해결할 수 없다. 계약이 허용하는 사용자 순서 해소 경로가 영구 차단된다. 동률일 때 matching review의 명시적 순서를 검증·적용하고, 해소 근거가 없을 때만 conflict를 반환하라. |
| `834cbe685e9846ae` | P2 | codex | `src/harness_maker/intent_trial.py:453` | [P2] 관측 기간이 끝나도 workflow가 영구적으로 대기를 안내한다. until을 검증·비교하고 종료된 기간에는 reconciliation 또는 assessment의 다음 행동을 계산해야 한다. 종료 전·경계·종료 후와 후속 해소 이벤트를 테스트하라. |

## Disagreements

The expired-observation-window issue was rated P1 by the functionality lens and P2 by Codex. These are kept as independent, cross-tier findings; the P1 lens finding drives the grade.

## Cross-model findings (frozen @ round 1)

Codex invocation status: `invoked`; PIDA dispositions: nine accepted, zero rejected/duplicate/unresolved. The exact frozen set follows and remains in this REVIEW artifact. Subsequent rounds must not invoke Codex again.

```json
{
  "frozen_at_round": 1,
  "models": [
    {
      "model": "codex",
      "status": "invoked"
    }
  ],
  "findings": [
    {
      "id": "a0242a1ee903c0f4",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 656,
      "summary": "[P1] 첫 landing 이후 정상적인 trial 변경을 다시 landing할 수 없다. 이전 publication이 현재 HEAD에 반영됐는지 확인하여 새 변경의 base_blob을 현재 HEAD로 갱신해야 한다. 실제 Git으로 연속 두 번의 publish→landing 회귀 테스트를 추가하라.",
      "evidence": "H0에서 첫 publish → H1 landing → 새 decision/reconcile → 두 번째 landing 순서에서 base_blob은 계속 H0를 가리킨다. 메모리 재현에서 verified_trial_landing_paths가 'trial HEAD changed since publication'을 반환했다. 현재 integration test는 첫 landing만 검증한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:656은 이전 base_blob을 재사용하고, :615-617은 다음 landing에서 현재 HEAD와 비교해 거부한다.",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "1e6340632ab42259",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 648,
      "summary": "[P1] 첫 publication이 기존 수동 변경까지 runtime 소유 변경으로 인증한다. 최초 receipt 생성 시 원본이 HEAD와 일치하는지 확인하거나 승인된 기계적 delta만 분리해야 한다. 현재 테스트의 'publish 이후 수동 편집'뿐 아니라 'publish 이전 수동 편집'도 검증하라.",
      "evidence": "_prior_publication_valid는 receipt가 없으면 True다. 최초 publish 전에 canonical PLAN에 무관한 미커밋 문구를 추가하고 policy decision을 기록하면, _publish가 그 문구까지 content_hash로 인증한다. task_land는 인증된 전체 파일을 git add하므로 무관한 변경도 함께 커밋한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:648은 최초 publication을 무조건 허용하며, :658-660은 기존 수동 편집을 포함한 전체 내용을 인증한다.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "3d2e3ecef04cabd8",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 322,
      "summary": "[P1] 개별 start 이벤트의 존재를 전체 구간의 coverage 승인으로 취급한다. 누락된 시작이나 수집 실패가 있는 population에서도 cohort가 확정될 수 있다. 모든 발견된 task의 시작 귀속, 구간 경계, 선행 구간 승인 및 unresolved gaps를 검증한 뒤 commitment를 허용하라.",
      "evidence": "a에는 start acknowledgment가 있고 b에는 observation만 있으며 첫 시작 시각이 없는 경우, b는 starts에서 빠지고 source.bad에도 들어가지 않는다. _coverage는 a만 검사하여 accepted 처리한다. 시각·출처가 전혀 없는 {'kind':'start','task_slug':'a'}도 메모리 재현에서 (True, 'acknowledged')를 반환했다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:322-329은 발견된 starts에 대응하는 이벤트만 검사한다. 시작 시각이 없는 다른 task와 이벤트 출처는 확인하지 않는다.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "e3c20ecf21b33093",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 241,
      "summary": "[P1] activation 필터를 earliest-start 계산보다 먼저 적용해 기존 task의 resume를 새 task로 등록한다. 전체 시작 기록에서 task별 최초 시각을 먼저 구하고 그 결과에 activation 조건을 적용하라. activation 전 시작→activation 후 resume 사례를 추가하라.",
      "evidence": "ledger에 a의 activation 이전 시작과 activation 이후 resume가 함께 있으면 이전 시작은 241행에서 제거된다. 메모리 재현 결과 a의 resume 시각이 first start로 반환됐다. 이후 source review나 acknowledgment가 있으면 기존 task가 새 cohort 슬롯을 차지한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:241-242, :282-283은 activation 이전 시작을 버린 뒤 task별 최소 시각을 계산해 resume를 최초 시작으로 삼을 수 있다.",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "3f4e2f8a0a9b5ff9",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 360,
      "summary": "[P1] 승인된 source-review 제외 목록을 적용하지 않는다. 정상적으로 synthetic/administrative task를 제외하면 수집이 막히고, 전체 목록을 승인하면 제외 대상까지 등록된다. 관측 population과 eligible 순서를 분리하고 명시적 제외 및 기존 eligibility 정책을 cohort 계산에 적용하라.",
      "evidence": "source starts=[synthetic,a], accepted review ordered_tasks=[a], excluded_tasks=[synthetic]이면 _coverage가 order_conflict를 반환한다. excluded_tasks를 읽는 production 코드가 없고 reconcile은 원시 candidates[:3]을 사용한다. 메모리 재현에서도 승인된 제외가 거부됐다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:360은 전체 starts를 승인 순서와 비교하고, :766은 원시 candidates에서 등록한다. excluded_tasks는 적용되지 않는다.",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "9d900306604f5b3f",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 693,
      "summary": "[P1] decision payload 타입 검증 누락으로 잘못된 revocation이 수집 권한을 활성 상태로 남긴다. policy.enabled는 정확한 boolean, assessment는 유효한 member/verdict, source_review는 완전한 타입과 필수 필드를 요구해야 한다. 잘못된 입력은 publication 전에 변경 없이 거부하라.",
      "evidence": "record-decision은 kind별 payload를 검사하지 않는다. 메모리 재현에서 payload.enabled='false'가 validation을 통과했고, _status의 truthiness 검사에서도 authority_required가 되지 않았다. 빈 assessment payload나 허용되지 않은 verdict도 저장 가능한 구조다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:682-699은 종류별 payload를 검증하지 않고, :729-734는 문자열 enabled도 정책에 저장한다.",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "adfbc481fc995d2e",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 409,
      "summary": "[P1] 새로운 assessment ID가 기존의 확정 실패를 결과 계산에서 지운다. 실패 우선순위는 전체 유효 decision 이력에서 계산하고, 상충하는 후속 판단은 명시적인 정정 규칙 없이는 덮어쓰지 않아야 한다. 서로 다른 ID의 fail→pass 테스트를 추가하라.",
      "evidence": "서로 다른 decision ID로 a=fail 뒤 a=pass를 기록하면 dict comprehension이 fail을 덮는다. 메모리 재현에서 outcome이 failed가 아닌 pending으로 바뀌었다. 세 terminal member가 모두 pass이면 같은 경로로 passed가 된다. 기존 테스트는 동일 ID의 payload 충돌만 검사한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:409-427은 task별 최신 verdict만 남겨 서로 다른 ID의 후속 pass가 기존 fail을 지운다.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "6fbd13b4a05b5467",
      "source": "codex",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 443,
      "summary": "[P2] 명시적인 source-review로 동률 순서를 해결할 수 없다. 계약이 허용하는 사용자 순서 해소 경로가 영구 차단된다. 동률일 때 matching review의 명시적 순서를 검증·적용하고, 해소 근거가 없을 때만 conflict를 반환하라.",
      "evidence": "동일 시각의 a,b에 대해 사용자가 matching source review로 ordered_tasks=[b,a]를 승인해도 _status가 _coverage 호출 전에 무조건 order_conflict를 반환한다. 또한 _source_snapshot은 동률을 slug 순으로 정렬한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:441-448은 동률을 source-review 확인 전에 무조건 order_conflict로 처리한다.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "834cbe685e9846ae",
      "source": "codex",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 453,
      "summary": "[P2] 관측 기간이 끝나도 workflow가 영구적으로 대기를 안내한다. until을 검증·비교하고 종료된 기간에는 reconciliation 또는 assessment의 다음 행동을 계산해야 한다. 종료 전·경계·종료 후와 후속 해소 이벤트를 테스트하라.",
      "evidence": "deferred.until의 존재만 검사하고 현재 시각이나 후속 해소 이벤트는 확인하지 않는다. until='2020-01-01'을 넣은 메모리 재현에서도 action='wait_until_window_closes'가 반환됐다. 현재 golden test는 미래 날짜만 다룬다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_trial.py:453-454는 deferred_until의 존재만 확인하며 종료 시각이나 후속 해소 이벤트를 검사하지 않는다.",
      "status": "resolved",
      "invalidation_reason": null
    }
  ]
}
```

## Round 2 model groups

- `group_key: intent_trial` (derived path stem `intent_trial`); covered findings: `e2c0aa430075695f`, `3e193405b97d98cd`, `ca0161e946314147`, `79cca9df6521aa61`, `895865e3aa2a8d1e`, `2d19a2c748b20c8b`. Dimensions: reviewed versus eligible source population, member assessment authority, observation deadline, Git reader failure, policy payload type, and bounded task slugs. Consolidated edit: validate source and decisions at ingress, derive eligible candidates from accepted exclusions, calculate current deadline and member-only outcome, and bound Git subprocesses.
- `group_key: worktree` (derived path stem `worktree`); covered findings: `74bafcb7342809fb`, `5ef5a2af635213da`. Dimensions: branch already present versus divergent versus empty squash, trial runtime publication, staged index ownership, commit failure and teardown. Consolidated edit: persist verified runtime even on convergent land and unstage newly staged runtime on failed commit.

### Iteration 2 (Grade: C → A)

Fixes applied: 8. A date-only observation closing day initially made the AC-008 golden test fail; the parser now treats that calendar day as open through 23:59:59.999999 UTC. The affected golden test and covering intent-trial, concurrency and task-land tests passed; the full non-advisory suite, Ruff and mypy passed afterward.

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Apply approved exclusions to eligible cohort | `intent_trial.py` | Applied · caused_by=none |
| 2 | P1 | Persist verified runtime on convergent land | `worktree.py` | Applied · caused_by=none |
| 3 | P1 | Expire closed observation windows | `intent_trial.py` | Applied · caused_by=none |
| 4 | P1 | Restrict assessments to enrolled members | `intent_trial.py` | Applied · caused_by=none |
| 5 | P1 | Bound and check Git calls | `intent_trial.py` | Applied · caused_by=none |
| 6 | P1 | Validate policy enabled as a boolean | `intent_trial.py` | Applied · caused_by=none |
| 7 | P1 | Reject unsafe source task slugs | `intent_trial.py` | Applied · caused_by=none |
| 8 | P1 | Unstage trial runtime after failed land | `worktree.py` | Applied · caused_by=none |

Remaining: 7 (one consensus P2, five manual-only P1, one manual-only P2). New issues introduced: 0. Churn: 0.13989071038251366 (max: `src/harness_maker/intent_trial.py`, measured 2, excluded 0). Complexity increased in both touched files, most noticeably intent-trial cyclomatic complexity 219 → 252; this is a maintainability cost to watch. Re-review: skipped — `churn 0.14 < 0.30` (the CLI dispatch plan returned no reviewer). Cumulative lens coverage: all seven, no blockers. The five manual-only P1 findings remain pending human review despite the letter grade.

## Confirmation pass 1

The frozen artifact `52f281b260deef582b9a4e7b93b84dd21b0e6177` was reviewed against base `cdc6a7181c5ffa2e6b350c22077f92055778b87b`. All seven mandatory lenses returned. The test lens retained the prior P2 evidence-freshness issue. Five new severe issues were found (the canonical-root discovery issue was independently reported by robustness and security): repeated trial landing uses a stale publication base; first publication can certify earlier manual edits; pre-activation resumes enter the cohort; failed worktree enumeration can change the authoritative root and hide sources; and evidence symlinks can read outside registered repositories. Confirmation verdict: FAIL. The one separately budgeted repair round is entered; this is not a terminal review outcome.

## Confirmation repair round

- `group_key: intent_trial` (derived path stem `intent_trial`); covered findings: repeated publication, first publication ownership, pre-activation resume, worktree discovery failure, and symlink source escape. Dimensions: committed versus pending publication, user-authored legacy trial edits, earliest task start, canonical base discovery, and registered source containment. Consolidated edit: refresh the publication baseline once the previous version is in HEAD; compute first starts before the activation filter; fail closed on Git worktree-list errors; reject evidence paths resolving outside the registered root.

### Iteration 3 (Confirmation repair)

Five P1s were attempted. Four production fixes were retained; the first-publication ownership change was reverted because it made the approved legacy migration and raw-source SPEC golden cases fail. Those tests pin a reachable historical edit state that cannot be excluded by a blanket clean-HEAD requirement. Its finding is retagged `manual-only`, `disposition: unresolved`, `authority: oracle-blocked`; the underlying safety question remains open. The full non-advisory suite, Ruff and mypy passed after the revert.

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 9 | P1 | Refresh publication base after prior land | `intent_trial.py` | Applied · caused_by=none |
| 10 | P1 | Prevent first receipt certifying earlier manual edits | `intent_trial.py` | Reverted — test pins reachable historical edit state · caused_by=none |
| 11 | P1 | Filter eligibility after earliest task start | `intent_trial.py` | Applied · caused_by=none |
| 12 | P1 | Fail closed on worktree discovery error | `intent_trial.py` | Applied · caused_by=none |
| 13 | P1 | Reject source paths outside registered repo | `intent_trial.py` | Applied · caused_by=none |

Churn: 0.0660377358490566 (max: `src/harness_maker/intent_trial.py`, measured 1, excluded 0). Complexity: intent-trial LOC 915 → 954, cyclomatic 252 → 263, max nesting 10 → 10. Re-review: skipped — `churn 0.07 < 0.30`. Confirmation pass 2 must evaluate the complete frozen artifact.

## Confirmation pass 2 and terminal finding set

The final frozen artifact is `f3319c25566ea6d9795e63ba2581e5c82df30a8d`, reviewed against the original base `cdc6a7181c5ffa2e6b350c22077f92055778b87b`. All seven mandatory lenses returned with no coverage blocker. The pass found two newly counted P1 defects: `eb1148a9a985cdcc`, a changed hash in previously reviewed evidence is accepted when a later typed task start arrives; and `21c5a8bb2d307879`, canonical trial PLAN lookup can still follow a symlink outside the registered repository. The previously identified first-publication ownership defect `4183447cba27c531` remains unresolved with `authority: oracle-blocked` after its attempted fix broke approved legacy-recovery tests. The prior P2 native-evidence freshness finding also remains. No additional repairs are permitted in this confirmation pass.

## Review Iteration Summary

| Iteration | Grade | Fixes applied | Remaining counted severe | New severe |
|---|---|---:|---:|---:|
| 1 (initial) | C | — | 8 | — |
| 2 | A | 8 | 0 | 0 |
| confirm-1 | fail | — | 5 observed | 5 |
| 3 (confirmation repair) | B | 4 retained, 1 reverted | 2 | 0 |
| confirm-2 | B | — | 2 | 2 |

Final grade: **B**. Iterations used: 3 / 3 plus the separately budgeted confirmation repair and two confirmation passes. Exit reason: `confirmation-pass-2-dirty`. Status: **CHANGES_REQUESTED**. `human_review_needed: true`. Counters: unreviewed repair-round fixes 4; prior-fix regressions 0; unattributed findings 0. Cross-model findings were invoked once and their unresolved records are retained above.

## Size and complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|---|---|---|---|---|
| `src/harness_maker/intent_trial.py`, round 2 | 831 → 915 | 219 → 252 | 10 → 10 | measured |
| `src/harness_maker/worktree.py`, round 2 | 6161 → 6197 | 772 → 778 | 7 → 7 | measured |
| `src/harness_maker/intent_trial.py`, round 3 | 915 → 954 | 252 → 263 | 10 → 10 | measured |

The complete non-advisory pytest suite passed after the final code edits, as did Ruff and mypy. No oscillating hunk was reported. The execute worktree and branch remain open for follow-up; this review made no commit.
