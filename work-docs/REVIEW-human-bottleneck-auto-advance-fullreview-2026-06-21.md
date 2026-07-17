---
type: review
task_slug: human-bottleneck-auto-advance
scope: full-feature retrospective (P0–P8, autonomy/autopilot)
status: CHANGES_REQUESTED
created: 2026-06-21
reviewers_invoked: [security-guard, caps-boundary, marker-failsafe, ledger-adr009, config-roundtrip, templates-crosside, tests-coverage, wiring-coherence]
consensus_method: per-dimension reviewer + independent adversarial verifier (k-of-2, high-confidence)
range: 42c34ba~1..HEAD
grade: C
human_review_needed: true
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-21
  note: >
    PLAN "Affected Components" lists render.py + settings*.json.j2 deny-baseline.
    Those are intentionally untouched — ADR-003's P4-impl refinement replaced the
    static settings.json deny with a marker-gated PreToolUse hook (documented in the
    execution log). Not a drift defect.
---

# REVIEW — Autonomy / autopilot pipeline auto-advance (full-feature retrospective)

Reviewed the entire autonomy feature landed across the 8 `feat(autonomy)` commits
(`42c34ba..832c328`, "feature complete"): the marker (`autopilot.py`), caps + boundary
CLI (`autopilot_caps.py`), ledger (`autopilot_ledger.py`), the never-auto PreToolUse +
Stop-hook (`hooks/autopilot_guard.py`), config schema/round-trip (`models.py`,
`interview.py`, `synthesize.py`), the CLI subcommand (`cli.py`), and the stage templates
(`stage_end_summary.md.j2`, all 7 `stages/*.md.j2`, `hooks.json.j2`, `health.md.j2`).

Method: 8 parallel dimension reviewers, each finding adversarially re-verified against the
live code by an independent skeptic (default-to-refute). 20 findings survived verification;
the orchestrator independently re-confirmed the two highest-impact ones (rm-regex bypass via
live regex execution; wrapup land/gate ordering via template read).

## 🎯 Summary

| | |
|---|---|
| **Grade** | **C** (0 consensus P0, 4 consensus P1) |
| **Status** | CHANGES_REQUESTED |
| **Top risk** | The chain auto-advances **into** `wrapup` and runs the irreversible squash-land **before** the merge gate evaluates — the feature's headline "always stop at wrapup merge/push" guarantee does not hold (P1, borderline-P0). |
| **Good news** | The core *modules* are strong — fail-safe matrix, ADR-009 import-time assert, the ts-resolution fix, future-dated-marker rejection, and the fields-overwrite guard are all correctly in place. The defects cluster in the **template/wiring seam** (where the safe modules are composed) and in **enforcement completeness**. |
| **Timing** | The P8 version bump is still deferred — this is pre-release, the right moment to fix the P1 cluster before 0.31.0. |

The verdict is harsh on one axis only: the auto-advance *plumbing* between the well-built
pieces lets the chain reach the one door the whole design exists to keep shut. Everything
upstream of that door is solid.

---

## ✅ Consensus Findings (grade-affecting)

### P1-1 — `wrapup` squash-lands to main BEFORE the merge gate fires  ⚠️ borderline-P0
**File:** `src/harness_maker/templates/stages/wrapup.md.j2` (Step 7.7 @ 401-437 vs gate @ 480, terminal include @ 481)

- **OBSERVE:** The auto-advance + mandatory-gate block lives in `stage_end_summary.md.j2`,
  `{% include %}`'d at wrapup line **481 — the last line**. Step 7.7 `task-land` (squash onto
  base HEAD + delete the `hm/<slug>` branch + worktree) runs at lines 401-437, *before* it.
- **INFER:** When autopilot auto-advances *into* wrapup (default pipeline ends `…verify, wrapup`),
  wrapup executes its full body — including the Step 7.7 land — and only *then* reaches the
  gate at line 480 ("if push boundary, STOP"). The gate guards advancing *past* wrapup, not
  wrapup's own land. The never-auto hook does **not** cover the land: it blocks `git push` /
  `reset --hard` / `stash drop` / rm-escape / publish — a local `git merge`/branch-delete is
  not in the list.
- **CONCLUDE:** Under `auto_safe`/`full` with wrapup in the pipeline (the default), the chain
  performs an unattended squash-land onto main. PLAN Success Criterion "The chain ALWAYS stops
  at … the wrapup merge/push" (marked ✅) is **false**. Recoverable via reflog and local-only,
  which is the only reason this is P1 and not P0.
