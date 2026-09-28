---
type: review
task_slug: intent-feedback-continuity
status: CHANGES_REQUESTED
created: 2026-09-24
run_id: 0e2cac9e2ad8
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-feedback-continuity
  computed_at: 2026-09-24T01:00:23.400631+00:00
---

# Intent feedback continuity: independent re-review

## Result

**Grade C; CHANGES_REQUESTED; human_review_needed: true.** All seven mandatory lenses returned in both confirmation passes, and the coverage CLI reported no blocker. The final frozen artifact is `b5f2f9d8f1f7d09a3a250e81239d51520ee29484`, reviewed against `cdc6a7181c5ffa2e6b350c22077f92055778b87b`. Six consensus-passed P1 defects remain. Four were discovered or induced by the confirmation repair, so a passing test suite is not evidence of approval. No commit or task landing occurred.

The changed paths remain within PLAN Phase 1/2 scope or are review/evidence artifacts. No uncovered SPEC scenario or intent-scope drift was identified. The live WORLD-INTENT-CLOSED-LOOP trial remains at two committed tasks of three, `collecting`, `pending`, with no user assessments; this review neither supplies a verdict nor closes the intent.

## Round 1: independent findings

Pass 1 used redacted metadata; Pass 2 restored full PLAN/SPEC context. Pass 2 dropped an external `stash@{N}` position race because arbitrary external Git mutations are outside SPEC synchronization guarantees. It also dropped a native-capture freshness objection after confirming AC-009 explicitly requires captured execution. Six reviewer findings survived: five P1 and one P2. Codex was invoked exactly once and returned eight findings; PIDA accepted all eight, with no rejection, duplicate or unresolved disposition. One accepted Codex issue duplicated the reviewer's source-drift finding at the consensus fold.

Initial reviewer findings:

| ID | Severity | Lens / source | Location | Finding |
|---|---|---|---|---|
| `6567c588b53581b6` | P1 | robustness | `src/harness_maker/intent_trial.py:255` | A missing reviewed ledger is reported as no candidates |
| `6db404949021921a` | P1 | functionality | `src/harness_maker/intent_trial.py:387` | A later acknowledgment bypasses drift in reviewed source bytes |
| `7b5ef28ed8395cc6` | P1 | functionality | `src/harness_maker/intent_trial.py:446` | Terminal events without evidence can produce a passed trial |
| `d0d11eee14eaff3a` | P1 | security | `src/harness_maker/intent_trial.py:365` | Task document start claim can bypass source review |
| `4d684ff1635ce148` | P1 | security | `src/harness_maker/intent_trial.py:267` | Non-object JSON ledger record crashes trial status |
| `d0823d71e6afc46e` | P2 | tests | `tests/unit/test_intent_trial.py:291` | Order-conflict test omits affected source or task |

Round 1 grade: **C** (5 counted P1). The reviewed-source drift finding was reproduced but its attempted repair conflicted with `test_s1_reviewed_members_survive_later_artifact_edit_until_new_ack` (`tests/unit/test_intent_trial.py:322–335`), which requires enrollment after changing a reviewed artifact. The approved SPEC requires changed source identities to invalidate affected coverage (`specs/SPEC-intent-feedback-continuity.md:107–109`). The covering test was not edited; the finding is `manual-only`, `unresolved`, `authority: oracle-blocked`.

## Round 2: bounded repair

The following production fixes were retained and checked with existing tests and isolated Git repositories:

| # | Finding | Result |
|---|---|---|
| 1 | Missing reviewed base or registered-worktree ledger | Applied; now `source_incomplete` with a source locator · caused_by=none |
| 2 | Bare terminal event could produce `passed` | Applied; now `insufficient_evidence` · caused_by=none |
| 3 | Foreign-task start claim in another task artifact | Applied; now `source_incomplete` · caused_by=none |
| 4 | Non-object JSONL ledger record crashed status | Applied; now `source_incomplete` · caused_by=none |
| 5 | Reviewed source-byte drift on later acknowledgment | Refused; approved covering test expects the opposite behavior · caused_by=none |

Round 2 grade from remaining findings: **A**, with severe manual-review items still present. The churn pre-pin was accidentally placed after the first edit, so its measured ratio is not a valid measure of all Round 2 changes; the affected code was selectively re-reviewed anyway. The first confirmation pass then reviewed the full frozen diff and found eight P1 defects and two P2 test gaps. It did not approve the artifact.

## Confirmation repair

