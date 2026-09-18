---
type: plan
task_slug: intent-layer-ops
status: complete
created: 2026-09-18
tags: [harness-maker, plan, python, jinja2, intent-layer, outcomes, withdrawal, evidence]
spec: "[[SPEC-intent-layer-ops]]"
interview_rounds: 5
adrs: 5
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Short hash-referenced measure evidence; `hm world gap` measures the withdrawal criterion; one wrapup 5.7 line"
spec_need_verdict: change
spec_need_target: outcome-measure
---

# PLAN — Intent layer operations

## 🎯 Executive Summary

**TL;DR.** Two operational defects in the intent layer, found by reading the dogfood world on
2026-09-18, are fixed; two further concerns raised in the same read are deliberately left alone.

- **Evidence (ADR-001).** `run_measure` copies the full measure argv into every `outcomes.yaml`
  row (dogfood commands are 300–700 chars of inline Python). The argv is already bound by the
  row's `definition_hash` and recoverable from `intent.yaml` at the recorded commit, so evidence
  becomes `auto: measure#<definition_hash[:12]> @ <sha> exit=0 cwd=<base|checkout>`. Old rows untouched.
- **Withdrawal (ADR-002..004).** The layer's own kill criterion ("10 wrapups, no `observed:`, no
  `candidate` revisit → remove the layer") is a skeleton comment nothing counts. `hm world gap
  --json` gains a `withdrawal` block measured from git history + base-root `stage-spans.jsonl`
  (`hm:wrapup` **start** events — `end` is Claude-Code-only and misses chained stages, ADR-004);
  a count that cannot be taken is `null` with a `reason`, never a disguised `0`.
- **Surface (ADR-005).** `/hm:wrapup` 5.7 gains one sentence reading the `gap` output it already
  obtains — zero new calls; allowance declared and retired inside this task.

**Out of scope, by decision:** an assumption-creation verb (interview #1 — the operator keeps
the axis as is) and INTENT body enforcement (interview #2 — SPEC-playbook-alignment made the body
human-owned on purpose; the contract lives in the hashed frontmatter).

**Impact.** `world.py` (~70 lines), `intent.py` (small refactor + skeleton comment), one wrapup
template sentence, four test files, two SPEC amendments (already written at spec time).

## 📚 Prior Work

- **SPEC-outcome-measure** AC-002 fixed the evidence string with argv; its own Constraints row
  says "evidence stays short" — the argv copy contradicted that intent. Amended at spec time.
- **SPEC-objective-gap-proposal** pins `status --json` unchanged (`test_world_gap.py:156`) —
  hence ADR-002 (`gap` only).
- **PLAN-outcome-measure ADR-010** is the surface procedure this PLAN copies (Phase 0 pin →
  in-flight allowance → Phase-N retirement with delta-doc §3.1).
- **[fail:design] surface-allowance-expires-at-wrapup-no-fold** (count 3): an allowance that is
  not retired before land leaves main red for the next task. Phase 4 retires it in-task.
- **[fail:tooling] mutation-gate-timeout-leaves-source-mutated-on-disk** (count 4): mutmut 2.5.1
  collects zero mutants on `world.py`. Never kill a `mutmut run` in the worktree; `git diff
  src/` before every commit after a mutation attempt.
- **Side finding (not fixed here):** wrapup 5.7 Q1 builds "one option per assumption id (from
  the status output)", but `status` carries no assumption id list — only `conflicts`. Belongs to
  the assumption axis the operator left out of scope; recorded for a follow-up.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Assumption axis | Scope | How should assumptions be created? | add verb / hand-edit + skeleton / migrate unknowns / leave | **leave** | out of scope this task | — |
| 2 | INTENT body | Scope | Enforce or hash the body? | keep / approve warning / drop scaffold / refuse empty | **keep** | SPEC-playbook-alignment decision stands | — |
| 3 | Withdrawal | Scope | The criterion is uncounted — what to do? | measure in payload / fix comment / delete criterion | **measure** | — | ADR-002 |
| 4 | Evidence | Contract | Evidence copies the whole argv | hash ref / truncate / keep | **hash ref** | old rows unchanged | ADR-001 |
| 5 | Clock start | Contract | When does the 10-wrapup count start? | first filling git commit / `filled_at` field / first objective | **first filling git commit** | — | ADR-003 |
| 6 | Surfacing | Contract | Where is `due` shown? | payload + one wrapup line / payload only / health signal | **payload + wrapup line** | — | ADR-005 |
| 7 | SPEC | Process | Contract change needs SPEC | `/hm:spec` first / waive | **`/hm:spec` first** | done (spec stage) | — |
| 8 | Objective | Intent | Which objective does this serve? | SOURCE-PLAN-STEPS / LOOP-OPT-IN / none | **none**; no draft | — | — |
| 9 | Absent cases (spec) | Failure handling | Unmeasurable count? | null + due false + reason / now as clock | **null + reason** | absent-case rule | ADR-004 |
| 10 | SPEC layout (spec) | Process | Where do the ACs live? | new SPEC + AC-002 amend / two existing SPECs | **new SPEC + amend** | — | — |
| 11 | Lock-in (plan re-entry) | Process | Proceed to phases? | proceed / one question / several | **proceed** | brief defaults accepted | — |
| 12 | V-01 wrapup source | Contract | `end` events are Claude-Code-only (dogfood 42 start / 32 end) — count what? | start + `no_wrapup_spans` / git commits / keep end + document | **start + `no_wrapup_spans`** | validator critical | ADR-004 |
| 13 | V-03 provenance | Contract | Dirty / cross-checkout / nogit rows lose the command | conditional guarantee / intent sha + `+dirty` / keep truncated argv | **conditional guarantee** | hash still pins by equality | ADR-001 |
| 14 | V-07 shallow clone | Failure handling | Shallow clone fabricates `filled_at` | shallow → `no_git` / accepted limitation | **shallow → `no_git`** | — | ADR-003 |
| 15 | V-02/04/05/06/08/09/10 | Mixed | Seven verified consistency fixes | revise all / individually | **revise all** | see Plan Validation | ADR-003/004/005 |

## 📐 Architecture Decision Records

### ADR-001: Measured evidence references the definition hash, not the argv
**Status:** Accepted (2026-09-18, via /hm:plan interview)
**Context:** `run_measure` builds `auto: {' '.join(argv)} @ …`; the dogfood rows carry 300–700
chars of command each. The same row's `definition_hash` already covers `measure.cmd/select/cwd/
timeout_s`, and the short sha pins the `intent.yaml` that held that command.
**Decision:** `evidence = f"auto: measure#{outcome_definition_hash(outcome)[:12]} @ {sha} exit=0 cwd={measure.cwd}"`.
`hm world outcome record` (manual) evidence is untouched; existing rows are never rewritten.
SPEC-outcome-measure AC-002 (md + machine predicate) is amended and its two assertions in
`tests/unit/test_world_outcome_measure.py` (lines ~96 and ~120) move to the new string.
**Consequences:**
- ✅ Constant-length rows; the hash still pins **which definition** produced the number, by equality,
  which is all `stale_definition` and `gap` need.
- ⚠️ **Conditional recovery (accepted, interview #13).** The command text is recoverable by
  `git show <sha>:.claude/intent.yaml` only when `intent.yaml` was committed and clean at that sha
  and that sha's tree is the checkout the intent was read from. Unrecoverable: a dirty
  `intent.yaml`, a task-worktree edit measured with `cwd: base` (the sha is the base HEAD), and
  `nogit` rows. Today's argv copy made recovery unconditional; that is the price of short rows.
  Old and new rows coexist in one file.
**Rejected alternatives:**
- Truncate argv to N chars — loses the tail irrecoverably and still grows with N.
- Keep the argv — the file grows by the command length on every measurement.
**Source:** Interview #4

### ADR-002: The withdrawal block lives in `gap` only; `status` stays frozen
**Status:** Accepted (2026-09-18, via /hm:spec default, confirmed at plan lock-in)
**Context:** SPEC-objective-gap-proposal pins `status --json` byte-for-byte (plan Step 0.5 and
tests read it). Wrapup 5.7 already runs `hm world gap --json` to decide its third question.
**Decision:** `gap_report` adds `withdrawal`; `status_report`/`_status_payload` are not touched.
The invalid-world payload (shared by both) carries no `withdrawal`.
**Consequences:**
- ✅ No change to the gate-adjacent reader; zero new calls in wrapup.
- ⚠️ `status` users do not see the criterion — by design, only the proposer/wrapup path does.
**Rejected alternatives:**
- Add to both — breaks a pinned contract and its test for no additional reader.
**Source:** Interview #3, spec round default

### ADR-003: `filled_at` = committer date of the oldest commit whose `intent.yaml` is filled
**Status:** Accepted (2026-09-18, via /hm:plan interview)
**Context:** The criterion's clock "starts at the first wrapup after the user fills it in"
(PLAN-intent-world-model ADR-011); nothing records that moment.
**Decision:** At `checkout_root(root)`: first `git rev-parse --is-shallow-repository` — `true` →
`no_git` (a shallow boundary would fabricate `filled_at`, interview #14). Then
`git log --reverse --format=%H%x09%cI -- .claude/intent.yaml`, and for each sha
`git show <sha>:.claude/intent.yaml` until the first blob that parses, validates and is not
`is_not_filled_in`; its committer date normalised to UTC `Z` is `filled_at`. Every git call:
`shell=False`, `timeout=10`. `FileNotFoundError`/`TimeoutExpired`/`PermissionError`, or a
non-zero exit **from `rev-parse` or `git log`** → `no_git`. A non-zero `git show` (e.g. a commit
that deleted the file), an unparseable or invalid blob → **skip that blob** (V-04). To judge a blob,
`intent.py` gains `_intent_from_raw(path, raw) -> Intent` (the body of `load_intent` after the
read), so there is still one construction rule; `load_intent` delegates to it.
**Consequences:**
- ✅ No new field for a human to forget; reproducible from history.
- ⚠️ A history rewrite (squash of the fill commit) moves the clock; accepted — the criterion is
  a coarse instrument. Shallow clones report `no_git` rather than a boundary date. Cost is one `git show` per commit touching the file (tens at most).
**Rejected alternatives:**
- `filled_at` field in `intent.yaml` — unmeasured when unset, the exact failure being fixed.
- First objective `created_at` — a layer with no objective (the unused case) never starts.
**Source:** Interview #5

### ADR-004: Counts that cannot be taken are `null` with a precedence-ordered `reason`
**Status:** Accepted (2026-09-18, via /hm:spec interview)
**Context:** A `0` for "could not count" is indistinguishable from "unused" and would trip the
criterion or hide it (CLAUDE.md absent-case correction, 2026-06-08).
**Decision:** `withdrawal = {filled_at, wrapups_since_fill, objectives_observed,
revisit_candidates_now, due, reason}`. `reason` is the first applicable of `not_filled_in` (working
tree), `no_git`, `fill_uncommitted` (working tree filled, no filled commit), `no_stage_spans` (the
path `resolve_base_root(root)/.claude/observability/stage-spans.jsonl` is not a regular file, or
reading it raises `OSError`), `no_wrapup_spans` (the ledger holds no `hm:wrapup` event at all —
worktree off, Cursor/Codex: the instrument is absent, not reading zero), else `ok`. Fields that
could not be computed are `None`; `objectives_observed` (objectives whose `observed` is not
`None`, any state) and `revisit_candidates_now` (`len(fired_revisits)`) are always computable
from the loaded world. `wrapups_since_fill` counts events with `event == "start"` and
`stage == "hm:wrapup"` and `ts` strictly after `filled_at` (interview #12: `start` is written by
every wrapup that emits spans; `end` only by the Claude-Code Stop hook and only when no later
stage closed the span first — dogfood 42 start vs 32 end). Parsing reuses
`stage_spans.read_events` (decode `errors="replace"`, malformed lines counted, not raised) after
an explicit `is_file()` check, because `read_events` returns `[]` for both missing and empty. A
naive (timezone-less) `ts` is skipped like a malformed line — never compared (V-02). Once the
ledger has any `hm:wrapup` event, a count of 0 after `filled_at` is a real 0. `due = wrapups is not None and wrapups >= WITHDRAWAL_WRAPUPS (10)
and observed == 0 and candidates == 0`.
**Consequences:**
- ✅ `gap` never crashes on a missing git/file; `due` can only fire on real counts.
- ⚠️ "Ever candidate" is approximated by "candidate now" — revisits are not logged (SPEC non-goal).
- ⚠️ A wrapup abandoned after its `start` still counts; accepted — the threshold is 10.
**Rejected alternatives:**
- `filled_at = now` when uncommitted — the clock would reset on every read.
**Source:** Interview #9

### ADR-005: One wrapup 5.7 sentence, zero new calls; allowance declared and retired in-task
**Status:** Accepted (2026-09-18, via /hm:plan interview)
**Context:** The command-surface ratchet guards every rendered command; the last three tasks
tripped on allowances that outlived their PLAN.
**Decision:** After the three answer-gated blocks in 5.7 (both arms), one sentence tied
explicitly to **the `hm world gap --json` output of the outcome-measure check above** (V-10 — the
dependency is named, not inferred): when it reports `withdrawal.due: true`,
print exactly once `[intent] withdrawal criterion met — <wrapups_since_fill> wrapups since
<filled_at>, no observed objective, no fired revisit; removing the layer is the operator's
call` and nothing when false. No new Bash call → `round_trips` unchanged. Process mirrors
PLAN-outcome-measure ADR-010: Phase 0 pins plan/review/help sha + wrapup length per arm in
`work-docs/BASELINE-DELTA-intent-layer-ops.md`; Phase 3 declares `surface_allowance` (chars,
`commands.wrapup/hm-wrapup`, delta_doc) in the same commit as the sentence; Phase 4 re-freezes the
baselines, writes §3.1 attribution, deletes the allowance and exits green with zero allowances.
The intent-layer skill is not touched.
**Consequences:**
- ✅ Operator sees the criterion when the layer is exercised; main is green after land.
- ⚠️ One more sentence on the wrapup surface (~300 chars per arm).
**Rejected alternatives:**
- Payload only — a field no prose reads is the comment it replaces.
- `/hm:health` signal — seen only when health runs.
**Source:** Interview #6

## 🏗️ Technical Design

**Current state.** `world.run_measure` (world.py:1132) formats argv into evidence.
`gap_report` (world.py:817) folds `_status_payload` and adds `outcomes[*].reason` and
`objectives`. The withdrawal criterion is text in `intent.SKELETON` (intent.py:52) and in
SPEC-intent-world-model (Constraints row, amended at spec time to point here).

**Affected components.**
- `src/harness_maker/world.py` — evidence line; new `WITHDRAWAL_WRAPUPS`, `_filled_at(root)`,
  `_count_wrapups(base, since)`, `withdrawal_report(world, root)`; `gap_report` adds the key.
- `src/harness_maker/intent.py` — `_intent_from_raw` extracted from `load_intent`; `SKELETON`
  comment names `hm world gap` / `withdrawal.due`.
- `src/harness_maker/templates/stages/wrapup.md.j2` — one sentence at the end of 5.7.
- Tests: `tests/unit/test_world_evidence_ref.py` (new), `tests/unit/test_world_withdrawal.py`
  (new), `tests/unit/test_world_outcome_measure.py` (two assertions), `tests/unit/test_render_intent_layer.py`
  (AC-005), `tests/structural/test_intent_layer_ops_invariance.py` (new); snapshots regenerated.

**Data flow (withdrawal).**
```
gap_report(root)
  world = load_world(root)                        # unchanged
  status = _status_payload(world)                 # unchanged
  report["withdrawal"] = withdrawal_report(world, root, fired=status["fired_revisits"])
     ├─ is_not_filled_in(world.intent)        → reason not_filled_in
     ├─ _filled_at(checkout_root(root))       → (iso | None, reason no_git | fill_uncommitted)
     ├─ _count_wrapups(resolve_base_root(root), filled_at) → int | None
     │        (no_stage_spans | no_wrapup_spans; start events; naive ts skipped)
     └─ due per ADR-004