- **FIX:** Gate the land, not the terminal. Either (a) the chain must STOP at the stage *before*
  wrapup (don't auto-`Skill(hm:wrapup)`; let the human invoke it), or (b) Step 7.7 must check
  `autopilot.active_marker()` and STOP/skip the `task-land` under an active marker, deferring it
  to a human-confirmed run. (a) matches ADR-002's "stop at wrapup merge/push" wording most
  directly.

### P1-2 — `rm-escapes-worktree` guard misses mid-token `..` traversal
**File:** `src/harness_maker/hooks/autopilot_guard.py:37`

- **OBSERVE:** `re.compile(r"\brm\b[^\n]*(?:[\s\"'` + "`" + `](?:/|~|\.\.)|\$)")` requires the
  `..`/`/`/`~` to be preceded by whitespace, quote, or backtick.
- **INFER (orchestrator-confirmed via live regex + `_bash_hit`):** `rm -rf build/../../etc`,
  `rm -rf a/../../../b`, `rm -rf node_modules/../../outside` all return **ALLOW** — the `..` is
  preceded by `/`, matching no alternative. Only whitespace/quote-prefixed forms block.
- **CONCLUDE:** Under an active marker the agent can delete a path resolving outside the worktree
  via the canonical traversal form — bypassing a documented non-overridable never-auto target.
  P1 (not P0) only because the docstring frames the regex as defense-in-depth with the worktree
  sandbox as the real boundary.
- **FIX:** Stop using the prefix-char trick. `shlex.split` the segment; for each non-flag `rm`
  operand, block if it is absolute, starts with `~`, contains any `..` component
  (`any(p == ".." for p in PurePosixPath(tok).parts)`), or contains `$`. Add regression cases
  `rm -rf a/../../../b` and `rm -rf build/../../etc`.

### P1-3 — Fused workflow commands embed live auto-advance after EVERY stage → scope escalation
**File:** `src/harness_maker/templates/agents/_partials/stage_end_summary.md.j2:18-51` (rendered into each fused fragment)

- **OBSERVE:** The auto-advance block is in the shared partial appended to every `stages/*.md.j2`.
  Fused commands (`/hm:exec-rev`, `/hm:plan-exec-rev-wrap`, …) concatenate stage fragments, so
  each fragment carries its own live auto-advance block. Its NO-OP conditions are: Skill
  unavailable / no marker / `.hm-loop-active` — none of which is "inside a fused command."
- **INFER:** With an active `.hm-autopilot` marker, an autopilot `/hm:exec-rev` reaches the
  review fragment's block, computes `next=verify/wrapup` from the *marker's* pipeline, and issues
  `Skill(hm:wrapup)` — escalating past the two stages the user invoked.
- **CONCLUDE:** A fused invocation under autopilot can run all the way to the wrapup land (P1-1),
  past the user's intended scope. Requires marker-active + fused-command combo, so ranked below
  P1-1.
- **FIX:** Suppress the auto-advance block for all but the last fragment of a fused render. Thread
  an `is_terminal_stage` flag into `workflow_fuse.fuse`'s per-stage render and wrap the
  `@hm:autopilot-advance` section in `{% if autopilot_advance_enabled %}`.

### P1-4 — `autopilot on` bare default puts verify AFTER wrapup (enum order vs config default)
**Files:** `src/harness_maker/models.py:85-86` (AtomicStage) + `cli.py:~1947` (bare default) + `tests/e2e/test_autopilot_chain_e2e.py:20`

- **OBSERVE:** `AutonomyConfig.pipeline` default factory is correct (`…REVIEW, VERIFY, WRAPUP`),
  but the `AtomicStage` enum declares `WRAPUP` *before* `VERIFY`, and `autopilot on` with no
  `--pipeline` writes `list(AtomicStage)` → `…REVIEW, WRAPUP, VERIFY`.
- **INFER:** The common CLI/picker entry point produces a pipeline where the safety check runs
  *after* the commit/land. The e2e fixture uses the same wrong order, so the hazard is masked
  rather than caught.
- **CONCLUDE:** Two "default pipeline" sources disagree; one defeats the verify-before-commit
  invariant. (Compounds P1-1.)
- **FIX:** Make the CLI bare default reuse `AutonomyConfig().pipeline` (single source of truth);
  update the e2e fixture to the canonical order so it exercises verify-before-wrapup. Optionally
  add an invariant test: any pipeline ending in `wrapup` has `verify` strictly before it.

---

## 📝 Manual-Only / Secondary Findings (P2 — not grade-affecting, but fix-worthy)

| # | File | Issue | Fix |
|---|------|-------|-----|
| P2-1 | `autopilot_guard.py:143` | `cd /etc && rm -rf hosts` bypasses rm-escape (segments evaluated with no cwd awareness) | Treat any absolute/home `cd` segment as poisoning later rm/find-delete segments; or document + xfail so the gap is visible, not silent |
| P2-2 | `autopilot_guard.py:50` | Bash permission-surface regex covers only `.claude/…`; the Write-tool regex also covers `.cursor/hooks.json` + `.codex/hooks.json` — asymmetric | Align the Bash regex path-set with the Write regex; add redirect regression tests |
| P2-3 | `autopilot.py:50-71` | `write()` never seeds the `.hm-autopilot` gitignore entry → the marker can be committed and shipped to collaborators (contradicts the module's own contract) | Seed the gitignore entry in `write()` (idempotent), mirroring `_current_session_uuid` self-seeding; add a regression test |
| P2-4 | `autopilot_ledger.py:166-171` | `count_events` `since` path **drops** rows with an unparseable `ts` → undercounts `advanced` → step cap fires late (**wrong fail-safe direction**) | Count rows with missing/garbage ts as in-window; only skip rows provably older than `since` |
| P2-5 | `autopilot_caps.py:211-215` | `gate-blocked` subcommand appends with **no active-marker guard** → records events even when autopilot is off/foreign/stale, polluting the smoke denominator + audit trail | Add `if autopilot.active_marker(root) is None: return 0` before `append_event`, matching the `boundary` path |
| P2-6 | `autopilot_guard.py:220-239` + `autopilot_caps.py:178` | After a gate-block / cap-halt the marker is **not** cleared → the Stop-hook backstop blocks the first Stop of every later turn until the 18h TTL or manual `autopilot off` | On a terminal cap halt, clear the marker after recording `halted_cap`; or treat a marker with a recorded terminal halt as inactive |
| P2-7 | `tests/unit/test_autopilot_template_render.py:66-77` | ADR-004 Codex/Cursor exclusion is "tested" by grepping the `.j2` **source**, not by rendering a Codex/Cursor target and asserting the auto-advance branch is **absent** from output (downgraded from the reviewer's P1 — the runtime guard `{% if is_codex is defined and not is_codex %}` is present and correct; only the *test* is weak) | Add a behavioral negative-render test asserting `.codex/**`/`.cursor/**` outputs contain no `autopilot-advance` / boundary call |
| P2-8 | `tests/unit/test_autopilot.py:86-101` | "uuid mismatch resolves OFF under concurrency" is only proven by monkeypatching `_current_session_uuid`; the real same-project guard is the TTL, not the uuid — the label misleads | Relabel to "foreign/crashed-project marker"; add a test that two same-project sessions BOTH see the marker active (documenting the acknowledged limitation) |

## 🔧 Minor (P3)

- `autopilot_caps.py:75,153-163` — a tripped cap is sticky: re-emits a duplicate `halted_cap`
  on every subsequent boundary call (no clear/quiesce). Make `halted_cap` once-per-session or clear the marker.
- `autopilot_caps.py:75` — `time_cap` reason uses `:.0f`, can display `31/30` or `30/30`; use `:.1f` or floor.
- `autopilot_ledger.py:185-210` — `smoke_check` reads only `yaml_level`, ignores an active marker, so a
  marker-armed (start-answer) session reports "not armed" and never raises the silent-degrade alarm. Resolve
  via `effective_level`, or tighten the docstring to say smoke is committed-yaml-scoped only.
- Test gaps (all P3): same-second `since==ts` boundary (the exact bug `_utc_now_iso`'s comment says e2e caught)
  has no unit regression; the two guard rm bypasses (P1-2/P2-1) have no test; the PIPE_BUF/4096 oversized-line
  guard is untested; per-stage gate render coverage is incomplete (no assert of `gate-blocked --stage <X>`,
  the default-STOP fallback, or the `.hm-loop-active` self-disable clause).

---

## 🤝 Notes on consensus & method

- **0 findings refuted.** Each surviving finding carries a code-cited trigger trace from both the
  reviewer and an independent default-to-refute verifier; the two highest-impact (P1-1, P1-2) were
  additionally re-confirmed by the orchestrator directly.
- One reviewer severity was lowered on consensus: the Codex/Cursor-exclusion test (P2-7) was filed
  P1 but the *runtime* behavior is correct — only the test is grep-based — so it is a P2 test-quality
  item, not a P1 enforcement gap.
- **Drift:** clean. The only PLAN/diff divergence (render.py/settings.json deny baseline untouched) is
  the documented ADR-003 P4-impl refinement, not a defect.

## Grade computation

Consensus-passed P0 = 0; consensus-passed P1 = 4 (P1-1…P1-4) → **C** (0 P0, ≥3 P1).
Letter grade aside, **P1-1 + P1-4 together are a release blocker**: the default autopilot pipeline
both runs verify after the commit and lands to main unattended. Recommend fixing the P1 cluster before
the deferred 0.31.0 version bump.

## ➡️ Recommended order of fixes

1. **P1-1** (gate the wrapup land) + **P1-4** (canonical pipeline order) — together restore the
   "stop at merge / verify-before-commit" guarantee. Smallest change with the largest safety payoff.
2. **P1-2** (rm shlex-tokenize) + **P1-3** (suppress auto-advance in fused renders) — close the two
   paths to an irreversible op.
3. **P2-3 / P2-4 / P2-5 / P2-6** — gitignore-seed, fail-safe count direction, gate-blocked guard,
   marker-clear-on-halt.
4. P2/P3 test gaps last — they pin the fixes above so they cannot regress.
