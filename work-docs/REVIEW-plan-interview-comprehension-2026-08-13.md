---
type: review
task_slug: plan-interview-comprehension
status: APPROVED
created: 2026-08-13
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/structural/_surface_baseline.py
    - tests/structural/test_instruction_preservation.py
  scenario_misses: []
  task_slug: plan-interview-comprehension
  computed_at: 2026-08-13T00:00:00Z
---

# REVIEW — plan-interview-comprehension

## 🎯 Round 1 Summary

**Voter pool N = 4** (2 Claude reviewers + 2 cross-model), threshold **K = 2**.

| Source | Status | Findings |
|---|---|---|
| `code-reviewer` | returned | 3 × P1, 1 × P2 |
| `security-reviewer` | returned | 0 × P0/P1, 1 × P2 |
| `codex` | invoked | 2 × P2 |
| `antigravity` | invoked | 1 × P1, 2 × P2 |

**Grade: A** — zero `consensus-passed` P0/P1. **`unverified_severe` = TRUE**, so
`human_review_needed` = TRUE: three P1s were `manual-only` (single-source), which the grade
formula does not count.

**All eight surviving findings were fixed in this round.** That is a deviation worth naming:
the auto-fix loop applies only `consensus-passed` findings, and three of these were
`manual-only`. They were applied after I independently reproduced each one against the code
(counts, oracles, and a disable-the-fix discrimination check), not on the strength of a
single reviewer's say-so. Round 2 re-review is what confirms them.

### A note on the two-pass split

Step 3's Pass 1 redacts PR title / description / author / commit message. **This input has
none of those** — it is an uncommitted worktree diff, so the redaction is an identity
operation and the two passes would have seen byte-identical context. One dispatch per
reviewer was run instead, and this is recorded rather than silently skipped.

## 🔍 Drift Findings

**P1 — two files changed that no PLAN phase's scope lists.**

| File | Why it changed | Judgment |
|---|---|---|
| `tests/structural/_surface_baseline.py` | `render_surface()` gained `depth_override`, so AC-003's two sides go through ONE render path (the install-ref pin and frozen timestamp are what make renders comparable; a second implementation would drift) | Necessary, but Phase 0's scope named only "the golden and the generator that writes it" |
| `tests/structural/test_instruction_preservation.py` | ADR-007/008 are *replacements*, i.e. disappearances; four `_ALLOWED_REMOVALS` arms were required | Necessary, and the PLAN's own note said this gate would not fire |

Both are recorded in the PLAN's STATUS blocks, but the **phase scope lists were never
amended**, which is what drift means. No scenario misses: all six SPEC scenarios have
tests.

**Known incomplete phase (expected, documented):** Phase 3b has not run. It regenerates
`surface_baseline.json` at base after the squash-land, because `assert_sha_is_durable`
refuses a task-branch SHA. Two structural tests stay RED until it does.

## ✅ Consensus Findings

### P2 — `.get('comprehension', {})` does not guard a present-but-falsy value `[2/4]`

`codex:16d08108` + `antigravity:bcedfacf`, independently, same symbol, same tier, aligned
reasoning. `dict.get(k, {})` returns the stored value when the key EXISTS, so
`None.get('depth', …)` raises under `StrictUndefined`.

**Oracle (expression-level, decisive):** `{'comprehension': None}` → `UndefinedError: 'None'
has no attribute 'get'`; `{}` and absent → `'standard'`.

**Fixed** at all five template sites: `(config.interview.get('comprehension') or {}).get(…)`.

**Two corrections to the finding as filed**, both from running it rather than reading it:

1. **Reachability is nil.** Templates read the per-file `fe.context` built at synthesize
   time, not `bp.config`, and `_parse_comprehension` normalizes on read. No code path can
   deliver a malformed value. The fix is defense-in-depth and is labelled as such.
2. **The first regression test for it was a false green.** It mutated
   `blueprint.config.interview` after `synthesize` and rendered — and passed against the OLD
   expression too. Replaced with a direct expression test, verified to discriminate old vs
   new.

**Stated residual:** `or {}` catches falsy non-mappings only. A truthy non-mapping (`'oops'`,
`3`) still raises and is deliberately unguarded — equally unreachable, and an `is mapping`
ternary across five sites buys nothing but length. The test parametrize is scoped to what
the guard actually promises so it cannot drift back into a false green.

## ⚠️ Weak Consensus

None. No pair matched on surface while diverging on conclusion.

