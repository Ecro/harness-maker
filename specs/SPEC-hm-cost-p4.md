---
type: spec
task_slug: hm-cost-p4
status: approved
created: 2026-11-10
tags: [cost, execute-stage, spec-machine, hm-check, bench, test-shape]
test_framework: pytest
interview_rounds: 1
intent: HM-LIGHT-LANE
summary: Bind AC tests by name with the project's own pytest runner, stop duplicated golden tests and pasted implementations, drop same-session re-reads, fix three stale texts, and re-measure tier 1 (plain / hm / hm-novalidator) against a 10.0x bar.
---

# SPEC — hm-cost-p4

## Intent

hm costs 11.36x plain on tier 1 (harness cdf28dce, transcript price) and loses the blind judge 3.49 vs
4.22. `/mnt/project-files/hm-cost-research/RESEARCH-hm-cost-p4.md` showed the remaining spend is now
output ≈37%, cache-read ≈38%, cache-write ≈25%, and that the lever left is the number of main-loop calls.
A diagnostic run on main 579e719 (t1 and t4, one hm run each, $1.57,
`/var/tmp/hm-diag-p4`) found where execute's calls go:

- `spec_machine mark-tested` failed in **both** runs. Its `pytest --collect-only` calls the `pytest` on
  PATH, while `hm check` runs `<project>/.venv/bin/python -m pytest`; bare `pytest` does not put the
  project root on `sys.path`, so collection fails with ImportError on a project without
  `pythonpath` config. The agent spent 5–6 calls at ~45k context diagnosing it (reading harness-maker's
  own source), and in t4 added `pythonpath = ["."]` to the user's `pyproject.toml` — an unrequested
  product change.
- Phase A's "put each test's node id in its AC's `test_ids`" was done with ad-hoc python string edits that
  failed once (2–3 calls), then `validate`.
- Tests repeated one body per AC over golden rows (t4: four identical functions) and pasted a frozen copy
  of the pre-change implementation (t1); 11 of 15 judge notes in the last counted run criticise test
  structure.

This task removes those round trips and the test shape that costs judge score, without removing a
quality device (AC tests first, RED gate, `hm check`, one review). It also adds a bench arm to measure
spec-validator (a TUNE step whose effect has never been measured) and folds in three stale texts.
The DRI revised the HM-LIGHT-LANE cost target from 5x to 8x on 2026-11-10; this task's bar is 10.0x.

## Outcomes

- `mark-tested`, `cross_validate` and `find-unbound` collect tests with the same pytest runner `hm check`
  uses, so a binding fails only when `hm check` could not run the test either.
- An AC test is found by its name, through one matcher shared by `mark-tested`, `hm check --red` and
  `find-unbound`: a parametrize case id `AC-NNN` / `AC-NNN-<suffix>` binds that node to AC-NNN only;
  a node with no AC case id binds by its function, `test_ac_NNN` / `test_ac_NNN_<short>`. A test file
  that fails to collect (a module-level import of a name that does not exist yet, a valid RED) binds by
  its static function names, and a file that reads `SPEC-<slug>.golden.json` binds to every live
  parametric AC of that slug. `hm check --red` binds an AC whose `test_ids` is empty this way without
  writing the yaml; `mark-tested --ac AC-NNN` records what it finds. The full `hm check` is unchanged:
  it still requires `pending_test: false`, so Bind stays the only writer. Execute's Phase A no longer
  edits `test_ids` or runs `validate`.
- Execute's test recipe: parametric ACs that share one call shape are one parametrized test over
  `(AC, row)` pairs with ids `AC-NNN-<i>`; a test never contains a copy of the implementation, old or new.
  The spec stage writes a "behaviour unchanged" AC as a parametric AC whose rows it computes at spec time
  by running the unchanged code, stores in the machine.yaml, and execute never regenerates.
- Execute reads the PLAN and SPEC only on Resume or when this session did not write them.
- The three stale texts are fixed (io_utils advisory, ARCHITECTURE stage diagram, consensus-arbiter).
- The bench has an `hm-novalidator` arm; tier 1 is re-measured with plain, hm and hm-novalidator.
- Tier-1 transcript ratio ≤ 10.0 with hm pass rate ≥ plain, pre-registered; the first complete batch counts
  and a miss is recorded as a miss.

## In-Scope Scenarios

- **S1 (normal):** Given a project with `pkg/` at its root, tests under `tests/` importing `pkg`, a
  `.venv/bin/python` and no `pythonpath` config, when execute binds its AC tests with `mark-tested`, then
  the binding succeeds because collection runs `.venv/bin/python -m pytest`, exactly the runner
  `hm check` uses.
