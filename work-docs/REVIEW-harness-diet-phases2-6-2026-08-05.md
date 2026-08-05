---
type: review
task_slug: harness-diet
status: CHANGES_REQUESTED-then-resolved
created: 2026-08-05
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, codex, antigravity]
consensus_method: cross-check
second_opinion_results:
  - model: codex
    status: invoked
    reconciliation: [4 findings adapted; 2 folded into consensus clusters]
  - model: antigravity
    status: invoked
    reconciliation: [3 findings adapted; 2 folded into consensus clusters]
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: harness-diet
  computed_at: 2026-08-05T00:00:00Z
---

# REVIEW — harness-diet Phases 2–6

Scope: the Phase 2–6 diff (45 files, 643 added lines). Phase 1 was reviewed separately
(`REVIEW-harness-diet-2026-08-05.md`, final grade A).

Voter pool N = 5 (code-reviewer, security-reviewer, concurrency-reviewer, codex,
antigravity). Threshold K = 2.

## 🔍 Drift findings

`result: clean`. Two notes that are PLAN inaccuracies rather than code drift:

1. **Phase 6 named an artifact that does not exist.** "Regenerate the `tests/e2e/sandbox*/`
   render snapshots here." Both `tests/e2e/sandbox/` and `tests/e2e/sandbox-plugin-test/`
   are **gitignored scratch directories** (`.gitignore:117`) holding a `CLAUDE.md`, a
   `hello_world.py` and a `pyproject.toml` — not snapshots, not tracked. The real render
   snapshots are `tests/snapshot/*.expected.yaml`, which were regenerated twice. Checked
   rather than assumed; had it been assumed, this would have read as an incomplete phase.
2. **`cli.py` was edited outside Phase 3's named site list.** Phase 3 named
   `interview._parse_autonomy` and `interview.py:718-720`; `cli._build_autonomy_override`
   and (in round 2) `cli.py`'s preset-switch rebuild were also required. Both are inside
   ADR-013's stated intent, and both are recorded in the PLAN.

## ✅ Consensus findings (K≥2)

### P1 — `consensus-passed` — multi-year archive partial failure duplicates entries unboundedly
Voices: concurrency-reviewer (P1), antigravity (P1); corroborated at P2 by code-reviewer
and codex (separate tier, not bridged per Step 4c).

`_prune_archivable` archived every year and only then returned the pruned lines. A failure
on the second year unwound past the first year's already-durable `atomic_write`, so the
caller kept the unpruned text and those entries lived in **both** files. They remain
`count:1` and aged, so the next `upsert-failure` archived them again — a persistent fault on
one year made unbounded duplication the steady state, not a one-shot crash artifact. The
code's own docstring claimed the pass "skips the eviction entirely rather than
half-applying it", which was false across years.

**Fixed** (round 2): per-year `try`, dropping only the indices whose year actually landed.
Partial-but-correct replaces all-or-nothing-but-wrong.
**Gate added**: `test_one_years_archive_failing_does_not_strand_or_duplicate_another_year`.
The pre-existing failure test used a single-year fixture, so the multi-year case was
unasserted — which is why four reviewers had to find it instead of the suite.

### P1 — `consensus-passed` — a partial `autonomy:` block escalates an existing project
Voices: codex (P1), antigravity (P1).

`AutonomyConfig.model_validate(value)` filled omitted fields from the promoted class
default, so `autonomy: {autopilot_persistent: false}` became `level: auto_safe`, and
`autonomy: {step_cap: 20}` became fully auto-armed. ADR-013 had explicitly declined a
predicate here as over-reach.

**Overturned on new evidence, not on reviewer volume.** The docs finding below establishes
that an explicit block round-trips verbatim, which makes a partial block the *only* route by
which the promotion can reach an existing project — and it reaches it in the worst shape,
overriding an explicit `autopilot_persistent: false`.

**Fixed** (round 2): `_parse_autonomy` now applies the conservative value to the two
flipped fields only (`level`, `autopilot_persistent`) when a present block omits them.
Every other field keeps its ordinary class default, so this is scoped to ADR-010's flip and
is not a general strictness change. Applied to a copy — the branches above it copy only
conditionally, so an in-place `setdefault` would have mutated the caller's parsed yaml.

## 📝 Manual-only findings — SINGLE SOURCE BUT INDEPENDENTLY VERIFIED