## 📝 Manual-Only Findings

Single-source. All fixed after independent reproduction.

### P1 — `--preset` + `--comprehension-depth` clobbers the rebuilt `interview` block
`code-reviewer`, `cli.py`. `update` is applied with `model_copy` **after** the
`_build_answers` rebuild, so seeding the whole OLD `interview` dict wins and re-imports the
previous preset's `main_loop.max_rounds` (Side ⇒ 5, Production ⇒ None) — a value the
emitters write and `plan.md.j2` branches on ("up to 5 rounds" vs "unlimited rounds").
**Fixed**: the seed is now guarded by `and not preset_override`; on that path the depth
travels through `_build_answers(comprehension_depth=…)`, which mutates only that key.

> **My test walked this exact line and could not see it** — it asserted only the depth,
> the one field the bug does not touch. New test asserts `interview["main_loop"]` against
> the NEW preset's `_preset_extras`.

### P1 — `--reinterview` silently resets an explicit `depth`
`code-reviewer`, `cli.py`. `--reinterview` sets `reused = None`, so ADR-002's read-side
overlay never runs; ADR-003 deliberately adds no install-time question, so the user cannot
re-express the value either. A `depth: minimal` opt-out — the zero-cost escape ADR-005 leans
on to justify the surface growth — was destroyed with no diagnostic, and a `deep` user
silently downgraded. **Fixed**: an unconditional re-apply from `pre_yaml_body` inside the
existing `reinterview and existing_yaml.is_file()` block. Unconditional, unlike the
neighbouring `autonomy` repair, because depth is never interview-asked, so there is no fresh
answer to discard.

> **My fixture made the branch untestable**: it stubbed `answers_from_harness_yaml` and
> `interview` to the same disk-derived object. The new test stubs `cli.interview` with
> preset-default answers and carries a precondition assert. Verified discriminating by
> disabling the fix and watching it fail.

### P1 — `/hm:plan` shipped two conflicting round preambles at `standard`/`deep`
`code-reviewer`, `plan.md.j2`. ADR-008 gated only Step A's heading; the ORIGINAL preamble
block still rendered alongside the partial's, with two different empty-state rules ("skip the
block" vs "say no change since last round"). **Measured: plan 2, spec 1.** This is verbatim
the rationale ADR-008 gives for replacing rather than appending, violated in the stage
ADR-008 is about — and the higher-traffic of the two. **Fixed**: the original block is now
gated behind `{% if _cd == 'minimal' -%}`. Re-measured: 1 at every depth, both stages.

> The fix itself broke AC-003 byte identity on the first attempt (`{% if … %}` on its own
> line leaves a newline under `trim_blocks=False`); `-%}` corrected it. **My test had a
> spec-only arm**; it is now parametrized over both stages × all three depths.

### P2 — guard order hides a missing `block` at `minimal`
`code-reviewer`, the partial. `_depth != 'minimal' and block == 'brief'` short-circuits, so a
future include site that forgot `{% with block = … %}` would render clean for every `minimal`
install and raise only for `standard`/`deep` users. **Fixed**: identity first on all four
guards.

### P2 — `/hm:configure` flag unquoted, and missing from §4 entirely
`security-reviewer`, `configure.md.j2`. Two halves. The quoting half is hygiene (a free-text
"Other" answer substituted unquoted is evaluated by the shell before the CLI allowlist sees
it). **The second half is a functional bug**: the flag was absent from §4's "Append when
changed" list, so an LLM following §4 literally would never have emitted it — ADR-003's own
defect class (prose with no execution path) reproduced one layer down. **Both fixed.**

## 🤝 Disagreements

None on severity. Three cross-model findings were **refuted** at the Step 3.6 PIDA gate, by
oracle rather than by argument:

| id | Claim | Refutation |
|---|---|---|
| `antigravity:91e719fc` (P1) | `{%- else -%}` eats a newline, breaking AC-003 | The AC-003 test passes against the pre-change SHA-256 golden. Run, not reasoned |
| `antigravity:05203f84` (P2) | No test executes `render_surface(depth_override="minimal")` | Two do. The model could not see them — **my payload omitted the new test files**, which is my error, not the model's |
| `codex:d76e8b9e` (P2) | An explicit `comprehension:` with empty body should warn | Judgment: an empty body is a legitimate "use defaults", and warning on it is indistinguishable from warning on absence |

## 🧊 Cross-model findings (frozen @ round 1)