- **S2 (normal):** Given four parametric ACs with the same input/output shape, when execute writes Phase
  A, then it writes one `@pytest.mark.parametrize` test whose ids are `AC-001-0 … AC-004-k`, does not touch
  the machine.yaml, and `hm check --red` reports each AC RED through its own parametrized cases.
- **S3 (edge):** Given AC-001 and AC-0012 in one SPEC, when tests `test_ac_0012_x` and a case
  `[AC-0012-0]` exist, then neither binds to AC-001. Given a node `test_ac_001_golden[AC-002-0]`, it binds
  to AC-002 only.
- **S3b (edge):** Given Phase A's test module imports a name that does not exist yet, when
  `hm check --red` runs, then the ACs that module covers are RED by import, not `no test_ids`.
- **S4 (failure):** Given an AC with no recorded `test_ids` and no test matching its name, when
  `mark-tested --ac AC-003` runs, then it fails naming AC-003 and the convention it searched, and the
  yaml is unchanged; `hm check` reports that AC as `no test_ids` as today.
- **S5 (normal):** Given a task that must keep the default output unchanged, when the spec stage writes
  its ACs, then that AC is parametric with rows produced by running the unchanged code, and the test
  reads those rows instead of pasting the old function.

## Non-Goals

- Fresh sessions or stage delegation to cut carry (DRI rejected fresh sessions, 2026-11-10).
- Removing or changing spec-validator in the shipped harness; this task only measures it.
- Changing the `test_ids` field or its schema; a non-empty `test_ids` keeps its meaning and precedence over
  discovery. Discovery in the full `hm check`.
- Moving `Do not change` checking into `hm check`, or new composite CLI commands.
- Making the eval judge a gate.

## Constraints

| Constraint | Source |
|---|---|
| Test framework: pytest; unit tests under `tests/unit/`, mock LLM calls | CLAUDE.md |
| Python only, `mypy --strict`, ruff, atomic writes, no `shell=True`, every subprocess has a timeout | CLAUDE.md |
| Stage templates stay within their char budgets (`_ATOMIC_RATCHET`, overhaul AC-004 caps) | tests |
| Rendered Claude and Codex variants change together | CLAUDE.md |
| Discovery never writes from `hm check` (it writes only `.git/hm/check-verdict.json`) | hm-cost-p3 ADR-009 |
| Eval: claude-sonnet-5-5, tier 1, 5 tasks × 3 runs per arm, same budget per arm | SPEC-hm-eval |
| Bench arms run with `IS_SANDBOX=1` in this container | memory |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | `hm check --red` resolves an AC with empty `test_ids` by the name convention, and `mark-tested --ac` records the discovered ids instead of refusing | public API/CLI contract | Phase A stops editing yaml; users' scripts that relied on "no test_ids" for an AC with a convention-named test see a different result |
| IRR-002 | The convention gains parametrize ids: a case id `AC-NNN` or `AC-NNN-<suffix>` binds to AC-NNN | public API/CLI contract | One parametrized test can carry several ACs; existing `test_ac_NNN*` names keep working |

## Acceptance Criteria

### AC-001: spec_machine collects with hm check's pytest runner
Given S1's project, `mark_tested` (and `cross_validate`'s collect, and `find_unbound_closed_type_acs`)
succeed and record the ids; the runner used is `check.pytest_runner` over the project's gate commands,
falling back to PATH `pytest` only when that returns None.

### AC-002: mark-tested records tests found by name
Given an AC with no recorded `test_ids`, `mark-tested --ac AC-NNN` records every collected node the shared
matcher assigns to AC-NNN (case id first, then function name); it fails, leaving the yaml untouched and
naming the AC and the patterns it searched, when none matches. Recorded ids are kept and unioned.
`find-unbound` uses the same matcher, so a pending AC whose only test is a case id is reported.

### AC-003: hm check --red binds empty test_ids by name, read-only
`hm check --red` treats an AC with empty `test_ids` as bound to the tests the shared matcher assigns it,
including the static fallback for a module that fails to import, reports outcomes per AC, and leaves the
machine.yaml byte-identical. The full `hm check` still fails an AC with `pending_test: true`.

### AC-004: execute's Phase A names tests instead of editing test_ids, and has no pasted implementations
The rendered execute command (Claude and Codex) tells Phase A to name tests by the convention, to write
one parametrized test with `AC-NNN-<i>` ids for parametric ACs that share a call shape, and never to copy
the implementation into a test; it no longer tells the agent to put node ids in `test_ids` or run
`spec_machine validate` in Phase A.

### AC-005: execute reads the PLAN and SPEC only when it did not just write them
The rendered execute command has no unconditional "Read it back" / "Read it" of the PLAN and loads the
PLAN, RESEARCH and SPEC only on Resume or when this session did not write them.