The consensus filter tags these `manual-only` because one voice raised each. That tag is
about corroboration, not about truth: **each was verified directly against the code before
being acted on**, and the two P0s are the most consequential findings of this review. The
grade below counts only consensus-passed findings, so these do not lower the letter — which
is precisely why `human_review_needed` exists.

### P0 — the archive never reaches git on the default path (code-reviewer)
`commit_base_memory` stages only paths passing `_is_human_memory_tier_path`, whose allowlist
was four exact files plus `session/*.md`. `.claude/memory/archive/failures-<YYYY>.md` matched
neither. On the `feature_branch_workflow` path — the Production default and this repo's own
setting — an eviction therefore produced a commit that **deleted** entries from the tracked
`failures.md` and committed no replacement; the archive sat as untracked base dirt, invisible
to a collaborator, a fresh clone, or `git clean -xdf`. ADR-005 says "archive, never delete";
the implementation did the opposite on the default path.

Verified: `rg` shows `worktree.py:3990` (`_path_owner`) was the only production reference to
`memory/archive`; the fold allowlist at `worktree.py:4790` did not contain it.

This is a **third instance** of the failure the comment above that allowlist already records
for `pending-proposals.md` / `pending-drift.md`: "the escalation output the whole count>=3
machinery exists to produce simply never reached git." The correspondence test written after
that incident derives its expected set by scanning the rendered **wrapup template**, so a
writer invoked from Python inside `upsert-failure` is structurally invisible to it — it
passed before and after this fix.

**Fixed**: `.claude/memory/archive` added to `_HUMAN_MEMORY_TIER_PATHSPEC` and a directory
clause to `_is_human_memory_tier_path`.
**Gate added**: `test_the_archive_is_folded_into_the_base_memory_commit`, asserting the
predicate directly (with negative controls for a non-`.md` file and a sibling directory)
rather than through the template scan that cannot see it.

### P0 — a `--preset` switch destroys an explicit `gated` autonomy (security-reviewer)
`cli.py`'s preset-switch branch rebuilt answers via `_build_answers(...)` **without**
`autonomy=`, landing on `_build_answers`'s bare `AutonomyConfig()` — whose class default
ADR-010 had just flipped to `auto_safe` / persistent. `model_copy(update=update)` restores
autonomy only when `--autonomy-level` / `--autonomy-persistent` was passed. So
`/harness-maker:make --update --preset <other>` rewrote a `harness.yaml` that literally says
`level: gated` / `autopilot_persistent: false` — the off-switch the README documents — into
persistent auto-advance, after which the SessionStart autoarm hook armed it every session.

Verified by reading the branch: the same block already carries a comment worrying about
exactly this class of loss for `feature_branch_workflow`, and judges it benign *today*.
ADR-010's flip is what turned the same hazard into an escalation on a second field.

**Fixed**: `autonomy=answers.autonomy` passed through the rebuild.

### P1 — the retired-key advisory logs at INFO, which this package discards outright (code-reviewer)
`rg 'basicConfig|setLevel|logging.config' src/` returns zero matches, so the root logger
sits at WARNING and `logging.lastResort` also fires only at WARNING+. `hooks/autopilot_autoarm.py`
states this reasoning in-code at its own log site and uses `logger.warning` for it.

The Phase 2 advisory therefore reached **no user, ever**, and the once-per-project memo was
guarding a message nobody could see. The test written for it forced
`caplog.at_level(logging.INFO)` and so passed regardless — the vacuous-test pattern, in a
test authored during this same task after the pattern had already been hit twice in it.

**Fixed**: `logger.warning`, and the test now captures at WARNING and asserts `levelno`,
so it fails if the level regresses.

### P1 — the CHANGELOG and README advertised a migration path that cannot occur (code-reviewer)
Both claimed `/harness-maker:make --update` delivers the promoted autonomy default. It does
not: every `harness.yaml` any previous version rendered contains all six `autonomy:` fields
explicitly (the template emits them unconditionally), `answers_from_harness_yaml` →
`_parse_autonomy` round-trips them, and the template's `else "auto_safe"` arm is unreachable
whenever `config.autonomy` is present — which it always is.

Verified against `git show HEAD:.claude/harness.yaml`, which carries all six.