```

**API changes.** `hm world gap --json` payload gains `withdrawal` (additive). New measured rows
carry the ADR-001 evidence format. `hm world status --json` unchanged.

## 📝 Implementation Plan

### Phase 0 — Pin the surface and confirm the inherited state
- **Status:** DONE (2026-09-18, /hm:execute)
- **depends_on:** []
- **parallel_group:** serial-surface
- **merge_hazards:** `work-docs/BASELINE-DELTA-intent-layer-ops.md` (new)
- **Scope in:** from `<WT>`, run `uv run pytest tests/structural/test_surface_baseline.py tests/structural/test_command_size_budget.py` and confirm green (if red by a prior task's expired allowance, fold it first and record it in §2); write the delta doc §1 with the fenced JSON pin `{arms{arm:{plan,review,help,wrapup}}, wrapup_len{arm}, harness_maker_version}` using the recipe of `test_outcome_measure_invariance.py` (`_instruction_baseline.AXES` + `_render_atomic`, `test_command_size_budget._render`); §2 inherited-fold note; §3 placeholder. **Out:** src, templates.
- **Exit:** delta doc exists with a parseable JSON pin for all four arms; both structural files green.
- **Risk:** low
- **Rollback:** none (docs only).

### Phase 1 — Evidence references the definition hash (AC-001, ADR-001)
- **Status:** DONE (2026-09-18, /hm:execute)
- **depends_on:** []
- **parallel_group:** serial-world
- **merge_hazards:** `src/harness_maker/world.py` (shared with Phase 2)
- **Scope in:** RED first: `tests/unit/test_world_evidence_ref.py::test_ac_001_measured_evidence_references_the_definition_not_the_command` (Hypothesis, padded `python -c "print(n)"  # …` commands over `world_fixture`, padding filler a fixed character outside `[0-9a-f]` and outside the words `auto/measure/exit/base/checkout` (V-05); expected string built from the row's `definition_hash` and the fixture sha; no argv token > 3 chars; constant length; plus a manual `record` row keeps its evidence verbatim and a pre-existing row **seeded through `record_value`** (tool-written) is byte-identical after the new append (V-06 — `_append_value` re-dumps the file, so hand-written formatting is out of scope). Update the two old-format assertions in `test_world_outcome_measure.py` to the new string. GREEN: change world.py:1132 to ADR-001's format. **Out:** gap, templates.
- **Exit:** `uv run pytest tests/unit/test_world_evidence_ref.py tests/unit/test_world_outcome_measure.py` green; `uv run mypy --strict src/harness_maker/world.py` clean.
- **Risk:** low
- **Rollback:** Phase 0.

