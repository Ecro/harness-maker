---
type: plan
task_slug: mutation-survivors-and-approval-p2s
status: complete
created: 2026-09-20
tags: [harness-maker, plan, python, spec-approval, concurrency, mutation-testing]
spec: "[[SPEC-mutation-survivors-and-approval-p2s]]"
interview_rounds: 11  # numbered question rounds in the transcript, across three sittings
adrs: 5
validator_outcome: MAJOR_REVISION_TERMINAL
summary: "Per-field digests name what moved, one shared RMW lock, and tests for the branches mutation found"
spec_need_verdict: add
spec_need_target: mutation-survivors-and-approval-p2s
---

# PLAN: mutation-survivors-and-approval-p2s

## 🎯 Executive Summary

**TL;DR.** Three carried review findings and the untested branches the first real mutation run
named, in one pass: the approval stamp learns per-field digests so a hold can say *which* field
moved, the three machine-SPEC writers stop racing each other, a malformed SPEC reports its
validation error, and the branches mutation found get tests.

**What / Why.** `SPEC-ai-native-sdlc-vs-intent-world` landed on 2026-09-19 with three P2s accepted
as risk. The mutation measurement that followed (62.3%, `work-docs/MUTATION-ai-native-sdlc-vs-intent-world-2026-09-20.md`)
turned the vaguest of them into a list: 68 surviving mutants inside the approval surface, of which
about 25 are real logic gaps rather than message text.

**Key decisions.** Digests live inside the stamp, which the hash deny-list already excludes, so
adding them releases no existing approval (ADR-001). The lock is extracted from `world.py` rather
than copied (ADR-002). A stamp without digests keeps its verdict and says so (ADR-003). Mutation
is measured over `io_utils.py` and recorded, but gates nothing — the module scores 44.7% on helpers
this task does not touch (ADR-004).

**Estimated impact.** Five files: `io_utils.py`, `world.py`, `spec_machine.py`, and two existing
test modules. No template renders, no CLI surface change, no schema version bump.

## 📚 Prior Work

- `work-docs/MUTATION-ai-native-sdlc-vs-intent-world-2026-09-20.md` — the survivor list this plan
  works from, and the two tool faults (`.mutmut-cache` tracked; mutmut counting only `rc == 1` as
  killed) fixed in `865e3ef5` before it could be trusted.
- `[fail:test] fix-introduced-defect-passes-all-gates` (count:13). Its 2026-09-17 entry is this
  task's shape exactly: a lock fix introduced three P1s — the lock file in a **tracked** directory,
  an unguarded fallback, and **no test exercising concurrent acquisition**. Phase 1 puts the lock
  under `.claude/observability/` (gitignored churn) and AC-004 is a real two-writer test.
- `[fail:test] assertion-invariant-over-named-dimension` (count:16). AC-001/AC-002 are property
  criteria; each must bind to the real digest map, not to a rebuilt copy of it.
- `[fail:design] absent-case = feature black hole` (count:8, CLAUDE.md). A stamp with no digest map
  is that absent case; ADR-003 defines it rather than letting it no-op.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Hold diagnostics | Contract shape | How does a hold name the changed field? | stamp digests / git diff hint / message only | stamp digests | `approval` is deny-listed, so no re-approval | ADR-001 |
| 2 | Lock implementation | Architecture | Where does the RMW lock live? | shared helper / copy / none | shared helper in `io_utils` | one policy, one source | ADR-002 |
| 3 | Mutation scope | Testing depth | How far does this task chase the score? | tests only / narrow paths / re-measure | tests only, scope unchanged | narrowing the other SPEC releases its stamp | ADR-004 |
| 4 | Objective link | Scope boundaries | Which objective does this serve? | LOOP-OPT-IN / none / draft new | none | the only candidate is about render bytes | — |
| 5 | Digest granularity | Contract shape | How fine is the digest map? | top-level+AC / top-level / inside-AC | top-level + per-AC | "ac changed" is where most edits land, so it says nothing | ADR-001 |
| 6 | Absent case | Failure handling | What does a pre-digest stamp do? | keep verdict + explain / invalid / silent | keep verdict + explain | `invalid` would release every existing stamp | ADR-003 |
| 7 | Unlockable filesystem | Failure handling | What happens where flock is unavailable? | proceed unlocked / refuse | proceed unlocked | matches the code being extracted | ADR-005 |
| 8 | Test scope | Testing depth | Which survivors get tests? | logic only / all 68 / hash+state only | logic branches only | pinning message text makes wording fixes red | — |
| 9 | Phase entry | Implementation phasing | Proceed to decomposition? | proceed / lock design first / full interview | proceed | contracts settled in the SPEC interview | — |
| 10 | Mutation gating | Testing depth | The tier-2 bar of 70 missed: `io_utils.py` measured 44.7%. What now? | tier 3 + record / kill 22 survivors / drop the phase | tier 3 + record | `gate()` reads the tier floor, never the SPEC's `mutation_threshold` | ADR-004 |
| 11 | SPEC re-approval | Scope boundaries | Fixing AC-001/AC-002 edits the SPEC and releases the DRI stamp | fix + re-approve / gloss it in the PLAN | fix + re-approve | a contract that disagrees with its implementation is the defect, not the stamp | ADR-001 |

