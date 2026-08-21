---
type: review
task_slug: bench-study-adoption
status: CHANGES_REQUESTED
created: 2026-08-21
reviewers_invoked: [design, functionality, robustness, consistency, security, concurrency, tests, codex]
consensus_method: cross-check
run_id: f59eeffb07aa
review_base: de8ea0511624ff34d88713d1560445c3c975b73e
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations:
    - .github/workflows/ci.yml
    - .github/workflows/nightly.yml
    - .github/workflows/release.yml
  scenario_misses: []
  task_slug: bench-study-adoption
  computed_at: 2026-08-21T14:42:35Z
---

# REVIEW — bench-study-adoption

## 🎯 Round 1 Summary

**Grade: D.** One consensus-passed P0, seven P1. Coverage gate `blocks_approval: true`.

This review's headline is not a finding. It is that **Phase 4's own gating criterion failed**, and
failed in a way no fixture could have predicted.

## ⛔ The live gate — Phase 4's exit criterion, executed

The PLAN made this the one piece of evidence that Phase 4's contract is answerable by real
reviewers: re-render this repo's harness, confirm the rendered command carries the new flags, then
run `/hm:review` and see whether seven live lenses produce passing probes.

**The render is correct.** `.claude/commands/hm/review.md` carries `--diff-files`/`--rev` at all
three sites; each of the four backing agent files carries the `repo_probe` contract three times.
Verified on disk after `make . --update`, not inferred from the templates.

**The reviewers produced zero probes.**

```
{"blocks_approval": true, "exercised": [],
 "missing": ["design","functionality","robustness","consistency","security","concurrency","tests"]}
```

