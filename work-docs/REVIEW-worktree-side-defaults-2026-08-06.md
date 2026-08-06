---
type: review
task_slug: worktree-side-defaults
status: APPROVED
created: 2026-08-06
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/synthesize.py
    - src/harness_maker/templates/agents/_partials/g0_macros.md.j2
    - src/harness_maker/templates/agents/_partials/gate0_receipt.md.j2
    - tests/structural/test_command_size_budget.py
    - tests/structural/surface_baseline.json
  scenario_misses: []
  task_slug: worktree-side-defaults
  computed_at: 2026-08-06T00:00:00Z
---

# REVIEW — worktree-side-defaults

## 🎯 Round 1 Summary

**Grade: D → A after one auto-fix round** · 5 voters (3 Claude reviewers + codex + antigravity)
· 18 raw findings → 2 P0 + 6 P1 consensus-passed, all fixed in round 1's auto-fix pass.

The two P0s were independently found by different voters and both were **verified against
the source before any fix**:

1. **Every `/hm:wrapup` on an isolation-OFF harness would abort** (security-reviewer).
   `wrapup.md.j2` rendered `hm wrapup_land --worktree .`, and `wrapup_land._resolve_root`
   raises `LandAbortError` on any non-absolute path (`wrapup_land.py:63-65`, pinned by an
   existing test). Steps 6→7.6 — stage, commit, post-commit-pop, owned-crumb-clear,
   drain — are that one call, so the entire commit path was dead on the preset default
   this change introduces. My own `WTR = '.'` substitution created it.
2. **Isolation-OFF + a live `hm/*` worktree routed finalize to the destructive legacy
   path** (concurrency-reviewer). The dispatch was
   `if worktree_enabled(...) and _is_task_worktree(wt)`; a False conjunction fell through
   to stash + `merge` + `cleanup(on_success=True)` → `git worktree remove --force`,
   squash-merging an unlanded task branch into base HEAD. Reachable by a hand-edit, which
   bypasses `disable_preflight` entirely — and ADR-005 has already unrendered the recovery
   instructions. This is the count:3 `worktree-finalize-pulls-orphan-wip-into-main` shape.

## 🔍 Drift Findings

| Severity | File | Note |
|---|---|---|
| P1 | `synthesize.py` | Not in any PLAN phase's scope. Recorded as a Phase-1 deviation in the PLAN: it is THE normalization point, without which a pre-collapse answers dict renders `StrictUndefined`. |
| P1 | `_partials/{g0_macros,gate0_receipt}.md.j2` | Not in PLAN scope. Recorded as a Phase-6 finding: the receipt used a literal `<WT>` root, so under OFF it could never fire and Gate 0 would see every stage missing. |
| P2 | `tests/structural/*` | Baseline + the documented raise. Phase 7 named docs and e2e fixtures but not the structural baselines. |

No SPEC exists (task-driven), so `scenario_misses` is empty by construction, not by
omission.

## ✅ Consensus Findings (all fixed in round 1)

| # | Sev | Voters | Finding | Fix |
|---|---|---|---|---|
| 1 | **P0** | security | `--worktree .` aborts every OFF wrapup | Render `"$(pwd)"` in both `--worktree` and `--base` under OFF |
| 2 | **P0** | concurrency | flag-OFF + `hm/*` worktree → destructive legacy finalize | Refuse with the slug and `task-land` / `--worktree` remedies; branch + directory survive |
| 3 | P1 | code, codex, antigravity | `--reinterview` disk re-apply clobbered `--worktree/--no-worktree` **and** the fresh interview answer | Deleted the re-apply; `_apply_worktree_enabled` is now the only disk reader |
| 4 | P1 | code, codex, antigravity | preset-switch heuristic could not tell an explicit value from a defaulted one | Removed the heuristic; the single writer restores rung-1 disk values, so disk beats preset default and only a flag/interview answer beats disk |
| 5 | P1 | codex, concurrency | `disable_preflight` never read the registry, and missed branch-only state | Added live-registry annotation + `_unlanded_task_branch_blockers` (landed-marker vs tip) |
| 6 | P1 | concurrency | `_task_worktree_blockers` failed **open** on detached HEAD / git error | Fail-closed: unreadable branch or detached HEAD is an indeterminate blocker |
| 7 | P1 | concurrency | the refusal message told users to `task-land` a possibly-LIVE foreign worktree — the guard's own advice reproducing the contamination it prevents | Liveness-aware remedy; `(LIVE — pid N)` tags |
| 8 | P1 | security | `! uv run` — the corpus's only `!`-with-space bash-exec line, on the step that stamps the finding `id`s the whole auto-fix loop is keyed on | Space moved inside the ON literal |