The separately budgeted repair round retained fixes for unreviewed empty sources, task-attributed starts without timestamps, `passed` with incomplete sources, malformed trial metadata, malformed decision kinds, failed stash lookup, and a final worktree-root recheck. The visible Trial section was left unresolved because updating its derived presentation while preserving the original migration prose and snapshot requires an explicit representation decision. All changes were production-only; the covering tests were not relaxed. The final full non-advisory pytest suite, Ruff, and mypy passed. Targeted Git-repository reproductions also confirmed missing ledger, malformed JSONL, foreign start, bare terminal, empty accepted snapshot, invalid timestamp, evidence-invalidated outcome and failed stash lookup behavior.

Confirmation-repair churn was 0.06925996204933586 in `src/harness_maker/intent_trial.py`; cyclomatic complexity rose 282 → 301 and LOC 1005 → 1054. The ratio was below the 0.30 selective re-review threshold, so the next step was a full frozen confirmation pass, not another narrow reviewer dispatch.

## Confirmation pass 2: remaining counted P1

| ID | Severity | Lens / source | Location | Finding |
|---|---|---|---|---|
| `810306dc79cd3e3a` | P1 | consistency | `src/harness_maker/intent_trial.py:1044` | Migrated Trial section retains stale enrollment values |
| `f763bb704f91f051` | P1 | functionality | `src/harness_maker/intent_trial.py:281` | Valid stage starts without task slugs block trial collection |
| `fa726586d7a162fb` | P1 | robustness | `src/harness_maker/intent_trial.py:827` | Malformed trial metadata escapes write-command error handling |
| `289e56dcec813d65` | P1 | security | `src/harness_maker/intent_trial.py:218` | Malformed trial list entries still crash status |
| `c43137e68acf6656` | P1 | security | `src/harness_maker/intent_trial.py:693` | Invalid trial metadata disables landing protections |
| `86d71feda67c1346` | P1 | concurrency | `src/harness_maker/intent_trial.py:1022` | Worktree registration can race after final source check |

The slugless-start failure is a repair regression: `SpanEvent.task_slug` is optional and the existing stage-span test emits such starts, while the new trial parser flags all of them as broken. Invalid typed metadata can also make write commands re-read the same invalid file and throw, or make `active_trials` omit a PLAN from landing protection. The final worktree check narrows but does not close the registration race: supported `git worktree add` does not share the trial writer fence and can occur after the check but before publication. The unchanged legacy body still displays stale enrollment after typed membership changes.

## P2 and manual-review items

| ID | Severity | Lens / source | Location | Finding |
|---|---|---|---|---|
| `3ad29a74a7f85cd2` | P2 | tests | `tests/integration/test_intent_trial_concurrency.py:111` | Writer-kill recovery test accepts failed follow-up write |
| `9528c7677b8b1e68` | P2 | tests | `tests/unit/test_intent_trial.py:161` | Outcome tests omit failure precedence after later evidence |
| `6e31c2044b68e4dc` | P2 | tests | `tests/unit/test_intent_trial.py:294` | Malformed start record lacks an AC-005 regression test |
| `d0823d71e6afc46e` | P2 | tests | `tests/unit/test_intent_trial.py:291` | Order-conflict test omits affected source or task |

Unverified severe reviewer/model findings retained for human judgment:

| ID | Severity | Lens / source | Location | Finding |
|---|---|---|---|---|
| `6db404949021921a` | P1 | functionality | `src/harness_maker/intent_trial.py:387` | A later acknowledgment bypasses drift in reviewed source bytes |
| `127979ce592c7d01` | P1 | codex | `src/harness_maker/intent_trial.py:717` | [P1] 최초 publication이 기존 수동 변경까지 자동 커밋 대상으로 인증한다. canonical PLAN에 무관한 미커밋 내용을 추가한 뒤 정상 policy decision이나 reconcile을 실행하면 그 내용도 runtime 소유로 표시되어 다음 landing에 포함된다. 최초 변경의 소유권을 검증하거나 승인된 delta를 분리해야 한다. 기존 테스트는 publication 이후의 수동 편집만 검사한다. |
| `c161bb5071fb10fb` | P1 | codex | `src/harness_maker/intent_trial.py:459` | [P1] 후속 assessment가 확정 실패를 지운다. record_decision은 새 ID의 상충 평가를 허용하고 상태 계산은 마지막 평가만 사용하므로, fail 이후 pass를 기록하면 failed가 사라지며 세 작업의 조건이 충족되면 passed까지 가능하다. 명시적 정정 계약 없이 기존 실패를 덮어쓰면 안 된다. |
| `6e6cb3ff5a8112b3` | P1 | codex | `src/harness_maker/intent_trial.py:365` | [P1] 개별 start 이벤트를 전체 구간의 완전성 승인으로 취급한다. 시작이 누락된 발견 작업은 검사 대상에서 빠져 a의 cohort commitment를 막지 못한다. 나중에 b가 더 이른 작업으로 확인되어도 이미 고정한 cohort를 복구할 수 없다. 발견된 전체 population의 시작 귀속, 선행 구간 승인 및 unresolved gaps를 검증해야 한다. |
| `6d792326a318bd6d` | P1 | codex | `src/harness_maker/intent_trial.py:206` | [P1] canonical trial 경로가 symlink를 통해 저장소 밖으로 벗어날 수 있다. PLAN 파일 symlink는 외부 문서를 trial로 읽게 하고, work-docs 디렉터리 symlink는 publication 자체를 외부 디렉터리에 수행하게 한다. 읽기와 쓰기 전에 canonical 경로의 저장소 포함 여부와 symlink를 검증해야 한다. |