**Root cause, and it is a design defect in Phase 4 rather than a delivery failure.** The contract
asks for `repo_probe` as "one top-level field beside your findings array". All seven lenses
returned **narrative prose**, some with JSON fragments embedded; none returned an envelope with a
findings array to sit beside. The main loop transcribes reviewer output into the result file
(Step 3's own contract), so what the agents actually emit is free-form — and a top-level field of
a JSON envelope is a shape they do not produce.

The probe was designed against an envelope that does not exist. Every automated test passed
because every fixture wrote the envelope by hand.

**The reviewers did read outside the diff.** `concurrency` cited `review_telemetry.py` and
`common_ground.py`; `design` cited `io_utils.py`; `security` cited the PLAN. Repository access is
live. **The canary failed to observe a thing that was true** — a false negative, which for a
detector is the worse direction.

**Per the operator override (2026-08-21) the phase is NOT reverted.** R1 is therefore live and
named: with this contract in force, a Production `/hm:review` cannot reach APPROVED. That is
recorded, not resolved.

## ✅ Consensus Findings

### P0

**`_blob` kills the whole complexity command on any binary file in the diff**
`review_churn.py:543` · voices: robustness · `caused_by: none`

`_blob` reads through `_git`, which passes `text=True`. A binary blob raises `UnicodeDecodeError`,
which is not `CalledProcessError`, so `_blob`'s except does not catch it and neither does `main`'s.
One PNG in a diff destroys the round's telemetry for every other file.

The sibling that already does this job — `_post_loc`, twelve lines away — deliberately omits
`text=True` and counts `\n` bytes for exactly this reason. The new code reused the shared text-mode
helper instead of the byte-mode sibling written for the case.

Contradicts `review.md.j2` Step 5c's own promise that a telemetry failure never takes the churn
measurement down: here the telemetry command itself dies.

### P1

**`build_probe_check` builds `tracked` from the live index while its docstring says it does not**
`lens_coverage.py:229` · voices: codex, robustness, consistency

Content is read at `rev` via `git show`; **membership** comes from `git ls-files`, which reads the
current index. The docstring asserts "the git INDEX is deliberately not a source here either" and
"pins the evidence to the code under review". Both are false for `tracked`. Across auto-fix rounds
the index moves while `rev` stays fixed, so a probe legitimately quoting a file tracked at `rev`
can be rejected — a false access-loss signal from the access-loss detector.

Flagged during Phase 4's A.5 round 3 as outside that round's closed scope. It was outside S12; it
was not outside reality.

**`record_row` is the fifth copy of a primitive the codebase has a public helper for**
`review_complexity.py:132` · voices: codex, concurrency, robustness, design

`io_utils.append_atomic_line` exists, and its docstring addresses this exact caller: *"a NEW caller
reaching across a module boundary for a `_`-prefixed name is how a fifth copy starts, so new
ledgers import this one."* It raises above PIPE_BUF rather than writing a line the kernel may split.

`record_row` hand-rolls the loop with no size guard, on a **global** sink
(`review-complexity.jsonl`, no slug in the path — unlike `oscillation_path`). A 40-file round is
comfortably past 4096 bytes, and CLAUDE.md documents concurrent sessions as normal. Two rounds can
interleave into invalid JSON with nothing surfaced.

**`collect_complexity` misreports a rename as creation**
`review_churn.py:556` · voices: codex, functionality

`_parse_name_status` keys renames by post-path only; the old path is consumed and dropped. So
`_blob(pre_ref, new_path)` misses, `pre_src` is `None`, `_endpoint` reads that as a legitimate
absence, and the row says `measured` with a null pre side — "complexity appeared from nothing" for a
file that merely moved. No rename fixture exists in any test.

**`read_blob` lets `TimeoutExpired` escape and crash the gate**
`lens_coverage.py:233` · voices: security

Only `CalledProcessError` is caught, and `coverage_verdict` sits outside `main`'s try. A probe
naming a *real* tracked path whose `git show` exceeds 60s crashes `hm lens_coverage check` —
the command three sites call to decide `blocks_approval`. Fail-closed becomes unavailable.

**`_endpoint` catches only `SyntaxError`; `RecursionError` escapes**
`review_complexity.py:97` · voices: robustness

`ast.parse` and `_nesting_depth`'s unbounded recursion can raise `RecursionError` on generated or
deeply nested source. Same uncaught path as the P0. `unparseable` is the bucket that already exists
for "could not be analyzed".

**The confirmation pass validates probes against round 1's stale diff list**
`review.md.j2:1010` · voices: design

`probe_flags` is template-scope, so all three sites embed the mktemp path written once in Step 3.
The confirmation pass redefines the diff as `review_base..<freeze commit>` — the whole review,
including every auto-fix round's edits. A confirm-pass lens quoting a file the fixer edited in
round 2 is not in round 1's list, so it passes as out-of-diff evidence. Fires on any review that
needed one repair round.

## 📝 Manual-Only Findings

- **P2** `git ls-files` parsed with `splitlines()` instead of the repo's NUL-safe `-z` convention
  (`lens_coverage.py:229`, security). A tracked filename containing a newline fragments.
- **P2** three near-identical git-blob readers now exist across two modules (design). Not worth
  extracting at two call sites; worth it at a fourth.
- **P3** `test_analysis_is_deterministic_across_runs` calls a pure function twice in one process and
  varies none of the nondeterminism sources its docstring names (codex).
- **P3** the round-trip table comment says "a Side render is unchanged"; Side snapshot hashes did
  move, via the shared skill (codex). Narrow the claim to the round-trip count.
- **P3** `test_complexity_cli_appends_a_row`'s docstring argues the `INTEGRATION=1` gate was
  mis-scoped, then keeps the gate (codex). The reasoning for keeping it — a real subprocess — is in
  the docstring but reads as contradiction.

## 🤝 Disagreements

`review_complexity.record_row` drew P1 from codex, concurrency and design, and **P2** from
robustness, which judged it acceptable as a copy of the already-accepted `record_oscillations`
pattern. The P1 side is better founded: `record_oscillations` is per-slug and refuses to write an
empty payload, while `record_row` is global and writes unconditionally. Recorded rather than
averaged.

## 🧊 Cross-model findings (frozen @ round 1)

- **codex** — `status: invoked`, 7 findings, 64.4s. Three folded into consensus above (index
  membership, record_row atomicity, rename). Four are P2/P3, listed under manual-only.
- **antigravity** — `status: skipped`. `exit 1; CLI said: <<<<empty>>>>`. Warn-and-proceed; the
  verdict is Claude-plus-codex only for this review.

## 🔍 Drift Findings

**P1 scope_violation** — `.github/workflows/{ci,nightly,release}.yml` are in the reviewed range but
belong to the previous task. Cause: `freeze resolve-base` fell through to `HEAD~1` because this
task branch has no commits of its own (all work uncommitted), and every `merge-base` rule that
returns HEAD is skipped by design. `freeze.py:52-91` documents this as "over-scope rather than
fail-open". Not a defect in this change; recorded so the next reader does not read those files as
this task's work.

## Iteration 2 — repair round (operator chose "fix P0 + P1, defer the probe contract")

Fixes applied: 7 of 7 severe findings. Full suite, `ruff check`, `ruff format --check` and
`mypy --strict` all green afterwards.

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| 1 | P0 | binary blob kills the command | `_blob` returns bytes; `_endpoint` owns the decode decision and counts undecodable content byte-accurately |
| 2 | P1 | `tracked` from the live index | `git ls-tree -r -z --name-only <rev>` — what the docstring already claimed |
| 3 | P1 | fifth copy of the append primitive | `io_utils.append_atomic_line`, plus `_chunks` so a large round is split rather than lost to the helper's raise |
| 4 | P1 | rename read at the wrong name | `_parse_renames` keeps the old path for the pre endpoint |
| 5 | P1 | `TimeoutExpired` crashes the gate | `SubprocessError` |
| 6 | P1 | `RecursionError` escapes | folded into `unparseable`; no new status value |
| 7 | P1 | confirmation pass uses round 1's diff list | template instructs a fresh derivation from `review_base..<freeze commit>` |

**Three further defects surfaced while repairing, all mine:**

- **`UndefinedError` in `return_envelope.md.j2`.** It read `config.preset` directly, and
  `test_agent_body_partials` renders a body partial with a plain-dict context that has none —
  twelve tests down. Guarded with `is defined`.
- **A backward-compatibility break, reported by four pre-existing tests.** Making
  `--diff-files`/`--rev` required under Production fails every harness rendered before this
  change, whose `review.md` has no flags to pass. **Contract amended**: absent → skip with a
  loud stderr line naming the remedy; empty → still a hard error, because an empty list is a
  no-op wearing the appearance of a live canary. Absent and empty stay distinct. This edits a
  PLAN contract during a repair round and is flagged as such rather than folded in quietly.
- **The surface estimate was 2.6× low** — 1.44k predicted, 3817 measured. Raised to the
  measured figure with the reasons in the delta doc; no prose was trimmed to fit, because every
  block added since the estimate exists because a reviewer named its absence.

**Two of my own repair tests were the confound class this review found four times.** The P0 test
first passed `bytes` straight to `complexity_row` and **passed against the unrepaired code** —
`ast.parse` on undecodable bytes already raised `SyntaxError`; the real crash is a layer earlier,
in `_blob`. Moved to the CLI layer. The rename test then failed for a fixture reason (content
changed across the range, so git correctly saw delete+add, not a rename). Both recorded in the
test files.

**Twice this session a green run was taken as evidence and was not.** Once a round-trip check ran
against test files that do not count round trips; once a suite ran with cwd drifted to the base
repo, testing unmodified source. Both are the same mistake — not asking what the green was green
about.

### Still open

`repo_probe` itself. The gate failed because the contract asks for a top-level field of an
envelope reviewers do not emit; option 1 deferred it, and R1 stays live. Nothing in this repair
round touched it.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 8 (1×P0, 7×P1) | — |
| 2 (repair)| —     | 7             | 1 (probe contract, deferred) | 3 (all repaired) |

Final grade: not re-computed — a re-review was not dispatched.
Iterations used: 2 / 3
Exit reason: operator-directed repair, deferred re-review
Status: CHANGES_REQUESTED
human_review_needed: true

**Why the auto-fix loop did not run.** Two of the eight findings are defects in the review
machinery this task just changed — the probe validator and the coverage gate. Repairing them with
the loop that consumes them would have the round measuring its own instrument. The operator decides
the order.
