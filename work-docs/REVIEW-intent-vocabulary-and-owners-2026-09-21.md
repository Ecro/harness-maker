---
type: review
task_slug: intent-vocabulary-and-owners
status: APPROVED
grade: A
human_review_needed: false
created: 2026-09-21
review_run_id: cd8632bc72ba
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, code-verifier, codex]
consensus_method: cross-check
second_opinion_results:
  - model: codex
    status: invoked
    reason: null
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-vocabulary-and-owners
  computed_at: 2026-09-21T03:55:33.846805+00:00
---
# Review: Intent vocabulary and owners

## 🎯 Round 1 Summary
Grade B. All seven mandatory lenses exercised. Two accepted P1 findings require repair;
two P2 findings remain for a human sweep. Auto-fix enabled, threshold A, maximum 3 rounds.
Production's mandatory lenses override the older conditional-router fallback. Concurrency
slots required staggered dispatch; all four groups returned before adjudication.

Procedure limitation: initial redaction used title/description instead of the CLI's
pr_title/pr_description, exposing rationale to core/security/concurrency reviewers. Corrected
before the tests dispatch; reviewers recorded exposure and used code evidence. Confirmation
will use fresh frozen-artifact context. No metadata claim is treated as behavioral evidence.

## 🔍 Drift Findings
No implementation-scope violations. Both task SPECs were read; approval remains a separate
DRI action. The resolved review base is d330abff5adf6f090204e9b118dfa45fca359ff1; the only
committed delta to task start 75239ea7 is pre-existing observability receipts, not task source.
All staged/unstaged implementation changes were reviewed. No common_ground_marks or intent
link on this PLAN; silent-intent hook and objective drift are inapplicable.

## ✅ Round 1 Consensus Findings

- **5472a8d9b9b43d42 · P1 · accepted · pending** — Question writes invalidate accepted documents retaining legacy unknowns (`src/harness_maker/world.py:1246`). Before writing questions, reject documents retaining unknowns and require explicit migration; apply the guard to legacy aliases too and add an observe/resolve regression.

- **dea465ec4a4aa4d9 · P1 · accepted · pending** — Migration can delete successfully recorded concurrent measurements (`src/harness_maker/intent_migrate.py:136`). Serialize migration and all intent writers with a shared project lock acquired before path selection; hold it through source retirement. Add an interleaved migration/record regression test.

- **11175f90347e8125 · P2 · accepted · pending** — Malformed destination fixture masks missing conflict protection (`tests/unit/test_intent_vocabulary.py:264`). Create a valid canonical destination with all required fields and change only its statement or body; retain nonzero exit and full filesystem equality assertions.

## ⚠️ Weak Consensus
None.

## 📝 Round 1 Manual-Only Findings
- **7124033e9a0203a8 · P2 · accepted · pending** — `purpose` 키 존재만으로 마이그레이션 완료를 판단합니다. 사용자가 프로젝트 정의만 새 형식으로 바꾸고 기존 ledger를 남겨두면 질문과 측정값이 진단 없이 사라지며 canonical 쓰기도 허용됩니다. 이후 metric 기록은 별도 저장소를 만들어 명시적 migrate까지 충돌로 실패하게 할 수 있습니다. 기존 저장소를 읽거나 미완료 마이그레이션을 진단하고, 쓰기는 완료 전 거부해야 합니다. (`src/harness_maker/world.py:145`).

## 🤝 Disagreements
No conflicting severity assessment of the same finding. Core mixed-question corruption and
Codex partial-migration read omission are distinct execution risks, retained separately.

## 🧊 Cross-model findings (frozen @ round 1)

