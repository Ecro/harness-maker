---
type: review
task_slug: codex-second-opinion-sandbox
status: APPROVED
created: 2026-06-17
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: cross-check (k-of-3, Codex as heterogeneous third voter)
drift_verdict:
  result: scope_violation
  scope_violations: [uv.lock]
  scenario_misses: []
  task_slug: codex-second-opinion-sandbox
  computed_at: 2026-06-17T18:18:00+09:00
codex_status: invoked
mechanical_grade: A
adjudicated_verdict: APPROVED
rounds: 2
human_review_needed: false
---

# REVIEW — codex-second-opinion-sandbox (Round 1)

## 🎯 Round 1 Summary

- **Voters:** code-reviewer + security-reviewer (Claude) + Codex (k-of-3, `codex exec` ran clean, exit 0).
- **Mechanical consensus grade: A** — 0 *consensus-passed* P0/P1 findings (the one 2-of-3 agreement is a P3).
- **Adjudicated verdict: CHANGES_REQUESTED** — the orchestrator independently **confirmed** a manual-only **P1** (CX3, verified empirically this session) plus a cluster of recipe-robustness P2s. Rubber-stamping Grade A would hide a gap that defeats the PLAN's own headless success criterion ("do NOT emit `skipped: Bash permission gate`").
- **Auto-fix:** none applied — every actionable finding is single-source (manual-only) or a design change; the consensus filter forbids auto-applying those, and they warrant user awareness.

The cutover itself is **correct**: all 3 reviewers reverted to exactly `tools: Read, Grep, Glob`; only `plan-validator` carries the re-homed `@hm:codex-reconcile` block; the 3 dead partials have zero remaining `{% include %}` refs; byte-zero disabled-render holds; and the 3-way merge with the concurrent locale feature kept BOTH the codex blocks and the `stage_end_summary` include in `plan.md.j2`/`review.md.j2` with no clobbering. Full pytest+ruff+mypy are green.

## 🔍 Drift Findings

- **P1 scope drift:** `uv.lock` is staged but is in no PLAN phase scope. **Benign** — it is a pre-existing lockfile sync to the already-committed `pyproject.toml` `mutmut<4` pin, not introduced by this task. Recommend keeping it in the wrapup commit or unstaging; not a defect.
- No incomplete phases (all 5 phase scopes touched). No SPEC → no scenario misses.

## ✅ Consensus Findings (consensus-passed)

| # | Sev | File:line | Finding | Voters |
|---|-----|-----------|---------|--------|
| C1 | P3 | `stages/plan.md.j2:346,394` | Bare `config.codex_second_opinion.enabled` guard vs the defensive `config.codex_second_opinion and …` used in `review.md.j2`/`health.md.j2`. Latent only — `synthesize` always supplies a default `CodexSecondOpinionConfig`, disabled render verified clean. | code-reviewer + security-reviewer (both: non-blocking) |

P3 → does not lower the grade. Optional consistency fix.

## ⚠️ Manual-Only Findings — recommend addressing before wrapup

> These are single-source (mostly Codex, the heterogeneous voter) but **orchestrator-confirmed real**. Per the consensus filter they are not auto-fixed; they are the substance of the CHANGES_REQUESTED verdict.

### M1 — [P1, CONFIRMED] allow-rule shape mismatch → headless permission-deny
- **File:** `templates/agents/_partials/codex_exec_mainloop.md.j2` (recipe) + `settings/Production.json.j2:3` / `Side.json.j2`
- **Source:** Codex. **Independently verified this session.**
- **OBSERVE:** the rendered allow rule is `Bash(codex exec:*)`, but the recipe is a **compound** one-liner: `content=…; prompt_tmp=$(mktemp); …; codex exec …`. Claude Code permission matching is command-prefix based; a command starting with `content=` is **not** a `codex exec …` command.
- **Evidence (this session):** compound `…; codex exec …` Bash calls were **DENIED** (foreground and background); a bare `codex exec … < file` was **ALLOWED**. `dangerouslyDisableSandbox` disables the *sandbox*, not the *allow/deny* check.
- **CONCLUDE:** in a headless autoloop the recipe is denied at the permission layer → `codex_status: skipped` → warn-and-proceed → Claude-only. The fix changes the *skip reason* from "sandbox" to "permission-deny" but does **not** achieve the PLAN's headless goal. **P1.**
- **Fix (shared with M2):** split the recipe so the sandbox-disabled Bash call contains **only** `codex exec … < "$prompt_tmp"`. Build the prompt file in a separate prior step (or via the Write tool). Then `Bash(codex exec:*)` matches and the call is pre-approved headless.