Rounds 1 and 5–8 were asked during the SPEC interview for this same slug and are recorded here
because they decide the implementation, not only the acceptance criteria. Rounds 10 and 11 came
after the validator pass: both were forced by findings, and both edited the SPEC, so the stamp was
released and re-issued at `6983950a…`.

## 📐 Architecture Decision Records

### ADR-001: The approval stamp carries per-field digests
**Status:** Accepted (2026-09-20, via /hm:plan interview)
**Context:** A hash mismatch tells the operator the SPEC changed but not what changed, so the only
way to decide whether to re-approve is to diff the file by hand.
**Decision:** `approve` writes a `field_hashes` map into the stamp, derived from the same payload
`approval_content_hash` consumes. **The key set is `set(payload) - {"ac"}` plus one key per AC id.**
`ac` is itself a hashed top-level field, so carrying both it and its expansion would make a single
AC edit name two fields — `ac` and `AC-00N` — which AC-002 forbids. It is expanded, never kept
beside its expansion.
**Consequences:**
- ✅ `approval` is in `HASH_DENYLIST_TOP`, so the map is not itself hashed and no existing approval
  is released by this change.
- ✅ `SpecApproval` is a plain pydantic model (`extra="ignore"`), so a 0.58.0 reader ignores the new
  key rather than failing.
- ⚠️ The stamp grows by roughly one line per AC.
- ⚠️ Two derivations of "what is hashed" must not drift, which is why they share one payload builder
  rather than two deny-list walks.
**Rejected alternatives:**
- A git-based diff hint — Rejected because an approval stamped before the SPEC was committed has
  nothing to diff against, which is the normal case during a task.
- Message-only guidance ("run `git diff specs/…`") — Rejected because it moves the diagnosis back to
  the operator, which is the finding.
**Source:** Interview #1, #5

### ADR-002: One read-modify-write lock, extracted to `io_utils`
**Status:** Accepted (2026-09-20, via /hm:plan interview)
**Context:** `approve`, `mark_tested` and `mark_judged` each load, mutate and atomically rewrite the
same `.machine.yaml`. `atomic_write` makes the replace atomic, not the read-modify-write around it,
so a wrapup's write-back and a concurrent approval discard one another. `world._rmw_lock` already
solves this for the intent layer.
**Decision:** Move that helper to `io_utils.rmw_lock(lock_path, *, timeout)`; `world.py` and all
three `spec_machine` writers call it. **The caller computes `lock_path`** — the helper never derives
it from the guarded file, because `world._rmw_lock`'s `path.parent.parent / "observability"` form is
correct only for `.claude/intent.yaml`. For a machine SPEC at `specs/SPEC-<slug>.machine.yaml` that
same expression yields `<repo>/observability/`, which is **not** gitignored. `spec_machine` therefore
builds `resolve_base_root(yaml_path.parent) / ".claude" / "observability" / f".hm-spec-{stem}.lock"`
— the base-root resolver `approve` already uses, so a worktree and a non-default `spec.dir` both land
in the right place. On timeout the helper raises `io_utils.LockTimeout`, which the three
`spec_machine` writers translate into `ApprovalError` so `_run_approve`'s existing `except` clause
still prints `approve: …` instead of a traceback; `world.py` keeps mapping it to `WorldError`.
**Consequences:**
- ✅ One policy for lock placement, timeout and the unlockable-filesystem branch.
- ✅ The lock file sits under `.claude/observability/`, which is gitignored churn — the tracked-lock
  mistake recorded on 2026-09-17 cannot recur.
- ⚠️ Touches `world.py`, which is working code with its own tests.
- ⚠️ Two error translations exist (`LockTimeout` → `ApprovalError` / `WorldError`) rather than one
  shared exception, because neither module may import the other's error type.