```json
{
  "frozen_at_round": 1,
  "models": [
    "codex"
  ],
  "findings": [
    {
      "id": "38850a7dd782ef7a",
      "severity": "P1",
      "file": "src/harness_maker/intent_migrate.py",
      "line": 136,
      "summary": "마이그레이션이 기존 writer의 RMW 잠금을 획득하지 않습니다. 따라서 다른 세션의 question 추가나 metric 기록이 초기 읽기 이후 완료되면, 오래된 스냅샷을 저장하고 원본을 삭제하면서 성공한 변경을 유실합니다. 읽기부터 원본 삭제까지 관련 writer와 동기화하고, 잠금 대기 중 저장 위치가 변경되는 경우도 처리해야 합니다.",
      "evidence": "메모리 내 재현에서 preflight 이후 기존 assumptions.yaml에 q_concurrent를 추가하자, migrate는 성공했지만 canonical 저장소에는 q_existing만 남고 기존 ledger는 삭제됐습니다.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "intent_migrate.py:34,75 reads snapshots and writes/removes at 136–139 without locking, so world.py:1356,1434 writer locks cannot prevent concurrent data loss.",
      "status": "resolved"
    },
    {
      "id": "7124033e9a0203a8",
      "severity": "P2",
      "file": "src/harness_maker/world.py",
      "line": 145,
      "summary": "`purpose` 키 존재만으로 마이그레이션 완료를 판단합니다. 사용자가 프로젝트 정의만 새 형식으로 바꾸고 기존 ledger를 남겨두면 질문과 측정값이 진단 없이 사라지며 canonical 쓰기도 허용됩니다. 이후 metric 기록은 별도 저장소를 만들어 명시적 migrate까지 충돌로 실패하게 할 수 있습니다. 기존 저장소를 읽거나 미완료 마이그레이션을 진단하고, 쓰기는 완료 전 거부해야 합니다.",
      "evidence": "canonical 프로젝트 정의와 기존 .claude/world/{assumptions,outcomes}.yaml을 함께 제공한 재현에서 load_world는 assumptions={}, values=[], errors=[]를 반환했고, _canonical_project는 True였습니다.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "world.py:145,155,163 choose canonical paths solely from purpose presence, hiding old ledgers; intent_cli.py:78 uses the same predicate to allow writes.",
      "status": "pending"
    }
  ]
}
```

## Round records