The cross-model P1 on first publication certifying preexisting manual dirt remains open; the earlier review's blanket clean-HEAD repair broke approved legacy-recovery cases. Separate Codex findings on later assessments replacing a confirmed failure, missing-start coverage, and canonical PLAN symlink escape also remain open. These are not counted in the C grade but keep `human_review_needed` true. The changed-source drift finding above is independently confirmed and oracle-blocked; it is not a dismissal of the risk.

## Frozen cross-model findings (round 1)

The following is the exact adapted Codex finding set with its PIDA results. It was not re-invoked in later rounds. `status` records lifecycle independently of PIDA disposition.

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
      "id": "127979ce592c7d01",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 717,
      "summary": "[P1] 최초 publication이 기존 수동 변경까지 자동 커밋 대상으로 인증한다. canonical PLAN에 무관한 미커밋 내용을 추가한 뒤 정상 policy decision이나 reconcile을 실행하면 그 내용도 runtime 소유로 표시되어 다음 landing에 포함된다. 최초 변경의 소유권을 검증하거나 승인된 delta를 분리해야 한다. 기존 테스트는 publication 이후의 수동 편집만 검사한다.",
      "evidence": "_prior_publication_valid()는 receipt가 없으면 True를 반환한다. _publish()는 최초 publication에서 현재 파일과 HEAD의 일치를 확인하지 않고 전체 문서에 content_hash를 부여한다. task_land()는 이 파일 전체를 git add한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "First publication marks the entire dirty document runtime-owned; no relevant test oracle was gathered.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "c161bb5071fb10fb",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 459,
      "summary": "[P1] 후속 assessment가 확정 실패를 지운다. record_decision은 새 ID의 상충 평가를 허용하고 상태 계산은 마지막 평가만 사용하므로, fail 이후 pass를 기록하면 failed가 사라지며 세 작업의 조건이 충족되면 passed까지 가능하다. 명시적 정정 계약 없이 기존 실패를 덮어쓰면 안 된다.",
      "evidence": "메모리 재현에서 서로 다른 ID의 a=fail, a=pass를 순서대로 제공하자 _status().outcome이 pending이 됐다. assessments dict comprehension은 같은 task의 이전 verdict를 덮어쓴다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Status retains only the last assessment for each task, so later pass erases fail.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "6e6cb3ff5a8112b3",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 365,
      "summary": "[P1] 개별 start 이벤트를 전체 구간의 완전성 승인으로 취급한다. 시작이 누락된 발견 작업은 검사 대상에서 빠져 a의 cohort commitment를 막지 못한다. 나중에 b가 더 이른 작업으로 확인되어도 이미 고정한 cohort를 복구할 수 없다. 발견된 전체 population의 시작 귀속, 선행 구간 승인 및 unresolved gaps를 검증해야 한다.",
      "evidence": "a에는 start acknowledgment, b에는 시작 시각 없는 observation만 있는 입력에서 _coverage()가 (True, 'acknowledged')를 반환했다. 검사는 source['starts']에 이미 들어온 task만 순회한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Coverage checks typed starts only for tasks already in starts, omitting observation-only tasks.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "b388c376aab49849",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 379,
      "summary": "[P1] 새 작업의 acknowledgment가 과거 검토 소스의 임의 변경까지 승인한다. inventory 불일치 분기는 기존 task 이름과 시작 시각만 비교하므로, 검토된 증거가 수정·삭제되어도 이후 task를 등록할 수 있다. 허용된 artifact 이동과 기존 증거의 내용 변경을 구분하고, 검증되지 않은 변경은 source_conflict로 유지해야 한다.",
      "evidence": "이미 등록된 a의 inventory hash를 original에서 changed로 바꾸고 이후 c의 typed start를 추가한 메모리 재현에서 _coverage()가 (True, 'acknowledged_extension')을 반환했다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Inventory mismatch extension does not compare changed historical source bytes.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "6d792326a318bd6d",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 206,
      "summary": "[P1] canonical trial 경로가 symlink를 통해 저장소 밖으로 벗어날 수 있다. PLAN 파일 symlink는 외부 문서를 trial로 읽게 하고, work-docs 디렉터리 symlink는 publication 자체를 외부 디렉터리에 수행하게 한다. 읽기와 쓰기 전에 canonical 경로의 저장소 포함 여부와 symlink를 검증해야 한다.",
      "evidence": "_path()는 slug만 검증하며 _doc()는 바로 path.read_bytes()를 호출한다. task evidence에 적용하는 _source_file_ok() 검사가 canonical trial에는 없다. _publish()도 같은 부모 경로에 임시 파일을 생성한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Canonical trial PLAN symlink is followed; symlinked work-docs permits outside write.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "b535c4adc21e9219",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 932,
      "summary": "[P1] commit 재검증이 새로 등록된 worktree를 놓친다. 최초 discovery 이후, 특히 lock 대기 중 다른 작업이 worktree를 등록하면 두 snapshot 모두 그 소스를 제외한 채 일치한다. 새 소스에 더 이른 시작이나 누락 증거가 있어도 cohort를 확정할 수 있다. lock 안과 publication 전 등록 소스 목록도 재검증해야 한다.",
      "evidence": "_roots()는 writer lock 획득 전에 한 번 실행된다. lock 이후 _read()와 commit 직전 _source_snapshot() 모두 동일한 roots 목록을 재사용한다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Commit recheck reuses pre-lock worktree roots; new registered source remains unseen.",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "e7e1988a2ce98a1f",
      "source": "codex",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 277,
      "summary": "[P2] 실제 SPEC artifact의 trial_feedback을 발견하지 못한다. PLAN이 없는 작업이 정상 경로 specs/SPEC-a.md에 start나 observation을 남기면 수집기가 이를 무시하여 enrollment 또는 evidence 상태가 계속 미완료로 남는다. 기존 artifact 경로 계약에 맞춰 SPEC 디렉터리를 검색하고 실제 경로로 회귀 테스트해야 한다.",
      "evidence": "현재 설정과 models.py의 기본 SPEC 경로는 specs/이다. 그러나 discovery와 legacy artifact inventory는 모두 work-docs/SPEC-*.md만 확인한다. artifact='SPEC' 테스트도 잘못된 work-docs 경로에 fixture를 만든다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "SPEC discovery scans work-docs whereas canonical SPEC directory is specs.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "6de3770aff3e2ce5",
      "source": "codex",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 493,
      "summary": "[P2] 명시적 source review로 동률 시작 순서를 해결할 수 없다. 사용자가 증거를 바탕으로 순서를 승인해도 reconcile이 항상 거부되어 계약상 지원하는 복구 경로가 막힌다. matching review의 명시적 순서를 적용하고 해소 근거가 없을 때만 충돌을 반환해야 한다.",
      "evidence": "동일 시각의 a,b에 matching inventory와 accepted ordered_tasks=['a','b']를 제공해도 _status()는 order_conflict를 반환했다. 동률 검사가 _coverage()보다 먼저 무조건 실행된다.",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Equal timestamp order_conflict precedes accepted source review resolution.",
      "status": "pending",
      "invalidation_reason": null
    }
  ]
}
```

## Verification and exit

- Final full non-advisory pytest run: passed (`uv run pytest -n 7 --dist loadfile -m 'not advisory' -q`).
- Ruff: passed (`uv run ruff check`). Mypy: passed (`uv run mypy src/harness_maker`). `git diff --check`: passed.
- Lens coverage: seven of seven in Round 1 and both confirmation passes; no approval blocker.
- Final grade: **C** (6 counted P1; 4 counted P2). Exit reason: `confirmation-pass-2-dirty`. Status: **CHANGES_REQUESTED**. Iterations used: Round 1, Round 2, and one confirmation repair plus two confirmation passes. Unreviewed fixes: 0; regression-attributed distinct findings: 3; attribution unknown: 0.
- Task worktree remains uncommitted for follow-up. The source-drift SPEC/test conflict and the six counted P1s block approval. No third confirmation pass or additional repair was performed in this invocation.