### M2 — [P2, CONFIRMED] untrusted-diff shell expansion in `content="…"`
- **File:** `templates/agents/_partials/codex_exec_mainloop.md.j2:32`
- **Source:** Codex (P0). **security-reviewer disagreed** (P2, "sound by intent") — see Disagreements.
- **OBSERVE:** the prose says "put the diff in a shell variable … so `$(...)`/backticks are never expanded," but the shown mechanism is a **double-quoted** assignment `content="<diff…>"`, and double quotes **do** expand `$(...)`/backticks. The diff is untrusted (adversarial PRs).
- **CONCLUDE:** with `dangerouslyDisableSandbox` active, a crafted diff containing `$(…)` pasted into the assignment is **host command execution outside the sandbox**. Latent (requires the orchestrator to follow the unsafe form literally; a careful orchestrator writes to a file — which is what the orchestrator did in *this* review). Inherited from the prior inline recipe but **elevated** by the sandbox escape. **P2.**
- **Fix:** same as M1 — write the diff to the prompt file via the Write tool (no shell assignment of untrusted content), or single-quote. One fix closes M1 + M2.

### M3 — [P2, CONFIRMED] recipe not `is_codex`-gated → codex-target skills leak a Claude-only directive
- **File:** `templates/agents/_partials/codex_exec_mainloop.md.j2:35` (+ `health.md.j2`)
- **Source:** code-reviewer. **Confirmed by construction:** `_codex_stage_skills` (synthesize.py:625-637) renders the stage body with `is_codex=True`, and the partial has no `is_codex` branch → codex-target `hm-review`/`hm-plan` skills instruct the **Codex runtime** to pass `dangerouslyDisableSandbox: true` (a Claude-Code Bash-tool param Codex lacks) and rely on a `.claude/settings.json` allow rule Codex never reads.
- **Status vs PLAN:** the PLAN Risks table anticipated this and allowed "**gate or document**, flag in code review." The impl chose document-only (probe doc); this review is the "flag." **Within accepted risk, but recommend gating** for codex-target correctness.
- **Fix:** wrap the sandbox-escape blockquote in `{% if not is_codex %}…{% endif %}` (+ optional `{% if is_codex %}` Codex-appropriate note). The stage templates already branch on `is_codex` elsewhere.

### M4 — [P2] failure-path not mechanically robust
- **File:** `templates/agents/_partials/codex_exec_mainloop.md.j2:40`
- **Source:** Codex.
- **OBSERVE:** the adapt block `python -m harness_maker.codex_adapter adapt < "$out_tmp"; rm -f …` runs unconditionally; on a non-zero `codex exec` the sink may be empty/error-text and `$?` is already clobbered by `echo`/`cat`.
- **CONCLUDE:** the adapter can error on a Codex failure before the skip path runs. LLM-driven skip-relay mitigates (the orchestrator reads `exit=`), so **P2**, not blocking.
- **Fix:** capture `status=$?` immediately after `codex exec`; run the adapter only on `status == 0`, else emit the skip ledger row.

### M5 — [P2] test gap: `is_codex` leakage is invisible to the suite
- **File:** `tests/unit/test_render_codex_partial_include.py`
- **Source:** code-reviewer. The suite only renders Claude-Code stages and asserts the directive **is** present; nothing renders with `is_codex=True`, so M3 ships green. Add a codex-target assertion (absent-case rule).

### M6 — [P3] byte-zero coverage for the reconcile block is indirect
- **File:** `tests/unit/test_codex_mandatory_matrix.py` / `test_codex_plan_pida.py`
- **Source:** Codex. The plan-validator reconcile block byte-zero is asserted via marker-absence in the full agent, not a direct `== ""` render (it is inline, not a standalone partial). Adequate but not byte-level.

### M7 — [P3] `health.md.j2` smoke check missing the scoping clause
- **File:** `templates/commands/hm/health.md.j2:58`
- **Source:** security-reviewer. The partial says "Do NOT disable the sandbox for any other command"; the health callout omits it. Append for uniform scoping.

### M8 — [P3] cosmetic double blank line before `**Invoke**` (Production plan render)
- **Source:** code-reviewer. Markdown collapses it; purely cosmetic.

## 📝 Manual-Only — security verdict (security-reviewer)

Design judged **sound**: allow-rule is narrow (`Bash(codex exec:*)`, not `Bash(codex *)`), gated on enabled; untrusted input goes through `mktemp`+`printf '%s'` (no `eval`/heredoc-injection); output sink is `mktemp` (no symlink clobber); skip-reason is a separate `--flag`; reviewer subagents lost Bash entirely (attack surface shrank). Residual headless-autoloop risk documented. Only P2/P3 raised.

## 🤝 Disagreements