**Rejected alternatives:**
- Copying the pattern into `spec_machine` — Rejected because a second source of truth for the lock
  policy is the failure the wiki records, and the two copies would diverge at the first fix.
- Leaving it unlocked and documenting the race — Rejected because the wrapup write-back and a
  concurrent approval are the harness's own normal path, not an exotic case.
**Source:** Interview #2, #7

### ADR-003: A stamp without digests keeps its verdict and says why
**Status:** Accepted (2026-09-20, via /hm:plan interview)
**Context:** Every stamp written before this change has no digest map — including the one this
project landed on 2026-09-19.
**Decision:** The hash comparison is unchanged. When the map is absent and the content moved, the
detail states that the fields cannot be named because the stamp predates digests.
**Consequences:**
- ✅ No existing approval is released.
- ✅ The absent case is a statement rather than a silent omission.
- ⚠️ Two detail shapes exist until old stamps are re-approved naturally.
- ⚠️ A 0.58.0 `mark-tested` loads a newer stamp, drops `field_hashes` through pydantic's
  `extra="ignore"`, and re-dumps the file without it. The verdict is unaffected (the hash is not
  touched) but the map is gone, so the detail says **"this stamp carries no digest map"** rather
  than "predates digests" — the wording must not assert when the stamp was written.
**Rejected alternatives:**
- Treating a digest-less stamp as `invalid` — Rejected because it releases every approval in every
  consuming project at once, for a diagnostic improvement.
- Naming no fields and explaining nothing — Rejected because the operator cannot tell the absent map
  from a bug in the naming.
**Source:** Interview #6

### ADR-004: Mutation is informational (tier 3), measured over `io_utils.py`
**Status:** Accepted (2026-09-20, revised after the validator pass and a baseline measurement)
**Context:** The first draft declared tier 2 (floor 70) over `io_utils.py`, on the argument that a
tier-1 bar over the 1938-line `spec_machine.py` (62.5%) would score the module rather than the
change. The validator observed that the same argument applies to the replacement, and asked for the
number before the bar. Measured 2026-09-20: `io_utils.py` is **44.7%** — 85 mutants, 38 killed, 47
survived, almost all of them in pre-existing helpers (`load_harness_yaml`, `strip_retired_keys`,
`atomic_append`).
**Decision:** Tier 3 — the run is taken and recorded, and gates nothing. `mutation_threshold: null`.
The oracles that bind this change are the property criteria AC-001, AC-002 and AC-004.
**Consequences:**
- ✅ The measurement still happens and lands in a `MUTATION-*.md` report, so the number is on record
  rather than asserted.
- ✅ No phase can be passed or failed by a score about helpers this task never touches.
- ⚠️ Neither module's mutation coverage improves as a result of this task.
- ⚠️ Tier is hashed, so this revision released the DRI stamp; the SPEC was re-approved at
  `6983950a…`. That is the approval gate working, and it is recorded rather than worked around.
**Rejected alternatives:**
- Tier 2 with the threshold lowered — Rejected because it is not available: `gate()` calls
  `threshold_for(tier, baseline=None)`, which returns the **tier floor**; the SPEC's
  `mutation_threshold` field is documentation and is never read by the gate.
- Tier 2 kept, with tests added until 70 — Rejected because reaching 60 kills of 85 means roughly 22
  new tests for helpers outside this task's subject.
- Dropping the measurement — Rejected because an unmeasured mutation field is the exact gap this
  task exists to close.
**Source:** Interview #3; plan-validator pass 1 (critical), baseline measured before deciding

### ADR-005: An unlockable filesystem proceeds unlocked
**Status:** Accepted (2026-09-20, via /hm:plan interview)
**Context:** `flock` returns `ENOSYS`/`EOPNOTSUPP` on some filesystems, and refusing to write there
would make `approve` unusable on them.
**Decision:** Keep `world._rmw_lock`'s branch verbatim: on those errnos, proceed without the lock.
**Consequences:**
- ✅ One policy across both callers, which is the point of extracting the helper.
- ⚠️ On such a filesystem the lost-update window remains; the SPEC says so rather than implying
  protection everywhere.
**Rejected alternatives:**
- Refusing the write — Rejected because it diverges from the caller being extracted and would break
  writes on filesystems where the harness already works.
**Source:** Interview #7

## 🏗️ Technical Design

