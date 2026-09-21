---
type: review
task_slug: dev-mode-removal
status: APPROVED
created: 2026-09-21
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 379a41407618
review_base: 3852e084368baedabe3c573e40e9fdf8dbd9c9a4
drift_verdict:
  result: scope_violation
  scope_violations:
    - commands/make.md
    - skills/hm-make/SKILL.md
    - scripts/codex_engine.py
    - README.md
    - README.ko.md
    - docs/ARCHITECTURE.md
    - docs/HOW-IT-WORKS.ko.md
    - docs/assets/showcase-diff.md
    - work-docs/BASELINE-DELTA-ai-native-sdlc-vs-intent-world.md
    - work-docs/BASELINE-DELTA-assumption-entry-and-evidence-locator.md
    - work-docs/BASELINE-DELTA-intent-layer-ops.md
    - work-docs/BASELINE-DELTA-mission-context-loop.md
    - work-docs/BASELINE-DELTA-objective-gap-proposal.md
    - work-docs/BASELINE-DELTA-observability-rows-at-base.md
    - work-docs/BASELINE-DELTA-outcome-measure.md
    - work-docs/BASELINE-DELTA-playbook-alignment.md
    - work-docs/BASELINE-DELTA-workflow-steps-vs-model-capability.md
  scenario_misses: []
  task_slug: dev-mode-removal
  computed_at: 2026-09-21T00:40:00Z
---

# REVIEW — dev-mode-removal

## 🎯 Round 1 Summary

Seven lenses in four dispatches plus one cross-model voter (codex, `status: invoked`). Nine
findings after the merge, three of them P1. **Two independent voices — the core lens and the
cross-model voter, seconded at P2 by the security lens — landed on the same defect**, which is
the one that mattered: the new knob could be silently defanged.

## 🔍 Drift Findings

`scope_violation` — seventeen files outside any PLAN phase's scope list. Two groups, both
declared in the PLAN's execution notes before this review ran:

1. **Three plugin-root files** (`commands/make.md`, `skills/hm-make/SKILL.md`,
   `scripts/codex_engine.py`) pass `--dev-mode` to the CLI and ship at the SAME version as it,
   so ADR-006's version-pin argument does not cover them. `commands/make.md` is also the real
   onboarding interview, which AC-009 requires to stop asking.
2. **Nine `work-docs/BASELINE-DELTA-*.md`** carry past tasks' arm names as literal strings that
   their invariance tests compare against the LIVE `ARMS`; re-spelled 1:1, content untouched.

The remaining five are user-facing docs that describe the retired axis (`README*`,
`docs/ARCHITECTURE.md`, `docs/HOW-IT-WORKS.ko.md`, `docs/assets/showcase-diff.md`). PLAN Phase 5
named the English `HOW-IT-WORKS` and `CLAUDE.md` but not its siblings.

## ✅ Consensus Findings

### P1 — `security.gates.spec_gate` overrode an explicit `spec.strictness: block` (FIXED)

`code-reviewer` (design/functionality) and `codex` independently; `security-reviewer` traced the
same path and filed it at P2, declining to promote it because the two-knob split predates this
diff.

`evaluate()` gated hook ACTIVATION on `resolve_strictness(cfg) == "block"` but took the exit code
from `_resolve_severity`, which read `security.gates.spec_gate` — a key the preset templates emit
as a LITERAL (`Side: warn`, `Production: block`). A Side project that set `spec.strictness: block`
therefore registered the hook, printed the missing-SPEC message, and allowed the write anyway.
The knob's own name promises the opposite. This is `[fail:design] template-literal-shadows-config-key`
with a second name on it.

**Fix:** severity is now the strictness (`_resolve_severity` reads through the one resolver), and
both `harness-yaml` templates render `security.gates.spec_gate: {{ strictness_of(config) }}` so
the on-disk value cannot disagree with behaviour. Two new tests pin both directions — an explicit
`block` blocks with the legacy key saying `warn`, and an explicit `warn` stands aside with the
legacy key saying `block`. `tests/unit/test_spec_gate.py`'s severity fixtures were migrated:
the old "warn severity allows with a message" path no longer exists, and `_resolve_severity`'s
other arm is pinned directly because `evaluate` can no longer reach it.

### P1 — the AST singleton scan missed four ordinary dict spellings (FIXED)