### Round 1
```json
{
  "counts": {
    "P0": 0,
    "P1": 2,
    "P2": 1,
    "P3": 0
  },
  "disposition_counts": {
    "accepted": 4,
    "duplicate": 0,
    "rejected": 0,
    "unresolved": 0
  },
  "errors": [],
  "findings": [
    {
      "authority": null,
      "caused_by": null,
      "disposition": "accepted",
      "evidence": "I/O-mocked world.observe: _validate_raw initially []; _canonical_project True; observe succeeds; subsequent validation conflict for question q_17ce4aba1d6039ec.",
      "file": "src/harness_maker/world.py",
      "id": "5472a8d9b9b43d42",
      "lens": "robustness",
      "line": 1246,
      "pass": 2,
      "reasoning": {
        "conclude": "Successful mutation makes valid compatible input unreadable, and migration also refuses it.",
        "infer": "Next read regenerates the same legacy question ID with empty evidence/history/open status, conflicting with the updated canonical record.",
        "observe": "Read intent_cli.py, intent_vocabulary.py and intent_migrate.py fully; escalated world.py to question loaders/writers/validators. _dump_assumptions updates open_questions while retaining unknowns.",
        "trace": "Canonical purpose plus legacy unknowns is accepted and allows mutation; observe appends evidence and persists without removing unknowns."
      },
      "severity": "P1",
      "status": "pending",
      "suggestion": "Before writing questions, reject documents retaining unknowns and require explicit migration; apply the guard to legacy aliases too and add an observe/resolve regression.",
      "summary": "Question writes invalidate accepted documents retaining legacy unknowns",
      "tag": "consensus-passed",
      "voices": [
        {
          "kind": "lens",
          "source": "robustness"
        }
      ]
    },
    {
      "authority": null,
      "caused_by": null,
      "cross_model_ids": [
        "38850a7dd782ef7a"
      ],
      "disposition": "accepted",
      "evidence": "for path, content in writes.items(): atomic_write(path, content); for path in retired: path.unlink()",
      "file": "src/harness_maker/intent_migrate.py",
      "id": "dea465ec4a4aa4d9",
      "lens": "concurrency",
      "line": 136,
      "pass": 2,
      "reasoning": {
        "conclude": "Successful concurrent measurements are permanently lost; coordinate before path selection through retirement.",
        "infer": "Concurrent append returns success after snapshot read; migration publishes older snapshot and deletes the source.",
        "observe": "Read migration/CLI fully; escalated world.py writer/CLI and io_utils.py locking. Migration reads legacy metrics and retires them without writer locks.",
        "trace": "Legacy record_value selects old path and appends under its per-file RMW lock while migration runs without that lock."
      },
      "severity": "P1",
      "status": "pending",
      "suggestion": "Serialize migration and all intent writers with a shared project lock acquired before path selection; hold it through source retirement. Add an interleaved migration/record regression test.",
      "summary": "Migration can delete successfully recorded concurrent measurements",
      "tag": "consensus-passed",
      "voices": [
        {
          "kind": "lens",
          "source": "concurrency"
        },
        {
          "kind": "cross-model",
          "source": "codex"
        }
      ]
    },
    {
      "authority": null,
      "caused_by": null,
      "disposition": "accepted",
      "evidence": "test_s4_conflict writes only id and statement. Migration's later independent destination validator rejects this incomplete record even if collision comparison is removed.",
      "file": "tests/unit/test_intent_vocabulary.py",
      "id": "11175f90347e8125",
      "lens": "tests",
      "line": 264,
      "pass": 2,
      "reasoning": {
        "conclude": "S4 requires two valid conflicting records to distinguish conflict refusal from malformed-record rejection.",
        "infer": "Implementation overwriting conflicting valid destination still passes this test.",
        "observe": "Read all test_intent_vocabulary.py including beyond initial 400 lines; escalated into intent_migrate.py:21-143.",
        "trace": "Missing destination collision check still reaches existing canonical validation before any writes; incomplete fixture is rejected there."
      },
      "severity": "P2",
      "status": "pending",
      "suggestion": "Create a valid canonical destination with all required fields and change only its statement or body; retain nonzero exit and full filesystem equality assertions.",
      "summary": "Malformed destination fixture masks missing conflict protection",
      "tag": "consensus-passed",
      "voices": [
        {
          "kind": "lens",
          "source": "tests"
        }
      ]
    },
    {
      "authority": null,
      "caused_by": null,
      "disposition": "accepted",
      "evidence": "canonical 프로젝트 정의와 기존 .claude/world/{assumptions,outcomes}.yaml을 함께 제공한 재현에서 load_world는 assumptions={}, values=[], errors=[]를 반환했고, _canonical_project는 True였습니다.",
      "file": "src/harness_maker/world.py",
      "id": "7124033e9a0203a8",
      "line": 145,
      "needs_relaxation": false,
      "severity": "P2",
      "source": "codex",
      "status": "pending",
      "summary": "`purpose` 키 존재만으로 마이그레이션 완료를 판단합니다. 사용자가 프로젝트 정의만 새 형식으로 바꾸고 기존 ledger를 남겨두면 질문과 측정값이 진단 없이 사라지며 canonical 쓰기도 허용됩니다. 이후 metric 기록은 별도 저장소를 만들어 명시적 migrate까지 충돌로 실패하게 할 수 있습니다. 기존 저장소를 읽거나 미완료 마이그레이션을 진단하고, 쓰기는 완료 전 거부해야 합니다.",
      "tag": "manual-only",
      "voices": [
        {
          "kind": "cross-model",
          "source": "codex"
        }
      ]
    }
  ],
  "grade": "B",
  "human_review_needed": false,
  "round": 1,
  "slug": "intent-vocabulary-and-owners"
}
```