### Phase 2 — Withdrawal reader in `gap` (AC-002/003/004, ADR-002..004)
- **Status:** DONE (2026-09-18, /hm:execute)
- **depends_on:** [1]
- **parallel_group:** serial-world
- **merge_hazards:** `src/harness_maker/world.py`, `src/harness_maker/intent.py`
- **Scope in:** RED: `tests/unit/test_world_withdrawal.py` — AC-002 on a tmp git repo (skeleton commit, fill commit at pinned `GIT_COMMITTER_DATE` with a non-UTC offset, stage-spans with 2 `hm:wrapup` `start` rows before and 3 after, plus `end` rows that must not be counted, a non-wrapup row, a malformed line and a naive-`ts` line) asserting the exact six keys/values and `"withdrawal" not in status_report(root)`; AC-003 parametrised over the golden table calling the pure `due` helper; AC-004 parametrised over the fixture shapes (git missing via monkeypatched `subprocess.run` raising `FileNotFoundError`; non-repo tmp dir; shallow clone; a history commit deleting the file is skipped, not `no_git`; working-tree-only fill; no stage-spans; a directory at the stage-spans path; a ledger with no `hm:wrapup` event → `no_wrapup_spans`; not_filled_in; invalid intent). GREEN: `intent._intent_from_raw` extraction (`load_intent` delegates; existing intent tests stay green); world.py per ADR-003/004; `SKELETON` comment update. **Out:** `status_report`, templates.
- **Exit:** `uv run pytest tests/unit/test_world_withdrawal.py tests/unit/test_world_gap.py tests/unit/test_intent*.py` green; `ruff check` + `mypy --strict` clean on both modules.
- **Risk:** medium (git history walk; timezone normalisation)
- **Rollback:** Phase 1.