`test-reviewer`, marked BLOCKING. `visit_Call` matched only positional `.get` / `.setdefault`, and
`_dict_bound_to_spec` never considered a `Call` parent — so `spec.update({"strictness": …})`,
`spec.pop("strictness")`, `spec.get(key="strictness")` and `spec |= {"strictness": …}` all passed
green with a second real writer present. The docstring's "two accepted limitations" was therefore
false: these are not evasion tricks, they are what a future engineer writes by habit.

**Fix:** the scan now covers `.pop` (read AND write), `.update({…})`, `|=` merges, keyword key
arguments, and dict literals passed to a call on a `spec` block. Verified by injecting each of the
four spellings into a real module and confirming the gate goes red for each, then restoring.

### P2 — the exception set claimed one exception while a second reader existed (FIXED with the above)
### P2 — `_ADVISED_DEV_MODE_PATHS` repeats a non-atomic check-then-act memo (CARRIED)

`concurrency-reviewer` grepped the package for threaded callers and found none — every consumer is
a separate OS process, so the compound operation cannot race today. Filed as maintenance debt
against a future threaded caller, not a live race. Not fixed: adding a lock for a hazard with no
trigger is the kind of device that costs more than it protects.

### P2 — `/hm:health`'s strictness drift signal does two unlocked reads (CARRIED)

Same reviewer. A concurrent `/harness-maker:make --update` between the two reads can produce a
transient false "stale render" advisory that self-corrects on the next run. `/hm:health` is
diagnostic-only and each read is individually atomic (`atomic_write` on the writer side), so the
worst case is one wrong advisory line.

### P2 — the deleted plan↔verify drift signal had no successor proof (FIXED)

`test-reviewer` could not confirm from the diff alone that the state the deleted readiness signal
watched is now unreachable. It is: Check 6 renders unconditionally (pinned by
`test_every_strictness_renders_check_6` and the AC-006 differential), and the other half of the
comparison cannot drift because the plan command is no longer rendered at all. That second half is
now asserted directly — `test_no_plan_command_survives_to_drift_against_check_6`.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### P1 — wrapup's SPEC gates still follow `preset`, not strictness (CARRIED — see the note)

`codex`, alone. `wrapup.md.j2:259` and `:323` branch on `config.preset == 'Production'`, so
`Production` + explicit `warn` still STOPs on `find-unbound` and the judgment-AC binding gate,
while `Side` + explicit `block` leaves both advisory. Verified against the templates: the claim is
factually correct.

**Why the behaviour is unchanged and the documents moved instead.** Those two gates are preset
DEPTH, which this SPEC's Non-Goals place out of scope ("Production and Side keep their current
depth"). The defect was therefore not in the code but in ADR-005 and the CHANGELOG, which said
`warn` "renders every SPEC check and blocks on none" — a claim broader than the change delivers.
Both now state the rule as "the gates this axis owns", and name the two gates that are
deliberately not on it. Moving them to strictness is a coherent follow-up and a separate task.

This finding is the reason `human_review_needed` is set: a single cross-model voice raised a real
P1, and the resolution was a judgment about scope rather than a code change. The DRI should see it.

### P2 — the CI strictness override was parsed and never forwarded (FIXED)

`codex`, alone. `/harness-maker:make --ci … strictness=warn` documented the parameter, and all four
dispatch commands omitted the flag unconditionally — so the value was silently dropped and the
preset-derived default rendered. Introduced by this change. Fixed by passing
`${STRICTNESS:+--strictness "$STRICTNESS"}` in every dispatch, which forwards it when set and omits
the flag when it is not.

## 🤝 Disagreements

One, and it is informative: the **security** lens filed the `spec_gate` severity split at **P2**
and explicitly declined to promote it, on the grounds that the two-knob design predates this diff;
the **core** lens and **codex** filed the same path at **P1** because an explicit `block` on the new
knob is newly expressible and newly defanged. Per Step 4a the tiers are not bridged, so both stand:
the P1 cluster drove the fix, and the P2 is recorded here rather than merged into it.

## 🧊 Cross-model findings (frozen @ round 1)

Model: `codex` · `status: invoked` · 3 findings · gathered 2026-09-21.