The PLAN itself said those `else` literals were "the *unreachable* arm for a normal render",
and the CHANGELOG was written claiming that route works anyway. This repo's memory already
records the identical confusion for the feature-branch flag ("re-render ≠ model switch").

**Fixed**: both documents now state that the flip reaches new installs only, and name the
two real routes (edit `harness.yaml`, or `harness-maker configure --autonomy-level`).

### P2 — `except Exception` also swallowed the post-splice marker-integrity check (concurrency-reviewer)
`_locate_block` on the spliced text validates data integrity, not archive I/O; reporting a
duplicated marker as "archive pass skipped" would misclassify corruption as a benign notice.
**Fixed**: hoisted out of the `try`.

**Honest scope note.** The accompanying test does **not** cover the hoist. Verified by
moving the check back inside the `try` — the test still passed, because the corrupt input it
builds is caught by the pre-existing `_locate_block` at the top of `_upsert`. The hoist is
forward defense with no reachable failing input today (`_upsert` already rejects bodies and
occurrence notes containing markers, and heading-shaped body lines, so the splice cannot
introduce a marker the input lacked). The test was renamed to what it actually asserts
rather than left implying a guard that does not exist.

### P3 — a `0001-01-01` heading produced `failures-1.md` (codex)
The heading regex accepts it and `strptime` parses it; `archive_path` interpolated a bare
`int`. No traversal (the int conversion rules that out), but the filename contradicts the
documented `failures-<YYYY>.md`. **Fixed**: `f"failures-{year:04d}.md"`.

## ⚠️ Accepted / deferred (recorded, not fixed)

- **P2 — command `description:` is English-only for a `ko` harness** (code-reviewer).
  `_COMMAND_DESCRIPTIONS` is keyed by rendered path, and `commands/hm/help.md` is the same
  path for both locales. A `ko` user sees 15 English one-liners in the tool picker, which
  contradicts CLAUDE.md's "user-facing output follows locale". Fixing it means keying the
  table by `(path, locale)` with an `en` fallback and threading `answers.locale` through —
  real work, cosmetic payoff, and not in this PLAN's scope. **Deferred deliberately**, and
  `tests/structural/test_command_descriptions.py` renders only the `en` profile, so the gap
  is currently unguarded.
- **P2/P3 — `_ADVISED_RETIRED_KEY_PATHS` is process-global and keyed only by path**
  (codex P3, antigravity P2 — tier split, no consensus). A retired key removed and later
  reintroduced at the same path in one long-lived process produces no second advisory, and
  the set leaks across tests that do not clear it. Kept: "one advisory per project" is the
  requirement, and the alternative (content-keyed identity) buys little for a message that
  fires once per upgrade. The one test module that depends on it clears it in an autouse
  fixture.
- **P2 — a legacy heading-shaped body line can split an entry across archive and live file**
  (security-reviewer). `_upsert` already refuses to *write* a heading-shaped body line, so
  only a hand-edited legacy entry can contain one. Not fixed.
- **The fresh-install non-tty path delivers `auto_safe` without prompting**
  (security-reviewer, framed P1). `effective_autoloop = autoloop or (not sys.stdin.isatty())`
  means a slash-command install never runs `_ask_autonomy`. **This is the intended
  behaviour**, explicitly requested for this task and now documented in the README as "on by
  default since 0.47.0" — the promotion is meant to reach new installs. The genuinely
  defective subsets of that path (a preset switch discarding an explicit block; a partial
  block overriding an explicit refusal) are the two fixes above. Recorded so the
  disagreement is visible rather than averaged away.

## 🤝 Disagreements

- **`interview.py:666` (bare `AutonomyConfig()` in `_build_answers`).** security-reviewer
  called it a P1 escalation; code-reviewer explicitly cleared it, noting `_parse_autonomy`
  overwrites it on the load path. Both are correct about different paths: the overwrite
  happens on **re-render**, and no overwrite exists on a **fresh install**. Kept bare — it
  is the delivery site the promotion needs — with the two real escalation routes fixed
  around it. Not merged into a middle position.
- **Archive multi-year severity.** P1 (concurrency-reviewer, antigravity) vs P2
  (code-reviewer, codex). Not bridged, per Step 4c. Treated at P1.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | disposition | note |