Both models were invoked **exactly once** for this `/hm:review`. Rounds 2..N re-read this
section instead of re-invoking.

| id | model | severity | disposition | status |
|---|---|---|---|---|
| `16d08108d167c52b` | codex | P2 | accepted | fixed (consensus-passed with `bcedfacf`) |
| `bcedfacf002262cb` | antigravity | P2 | accepted | fixed (same cluster) |
| `d76e8b9ec8ebe3f4` | codex | P2 | rejected | dropped — judgment, recorded above |
| `91e719fc68dffab8` | antigravity | P1 | rejected | dropped — refuted by the AC-003 oracle |
| `05203f84eebe9ad3` | antigravity | P2 | rejected | dropped — refuted; cause was my payload |

`second_opinion_results`: `codex` → `invoked`; `antigravity` → `invoked`. No skips, no
failures.

### Iteration 2 (Grade: A → A)

Re-review of the five fixes by `code-reviewer` (the only reviewer whose scope the fixes
touched). **Two of my five fixes moved their finding instead of closing it.**

Fixes applied: 2 · Disclosed without fixing: 1 · Recorded open: 1

| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| 1 | P1 | Fix 1 suppressed the seed on `--preset` **presence**, but the compensating `_build_answers` path runs only on an actual **switch** — so `--preset Production --comprehension-depth deep` on an already-Production harness had no carrier at all: exit 0, no diagnostic, old depth persisted | `cli.py` | Applied — gate on `Preset(preset_override) != answers.preset` |
| 2 | P1 | Fix 2's re-apply was unconditional on a premise that was **inverted**: `_apply_dimension_overrides` runs at line ~376, *before* the block at ~463, so `--reinterview --comprehension-depth minimal` was overwritten by disk — and by `standard` when the file had no key. Not ignored: the opposite was persisted | `cli.py` | Applied — gated on `comprehension_depth_override is None`; comment corrected |
| 3 | P2 | `_ATOMIC_RATCHET` and this task's BASELINE-DELTA report different sizes for the same edit (`plan` +1 092 vs +1 211; `spec` +1 577 vs +1 198) | delta doc | **Disclosed, not fixed** — see below |
| 4 | P2 | The golden's `source_sha` is the branch point, so a mid-task regeneration would write post-change digests under a pre-change SHA and AC-003 would go tautological with nothing in provenance showing it | `_comprehension_golden.py` | **Open** — recorded, not fixed |

Both P1 fixes were verified by **reverting each and watching its test fail**, then restoring.
The round-1 tests could not have caught either: every `--preset` case in the file throws
`Side` at a `Production` fixture, so the equal-preset branch was untested by construction,
and no test passed `--comprehension-depth` alongside `--reinterview`.

