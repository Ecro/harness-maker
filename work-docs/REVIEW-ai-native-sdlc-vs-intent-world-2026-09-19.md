---
type: review
task_slug: ai-native-sdlc-vs-intent-world
status: CHANGES_REQUESTED
created: 2026-09-19
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 6e185687caa0
review_base: fb8bfaca
grade: A
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/e2e/test_autopilot_chain_e2e.py
    - tests/unit/test_autopilot_caps_entry_and_slug.py
    - tests/unit/test_autopilot_unlimited_caps.py
    - tests/fixtures/autopilot_caps_baseline.json
    - tests/unit/test_spec_machine_oracle.py
    - tests/unit/test_spec_machine_check_all.py
    - tests/render/test_render_wrapup_delegation.py
    - tests/structural/test_instruction_preservation.py
    - tests/render/test_render_roundtrip_collapse.py
    - tests/structural/test_autopilot_gate_render.py
    - tests/structural/test_command_size_budget.py
  scenario_misses: []
  task_slug: ai-native-sdlc-vs-intent-world
  computed_at: 2026-09-19T11:21:48Z
---

# REVIEW — ai-native-sdlc-vs-intent-world (2026-09-19)

## 🎯 Round 1 Summary

- **Grade A** (consensus-passed P0=0, P1=0 counting; P2=2). `blocks_approval: false` — all 7 lenses exercised (4 dispatches, run `6e185687caa0`).
- **`human_review_needed: true`** — three `accepted` Codex P1 findings are `manual-only` (single cross-model voice; K=2 for cross-model). All three were reproduced by a main-loop probe or confirmed by source read — they are real defects, not noise. They carry no reviewer `suggestion`, so they are not auto-fix eligible under the rules.
- Fixes pending: none auto-eligible (the two consensus-passed `accepted` findings are P2, outside the P0/P1 queue at grade A).

## 🔍 Drift Findings

`scope_violation` — the files above are outside every PLAN phase's scope list. All are pinned
tests/fixtures that moved **because of IRR-003** (spec became judgment-gated → autopilot caps
baseline, chain e2e and gate golden change) and the new approval-status call in wrapup (round-trip
and size budgets, instruction-preservation allowlist). Each was recorded in the PLAN phase status
notes at the time it moved; none changes production behaviour beyond the SPEC. No incomplete phase.

## ✅ Consensus Findings

| id | sev | lens | location | summary | disposition |
|---|---|---|---|---|---|
| b93fe2fcf26b800d | P1 | concurrency | worktree.py:3501 | finalize hold pre-pass runs before capture/merge; external edit between check and merge is unseen | rejected — AC-006 ("checked for all worktrees before any merge"); the check reads the same working tree capture commits, so only an external concurrent writer opens the window |
| df526fca9797d0f9 | P2 | security | spec_machine.py:1666 | approval identity is git `user.name` (self-certifiable) | rejected — AC-001 (identity = base-root user name; SPEC non-goal: stamp records the flow, not a proven human) |
| ae6574c2dd6bbc6f | P2 | security | spec_machine.py:1520 | `slug` not checked for traversal/absolute path in `_resolve_checkout` | accepted — carried (P2) |
| 6b8af140dc367a55 | P2 | concurrency | spec_machine.py:1666 | `approve()` unlocked read-modify-write can race `mark_tested`/`mark_judged` | accepted — carried (P2). Pass 2 dropped it as pre-existing; `approve()` is new in this diff, so it was reinstated |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | sev | location | summary | disposition |
|---|---|---|---|---|
| 40bed418653412bf | P1 | worktree.py:5301 | task-land skips the hold when the worktree dir is gone but `hm/<slug>` remains, then squashes | accepted (source read) |
| 3c39e62dd526ff4b | P1 | spec_machine.py:1474 | `GoldenRow` lacks `extra="allow"`: unknown row keys are dropped from the hash and deleted on write | accepted (probe: hash unchanged) |
| 1e97a35571722762 | P1 | spec_machine.py:1609 | non-ASCII SPEC paths are quoted by git (`core.quotePath`) and missed by the change set | accepted (probe: `SPEC-한글` not found) |
| ca2104efdf3aa515 | P1 | spec_machine.py:1629 | a git failure in the change-set lookup makes finalize land with no SPEC check | unresolved — PLAN ADR-003 chose the slug-only fallback with a notice; reversing it is a human call (excluded from `unverified_severe` by the provenance carve-out) |

## 🤝 Disagreements

- Pass 1 core raised "approve() never calls validate()" (P1); Pass 2 core dropped it: SPEC Revision 1 bounds `malformed` to the enumerated cases and AC-004 scopes item-level checks to `validate`.
- Pass 1 concurrency rated the finalize TOCTOU P0; Pass 2 adjusted it to P1 (ADR-005 chose the single pre-pass to prevent partial multi-repo land).