**Current state.** `approval_content_hash` (`spec_machine.py:1476`) dumps the model with
`exclude_defaults=True`, pops `HASH_DENYLIST_TOP` and per-AC `HASH_DENYLIST_AC`, and hashes the
canonical JSON. `approve` clears `model.approval`, computes that hash, writes the stamp and calls
`_dump_machine_yaml` → `atomic_write`. `mark_tested` and `mark_judged` take the same
load-mutate-dump path. `approval_state_of` compares the recomputed hash to the stamp and returns
`invalid` with `detail="edited after approval"`. `hold_lines` already interpolates `detail`, so
naming fields needs no change there. `world._rmw_lock` (`world.py:1214`) is the lock to extract.

**Affected components.**
| Component | Change |
|---|---|
| `io_utils.rmw_lock` | new — the extracted context manager |
| `world._rmw_lock` | delegates to it, keeping its lock-path and error mapping |
| `spec_machine._hash_payload` | new — the single deny-list walk both consumers read |
| `spec_machine.approval_content_hash` | derives from `_hash_payload`; output unchanged |
| `spec_machine.field_digests` | new — the per-field map |
| `spec_machine.SpecApproval` | gains `field_hashes: dict[str, str] \| None = None` |
| `spec_machine.approve` | wrapped in the lock; **writes** `field_hashes=field_digests(model)` into the stamp it constructs |
| `spec_machine.mark_tested` / `mark_judged` | wrapped in the lock; an existing stamp's map is carried through untouched |
| `spec_machine._run_approve` | keeps its four-key JSON output — `field_hashes` is excluded explicitly |
| `spec_machine.approval_state_of` | names changed fields; carries the validation error |

**Data flow.** `_hash_payload(model)` → canonical dict. `approval_content_hash` hashes it whole;
`field_digests` hashes each entry separately. At read time, `approval_state_of` recomputes both: the
whole hash decides the verdict (unchanged), the per-field map decides the wording.

**The comparison is a three-way key-set diff, not an intersection.** `model_dump(exclude_defaults=True)`
omits any field sitting at its default, so the key set is content-dependent: setting `mutation_runner`
from null adds a key, clearing it removes one, and adding or deleting an AC does the same. An
implementation that iterates the stamp's keys alone reports **no changed field** for a pure addition —
which is the silent outcome ADR-003 rejected. So the detail names `added` / `removed` / `changed`
separately, and the added-key case gets its own test even though AC-002's input domain covers only
in-place edits.

**API changes.** `SpecApproval` gains one optional field and `io_utils` gains one helper. No CLI
flag and no schema version bump — `field_hashes` lives inside a deny-listed block, so v3 files
without it stay valid.

**The CLI's output is NOT part of that extension.** `_run_approve` prints
`json.dumps(stamp.model_dump(mode="json"))`, so a new model field would appear as a fifth key on
every `hm spec_machine approve` run, `null` included. The SPEC's IRR-001 authorises a disk-format
extension, not a change to what the command prints, and nothing in the interview asked for one. So
`_run_approve` dumps the four established keys explicitly and a test pins that key set. A later task
may decide to surface the map on the CLI; it would be its own decision, with its own record.

## 📝 Implementation Plan

### Phase 1 — One shared read-modify-write lock
**Status:** DONE
- `depends_on`: []
- `parallel_group`: serial-lock
- `merge_hazards`: `world.py` is shared with the intent layer; its tests must stay green
- **Scope in:** `src/harness_maker/io_utils.py`, `src/harness_maker/world.py`,
  `src/harness_maker/spec_machine.py`, `tests/unit/test_spec_approval.py`
- **Scope out:** every template, every CLI surface
- **Exit criterion:** `uv run python -m pytest -x tests/unit/test_io_utils.py tests/unit/test_spec_approval.py tests/unit/test_world_outcomes.py tests/unit/test_world_withdrawal.py` green, including the new two-writer test (AC-004), the unlockable-filesystem test (AC-005), a lock-timeout test asserting `ApprovalError` reaches `_run_approve`, and an assertion on the **literal** lock path `<base>/.claude/observability/.hm-spec-SPEC-<slug>.machine.lock` — a prose claim that it is gitignored is what the 2026-09-17 failure had
- **Risk:** medium — touches working intent-layer code
- **Rollback:** revert to the pre-phase commit; nothing else depends on Phase 1 yet