| id | severity | file:line | disposition | note |
|---|---|---|---|---|
| `a3a5d6e0` | P1 | `src/harness_maker/gates/spec_gate.py:132` | duplicate | same defect as the core lens finding; merged into one two-voice cluster |
| `fda3b616` | P1 | `src/harness_maker/templates/stages/wrapup.md.j2:259` | accepted | verified true; carried as a scope judgment, documents corrected |
| `ffe2297d` | P2 | `commands/make.md:572` | accepted | verified true; fixed |

Oracle for all three: direct reading of the named files plus the preset templates
(`security.gates.spec_gate` literals) and the wrapup preset branches. Dispositions are recorded in
`.claude/observability/second-opinion.jsonl`.

## 🔁 Oscillation

None — one repair round, no hunk removed and restored.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 9         | —   |
| 2         | A     | 5             | 3         | 0   |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged
Re-review: skipped — churn 0.25 < 0.30 (the CLI's own plan returned no dispatches)
Verification after the fixes: `9048 passed, 100 skipped, 3 xfailed` (`rc=0`) and `mypy --strict
src tests` clean. **Correction:** that `ruff check` result predated the last edit of the round —
the `test_spec_gate.py` migration added a 101-character docstring line that only `ruff format` ran
against, and the claim of a clean lint was carried forward without re-running it. The wrapup
delegate refused the stage on exactly that, which is what it is for; the line was wrapped and all
four gates re-run green before the commit.

### Iteration 2 (Grade: C → A)

Fixes applied: 5

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | severity follows strictness; the legacy key is rendered from it | `src/harness_maker/gates/spec_gate.py`, `templates/harness-yaml/*.j2` | Applied · caused_by=none |
| 2 | P1 | AST scan extended to `.update()` / `.pop()` / `\|=` / keyword `get` | `tests/structural/test_strictness_reader_singleton.py` | Applied · caused_by=none |
| 3 | P2 | four dispatches now forward `${STRICTNESS:+--strictness …}` | `commands/make.md` | Applied · caused_by=none |
| 4 | P1 | ADR-005 + CHANGELOG narrowed to "the gates this axis owns" | `work-docs/PLAN-dev-mode-removal.md`, `CHANGELOG.md` | Applied · caused_by=none |
| 5 | P2 | asserted that no plan command renders, closing the deleted signal | `tests/unit/test_render_verify_spec_need.py` | Applied · caused_by=none |

Remaining: 3 (two carried concurrency P2s, one carried cross-model P1) | New issues introduced: 0
Churn: 0.25 (max: `tests/structural/test_strictness_reader_singleton.py`, measured 14, excluded 0)

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `src/harness_maker/gates/spec_gate.py` | 171 → 181 | 32 → 29 | 2 → 2 | measured |
| `tests/structural/test_strictness_reader_singleton.py` | 179 → 203 | 31 → 48 | 3 → 4 | measured |
| `tests/unit/test_render_strictness_surface.py` | 172 → 205 | 13 → 17 | 1 → 1 | measured |
| `tests/unit/test_render_verify_spec_need.py` | 313 → 326 | 48 → 50 | 1 → 1 | measured |
| `tests/unit/test_spec_gate.py` | 287 → 316 | 36 → 40 | 0 → 0 | measured |
| `CHANGELOG.md`, `commands/make.md`, the two `harness-yaml` templates, four snapshots, the PLAN | — | null | null | not-python |

Report only, no threshold. The production file got simpler (32 → 29) while the scan that guards
it got more complex (31 → 48) — the round-2 fix moved complexity from the subject to its gate.

## Confirmation pass

`confirm_pass_ran: false`. The pass WAS dispatched — the artifact was frozen at `27bb3585` and all
four dispatches went out over `3852e084..27bb3585` — but the DRI directed the session to wrapup
before the results were collected, so no confirmation verdict exists. This is recorded as *not
run* rather than as a clean pass: a pass whose output nobody read is not evidence.

Status: **APPROVED**
human_review_needed: **true**
Counters: unreviewed 5 · prior-fix 0 · unattributed 0

> ⚠️ **Grade A but 1 unverified severe finding present** (`manual-only` P1 `fda3b616` — wrapup's
> SPEC gates still follow `preset`, resolved by narrowing the documented claim rather than by
> changing behaviour). Under autopilot this is the `pending` judgment gate. **The DRI answered it
> directly by directing wrapup**, which is recorded here as the answer; the finding itself stays
> open as a follow-up task.