### Phase 3 — Wrapup 5.7 sentence + in-flight allowance (AC-005, ADR-005)
- **Status:** DONE (2026-09-18, /hm:execute)
- **depends_on:** [0, 2]
- **parallel_group:** serial-surface
- **merge_hazards:** `src/harness_maker/templates/stages/wrapup.md.j2`, rendered snapshots, command-size gate goldens, this PLAN's frontmatter
- **Scope in:** add the ADR-005 sentence at the end of 5.7 (both arms render from the one template); measure the wrapup delta per arm; in the same commit declare `surface_allowance{chars, commands.wrapup, commands.hm-wrapup, delta_doc: work-docs/BASELINE-DELTA-intent-layer-ops.md}` in this PLAN's frontmatter (no `round_trips` key — zero new calls); gate golden re-capture for `wrapup` only (+ `rebases` entry/docstring bullet as the gate requires); snapshot regeneration in the worktree; `tests/unit/test_render_intent_layer.py::test_ac_005_wrapup_prints_withdrawal_line_when_due` (Claude + Codex renders; slice Step 5.7 by heading; exactly one `[intent] withdrawal criterion met`; `withdrawal.due` present; `intent.SKELETON` contains `hm world gap` and `withdrawal.due`). **Out:** plan/review/help templates, the skill.
- **Exit:** `uv run pytest tests/unit/test_render_intent_layer.py tests/structural` green with the allowance in place; plan/review/help hashes equal the Phase 0 pin.
- **Risk:** medium (surface gates, snapshot churn)
- **Rollback:** Phase 2.