|---|---|---|---|---|
| `6a8b59939c6e801c` | antigravity | P1 | accepted | multi-year archive duplication — fixed |
| `ace3b0bf6050aa78` | codex | P2 | accepted | same defect, lower tier — fixed |
| `066d4aa09113d4b9` | antigravity | P1 | accepted | partial autonomy block escalates — fixed |
| `d6eb0f6805953eb7` | codex | P1 | accepted | same defect, with the `{autopilot_persistent: false}` case — fixed |
| `a1e938cb97ae404c` | antigravity | P2 | accepted | `_ADVISED_RETIRED_KEY_PATHS` module state — deferred with rationale |
| `ef5c7101587c8d97` | codex | P3 | accepted | same, plus the reintroduced-key case — deferred |
| `5c4f3d020fe392da` | codex | P3 | accepted | `failures-1.md` zero-padding — fixed |

Both models returned `status: invoked`; neither degraded. 7/7 cross-model findings were
accepted — no refutations this round. Both independently found the two defects that also
carried Claude-reviewer votes, and codex supplied the `{autopilot_persistent: false}` case
that turned ADR-013's accepted limitation into a fixable defect.

## Round 1 grade

Consensus-passed P0 = 0; consensus-passed P1 = 2 → **Grade B**.

`unverified_severe` = **TRUE** (two verified P0s and two verified P1s tagged `manual-only`).
`human_review_needed` = **TRUE**.

The letter is misleading on its own and is reported here with that caveat: the two most
serious defects of this review are single-source by the counting rule and therefore invisible
to the grade. Both were verified against the code and both are fixed.


---

# Rounds 2–4

## Round 2 — re-review of the round-1 fixes

Re-spawned the three Claude reviewers on the delta only. Cross-model models were **not**
re-invoked: exactly one call per `/hm:review` is the contract, and rounds 2..N re-read the
frozen Section 7.

| Reviewer | Result |
|---|---|
| concurrency-reviewer | **0 findings.** Verified the partial-prune cannot split a heading from its body, `year_of_index` is total over `drop` so no `KeyError` is reachable, marker lines can never enter `drop`, and the pruned file still round-trips. Independently agreed the hoisted `_locate_block` has no reachable failing input, matching the honest scope note. |
| security-reviewer | P1 + P2 |
| code-reviewer | P1 |

**Both P1s were defects in my own round-1 fixes.**

### P1 — `--reinterview` was still an escalation route (security-reviewer)
`--reinterview` sets `reused = None`, so `answers_from_harness_yaml` — and therefore
`_parse_autonomy` — never runs; combined with the non-tty auto-flip, an existing project's
explicit `gated` was rebuilt from the promoted class default.

**A recurrence, not a new defect.** The identical bug was found once before for
`worktree.feature_branch_workflow`, and its fix sits on the immediately adjacent lines
carrying its own "REVIEW security P2" note. A second field was added to the same rebuild
path without inheriting that guard — visible to anyone who read one line up.

### P1 — the corrected migration instruction named a command that does not exist (code-reviewer)
The round-1 fix replaced a false `--update` claim with
`harness-maker configure --autonomy-level …`. There is no `configure` subcommand. **The
second wrong migration instruction in the same paragraph rewritten to fix the first.**

Verified by running both: `harness-maker configure` → "No such command"; `harness-maker make
. --update --autonomy-level auto_safe --autonomy-persistent` → writes `auto_safe` / `true`.
The docs now carry the executed form. A new gate,
`tests/structural/test_documented_commands_exist.py`, fails the build when a shipped doc
tells a user to run a command Typer does not accept.

### P2 — README claimed 0.47.0 renders auto-advance on; the interview still defaults it off
Both are now stated: on by default for **non-interactive** installs (the common case), and
the interactive prompt still treats a bare Enter as `gated`, because a non-answer is not
consent. Chose to correct the prose rather than flip the prompt's default — under ADR-013's
own logic, silence must not escalate.

**A fix that was itself broken.** The `--reinterview` fix shipped without importing
`_parse_autonomy`. Nothing exercised the line, so it would have passed the unit suite; the
end-to-end test written alongside it caught the `NameError` immediately.

## Round 3 — three more P1s, all in the round-2 fixes

### P1 — the `--reinterview` re-apply clobbered consent
It ran unconditionally, **after** `_ask_autonomy` and **after**
`_apply_dimension_overrides`, so it discarded a fresh interview answer and an explicit
`--autonomy-level`, inverting `--reinterview`'s own contract. The reviewer also dismantled my
stated rationale: the `feature_branch_workflow` precedent I copied is never interview-asked,
so "the same defect, one field over" did not carry even though the defect it fixed was real.
**Fixed**: gated on `not _asked and not _flagged`.