### AC-006: the spec stage writes "unchanged behaviour" as rows from the unchanged code
The rendered spec command (Claude and Codex) says a behaviour-must-not-change AC is parametric with golden
rows computed at spec time by running the unchanged code, stored in the machine.yaml and never
regenerated after the change; the rendered execute command forbids regenerating them.

### AC-007: three stale texts are fixed
`io_utils`'s retired-key advisory does not mention `/hm:loop` or autopilot; `docs/ARCHITECTURE.md`'s
generated-harness diagram lists research|spec|execute|wrapup and no `loop.md`; the rendered execute and
consensus-arbiter texts (body and description) no longer say the arbiter resolves severities.

### AC-008: the bench has an hm-novalidator arm
`scripts/bench_light_lane.py` accepts arm `hm-novalidator`: the hm arm's harness with the spec
command's spec-validator step removed, every other rendered file byte-identical to the hm arm's, and the
same prompt prefix, scripted DRI turns and provenance checks as the hm arm.

### AC-009: the tier-1 re-run is measured against the 10.0x bar and its result recorded
`tests/fixtures/hm_cost_p4/batches.json` lists every tier-1 batch run for this task in order; the first
complete one counts (5 tasks × 3 runs per arm for plain, hm and hm-novalidator, claude-sonnet-5-5). The bar:
hm transcript ratio ≤ 10.0 (rounded to 3 places) and hm pass rate (capped/leaked as failures) ≥ plain. The
test asserts that the SPEC's recorded result (met or missed, with the ratio) matches the counted rows; a
miss is recorded, never rerun into a pass. hm-novalidator's ratio and judge scope are recorded, not gated.

**Result (2026-11-10): missed.** Transcript ratio 10.243 (CLI 9.44) at harness 3063ad338e06, down from
11.359 at cdf28dce; every other guard held (pass rate 15/15 in all three arms, no capped or leaked run).
The one batch run counts; nothing was rerun. Per stage, hm's execute fell from $0.306 and 8.1 turns per
run to $0.236 and 6.5; spec, approve and wrapup did not move. hm-novalidator: transcript ratio 7.674,
15/15 hidden tests, judge overall 3.67 against hm 3.56 and plain 4.13 (one judge sample per run, noise
±0.67, so hm and hm-novalidator tie). Judge scope: all 45 runs were judged, blind, on the tier-1 rubric
only; tier 1 is saturated on the hidden tests, so this shows what spec-validator costs on small tasks
(≈2.6x of plain), not what it catches on a real SPEC. The judge gap to plain did not close (−0.73 →
−0.58): several runs still wrote one test function per AC, and the blind judge sees every AC id redacted
to the same token, so per-AC tests read as copies.

## Verification

| scenario | mode | test |
|---|---|---|
| S1 | unit (real pytest subprocess in tmp project) | AC-001 |
| S2, S3, S3b, S4 | unit (real collect in tmp project) | AC-002, AC-003 |
| S2 | unit (render) | AC-004, AC-005 |
| S5 | unit (render) | AC-006 |
| — | unit | AC-007, AC-008 |
| all | live eval (≈$20, run once) | AC-009 |

## Open Questions

none

## Refinement Decisions

- Bar (DRI card, 2026-11-10): transcript ratio ≤ 10.0 and pass rate ≥ plain, pre-registered; a miss is
  recorded as a miss.
- Binding (DRI card): name-convention discovery, read-only in `hm check`, recorded by `mark-tested`; no new
  command.
- Pre-change behaviour (DRI card): golden rows from the unchanged code; no pasted copy.
- Stale texts (DRI card): in this SPEC.
- spec-validator A/B (DRI card "측정"): measured through the AC-009 run's third arm; keeping or cutting it is
  a later DRI decision.
- Fresh sessions per stage: rejected by the DRI (card, 2026-11-10).
- Default (agent): the runner fallback is PATH `pytest`, so a project without `.venv` or gate commands
  behaves as today.
- spec-validator (11 critiques, all settled here as defaults; the DRI may veto): one shared matcher for
  mark-tested, `check --red` and find-unbound, case id before function name; a static fallback for a module
  that fails to import (valid RED); discovery dropped from the full `hm check` so `pending_test` stays the
  Bind signal (IRR-001 narrowed); AC-005 covers Steps 1–2, not only 0.3; AC-006 pins rows to spec time;
  AC-009 records the first complete batch instead of gating on a rerun; AC-008 matches the hm arm's prompt
  and DRI turns; AC-007 also checks the arbiter's description; S4's error names the AC and the patterns;
  the Non-Goal is narrowed to non-empty `test_ids`.