**Finding 3 is disclosed rather than fixed.** The two figures measure different renders
(synthetic preset fixtures vs this repo's own `harness.yaml`), but that difference is worth a
handful of characters, not 119 and 379. The residual is almost certainly the same
pre-existing drift §2 discloses for `execute` — the ratchet's "before" is stale, so this
entry silently absorbs another task's movement. I did not decompose it; the suite cannot
(±2% tolerance). Written into the delta document, because an attribution that reports the
right total with the wrong cause is worse than none.

**Finding 4 is open.** No mechanism enforces "never regenerated by this task" — it is a
convention. Evidence that the oracle is live in this run: the first attempt at Fix 3 **failed**
AC-003 and the `-%}` version passed.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 8             | 0         | —   |
| 2         | A     | 2             | 2 (1 disclosed, 1 open, both P2) | 4 |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged
Status: **APPROVED**
human_review_needed: **true**
Counters: unreviewed 0 · prior-fix 4 · unattributed 0

> ⚠️ **Grade A but 5 unverified severe findings were present across the two rounds**
> (manual-only P1: three in round 1, two in round 2) — human review required.
>
> The letter is A because the grade counts only `consensus-passed` P0/P1 and every P1 here
> was single-source. All five are fixed and regression-tested, but **`consensus` never
> verified them** — one reviewer found them, and I reproduced them myself.
>
> **The pattern matters more than the count.** Three rounds in a row, the defects landed in
> the same place: CLI override ordering and my own tests being unable to see the branch they
> walk. Round 1 found three false greens in my tests; round 2 found that two of my fixes for
> them opened the mirror-image hole. Round 2's fixes have **not** been independently
> reviewed — round 3 is within the cap and is the obvious next step if this area is going to
> be trusted.

## Round 3 — the re-run that the payload gate forced (and what it caught)

At wrapup, `test_review_payload_persisted.py` went red: **rounds 1 and 2 above never ran
Step 3.4's `persist-payload`.** I skipped that step — the cross-model findings arrive with
ids already stamped, so the "stamp ids" half looked satisfied, and the persist rode along in
the same step and went with it. The gate's own `_KNOWN_MISSING` already recorded three
consecutive slugs missing the same line and concluded it was evidence about the step's
placement; this is the fourth in a row.

Post-hoc reconstruction is forbidden by the gate ("the corpus is only useful if its entries
are captures"), so the operator chose to **re-run the review properly** rather than waive it.
That re-run paid for itself immediately:

| Source | Status | Findings |
|---|---|---|
| `code-reviewer` | returned | **1 × P0**, 3 × P2 |
| `codex` | invoked | 1 × P2, 1 × P3 |
| `antigravity` | **failed** | `SUCCESS` response with an empty body — a documented degrade; **this model had no voice in round 3** |
| `security-reviewer` | not dispatched | conditional routing: clean in round 1, its finding fixed and re-verified, no new security surface |

### P0 — the golden's own durability check was a scheduled CI break

`test_the_golden_is_never_regenerated_by_this_task` asserted
`golden["source_sha"] == merge_base_sha()`. On a task branch `merge-base(HEAD, main)` is the
branch point, so it was green. **Once this squash-lands, HEAD *is* main and merge-base
returns HEAD** — the frozen pre-change SHA would mismatch a strictly later commit and CI
would go red **on the very commit that ships the golden**, with a message accusing the author
of regenerating it. The natural fix from that position is to re-stamp `source_sha`, which
destroys AC-003's oracle.

Root cause: a durability check pinned to a **moving** quantity. **Fixed** by a content-derived
signal that cannot move — at a genuine pre-change capture the partial did not exist, so
`git cat-file -e <source_sha>:<partial>` must return non-zero. True on any branch, before or
after the land. Verified: the frozen SHA reports the partial absent.

`codex:219eacbc` is the same root cause seen from the other side (a post-change re-capture is
indistinguishable from a Phase-0 one) and closes with the same fix — one of the few genuine
two-source agreements in this review.

### The rest

| Finding | Severity | Disposition |
|---|---|---|
| No test ran `--reinterview` **with** a preset switch — the only input where both `cli.py` guards are live | P2 | **Fixed** — parametrized arms for flag-present and flag-absent, also asserting the NEW preset's `main_loop` survives |
| `/hm:spec` renders `decision_depth` and `teach_back` inside "§2.3 Round preamble" | P2 | **Deferred** — a real placement defect, but render-byte affecting; fixing it now forces a fourth baseline re-measure. Recorded, not hidden |
| `--reinterview` repairs only `comprehension`; the sibling `deep_gate` overlay is still dropped | P2 | **Out of scope** — pre-existing, not introduced here. `interview.py:1322`'s own comment already says a third overlay should force a generic mechanism |
| `codex:cbeb2498` — explicit `comprehension: null` gets no warning | P3 | **Accepted, not fixed** — an empty YAML body is a legitimate "use defaults"; warning on it is indistinguishable from warning on absence |

**The reviewer explicitly cleared the two-guard interaction**, having walked the full
`--reinterview × --preset{switch,same,invalid,absent} × --comprehension-depth{given,absent,invalid}`
matrix: the guards are disjoint in the case that matters, and guard B's
`{**a.interview, "comprehension": …}` is narrow enough that it cannot leak the pre-switch
preset's block. Rounds 1 and 2 had each found the opposite, so this is the first round where
that area came back clean.

**Round-3 grade: A**, one `consensus-passed` P0 — fixed within the round. Round 1's payload is
now a genuine capture (`20260813T0700Z-round1-merged.json`); round 2's is unrecoverable and is
recorded in `_KNOWN_MISSING` with its reason, because manufacturing a second round to produce
a file would be a round run for the gate rather than for the code.

## Known-RED at wrapup (expected, not a regression)

`test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow` and
`test_surface_baseline.py::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction`.
Both need `surface_baseline.json` regenerated at base after the squash-land —
`assert_sha_is_durable` refuses a task-branch SHA by design. **PLAN Phase 3b owns this and
has not run.** Everything else in the suite is green; `ruff check`, `ruff format --check` and
`mypy --strict src` are clean. No commit was made from this stage.