### P1 — the absent-block case still escalated
The re-apply fired only when the on-disk value was a dict, so a harness predating the
`autonomy:` key fell through to the promoted default — contradicting the README claim
written two rounds earlier. **Fixed**: absent block on an existing harness pins `gated`.

### P1 — the new gate could not see the install entry point
`_CODE_SPAN` counted only shell-tagged fences. README's paste-into-Claude bootstrap — the
documented entry point for a new install — is an **untagged** fence, and the line inside it
reads `Bash  harness-maker make`.

This is the failure CLAUDE.md already records for `commands/make.md`: *a gate scoped to the
artifact being fixed lets the identical defect survive in the install entry point.* The gate
built to stop a wrong command from shipping could not see the most important command in the
repo. **Fixed**: untagged fences are scanned for lines carrying an explicit run marker
(`Bash`/`Run`/`$`/`>`), which is what separates an instruction from prose.

## Round 4 — closing the gate's own false negatives

Round 3's two P2s were both false negatives in that gate, and were fixed rather than
deferred: `_DOCS` is now **discovered** (`README*`, `CHANGELOG`, `docs/**` minus `adr/`)
instead of a fixed three-file tuple that missed `docs/BOOTSTRAP.md` and its 11 invocations;
`_current_release_section` keeps `[Unreleased]` **plus** the first release, so a shipped
release does not drop out of coverage the moment development resumes.

Tightening for the resulting false positives required `harness-maker` to be in **command
position** — three real cases drove it: prose inside an `echo` string, a diagnostic
`harness-maker installed=0.7.3`, and `…/plugins/local/harness-maker pull`, where the tool
name is a **path component** and `pull` is git's subcommand.

## Every gate added this review was verified to bite

Passing proves nothing about a negative gate. Each was broken deliberately and observed to
fail, then restored:

| Gate | Mutation | Result |
|---|---|---|
| render-side retired-key filter | delete the `and k not in …` clause | fails |
| `--reinterview` consent gating | replace the condition with `if True:` | fails |
| documented-command gate | plant `harness-maker configure` in README | fails |
| …on the install entry point | break only README line 75 | fails |
| …on a discovered doc | break only `docs/BOOTSTRAP.md` line 81 | fails |

One test was found vacuous and **relabelled rather than left implying coverage**: the
marker-integrity test exercises the pre-existing `_locate_block` at the top of `_upsert`, not
the hoisted one — verified by moving the hoist back inside the `try` and watching it still
pass.

## Deviation — the round cap was exceeded

`max_review_rounds: 3`; this ran **4**. Round 3 returned three verified P1s, all introduced
by round-2 fixes. Stopping at the cap would have shipped known P1s in order to respect a
number. The cap is recorded as exceeded rather than the findings deferred to honour it.

## Review Iteration Summary

| Iteration | Grade | Fixes applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 12        | —   |
| 2         | B     | 9             | 3         | 3   |
| 3         | B     | 3             | 2         | 3   |
| 4         | **A** | 2             | 0 severe  | 0   |

Final grade: **A** — no open P0/P1. Remaining items are P2/P3 recorded above as deliberate
deferrals (ko-locale command descriptions; the `_ADVISED_RETIRED_KEY_PATHS` path-keyed memo;
a legacy heading-shaped body line).

Iterations used: 4 / 3 (see Deviation)
Exit reason: converged
Status: **APPROVED**
human_review_needed: **false**

The flag measures one thing: whether an unresolved `manual-only` / `weak-consensus` P0 or P1
is still present. At round 4 every P0 and P1 is resolved and gated, so it is false.

An earlier draft of this line said **true**, on the reasoning that fourteen findings landed
and **eleven were defects I introduced** — seven of them while fixing the other four, each
time on a green suite. That is worth recording, and it is recorded here, but it is not what
this flag means. `human_review_needed: true` tells the operator to stop and inspect before
wrapup; setting it for process unease rather than for an unverified finding would degrade
the signal for the case it exists to catch.

The honest summary belongs in prose, not in the flag: the letter grade says A, and what
earned it was four rounds of adversarial re-review, not the test suite.