| Issue | Codex | security-reviewer | Orchestrator adjudication |
|-------|-------|-------------------|---------------------------|
| `content="<diff>"` recipe (M2) | **critical** — double-quote expands untrusted `$(…)` → sandbox-off RCE | **P2, sound** — placeholder; LLM substitutes safely, prose mandates the variable+`printf` pattern | **Codex is technically right**: double quotes *do* expand; the prose's guarantee isn't enforced by the shown mechanism. Downgraded to **P2** (latent, orchestrator-dependent) but real and elevated by the sandbox escape. Fix coincides with M1. |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A (mechanical) | 0 | 1×P1 + 5×P2 + 4×P3 (all manual-only) | — |

Final grade (mechanical consensus): **A**
Adjudicated verdict: **CHANGES_REQUESTED**
Iterations used: 1 / 3
human_review_needed: **true**

**Why not auto-A:** the k-of-3 heterogeneous voter (Codex) + the orchestrator's own empirical evidence establish a confirmed **P1 (M1)** that defeats the PLAN's headless success criterion. It is single-source, so the consensus filter correctly does not auto-fix it — but it is surfaced loudly here rather than averaged away.

**Recommended next step:** apply the **one combined fix** for M1+M2 (isolate `codex exec` as its own command reading a pre-written prompt file) + the `is_codex` gate for M3. These are central to the feature actually working headless. Then re-render and re-verify. (Not committed — wrapup owns the commit.)

---

## Round 2 — Fixes applied (2026-06-17)

User approved applying the combined M1+M2+M3 fix; M4 + M5 + M7 came along for free in the same restructure. All edits in `templates/agents/_partials/codex_exec_mainloop.md.j2`, `templates/commands/hm/health.md.j2`, and `tests/unit/test_render_codex_partial_include.py`.

| # | Sev | Resolution | Status |
|---|-----|-----------|--------|
| **M1** | P1 | Recipe split into 3 steps; the sandbox-disabled call is now a **bare `codex exec … < "$prompt_tmp"`** column-0 command → `Bash(codex exec:*)` prefix-matches it headless. Health smoke check likewise restructured to a bare `codex exec … <<< '…'`. | ✅ Fixed |
| **M2** | P2 | Untrusted diff is now written to the prompt file **via the Write tool**, never a double-quoted shell assignment — no `$(…)`/backtick expansion. The `content="…"` assignment is gone. | ✅ Fixed |
| **M3** | P2 | The `dangerouslyDisableSandbox` directive is gated on `{% if not is_codex %}`; the Codex runtime gets a runtime-appropriate note (no Claude-only Bash-tool param, no settings-allow reference). | ✅ Fixed |
| **M4** | P2 | Adapter now runs only under `if [ "$exit" -eq 0 ]`; temp files always cleaned up. | ✅ Fixed (bonus) |
| **M5** | P2 | Added `test_partial_gates_sandbox_directive_on_is_codex` (renders is_codex=True, asserts directive absent + runtime note present) and `test_partial_codex_exec_is_a_bare_command_for_allow_match` (asserts a bare `codex exec` block + no `content="` assignment). | ✅ Fixed |
| **M7** | P3 | Health smoke callout now carries "Do NOT disable the sandbox for any other command." | ✅ Fixed |

**Deferred (not blocking, recorded):** M6 (byte-zero of the reconcile block tested via marker-absence, not a direct `==""` render — inline block, adequate), M8 (cosmetic blank line), C1 (P3 guard consistency in plan.md.j2 — latent, `synthesize` always supplies the config).

### Verification (Round 2, merged base)
- `ruff check` ✅ · `ruff format --check` ✅ · `mypy --strict` ✅ (105 files).
- Full `pytest`: **all deterministic tests pass.** One e2e (`test_plugin_live.py::test_make_no_interactive_prompts`) timed out at 60s under heavy machine contention (the whole suite ran ~6 min vs the usual ~90 s); **re-run in isolation → PASS (exit 0)**. Confirmed environmental flake — and structurally impossible for this change to cause it, since that test exercises `make` with codex **disabled**, where every edit in this diff renders byte-zero/absent.
- Partial-level render checks: M1 bare-`codex exec` block ✅, M2 no `content="` ✅, M3 directive gated (claude=present / codex=absent + runtime note) ✅, M4 status guard ✅, byte-zero disabled ✅.

## Review Iteration Summary (final)

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A (mechanical) | 0 | 1×P1 + 5×P2 + 4×P3 (manual-only) | — |
| 2 (fix)   | A | 6 (M1,M2,M3,M4,M5,M7) | 0 P0/P1; 3×P3 deferred-cosmetic | 0 |

Final grade: **A** · Status: **APPROVED** · Iterations: 2 / 3 · `human_review_needed: false`

The P1 (M1) that drove the Round-1 CHANGES_REQUESTED is resolved: the feature now matches its allow rule headless and closes the untrusted-diff expansion vector in the same restructure. Ready for wrapup.