### Phase 2 — Per-field digests and the fields a hold names
**Status:** DONE
- `depends_on`: [1]
- `parallel_group`: serial-digest
- `merge_hazards`: `approval_content_hash`'s output — a moved value invalidates every stamp in every consuming project
- **Scope in:** `src/harness_maker/spec_machine.py`, `tests/unit/test_spec_approval.py`
- **Scope out:** `HASH_DENYLIST_TOP` / `HASH_DENYLIST_AC` membership — the deny-lists themselves do not change
- **Exit criterion:** the AC-001/AC-002/AC-003 tests pass; a pinned regression asserts that `approval_content_hash` of `specs/SPEC-ai-native-sdlc-vs-intent-world.machine.yaml` still equals `9b4df032189323f6a9daf25ccb27aae3a8bfeba199c85f315cf2161a53d0042e`; an approve→reload→edit→`approval-status` test proves the map is actually written and read back; and a test pins `_run_approve`'s JSON key set to the four established keys
- **Risk:** high — the hash is load-bearing for every existing approval
- **Rollback:** revert to Phase 1's tip; the lock stands on its own

### Phase 3 — A malformed SPEC reports its validation error
**Status:** DONE
- `depends_on`: [2]
- `parallel_group`: serial-digest
- `merge_hazards`: none
- **Scope in:** `src/harness_maker/spec_machine.py`, `tests/unit/test_spec_approval.py`
- **Scope out:** the `malformed` verdict itself — only the detail text gains content
- **Exit criterion:** the AC-006 test passes: the detail names the offending field and is ≤ 200 characters
- **Risk:** low
- **Rollback:** revert this phase alone

### Phase 4 — Tests for the branches mutation found
**Status:** DONE
- `depends_on`: [3]
- `parallel_group`: serial-tests
- `merge_hazards`: none — test-only
- **Scope in:** `tests/unit/test_spec_approval.py`, `tests/unit/test_land_hold.py`
- **Scope out:** any production file; this phase adds no behaviour
- **Exit criterion:** AC-007..AC-011 tests pass, **and** each has a recorded artefact pair in the phase notes: the one-line inversion diff applied to the branch, and the verbatim pytest failure line it produced. `spec_machine.py` is outside `paths_to_mutate`, so no mutation run covers these tests — an assertion that never fails is indistinguishable from a passing one without the artefact
- **Risk:** low
- **Rollback:** delete the added tests