### Phase 4 — Retire the allowance and pin close-out (AC-006, ADR-005)
- **Status:** DONE (2026-09-18, /hm:execute)
- **depends_on:** [3]
- **parallel_group:** serial-surface
- **merge_hazards:** surface baseline files, this PLAN's frontmatter, delta doc
- **Scope in:** re-freeze the surface baselines from the worktree; move `_ATOMIC_RATCHET['wrapup']` only if outside its band; delta doc §3 measured delta and §3.1 attribution rows; delete the `surface_allowance` block; re-pin `wrapup` in §1; write `tests/structural/test_intent_layer_ops_invariance.py::test_ac_006_surface_pinned_and_allowance_retired` modelled on `test_outcome_measure_invariance.py` (loud skip when `__version__` differs from the pin). Flip `specs/SPEC-intent-layer-ops.machine.yaml` `pending_test: false` for every AC whose test now exists. **Out:** src.
- **Exit:** `uv run pytest tests/structural` green with **zero** in-flight allowances; `hm spec_machine check --all` on both SPECs `ok: true`; full `uv run pytest` green (run in background).
- **Risk:** low
- **Rollback:** Phase 3.

### Execution notes (2026-09-18)

- **Refresh before work.** `hm/intent-layer-ops` was 2 commits behind `main` (source-plan-steps
  landed from another session); rebased via a temporary WIP commit, restored uncommitted. No
  overlap with this task's files.