## ⚠️ Weak Consensus

| Sev | Finding | Why weak |
|---|---|---|
| P1 | The preset-switch heuristic (#4 above) | codex and code-reviewer agree the mechanism is "cannot distinguish explicit from defaulted"; antigravity's OBSERVE matches but its CONCLUDE misreads the code (it says the comparison uses the NEW preset's default — it uses `answers.preset`, the OLD one, before the rebuild). Fixed on the codex/code-reviewer reading; recorded here because the divergence is real. |

## 📝 Manual-Only Findings

| Sev | Source | Finding | Disposition |
|---|---|---|---|
| P2 | codex | `resolve_worktree_enabled` treated a non-dict block (`worktree: false`) as absent, so a Production re-render could run the enablement probe and write `true` over a visible opt-out | **Fixed** — returns rung 1 fail-closed |
| P2 | antigravity | the resolver diagnostic was dropped in `answers_from_harness_yaml`, so a hand-edit was overwritten with no explanation | **Fixed** — printed to stderr |
| P2 | code | `readiness.py`'s absent-key default was `True` while the reader's is `False` — `/hm:health` could report a mode the execution path does not take | **Fixed** |
| P2 | concurrency | `disable_preflight` probe → config write is unlocked (TOCTOU) | **Accepted.** No git state is mutated on this path and config files are last-writer-wins; holding the registry lock across probe→render would be a new lock ordering against the merge fence. Recorded, not fixed. |
| P2 | antigravity | a deferred `enablement_preflight` writes `enabled: false`, so the absent-key retry is lost | **Accepted with a named remedy.** The lock-in is escapable through the supported `--worktree` flag this change introduces, which the deferral warning already names. Before this change there was no such flag. |
| P2 | codex | stale `.hm-loop-*` markers cause a permanent false refusal | **Accepted** — pre-existing `_old_model_residue_blockers` behavior, not introduced here; widening it to liveness is a separate change to a load-bearing guard. |
| P2 | security | dead `wt_on` conditionals inside the ON-only Step 7.7 | **Fixed** — collapsed to literals |
| P3 | codex | the migration docstring over-promised "loudly" for a `scope` that never isolated anything | **Fixed** — docstring corrected rather than adding a notice for a no-op change |

## 🤝 Disagreements

- **`_task_worktree_blockers` should block on FOREIGN sessions' worktrees.** concurrency
  explicitly argued *for* keeping it foreign-blind (consistent with the repo's recorded
  position that the queue-guard's foreign-counting is load-bearing) and putting ownership
  only in the *message*. codex's registry finding could be read as arguing for
  per-session narrowing. Resolved the concurrency way: still blocks on foreign, message
  now names liveness.
- **antigravity rated the preset-switch heuristic P0, codex P1.** Not bridged (Step 4a
  does not bridge tiers). Fixed regardless; recorded at P1 per the two-voter agreement on
  mechanism.

## 🧊 Cross-model findings (frozen @ round 1)

```yaml
second_opinion_results:
  - model: codex
    status: invoked
    findings: 7   # 3×P1, 3×P2, 1×P3
  - model: antigravity
    status: invoked
    findings: 5   # 3×P0, 2×P2
```

| id | model | sev | disposition | note |
|---|---|---|---|---|
| `964741b9fa3df5f5` | codex | P1 | accepted | `--reinterview` clobbers the flag — corroborated by code-reviewer and antigravity |
| `48de2f9068e6dee8` | codex | P1 | accepted | preset-switch heuristic |
| `585b6450c407e3d5` | codex | P1 | accepted | registry rows absent from `disable_preflight` |
| `a999799c8446b2f7` | codex | P2 | accepted | non-dict block not fail-closed |
| `ff881b6c299d52fd` | codex | P2 | accepted (not fixed) | stale loop marker — pre-existing |
| `f16477fed24386a6` | codex | P2 | accepted | FS errors escaped `_task_worktree_blockers` |
| `efad6fc010e288fe` | codex | P3 | accepted | docstring over-promise |
| `1fc4008e09fdc9c2` | antigravity | P0 | accepted | same as `964741b9` (duplicate by mechanism, kept: it also names the discarded interview answer) |
| `e141d8e29a17a7eb` | antigravity | P0 | accepted | `worktree_enabled` hardcodes `stage="execute"`, so a legacy `scope: ["plan"]` harness bypasses the disable guard. **Initially written up as accepted while still unfixed** — caught on re-read of this table; `resolve_worktree_enabled` now takes `stage=None` ("live for ANY stage") and the guard uses it |
| `693159185da30fbe` | antigravity | P0 | accepted-with-correction | right target, wrong mechanism (see Weak Consensus) |
| `d26470750af39666` | antigravity | P2 | accepted | dropped diagnostic |
| `ebdd9856d7fba22c` | antigravity | P2 | accepted (not fixed) | enablement retry lock-in |

Both models ran; neither degraded.


---

## Iteration 1 (Grade: D → A)

Fixes applied: 13 (2×P0, 6×P1, 5×P2/P3). No fix was reverted; no build break.

| # | Sev | Summary | File | Status |
|---|-----|---------|------|--------|
| 1 | P0 | `--worktree .` aborts every OFF wrapup | `templates/stages/wrapup.md.j2` | Applied · caused_by=#none (introduced by this PLAN's Phase 6) |
| 2 | P0 | flag-OFF + `hm/*` worktree → destructive legacy finalize | `worktree.py:3010` | Applied |
| 3 | P0 | guard bypassed on a legacy `scope: ["plan"]` harness | `worktree.py`, `cli.py` | Applied |
| 4 | P1 | `--reinterview` clobbered the flag and the interview answer | `cli.py:403` | Applied — block deleted |
| 5 | P1 | preset-switch heuristic could not detect explicit intent | `cli.py:1274` | Applied — heuristic removed, precedence moved into the single writer |
| 6 | P1 | `disable_preflight` missed registry rows and branch-only state | `worktree.py:1043` | Applied |
| 7 | P1 | `_task_worktree_blockers` failed OPEN on detached HEAD / FS error | `worktree.py:1056` | Applied — fail-closed |
| 8 | P1 | refusal advised `task-land` on a possibly-LIVE foreign worktree | `worktree.py:1050` | Applied — liveness-aware |
| 9 | P1 | `<BASE>` unbound in the OFF render | `templates/stages/wrapup.md.j2` | Applied |
| 10 | P1 | `! uv run` — the corpus's only `!`-with-space exec line | `templates/stages/review.md.j2:303` | Applied |
| 11 | P2 | non-dict `worktree:` block treated as absent | `worktree.py` | Applied — rung 1 fail-closed |
| 12 | P2 | resolver diagnostic dropped on the round-trip | `interview.py` | Applied |
| 13 | P2 | readiness absent-key default disagreed with the reader | `readiness.py:630` | Applied |

**Verification.** `ruff check` + `ruff format --check` + `mypy --strict` clean; full suite
green. Six new regression tests: the disable guard on a live worktree / an unlanded
branch / a detached HEAD / a clean repo, the finalize refusal, and `stage=None`.

**One fixture had to change, and it is worth naming.**
`test_readiness_delegation._project` omitted the `worktree` block and relied on readiness
defaulting an absent key to `True`, while the single reader defaults it to `False`. Fix
#13 made the two agree and broke the fixture. A fixture that passes only while two
readers disagree is exactly the drift the single-reader invariant exists to prevent — so
the fixture is now explicit, with that reasoning inline.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | 13            | 3         | 0   |

Final grade: **A**
Iterations used: 1 / 3
Exit reason: converged
Status: APPROVED
human_review_needed: false
Counters: unreviewed 0 · prior-fix 0 · unattributed 0

Three findings remain open by decision, all P2, all recorded above with reasoning: the
`disable_preflight` TOCTOU window (no git mutation on that path), the deferred-enablement
retry lock-in (escapable via the `--worktree` flag this change introduces), and stale
`.hm-loop-*` markers causing a false refusal (pre-existing behavior of a load-bearing
guard, not introduced here). None is `manual-only`/`weak-consensus` at P0/P1, so
`unverified_severe` is false.