### Phase 5 — Measure mutation on the new module
**Status:** DONE
- `depends_on`: [4]
- `parallel_group`: serial-tests
- `merge_hazards`: none
- **Scope in:** `specs/SPEC-mutation-survivors-and-approval-p2s.machine.yaml` (`last_mutation_run` only — a deny-listed field, so the stamp survives), `work-docs/MUTATION-mutation-survivors-and-approval-p2s-2026-09-20.md`
- **Scope out:** `paths_to_mutate`, `mutation_threshold`, `mutation_runner` and every other authored field — **all three are hashed**, so writing any of them releases this SPEC's own DRI stamp. The runner is passed as a one-off `--runner`, and the literal command is recorded below so the number is reproducible
- **What is written where:** `last_mutation_run` takes an **ISO date** (the field's declared meaning, `spec_machine.py:245`); the mutant count, the score and the survivor list go into the `MUTATION-*.md` report, matching the precedent this PLAN cites in Prior Work. Nothing in `spec_mutation` writes the yaml back — the date is a hand edit to one deny-listed field
- **Exit criterion:** `hm spec_mutation gate --yaml specs/SPEC-mutation-survivors-and-approval-p2s.machine.yaml --tier 3 --runner 'python -m pytest -x -p no:cacheprovider tests/unit/test_io_utils.py tests/unit/test_spec_approval.py'` returns `ran: true` with a non-zero mutant count, and `work-docs/MUTATION-mutation-survivors-and-approval-p2s-2026-09-20.md` records the count, the score and the survivors that fall inside `rmw_lock` or its callers. **A zero-mutant report is a failed phase, not a pass** — that is the shape the 2026-09-20 run caught twice. Tier 3 is informational (`TIER_FLOORS` `{1: 85, 2: 70, 3: None}`), so the score gates nothing; the pre-change baseline is 44.7% (38/85) and any survivor inside the new lock code is a test to write, not a number to accept
- **Risk:** low — at tier 3 the gate is informational, so the phase cannot fail on pre-existing helpers. The remaining hazard is a zero-mutant run reading as success, which the exit criterion forbids
- **Rollback:** none needed; the field is a record

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/` — no rendered command changes in this task
- Advisory: `approval_content_hash`'s output for an unchanged SPEC must stay byte-identical. Every
  stamp in every consuming project is bound to it, and a moved value reads as "the SPEC was edited".
- Advisory: `SpecApproval`'s existing four fields — `kind`, `content_hash`, `approved_by`,
  `approved_at` — keep their names and meanings. `field_hashes` is additive and optional.
- Advisory: `HASH_DENYLIST_TOP` and `HASH_DENYLIST_AC` membership is unchanged. Adding or removing a
  key moves every hash, which is the same failure as the line above.
- Advisory: `hm spec_machine approve`'s stdout keeps exactly the four keys it prints today. A
  declared model field reaches that payload automatically (`_run_approve` dumps the whole stamp), so
  keeping the shape is an explicit act, not the default.
- Advisory: this SPEC's own `paths_to_mutate`, `mutation_threshold` and `mutation_runner` are hashed
  fields. Writing any of them during implementation releases the DRI stamp this task was approved
  under — it is the DRI's call, never a convenience during execute.

## 🧪 Testing Strategy

**Unit.** Every AC binds to a pytest node in `tests/unit/test_spec_approval.py` (AC-001..AC-006,
AC-011) or `tests/unit/test_land_hold.py` (AC-007..AC-010). AC-001/AC-002/AC-004 are Hypothesis
property tests under the `ci` profile; AC-007/AC-008/AC-010 load their rows through
`load_golden_table` rather than inlining them.

**Concurrency (AC-004).** Two real processes, not two threads: `multiprocessing` with a barrier so
both enter the read-modify-write window together. A thread-only test would pass against an unlocked
implementation under the GIL for small files, which is the `assertion-invariant-over-named-dimension`
shape.

**Regression.** The pinned `9b4df032…` hash assertion in Phase 2 is the guard for the boundary above.

**Mutation.** Phase 5, **tier 3 — informational, gates nothing** (ADR-004), over `io_utils.py` through the exit-code-normalising runner. The pre-change baseline is 44.7%.

**Manual.** None.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Refactoring the payload builder moves `approval_content_hash`'s output | medium | every existing stamp reads as edited | Phase 2's pinned-hash regression, asserted against the real 2026-09-19 stamp before any other Phase 2 work |
| The lock extraction breaks `world.py`'s intent-layer writers | medium | outcome rows lost | Phase 1 runs the world test modules in its exit criterion; the helper keeps the same lock path and error mapping |
| The digest map and the hash deny-list drift apart | medium | a hold names fields that are not hashed, or misses ones that are | one payload builder feeds both; AC-001 asserts the key set equals the hashed set |
| A new lock file lands in a tracked directory | low | repo dirt on every approve | the path is under `.claude/observability/`, already gitignored churn (recorded failure, 2026-09-17) |
| The concurrency test is flaky in CI | medium | a red suite unrelated to the change | a barrier rather than a sleep; the assertion is on the file's content, not on interleaving order |
| The lock path is derived from the guarded file, as `world._rmw_lock` does | high if unstated | an untracked, non-ignored `<repo>/observability/` file on every approve, which the dirty-base guard then blocks `worktree create` on | the caller passes `lock_path`; Phase 1 asserts the literal `<base>/.claude/observability/.hm-spec-*.lock` |
| A survivor inside the new `rmw_lock` code is waved through because tier 3 gates nothing | medium | the lock ships with an unexercised branch | the exit criterion separates the two populations: survivors inside `rmw_lock` or its callers are tests to write; survivors in pre-existing helpers are recorded and left |
| A lock timeout escapes as an untranslated exception | medium | `approve` prints a traceback instead of its error line | Phase 1 translates `io_utils.LockTimeout` into `ApprovalError` and tests that `_run_approve` catches it |

## ✅ Success Criteria

- [x] AC-001 — the digest map's keys equal the hashed field set
- [x] AC-002 — one edited field, one named field
- [x] AC-003 — a pre-digest stamp keeps its verdict and says why
- [x] AC-004 — two concurrent writers, both updates present
- [x] AC-005 — an unlockable filesystem still writes
- [x] AC-006 — the malformed detail carries the validation message, bounded
- [x] AC-007..AC-011 — the found branches each fail a test when broken
- [x] `approval_content_hash` of `specs/SPEC-ai-native-sdlc-vs-intent-world.machine.yaml` still equals `9b4df032189323f6a9daf25ccb27aae3a8bfeba199c85f315cf2161a53d0042e`
- [x] `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src tests` clean
- [x] `hm spec_machine approve` still prints exactly `kind`, `content_hash`, `approved_by`, `approved_at`
- [x] `last_mutation_run` recorded as an ISO date, with `ran: true`, a non-zero mutant count and the survivor split in `work-docs/MUTATION-mutation-survivors-and-approval-p2s-2026-09-20.md`

## 🧭 Phase D.5 — the window this repair newly made reachable

Written during execute, per the stage's requirement that this be an artifact rather than a
reflection. Four windows opened; each names the test that enters it.

**1. A machine SPEC write can now fail on the lock.** Before, `approve`/`mark_tested`/
`mark_judged` had exactly two outcomes: wrote, or raised for a reason of their own. They now
have a third — another process holds the lock. Entered by
`tests/unit/test_spec_approval.py::test_a_lock_timeout_reaches_the_cli_as_an_approval_error`,
which asserts the timeout reaches `_run_approve`'s `except` clause rather than escaping as a
traceback.

**2. `approve` can now refuse before it reads the identity.** The lock path is computed first,
so a repository git will not resolve stops the write earlier than the empty-`user.name` check
ever did. Entered by `test_an_ambiguous_base_root_refuses_to_write`. **This window was measured
the hard way**: the first implementation refused whenever a base root did not resolve, which
broke 27 existing tests across 7 files — `mark_tested` and `mark_judged` had never required
git, and deriving their lock path from a base root created that coupling. The rule was narrowed
to refuse only when a repository IS present and git will not name it;
`test_outside_any_repository_the_lock_sits_beside_the_spec` pins the other half so the coupling
cannot come back silently.

**3. A hash mismatch now reads the stamp's digest map.** The detail used to be one constant
string; it is now derived from a three-way key-set diff. Entered by the four
`test_ac_002_one_change_names_exactly_that_field` cases (edit / top-level edit / addition /
removal) and `test_ac_002_a_reordered_ac_list_names_ac_order`.

**4. ABSENT CASE — a stamp with no digest map.** The repo's most-recurring class (count:8), and
here it is not hypothetical: every stamp written before this change lacks the map, including
the one landed on 2026-09-19. The behaviour is defined (ADR-003) rather than defaulted: the
verdict is unchanged and the detail says the fields cannot be named. Entered by
`test_ac_003_a_pre_digest_stamp_says_it_cannot_name_fields`, which also asserts the wording does
NOT claim the stamp "predates digests" — an older writer can erase the map from a newer stamp,
so its absence is not evidence about when it was written.

**One regression this repair caused, found by the full suite and fixed:**
`test_spec_dir_outside_the_checkout_is_ignored` approved a decoy SPEC that sat outside any
repository. The decoy is now its own repository; it is still outside the *checkout*, which is
what that test is about.

**One pre-existing regression found while running:** `.gitignore` gained `!work-docs/MUTATION-*.md`
in `865e3ef5` without the matching entry in `worktree.DELIVERABLE_PREFIXES`, whose comment says
to add a document type "HERE and nowhere else". `tests/structural/test_deliverable_single_source.py`
was red on main as a result. Fixed in this task.

## 🔍 Plan Validation

Two passes, the cap. `hm plan_rounds outcome` reports **`progress`**: pass 1's 12 critiques were
all resolved and pass 2 found 12 new ones (`resolved_n: 12, new_n: 12, unresolved_n: 0`). The loop
was still moving when the two-pass cap stopped it — which is a different fact from a loop that
stalled, and the reason this section says so rather than reporting only "cap reached".

`validator_outcome: MAJOR_REVISION_TERMINAL`: a second pass ran and these findings survived it.
`/hm:execute` proceeds and carries them as known risks.

**The DRI answered the Step 4 A/B question on 2026-09-20 and chose A — proceed, with the four
surviving criticals accepted as risk.** A human was present for that choice; the frontmatter keeps
`MAJOR_REVISION_TERMINAL` because that is what the record is (a second pass ran, these survived),
not `APPROVED`. Execute's first order of business is findings 3, 4 and 5: each one either edits the
SPEC or settles a contract the SPEC named, and finding 3 in particular means an AC-006 test written
today would pass against unmodified code.

### Pass 1 — MAJOR_REVISION (4 critical, 5 warning, 3 suggestion), all addressed

| Finding | Resolution |
|---|---|
| ADR-001's key set made AC-002 unsatisfiable — `ac` is itself hashed | ADR-001 states `set(payload) - {"ac"}` plus one key per AC id; SPEC AC-001 reworded. **Released the DRI stamp**; re-approved at `6983950a…` |
| The lock path lands outside `.claude/` for `specs/*.machine.yaml` | the caller computes `lock_path`; Phase 1 asserts the literal path |
| Phase 5's exit criterion was a placeholder command | the literal pytest invocation is written out; `mutation_runner` stays null because it is hashed |
| Phase 5's risk mis-stated and 70 unbaselined | measured first: 44.7%. Moved to tier 3 (ADR-004) |
| Read-time comparison undefined for added/removed keys | Data flow specifies a three-way key-set diff; AC-002's domain widened |
| Lock timeout exception undefined | `io_utils.LockTimeout` → `ApprovalError`, tested in Phase 1 |
| `last_mutation_run` asked to hold a count | ISO date in the field; the count goes to the MUTATION report |
| Phase 4's exit criterion self-judged | a per-AC artefact pair (inversion diff + failure line) is required |
| CLI output gains a fifth key (codex `f5eb508f`, accepted) | `_run_approve` keeps its four keys; a Contract Boundary records it |
| Truncated pinned hash | full path and 64-hex literal |
| An older reader erases `field_hashes` | recorded in ADR-003; the detail says "carries no digest map", not "predates digests" |
| Phase 1 did not run `test_io_utils.py` | added to its exit criterion |

Codex was invoked and returned three findings: one accepted (the CLI key set, verified in
`_run_approve`) and two rejected with source evidence — the tier-2-is-not-gated claim is refuted by
`TIER_FLOORS`, and the "approve never persists the map" claim is refuted by ADR-001's own Decision
plus `_dump_machine_yaml`'s round-trip.

### Pass 2 — MAJOR_REVISION, TERMINAL. Carried into execute as known risks

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | Testing Strategy still said "tier 2" while every other statement said tier 3 | critical | **fixed** — a stale line contradicting a decision recorded in the same document is not a finding to carry, it is a typo the revision missed |
| 2 | Phase 5's exit criterion asks for `ran: true` and a mutant count, which the `gate` subcommand never prints (at tier 3 it returns before the `ran` check and emits one line) | critical | **carried** — execute must take the counts from the mutmut output itself, not from the gate's exit code. The criterion's intent (a zero-mutant run is a failed phase) stands; the observable named for it does not exist |
| 3 | AC-006's fixture does not reach the branch it targets: `irreversible_decisions` is `\| None = None`, so removing it raises no `ValidationError` and hits the pre-existing `schema_version 3 without irreversible_decisions` branch instead — the test would pass against unmodified code | critical | **carried** — the AC needs a fixture that actually raises (`verification_tier: 9`, malformed YAML). Fixing it edits the SPEC and releases the stamp again, so it is the DRI's call at execute time |
| 4 | Dropping `ac` from the key set leaves the AC list's **order** hashed but uncovered: `sort_keys` does not reorder lists, so permuting two ACs moves the hash and names zero fields | critical | **carried** — the pass-1 fix created this. Either a key covers the id sequence, or the empty-diff case must say so out loud instead of naming nothing |
| 5 | `resolve_base_root` falls back to its argument when `git rev-parse` fails (git absent, `safe.directory` refusal on WSL2), so the lock path becomes `specs/.claude/observability/…` — untracked, un-ignored, and a different lock file from the one a working-git peer takes | critical | **carried** — the absent case of the pass-1 fix. Fail closed or anchor on an upward `.claude/` search; either way it needs a decision and a test |
| 6 | `validator_outcome: APPROVED` in the frontmatter while this section was a placeholder | critical | **fixed** — the field now records the verdict that was actually returned |
| 7 | Phase 5's runner adds `test_spec_approval.py` while the baseline used `test_io_utils.py` alone, so the before/after comparison is confounded | warning | **carried** — the survivor split, not the score, is what the criterion should rest on |
| 8 | AC-010's cap rows (5 MB / 200 MB / 5000 files) need fixtures nobody sized; monkeypatching the constants weakens the rows silently | warning | **carried** — needs a decision recorded in the AC |
| 9 | AC-004 is described as both a Hypothesis property test and a two-process barrier test | warning | **carried** — pick one form and record the `@settings` if it stays under Hypothesis |
| 10 | `interview_rounds: 3` contradicted the eleven numbered rows | suggestion | **fixed** — the field now states its unit |
| 11 | `parallel_group` names groups in a fully serial chain | suggestion | **carried** — cosmetic; `depends_on` is what execute reads |
| 12 | AC-001 and AC-005 appear in no Verification Criteria row | suggestion | **carried** — traceability only; Phase 1's exit criterion names AC-005 |

Four of the six criticals (2, 3, 4, 5) are the same shape: **a pass-1 fix whose own absent case or
output contract was not checked**. That is the recorded failure mode for this document class
(`[fail:test] fix-introduced-defect-passes-all-gates`, count:13), reproduced inside the pass that
was supposed to close it. Execute should treat 3, 4 and 5 as the first things to settle, because
each one edits either the SPEC or a contract the SPEC named.