- **Phase 0.** Inherited state green (32 passed); pin written at base 43c7ded0.
- **Phase A–B.** 24 RED-stage nodes; A.4 measured 21 failed / 3 passed, the three justified in
  module docstrings; A.5 (one `test-reviewer`, three lenses) PASS on round 1, count re-verified.
- **Deviation — name.** The extracted constructor is public `intent.intent_from_raw` (ADR-003
  said `_intent_from_raw`): `world.py` calls it across modules, and a private name imported from
  another module is the pattern this repo avoids.
- **Deviation — root.** `withdrawal_report` runs git at the `root` `gap_report` already holds
  (the CLI resolves it to the checkout toplevel) instead of calling `checkout_root(root)` again,
  which would only add a subprocess and a stderr line on the no-git path.
- **Phase 3.** Wrapup +324 per arm, `plan`/`review`/`help` unmoved; gate golden re-captured with
  a `rebases` entry after verifying `wrapup` was the only moved command in every arm.
- **Phase 4.** Baselines re-frozen at 43c7ded0; `_ATOMIC_RATCHET["wrapup"]` 44 654 → 45 646 (the
  ask@flag_on render left the 2 % band — outcome-measure's +601 plus this task's +324);
  allowance deleted; mutation receipt recorded for the new AC-006 gate (deleting the new 5.7 line
  turns it red — verified, source restored byte-identical).