## 🔒 Confirmation pass 1 (frozen `50249d88`, span `fb8bfaca..50249d88`)

All 7 lenses exercised (`blocks_approval: false`). New findings (ids absent from round 1):

| lens | sev | location | summary | disposition |
|---|---|---|---|---|
| security | **P0** | spec_machine.py:1510 | land hold read `spec.dir` from the gated checkout's own `harness.yaml`; repointing it made the real SPEC invisible (`no_spec` → land ok) | accepted — **fixed** in repair round |
| concurrency | **P1** | worktree.py:5301 | task-land evaluated the hold before the already-landed check | accepted — **fixed**. Note: the reviewer's trigger (SPEC edited in the worktree after the squash) does not reach it — `_capture_pending_in_worktree` commits the edit, so the retry is a real unlanded change and holding is correct (verified by a test that failed on exactly that). The reachable case is content landed into base by another path; that is what the regression test pins |
| security | P2 | spec_machine.py:1472 | `exclude_defaults=True` hides a field reset to its default | rejected — AC-002 (a new defaulted field must not change the hash; a present field reset to default leaves the dump, so the hash changes) |
| consistency | P2 | spec_machine.py:1564 | `invalid` hold carries no detail | accepted — **fixed** (`edited after approval` / `exempt with irreversible decisions`) |
| design | P2 | spec_machine.py:1639 | hold lines do not name the diverged field | accepted — carried (no concrete replacement) |
| tests | P2 | tests/unit/test_spec_approval.py:154 | exempt test never asserts `approved_by is None` | accepted — **fixed** (the finding's own target is the test) |

Confirm-1 was dirty (new consensus-passed P0 + P1) → one repair round, then confirm-2.

## 🔧 Repair round (after confirm-1)

- [Fix #1] P0 `approval_state` / `_changed_spec_slugs` now search the **base's** configured SPEC dir first, then the checkout's (`_spec_dirs`). Probe: repointed `spec.dir` → `hold` (was `no_spec`/ok).
- [Fix #2] P1 task-land computes `already` first; the hold runs only when the content is not yet in base.
- [Fix #3] P2 (round-1 `ae6574c2dd6bbc6f`) `approval_state` refuses a slug that is not a plain name → `malformed` (hold).
- [Fix #4] P2 `invalid` states carry a `detail`.
- [Fix #5] P2 exempt test asserts `approved_by is None`.
- Regression tests added: `test_task_land_holds_when_the_checkout_repoints_spec_dir`, `test_task_land_teardown_of_already_landed_content_is_not_held` — both fail on the confirm-1 freeze and pass after the fix.
- Not pinned: the `review_churn pin r{N}-pre` step was skipped (edits began before the pin); the churn for this round is the diff `refs/hm-freeze/v1/ai-native-sdlc-vs-intent-world-confirm-1..confirm-2`.
- Not touched: the manual-only Codex P1s (`40bed418653412bf`, `3c39e62dd526ff4b`, `1e97a35571722762`) and the unresolved `ca2104efdf3aa515` — not in the repair queue (single cross-model voice); status stays `pending`.

## 🔒 Confirmation pass 2 (frozen `991e4491`, span `fb8bfaca..991e4491`)

All 7 lenses exercised. Confirm-1 fixes verified in place by the concurrency and core lenses.

| lens | sev | location | summary | disposition |
|---|---|---|---|---|
| security | P1 | spec_machine.py:1510 | `spec.dir` joined unvalidated; an absolute value escapes the checkout | rejected — AC-005 row 1. The base's dir is searched first inside the checkout, so a decoy outside it is read only when the SPEC is absent from that dir — where the state is already `no_spec` / land ok. The decoy yields nothing beyond deleting the SPEC (the accepted "agent can act as the DRI" limitation). Hardening (reject absolute / `..` in `spec.dir`) is a cheap follow-up |
| consistency | P2 | spec_machine.py:1552 | malformed detail keeps only the exception class name | accepted — carried |
| tests | P3 | tests/unit/test_land_hold.py:245 | repointed-`spec.dir` test does not assert the hold line | accepted — carried |
| tests | P3 | tests/unit/test_land_hold.py:161 | golden row `hold_in` is not read by the builder | accepted — carried |

**Outcome: CHANGES_REQUESTED.** Confirm-2 surfaced one new `consensus-passed` P1. Its AC-cited
rejection clears the grade (A), but C3's arm is worded on the tag ("zero new consensus-passed
findings at P0 or P1"), not the disposition; the stricter reading was taken. No third pass.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 3 manual-only P1 + 1 unresolved P1, 2 P2 | — |
| confirm-1 repair | — | 5 | — | 2 severe (P0, P1), both fixed |
| confirm-2 | A     | —             | 1 P1 (AC-rejected), 1 P2, 2 P3 | 1 severe |

Final grade: A
Iterations used: 1 / 3 (+ one confirmation repair round)
Exit reason: converged (grade) — terminal status set by the confirm-2 arm
Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0

### For the DRI

1. The three Codex P1s (`40bed418653412bf` missing-worktree hold skip, `3c39e62dd526ff4b` GoldenRow extras, `1e97a35571722762` non-ASCII paths) are reproduced real defects left unfixed only because a single cross-model voice is not auto-fix eligible.
2. `ca2104efdf3aa515`: keep ADR-003's slug-only fallback on git failure, or fail closed.
3. Confirm-2 P1 (`spec.dir` absolute path): accept the AC-005 rejection, or add the hardening.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

- id: ca2104efdf3aa515
  source: codex
  severity: P1
  file: src/harness_maker/spec_machine.py
  line: 1629
  summary: "Git 조회 실패가 land 허용으로 처리됩니다. finalize는 지정 slug 없이 이 함수를 호출하므로 diff 또는 ls-files가 타임아웃·오류로 실패하면 모든 SPEC 검사가 사라집니다. 이후 capture/merge가 성공하면 invalid SPEC도 그대로 반영됩니다. 조회 실패는 빈 변경 집합과 구분하여 land를 중단해야 합니다."
  evidence: "land_states()는 _changed_spec_slugs()가 None을 반환하면 found=[]로 대체합니다. Git 실패를 모의한 읽기 전용 실행에서도 hold_lines(land_states(...))는 []였습니다."
  needs_relaxation: false
  disposition: unresolved
  oracle_result: "Confirmed by probe: git failure makes land_states return []. PLAN ADR-003 sanctioned the slug-only fallback; human call."
  status: pending
- id: 40bed418653412bf
  source: codex
  severity: P1
  file: src/harness_maker/worktree.py
  line: 5301
  summary: "task worktree를 제거하거나 다른 위치로 옮기고 hm/<slug> 브랜치를 남기면 task-land의 승인 검사를 우회할 수 있습니다. 브랜치에 미승인 irreversible decision이 있어도 기존 경로가 없다는 이유로 검사를 생략하고 squash한 뒤 브랜치를 삭제합니다. checkout이 없는 복구 경로도 실제 브랜치 내용을 검사하거나 land를 거부해야 합니다."
  evidence: "승인 검사는 if wt.is_dir() 안에만 있지만, 이후 already 판정과 git merge --squash는 worktree가 없어도 실행됩니다."
  needs_relaxation: false
  disposition: accepted
  oracle_result: "worktree.py:5301 hold is inside `if wt.is_dir()`; squash proceeds when the worktree dir is missing."
  status: pending
- id: 3c39e62dd526ff4b
  source: codex
  severity: P1
  file: src/harness_maker/spec_machine.py
  line: 1474
  summary: "모델을 거친 해시는 golden_table 행의 미지정 필드를 누락합니다. 이 위치의 authored extension을 승인 후 수정해도 approved 상태가 유지되고, approve/mark-tested 저장 시 해당 데이터가 삭제됩니다. 전체 YAML의 unknown key도 해시와 round-trip에 포함한다는 AC-002 계약을 위반합니다. 현재 unknown-key 테스트는 최상위와 AC 수준만 확인하여 이 결함을 놓칩니다."
  evidence: "GoldenRow에는 extra=\"allow\"가 없습니다. ac[0].golden_table[0].extension을 before→after로 바꾼 두 모델의 해시가 같았고, model_dump 결과에서 extension이 사라졌습니다."
  needs_relaxation: false
  disposition: accepted
  oracle_result: "Probe: golden row extra key change leaves hash unchanged; GoldenRow lacks extra='allow'."
  status: pending
- id: 1e97a35571722762
  source: codex
  severity: P1
  file: src/harness_maker/spec_machine.py
  line: 1609
  summary: "비ASCII 이름의 SPEC은 변경 집합에서 누락됩니다. SpecMachine은 한국어 같은 Unicode 영숫자 slug를 허용하지만 기본 Git 설정은 해당 파일명을 인용합니다. 따라서 execute-<uuid>에서 SPEC-한글.machine.yaml의 승인을 무효화해도 finalize는 이 SPEC을 발견하지 못하고 merge합니다. Git 경로를 NUL 구분으로 받아 원래 파일명을 보존해야 합니다."
  evidence: "Git 경로를 -z 없이 받아 startswith(prefix)로 비교합니다. Git이 반환하는 따옴표 및 octal escape가 포함된 한국어 SPEC 경로를 입력한 재현에서 발견 slug는 []였습니다."
  needs_relaxation: false
  disposition: accepted
  oracle_result: "Probe: untracked SPEC-한글.machine.yaml not found; git output lacks -z so quotePath quotes it."
  status: pending


---

# Re-review after the DRI's fix decision (run `6b2de2ca03c8`)

The DRI chose (2026-09-19): fix the three Codex P1s, make a git failure hold (PLAN ADR-003
amended), and reject absolute / `..` `spec.dir`. Applied, then re-reviewed. Codex invoked once.

## Round 1 — grade D

| id | sev | source | summary | disposition |
|---|---|---|---|---|
| dffc85ca09b90f20 | **P0** | security | approval never checked `model.spec_slug` against the file name: an approved SPEC copied under another slug read `approved` (copy-as-template path, not only adversarial) | accepted — **fixed** (round 2): mismatch → `invalid` |
| d00f285b4747ed61 | P1 | concurrency | missing-worktree probe runs git inside the merge fence, past `_FENCE_TIMEOUT`'s stated budget | accepted in round 1, **re-adjudicated in round 3 → rejected** (`docstring:…:_FENCE_TIMEOUT`, below) |
| f4caab0350d4b649 | P2 | security | `approve()` unlocked read-modify-write vs `mark_tested` | accepted — carried |
| 76f75a424b5f8a49 | P1 | codex | moved `spec.dir` hid a changed SPEC left in the old dir (worktree off) | accepted (PIDA) — fixed: per-file discovery |
| 2b846692d8e70b68 | P1 | codex | first-match dir masked a changed same-slug SPEC in another dir | accepted (PIDA) — fixed: every changed `(dir, slug)` evaluated |
| 338c2fb6290c13c3 | P1 | codex | `./specs/` never matched git's `specs/…` paths; finalize found nothing | accepted (PIDA) — fixed: `_spec_dir` normalised |

**Process deviation (recorded, not hidden):** the three Codex fixes were applied while Pass 1
reviewers were still reading, so Pass 1 did not review one frozen artifact. Each fix has a
regression test that failed on the pre-fix source; rounds 2–3 re-reviewed the result.

## Round 2 — grade B

- Fixes: P0 `spec_slug` binding; P1 moved the missing-worktree probe **outside** the fence, reusing
  it inside only if the branch tip was unchanged.
- Re-review: security 0 findings. Concurrency: P1 — the base could move between probe and fence
  (fixed by also pinning base HEAD); P2 — probe path always named `checkout` (fixed: unique name).

## Round 3 — grade B, cap reached

- Concurrency: P1 — pinning base HEAD does not pin the base's **uncommitted** `.claude/harness.yaml`
  (the dirty-base guard forgives `.claude/`), so a stale probe could still be reused.
- **Resolution — revert to the in-fence probe.** Each out-of-fence pin surfaced another input to
  pin (branch tip → base HEAD → uncommitted base config). The premise of round-1 P1 was weak:
  `_FENCE_TIMEOUT` (360 s) is sized for *finalize's* stash (300 s) + merge (60 s); task-land's
  **worktree-present** path already runs capture + the same `land_states` git calls inside the
  fence, and the missing-worktree path has no capture, so its in-fence probe (worktree add +
  4 listing calls + remove) is the same order of cost. In-fence reads live state under the lock —
  no staleness class at all. The round-2/3 pin findings are **stale** (their code is gone); the
  round-1 fence finding is **rejected** with a docstring authority, which by rule still counts
  toward the grade and sets `human_review_needed`.
- The revert itself was not re-reviewed (cap). Tests: land/approval suites 112 passed; full
  suite on the final code: 8957 passed, 100 skipped, 3 xfailed, rc=0.

## Review Iteration Summary (run `6b2de2ca03c8`)

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | 3 (Codex, mid-Pass-1) | P0, P1, P2 | — |
| 2         | B     | 2 | P1 (base drift), P2 | 2 |
| 3         | B     | 2 + revert | P1 fence (docstring-rejected), P2 | 1 (now stale) |

Final grade: B
Iterations used: 3 / 3
Exit reason: cap-exhausted
Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 1 (the in-fence revert) · prior-fix 2 (round-2 fix → round-3 finding) · unattributed 0

### For the DRI

1. Accept the in-fence probe (fence P1 rejected: same cost class as the worktree-present path), or
   ask for the fence budget to be raised explicitly.
2. Carried P2s: `approve`/`mark_tested` unlocked RMW; hold lines do not name the changed field;
   malformed detail keeps only the exception class name.