### Round 2 repair model and execution
- group_key: intent-storage (derived from world / intent_migrate / intent_cli).
- covered_finding_ids: 5472a8d9b9b43d42, dea465ec4a4aa4d9.
- Dimensions: legacy/canonical/mixed input; question/metric/record writer; migration
  before/during/after a write; waiting writers; refused/successful writes.
- Consolidated repair: a stable checkout-directory flock before leaf writer reads/path
  selection and migration preflight; existing per-file locks remain inside. Delegating
  wrappers and measurement execution do not reacquire it. Directory inode locking creates
  no lock artifact on a refused operation. Non-POSIX fallback matches existing rmw_lock.
- Mixed purpose+unknowns is rejected before question mutation, including legacy aliases
  and the canonical resolve branch; explicit migration remains the only format rewrite.
- [Fix #1] P1 migration lost update: shared directory lock covers migration and metric,
  question and record leaf writers. Applied · caused_by=none.
- [Fix #2] P1 mixed-question corruption: require migration before modifying retained legacy
  unknowns. Applied · caused_by=none.
- Initial decorator draft produced mypy Callable/Concatenate errors; revised to preserve
  the whole ParamSpec and wrapped public signatures before the successful verification.
  No test assertion was edited and no runtime repair was reverted.
- Covering tests read before editing: vocabulary S4/S5/S6 and failure/retry cases,
  world assumptions observation cases, world outcome concurrent writers, objective lifecycle.
- Verification: focused 146 passed; selected regression 1272 passed; Ruff check/format and
  strict mypy (775 files) passed. Prior execute full suite: 9096 passed,100 skipped,3 xfailed.
- Separate deterministic reproduction (no repository test edits): mixed input is refused
  byte-identically and works after migrate; pause migration at first metrics publication,
  launch a ready-signalled record subprocess, verify it waits, release migration, then assert
  both rows in canonical storage and the legacy source retired. Both passed.
- P2 findings are retained without auto-fix under the grade-B repair policy.
- Churn 1.0, maximum path REVIEW report (a new artifact); source ratios: CLI .114,
  migration .034, world .031. CLI selected one functionality re-review; no manual override.

### Iteration 2 (Grade: B → A)
Fixes applied: 2; remaining P1: 0; remaining P2: 2. New issues: 0.
Functionality re-review found no new issues and confirmed both repairs.
Lifecycle transitions: two pending → resolved; no-progress invariant cleared.
```json
[
  {
    "severity": "P1",
    "file": "src/harness_maker/world.py",
    "line": 1246,
    "summary": "Question writes invalidate accepted documents retaining legacy unknowns",
    "suggestion": "Before writing questions, reject documents retaining unknowns and require explicit migration; apply the guard to legacy aliases too and add an observe/resolve regression.",
    "evidence": "I/O-mocked world.observe: _validate_raw initially []; _canonical_project True; observe succeeds; subsequent validation conflict for question q_17ce4aba1d6039ec.",
    "lens": "robustness",
    "reasoning": {
      "observe": "Read intent_cli.py, intent_vocabulary.py and intent_migrate.py fully; escalated world.py to question loaders/writers/validators. _dump_assumptions updates open_questions while retaining unknowns.",
      "trace": "Canonical purpose plus legacy unknowns is accepted and allows mutation; observe appends evidence and persists without removing unknowns.",
      "infer": "Next read regenerates the same legacy question ID with empty evidence/history/open status, conflicting with the updated canonical record.",
      "conclude": "Successful mutation makes valid compatible input unreadable, and migration also refuses it."
    },
    "pass": 2,
    "disposition": "accepted",
    "status": "resolved",
    "caused_by": null,
    "voices": [
      {
        "source": "robustness",
        "kind": "lens"
      }
    ],
    "id": "5472a8d9b9b43d42",
    "resolution": "Round 2 repair and 1272 selected tests plus deterministic reproductions passed; functionality re-review clear."
  },
  {
    "severity": "P1",
    "file": "src/harness_maker/intent_migrate.py",
    "line": 136,
    "summary": "Migration can delete successfully recorded concurrent measurements",
    "suggestion": "Serialize migration and all intent writers with a shared project lock acquired before path selection; hold it through source retirement. Add an interleaved migration/record regression test.",
    "evidence": "for path, content in writes.items(): atomic_write(path, content); for path in retired: path.unlink()",
    "lens": "concurrency",
    "reasoning": {
      "observe": "Read migration/CLI fully; escalated world.py writer/CLI and io_utils.py locking. Migration reads legacy metrics and retires them without writer locks.",
      "trace": "Legacy record_value selects old path and appends under its per-file RMW lock while migration runs without that lock.",
      "infer": "Concurrent append returns success after snapshot read; migration publishes older snapshot and deletes the source.",
      "conclude": "Successful concurrent measurements are permanently lost; coordinate before path selection through retirement."
    },
    "pass": 2,
    "disposition": "accepted",
    "status": "resolved",
    "caused_by": null,
    "voices": [
      {
        "source": "concurrency",
        "kind": "lens"
      },
      {
        "source": "codex",
        "kind": "cross-model"
      }
    ],
    "cross_model_ids": [
      "38850a7dd782ef7a"
    ],
    "id": "dea465ec4a4aa4d9",
    "resolution": "Round 2 repair and 1272 selected tests plus deterministic reproductions passed; functionality re-review clear."
  },
  {
    "severity": "P2",
    "file": "tests/unit/test_intent_vocabulary.py",
    "line": 264,
    "summary": "Malformed destination fixture masks missing conflict protection",
    "suggestion": "Create a valid canonical destination with all required fields and change only its statement or body; retain nonzero exit and full filesystem equality assertions.",
    "evidence": "test_s4_conflict writes only id and statement. Migration's later independent destination validator rejects this incomplete record even if collision comparison is removed.",
    "lens": "tests",
    "reasoning": {
      "observe": "Read all test_intent_vocabulary.py including beyond initial 400 lines; escalated into intent_migrate.py:21-143.",
      "trace": "Missing destination collision check still reaches existing canonical validation before any writes; incomplete fixture is rejected there.",
      "infer": "Implementation overwriting conflicting valid destination still passes this test.",
      "conclude": "S4 requires two valid conflicting records to distinguish conflict refusal from malformed-record rejection."
    },
    "pass": 2,
    "disposition": "accepted",
    "status": "pending",
    "caused_by": null,
    "voices": [
      {
        "source": "tests",
        "kind": "lens"
      }
    ],
    "id": "11175f90347e8125"
  },
  {
    "id": "7124033e9a0203a8",
    "severity": "P2",
    "file": "src/harness_maker/world.py",
    "line": 145,
    "summary": "`purpose` \ud0a4 \uc874\uc7ac\ub9cc\uc73c\ub85c \ub9c8\uc774\uadf8\ub808\uc774\uc158 \uc644\ub8cc\ub97c \ud310\ub2e8\ud569\ub2c8\ub2e4. \uc0ac\uc6a9\uc790\uac00 \ud504\ub85c\uc81d\ud2b8 \uc815\uc758\ub9cc \uc0c8 \ud615\uc2dd\uc73c\ub85c \ubc14\uafb8\uace0 \uae30\uc874 ledger\ub97c \ub0a8\uaca8\ub450\uba74 \uc9c8\ubb38\uacfc \uce21\uc815\uac12\uc774 \uc9c4\ub2e8 \uc5c6\uc774 \uc0ac\ub77c\uc9c0\uba70 canonical \uc4f0\uae30\ub3c4 \ud5c8\uc6a9\ub429\ub2c8\ub2e4. \uc774\ud6c4 metric \uae30\ub85d\uc740 \ubcc4\ub3c4 \uc800\uc7a5\uc18c\ub97c \ub9cc\ub4e4\uc5b4 \uba85\uc2dc\uc801 migrate\uae4c\uc9c0 \ucda9\ub3cc\ub85c \uc2e4\ud328\ud558\uac8c \ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4. \uae30\uc874 \uc800\uc7a5\uc18c\ub97c \uc77d\uac70\ub098 \ubbf8\uc644\ub8cc \ub9c8\uc774\uadf8\ub808\uc774\uc158\uc744 \uc9c4\ub2e8\ud558\uace0, \uc4f0\uae30\ub294 \uc644\ub8cc \uc804 \uac70\ubd80\ud574\uc57c \ud569\ub2c8\ub2e4.",
    "evidence": "canonical \ud504\ub85c\uc81d\ud2b8 \uc815\uc758\uc640 \uae30\uc874 .claude/world/{assumptions,outcomes}.yaml\uc744 \ud568\uaed8 \uc81c\uacf5\ud55c \uc7ac\ud604\uc5d0\uc11c load_world\ub294 assumptions={}, values=[], errors=[]\ub97c \ubc18\ud658\ud588\uace0, _canonical_project\ub294 True\uc600\uc2b5\ub2c8\ub2e4.",
    "source": "codex",
    "needs_relaxation": false,
    "disposition": "accepted",
    "status": "pending",
    "caused_by": null,
    "voices": [
      {
        "source": "codex",
        "kind": "cross-model"
      }
    ]
  }
]
```

## Confirmation 1: FAIL (one new P1)

Artifact: `16ed3147cfed0ec41a06064d868e19c0c9214294`; base unchanged. All four
groups returned; CLI coverage exercised all seven lenses, missing=[], blocks_approval=false.
Security returned no findings; core and tests repeated the two known P2 findings. Core's
independent functionality voice now also makes the partial-layout P2 consensus-passed
(the frozen cross-model record remains unchanged). No new P0/P1 from those groups.

Concurrency found **4ebc24d2eb82c302**, P1, consensus-passed: a writer resuming after
partial publication can append to the old ledger and make a subsequent migration conflict.
An injected project-write failure left canonical metrics=[1], then a successful writer
produced legacy metrics=[1,2]. This defect was present before round 2; `caused_by: null`,
not an attributed repair regression. Pass 1 ledger: FAIL, nonterminal; duration measured
from frozen artifact timestamp to coverage completion. No source edit occurred during
the pass. Cross-model voters were re-read, not invoked again.

## Confirmation repair (measurement round 3; ordinary iteration count remains 2)

[Fix #3] P1 Writes after interrupted migration prevent migration retry in world.py:196.
Read test_migration_write_failure_preserves_sources_and_can_retry before editing.
The existing test permits a retry and does not require accepting intermediate writes.
Under the checkout lock, reject writes when a legacy project has canonical destinations,
or a canonical project retains legacy fields, ledgers, or records. Migration bypasses
this writer guard so it can finish publication/retirement. Pure legacy and completely
canonical layouts retain their write behavior. Update the inline question resolve caller.
No repository tests changed.

A draft caller rename had incorrect indentation detected by ruff format before validation;
the indentation was immediately corrected. No runtime fix was reverted. External deterministic
reproductions pass for publication failure and retirement failure: rejected metric/record
writes preserve all bytes, retry completes, then the next metric append preserves both rows.
The prior mixed-input and interleaved-process reproductions also remain green.

## Final confirmation: PASS

Confirm-2 artifact: `cb0aebe7c14b8a697aee38d96cece79d3fa6eed8`; base
`d330abff5adf6f090204e9b118dfa45fca359ff1`. All four groups returned and all seven
mandatory lenses were exercised. No new consensus-passed P0/P1. Security and concurrency
returned no findings; core and tests retained the known P2 findings. The concurrency owner
confirmed the interruption/retry P1 resolved. Core independently checked eight layout states.
Source, tests and SPECs remained byte-identical to this artifact through confirmation.
Only final REVIEW/PLAN evidence was added afterwards. No third pass or second oracle invocation.

### Final lifecycle

| ID | Severity | Status | Remaining behavior / repair |
|---|---|---|---|
| 5472a8d9b9b43d42 | P1 | resolved | Mixed legacy question writes refused before mutation |
| dea465ec4a4aa4d9 | P1 | resolved | Stable shared lock serializes migration and leaf writers |
| 4ebc24d2eb82c302 | P1 | resolved | Partial publication/retirement refuses writers until migration retry |
| 11175f90347e8125 | P2 | pending, consensus-passed | Invalid destination fixture does not discriminate valid-record collision protection |
| 7124033e9a0203a8 | P2 | pending, consensus-passed | Manually converted project still hides legacy ledgers on reads without diagnosis; writes are now refused |

The last P2 gained a functionality lens voice during confirmation, so it is no longer
manual-only in the current voting set. The round-1 frozen cross-model records retain their
original content and identities. Neither P2 is eligible for this A/B review's severe-only
repair queue. No claim that the remaining read-omission defect is resolved.

## Review Iteration Summary

| Iteration | Grade | Fixes applied | Pending | New severe |
|---|---|---|---|---|
| 1 (initial) | B | 0 | 4 | 2 |
| 2 | A | 2 | 2 | 0 |
| Confirmation 1 | B | 0 | 3 | 1 |
| Separate confirmation repair (measurement round 3) | A | 1 | 2 | 0 |
| Confirmation 2 | A | 0 | 2 | 0 |

Final grade: A. Ordinary iterations used: 2 / 3; one separately budgeted confirmation repair.
Exit reason: converged. Status: APPROVED. human_review_needed: false.
Fix #3: Applied · caused_by=none. Progress: one pending→resolved in confirmation repair.
Oscillation CLI returned []. Round-3 re-review: skipped — churn 0.08 < 0.30.
This skip was followed by mandatory full confirmation, not treated as a clean re-review.
Counters: unreviewed_fix_count=1 (terminal repair's selective loop re-review was skipped;
full confirmation subsequently covered it), regression_attributed_n=0, attribution_unknown_n=0.

## Validation and limits

- Repair round 2: 146 focused tests and 1,272 dependency-selected tests passed.
- Confirmation repair: the same dependency-selected 1,272 tests passed (exit 0).
- Final Ruff checks and formatting passed; strict mypy passed for 775 source files.
- External probes: mixed input refusal, interleaved process append, publication-failure retry,
  and retirement-failure retry all passed. Rejected writes preserved all bytes.
- Repository tests were not edited during review. Probes are supplemental evidence, not
  replacement repository regression coverage.
- Execute's earlier full suite had 9,096 passed, 100 skipped, 3 xfailed. It predates these
  review fixes; this review used the dependency-selected suite on the final tree.
- Final intent status remains readable. No branch commits, push or worktree landing.

## 📏 Size & Complexity (separate confirmation repair)

| File | LOC | Cyclomatic | Max nesting | Status |
|---|---|---|---|---|
| src/harness_maker/intent_cli.py | 193 → 193 | 46 → 46 | 10 → 10 | measured |
| src/harness_maker/world.py | 2166 → 2183 | 414 → 418 | 5 → 5 | measured |
| work-docs/REVIEW-intent-vocabulary-and-owners-2026-09-21.md | 379 → 412 | null → null | null → null | not-python |

CLI churn: 0.08009708737864078; max REVIEW report; 3 measurable files, 0 excluded.
Source churn: world.py 0.011452130096197893; intent_cli.py 0.010362694300518135.
Numbers are reported from CLI endpoints before final evidence append, not estimates.