- **⚠️ For `/hm:wrapup`: the mutation-receipt row exists in BOTH copies** of
  `.claude/observability/mutation-receipts.jsonl`. The gate resolves the ledger at the **base**
  root (`mutation_receipt._base_root`), so the row must be there for the gate to pass now; the
  worktree copy is what the squash-land commits. The two rows are identical. **Before
  `task-land`, run `git -C <base> checkout -- .claude/observability/mutation-receipts.jsonl`** —
  the landing commit brings the same row, and a dirty base makes `task-land` self-abort.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/stages/plan.md.j2` — pinned byte-for-byte (AC-006)
- `src/harness_maker/templates/stages/review.md.j2` — pinned byte-for-byte (AC-006)
- `src/harness_maker/templates/skills/intent-layer/SKILL.md.j2` — no skill change in this task
- `.claude/intent.yaml` — the dogfood file is human-written
- `.claude/world/outcomes.yaml` — existing rows are append-only history; never rewritten
- Advisory: `status_report` / `_status_payload` output is frozen by SPEC-objective-gap-proposal — no key added, removed or reordered.
- Advisory: `definition_hash` payload and `outcomes.yaml` row schema are unchanged — changing either stales every existing row.
- Advisory: no assumption-creation verb and no INTENT body validation (interview #1, #2).

## 🧪 Testing Strategy

- **Unit:** AC-001 property (Hypothesis, ci profile derandomized); AC-002 golden git fixture
  (tmp repo, `git -c user.name=t -c user.email=t@t commit` with pinned `GIT_COMMITTER_DATE`,
  `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1` so signing/hooks/defaultBranch on the
  host cannot change the fixture — V-08);
  AC-003 golden table on a pure helper; AC-004 six fixture shapes.
- **Render:** AC-005 renders the real template for Claude + Codex arms.
- **Structural:** AC-006 pin vs live; surface baseline + command-size gates.
- **Regression:** existing `test_world_outcome_measure.py`, `test_world_gap.py` (incl. the
  status-unchanged differential), `test_intent*.py`.
- **Full suite** once at the end of Phase 4, in the background (~6 min).
- **Mutation:** `spec_mutation gate` on `world.py` is known to collect zero mutants under mutmut
  2.5.1; if it is run, never kill it mid-run in the worktree, and `git diff src/` afterwards.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Committer date vs stage-spans `ts` timezone mismatch miscounts wrapups | medium | wrong `due` | both aware, compared in UTC; naive `ts` skipped (never compared); AC-002 fixture uses a non-UTC committer offset and a naive line |
| Wrapup instrumentation absent (worktree off, Cursor/Codex) reads as 0 | high before V-01 | criterion never fires | count `start`; `no_wrapup_spans` → `null` |
| `git show` on many commits slows `gap` | low | latency | stop at the first filled blob; commits touching one file are few; 10 s timeout per call |
| Surface allowance outlives the PLAN → main red for the next task | medium (3 priors) | next task blocked | Phase 4 retires it; AC-006 asserts no `surface_allowance` |
| Snapshot/gate goldens drift beyond wrapup | low | noisy review | Phase 3 exit checks plan/review/help hashes equal the pin |
| mutmut interrupted in the worktree leaves `world.py` mutated | medium (4 priors) | silent corruption | never kill it; `git diff src/` before commit |
| Old-format rows confuse a future reader of evidence | low | none functionally | nothing parses evidence; documented in SPEC-outcome-measure AC-002 note |

## ✅ Success Criteria

- [x] S1 / AC-001 — `test_ac_001_measured_evidence_references_the_definition_not_the_command`
- [x] S2 / AC-002 — `test_ac_002_gap_reports_the_withdrawal_block`
- [x] S3 / AC-003 — `test_ac_003_due_is_the_criterion_exactly`
- [x] S4 / AC-004 — `test_ac_004_unmeasurable_counts_are_null_with_reason`
- [x] S5 / AC-005 — `test_ac_005_wrapup_prints_withdrawal_line_when_due`
- [x] S6 / AC-006 — `test_ac_006_surface_pinned_and_allowance_retired`
- [x] SPEC-outcome-measure AC-002 test green with the amended string
- [x] Full `pytest`, `ruff check`, `mypy --strict` green; zero `surface_allowance` at land

## 🔍 Plan Validation

**Pass 1 — `MAJOR_REVISION`** (plan-validator, 1 critical / 2 warning / 7 suggestion; codex second
opinion `invoked`, 5 findings, all `accepted` by the validator and folded into V-01..V-07).
Follow-up rounds were planned by `hm plan_rounds plan` (10 rounds, 0 skipped) and answered in
interview #12–#15 with a human present; every critique was resolved by revising the PLAN/SPEC:

| ID | Sev | Resolution |
|---|---|---|
| V-01 | critical | count `hm:wrapup` **start**; `no_wrapup_spans` reason (ADR-004, SPEC S2/S4, AC-002/004) |
| V-02 | warning | reuse `read_events` + `is_file()`; naive `ts` skipped; non-file/OSError → `no_stage_spans` (ADR-004, AC-004 rows) |
| V-03 | warning | conditional recovery stated as accepted trade-off (ADR-001, SPEC-outcome-measure AC-002 note) |
| V-04 | suggestion | only `rev-parse`/`log` failures → `no_git`; per-blob `show` failure skips (ADR-003) |
| V-05 | suggestion | SPEC S1 wording aligned to >3-char tokens; padding filler constrained (Phase 1) |
| V-06 | suggestion | byte identity scoped to tool-written rows, seeded via `record_value` (Phase 1, SPEC S1) |
| V-07 | suggestion | shallow clone → `no_git` (ADR-003) |
| V-08 | suggestion | git fixture isolates global/system config (Testing Strategy) |
| V-09 | suggestion | `cwd=<base|checkout>` in summary and SPEC-outcome-measure AC-002 |
| V-10 | suggestion | 5.7 sentence names the outcome-measure check's `gap` output (ADR-005) |

**No pass 2 / Step 4.5 terminal re-validation** — operator preference recorded in project memory
(`feedback_plan_validator_single_pass`: re-validating after revision is not run). Consequence
accepted: any defect the revision introduced is caught by `/hm:execute` Phase A.5 and `/hm:review`,
not here. Outcome recorded as `MAJOR_REVISION_RESOLVED` (a human answered every round).
