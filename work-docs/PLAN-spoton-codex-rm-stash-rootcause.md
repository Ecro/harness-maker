---
type: plan
task_slug: spoton-codex-rm-stash-rootcause
status: complete
created: 2026-06-02
tags: [harness-maker, plan, permissions, worktree, codex, release]
research_doc: "[[RESEARCH-spoton-codex-rm-stash-rootcause]]"
interview_rounds: 2
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Issue1=harness template fix+0.28.5 release; Issue2/3=spoton manual remediation only"
---

# PLAN — spoton: codex-skip / rm-denied / recurring-stash

## 🎯 Executive Summary

**What:** Resolve three symptoms surfacing in `~/spoton`. They split into one harness-maker code fix (released as 0.28.5) plus spoton-local manual remediation.

**Why:** Root-caused in `RESEARCH-spoton-codex-rm-stash-rootcause.md`:
- **Issue 1 (codex skipped)** — a live template bug: the 3 codex agents declare `tools: Read, Grep, Glob` (no `Bash`) yet `permissions.allow` carries `Bash(codex exec:*)`. In Claude Code `tools:` is the hard gate, so the agent has no Bash tool → `codex exec` can't run → "validator env had no Bash" → skip.
- **Issue 2 (rm denied)** — `settings.json` deny carries a pre-0.28 baseline `Bash(rm:*)`/`Bash(curl:*)`; `render._merge_permissions` unions deny lists by design, so retired baseline entries survive every re-render (proven by spoton's relic `Bash(curl:*)`, which matches no current template branch).
- **Issue 3 (recurring stash)** — `.claude/observability/` was committed at 0.23.2, then later gitignored → tracked-yet-ignored. `_stash_base_dirty` triggers on any non-artifact dirt (a stray untracked `work-docs/RESEARCH-*.md`), and `git stash push -u` then sweeps the tracked observability files (the artifact filter only suppresses the *trigger*, not the *sweep*) → pop conflicts. A stale `.hm-loop-execute-*` marker (worktree already gone) is collateral.

**Key Decisions:**
- ADR-001 — Issue 1 fixed by adding **unconditional** `Bash` to the `tools:` line of the 3 codex agent templates; scope `codex exec` only via existing `permissions`.
- ADR-002 — Issues 2 & 3 remediated **manually in spoton only**; harness-maker is NOT hardened (no subtractive-deny mechanism, no pathspec-scoped finalize stash).
- ADR-003 — Ship the Issue-1 fix as a **full release 0.28.5** (5-file version sync + tag push → pipeline); spoton's own 3 agents are hand-patched immediately rather than waiting for `/plugin update`.

**Estimated impact:** harness-maker — 3 template lines + 1 unit-test assertion + dogfood re-render + 5 version files + CHANGELOG. spoton — 3 agent edits, 1 settings.json edit, 2 git operations + 1 file delete. No new modules, no contract changes in harness-maker.

## 📚 Prior Work

- `RESEARCH-spoton-codex-rm-stash-rootcause.md` — full root-cause evidence (code refs + live spoton state).
- `[wiki:fresh-install-health-baseline]` (0.17.0, 2026-05-19) — establishes that `_merge_permissions` unions `allow|deny|ask` *by design* (additive existing-install migration with zero new code path) and that 0.17.0 narrowed the Production deny baseline (`Bash(curl:*)` → `Bash(curl * | sh)`, flagged BREAKING). This is precisely why a *narrowing* never propagates to old installs — the union can add but not retire. Directly motivates ADR-002 (Issue 2 is a new subtractive mechanism, not a template tweak — out of scope).
- `[wiki:gotcha] worktree-finalize-conflicts-with-parallel-main-edits` (2026-05-19) — confirms squash-merge conflict class on files the worktree never touched; `--ours` resolution. Underpins the Issue-3 mechanism.
- `[feedback_subagent_model_override]` — reviewer/validator subagents fail to launch in 1M-Opus sessions; pass `model: "opus"` on the Task call (applied in Step 4 below).
- CLAUDE.md §보안/권한 (deny default-OFF, 2026-05-31), §Multi-session worktree accepted-limitation (gitignore can't untrack committed files; harness never auto-`git rm --cached`), §버전업 정책 (5-file sync), §릴리스 절차 (tag push → release.yml; never manual `gh release create`).

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|-------|----------|----------|---------|--------|------|-------|
| 1 | Issue 1 fix shape | Architecture | Conditional vs unconditional Bash in `tools:` | conditional / unconditional | **unconditional** | codex deny still blocks python/sh/rm/curl; simpler, one branch | ADR-001 |
| 2 | Issue 2 depth | Scope | spoton manual vs harness subtractive-deny vs both | manual / harness / both | **spoton manual only** | union-merge can't retire by design; harden = new mechanism, deferred | ADR-002 |
| 3 | Issue 3 depth | Scope | spoton manual vs harness pathspec-stash vs both | manual / harness / both | **spoton manual only** | accepted-limitation; harden touches 5-layer defense, deferred | ADR-002 |
| 4 | /hm:health checks | Observability | Add drift detection? | no / all / subset | **no** | out of scope; separate task | — |
| 5 | spoton Issue-1 immediacy | Phasing | hand-patch spoton agents now vs wait for release+update | patch now / wait | **patch now** | immediate codex unblock; accepts content_hash drift on generated agents | ADR-003 |
| 6 | Release scope | Phasing | commit+bump no-push / full release now / commit only | … | **full release now** | explicit authorization for tag push (git policy) | ADR-003 |

## 📐 Architecture Decision Records

### ADR-001: Issue 1 — unconditional `Bash` in the codex agents' `tools:` line
**Status:** Accepted (2026-06-02, via /hm:plan interview)
**Context:** `code-reviewer`, `consensus-arbiter`, `plan-validator` templates set `tools: Read, Grep, Glob`. The `codex_permission_line.md.j2` partial injects `Bash(codex exec:*)` into `permissions.allow` when codex is enabled, but Claude Code's `tools:` field is the hard allowlist of tool *availability* — `permissions` is a secondary filter that cannot grant a tool absent from `tools:`. Result: the agent has no Bash tool and `codex exec` cannot run.
**Decision:** Add bare `Bash` to the `tools:` line of all three templates, unconditionally (independent of `codex_second_opinion.enabled`). The `tools:` field does NOT support argument scoping — `Bash(codex exec:*)` is a *permissions* concept — so the bare tool name is the only valid form; scoping stays enforced by the existing `permissions.allow` (`Bash(codex exec:*)` only) + `deny` (python/node/sh/bash/rm/curl/npm/eval).
**Consequences:**
- ✅ Codex second opinion actually runs for the 3 agents when enabled. Matches the already-working pattern in `security-auditor.md.j2` (`tools: …, Bash`).
- ✅ **Second latent bug also fixed (validator W2):** `code-reviewer.md.j2:13-15` allow-lists `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git status:*)` — which, because `tools:` omitted Bash, have been **inert on every install**. The reviewer could never run `git diff` to inspect the change it was reviewing. Adding `Bash` to `tools:` restores this capability. (`plan-validator`/`consensus-arbiter` carry no git allow entries, so only `codex exec` was inert for them.) The "validator env had no Bash" symptom the user observed is the empirical proof that `tools:` is the hard gate.
- ✅ **No security regression (validator W1, verified):** all three templates already carry the full REVIEW-M7 interpreter-deny quartet `Bash(python:*)`, `Bash(node:*)`, `Bash(sh:*)`, `Bash(bash:*)` plus `rm/curl/npm/eval`. Unconditional `Bash` makes the deny list the sole barrier — but that barrier is already complete, so the `Bash(sh -c "…")` escape (REVIEW M7) stays blocked. Phase 1 asserts this deny-completeness in the same test that asserts `tools:` contains Bash.
- ⚠️ When `codex_second_opinion` is *disabled*, these reviewers carry the Bash *tool* with only git-scoped (code-reviewer) or zero (plan-validator/consensus-arbiter) allow-listed commands. Net exposure is the bare capability; every non-allow-listed command is denied-by-default for a non-interactive subagent and the dangerous ones are explicitly denied.
**Rejected alternatives:**
- Conditional `Bash` in `tools:` (only when enabled + agent in list) — Rejected: adds a second `{% if %}` site that must stay in lockstep with the permission partial; the disabled-state exposure (above) is negligible, so the lockstep cost isn't justified.
- Add only to permissions (status quo) — Rejected: it's the bug.
**Source:** Interview #1

### ADR-002: Issues 2 & 3 — remediate in spoton only; do NOT harden harness-maker
**Status:** Accepted (2026-06-02, via /hm:plan interview)
**Context:** Issue 2's stale deny survives because `_merge_permissions` unions deny lists *by design* (additive migration per `[wiki:fresh-install-health-baseline]`); retiring an entry would require a new subtractive "retired-deny" mechanism that conflicts with the preserve-user-deny contract. Issue 3's tracked-yet-ignored `.claude/observability/` is a CLAUDE.md-documented accepted limitation (gitignore can't untrack; harness never auto-`git rm --cached`); a durable fix means pathspec-scoping the finalize stash, which touches the 5-layer worktree defense.
**Decision:** Fix both manually in `~/spoton` only. Leave harness-maker's `_merge_permissions` and `_stash_base_dirty` unchanged.
**Consequences:**
- ✅ spoton unblocked immediately with surgical, reversible edits; zero blast radius on the most safety-critical harness subsystems.
- ⚠️ Other/old installs are NOT auto-healed; the same drift can recur. Acceptable: spoton is the only affected project today, and both hardening efforts are precedent-setting changes that deserve their own SPEC/PLAN if ever pursued.
**Rejected alternatives:**
- harness subtractive-deny mechanism — Rejected: new security-posture-sensitive code path; deferred.
- harness pathspec-scoped finalize stash — Rejected: high blast radius on worktree merge-fence/pop logic; deferred.
- Add /hm:health drift checks — Rejected (Interview #4): scope creep; separate task.
**Source:** Interview #2, #3, #4

### ADR-003: Ship as full release 0.28.5; hand-patch spoton's agents immediately
**Status:** Accepted (2026-06-02, via /hm:plan interview)
**Context:** spoton runs the installed 0.28.4 plugin, so the template fix doesn't reach spoton until a release + `/plugin update` + re-render. The user wants spoton's codex working now, and git policy requires explicit authorization for push/tag.
**Decision:** (a) Hand-patch spoton's three agent `.md` files' `tools:` line immediately for instant unblock; (b) ship the harness-maker template fix as a full release 0.28.5 — 5-file version sync + CHANGELOG + dogfood re-render + tag push, letting `release.yml` run the pipeline (no manual `gh release create`).
**Consequences:**
- ✅ Immediate spoton unblock + durable upstream fix that future `/plugin update` propagates.
- ⚠️ Hand-patching spoton's *generated* `plan-validator.md`/`consensus-arbiter.md` mutates their body → `content_hash` drift. On a later spoton re-render to 0.28.5, reconcile sees the hash mismatch and **KEEPs the hand-patched body ("theirs"), it does NOT heal-to-template** (validator W5). This is benign here only because the hand patch == the 0.28.5 template intent (both add `Bash`); if they ever diverged, the hand patch would win silently.
- ⚠️ **`code-reviewer` never self-heals (validator W3):** spoton's `code-reviewer.md` is user-customized with NO provenance frontmatter (Zephyr/Flutter rewrite). The 0.28.5 template fix reaches `plan-validator` + `consensus-arbiter` on re-render (they self-heal / KEEP-equal), but reconcile leaves the user-customized `code-reviewer` untouched forever. spoton's `code-reviewer` is therefore **permanently manual** — it must be re-checked on any future spoton agent re-customization.
**Rejected alternatives:**
- commit + bump, no push (release later) — Rejected (Interview #6): user wants spoton to receive it via `/plugin update`, which needs a published release.
- commit without version bump — Rejected: violates the 5-file sync policy.
**Source:** Interview #5, #6

## 🏗️ Technical Design

**Current State:**
- `src/harness_maker/templates/agents/{code-reviewer,consensus-arbiter,plan-validator}.md.j2` line 5 = `tools: Read, Grep, Glob`; `permissions.allow` includes `{%- include "agents/_partials/codex_permission_line.md.j2" %}`.
- `src/harness_maker/render.py` `_merge_permissions` (union) and `worktree.py` `_stash_base_dirty` — **unchanged** (ADR-002).
- Version = 0.28.4 across the 5 sync files.
- spoton: 3 agents missing Bash in `tools:`; `settings.json` deny = `[Bash(rm:*), Bash(curl * | sh), Write(/etc/**), Write(~/.ssh/**), Bash(curl:*)]`; `.claude/observability/` (4 files) + `.claude/.hm-iter-receipts/` tracked; orphan `.claude/.hm-loop-execute-b50f000b4e93-20260601T1633Z`.

**Affected Components:**
- harness-maker: 3 agent templates, 1 unit test, dogfood `.claude/agents/*`, 5 version files, CHANGELOG.
- spoton (external repo, manual): 3 agent `.md`, `settings.json`, git index, 1 marker file.

**Dependencies:** none added.

**Design Decisions:** all per ADR-001/002/003 above.

**Data Flow / API Changes:** none. The fix only widens the `tools:` allowlist of three rendered agents.

## 📝 Implementation Plan

### Phase 1 — harness-maker template fix + test (Issue 1)
- **depends_on:** []
- **parallel_group:** serial-harness
- **merge_hazards:** none (3 distinct template files; test file separate)
- **Scope (in):** `src/harness_maker/templates/agents/code-reviewer.md.j2`, `consensus-arbiter.md.j2`, `plan-validator.md.j2` (line 5 → `tools: Read, Grep, Glob, Bash`); `tests/unit/test_render_codex_permission_injection.py` — add **two** assertions per the 3 allow-listed agents: (a) the rendered `tools:` line contains `Bash`; (b) the rendered `deny` block contains the full quartet `Bash(python:*)`, `Bash(node:*)`, `Bash(sh:*)`, `Bash(bash:*)` (deny-completeness guard so unconditional Bash never outruns the M7 barrier — validator W1).
- **Scope (out):** `render.py`, `worktree.py`, any other agent template, `_partials/codex_permission_line.md.j2`.
- **Exit criterion:** `uv run pytest tests/unit/test_render_codex_permission_injection.py tests/unit/test_agent_body_partials.py -v` green; `grep -hE '^tools:' src/harness_maker/templates/agents/{code-reviewer,consensus-arbiter,plan-validator}.md.j2` all show `Bash`. (Note: this also restores `code-reviewer`'s previously-inert `Bash(git diff:*)` capability — validator W2.)
- **Risk:** low
- **Rollback point:** revert to pre-Phase-1 (no prior phase).

### Phase 2 — dogfood re-render + 5-file version bump + CHANGELOG
- **depends_on:** [1]
- **parallel_group:** serial-harness
- **merge_hazards:** `.claude/agents/*` (dogfood re-render output); the 5 version files must move together (CLAUDE.md §버전업); CHANGELOG `[Unreleased]`.
- **Scope (in):** re-render harness-maker's own `.claude/` (so dogfood agents gain Bash); bump `0.28.4 → 0.28.5` in `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`; add CHANGELOG entry (note BREAKING-adjacent: codex agents now carry Bash tool).
- **Scope (out):** spoton (Phase 4 owns it).
- **Exit criterion:** all 5 files show `0.28.5`; dogfood `.claude/agents/{plan-validator,consensus-arbiter,code-reviewer}.md` `tools:` line contains `Bash`; full gate green — `uv run pytest` (background), `uv run mypy --strict src/`, `uv run ruff check && uv run ruff format --check`. **Bounded-diff guard (validator W4, runnable not eyeball):** `git diff --name-only` lists ONLY {3 codex agent `.md.j2` + the dogfood-rerendered `.claude/agents/*` + 5 version files + CHANGELOG}; and within each of the 3 codex agent files, the only non-`content_hash` line delta is the `tools:` line (e.g. `git diff -- <file> | grep '^[+-]' | grep -v content_hash` shows just the tools line). Any out-of-set file in the diff fails the phase.
- **Risk:** low
- **Rollback point:** Phase 1.

### Phase 3 — release 0.28.5 (commit → advisory boundary → tag push)
- **depends_on:** [2]
- **parallel_group:** serial-harness
- **merge_hazards:** tag namespace (`v0.28.5` must be unique); release.yml owns post-tag artifacts.
- **Scope (in):** commit all Phase 1–2 changes; run advisory `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v` locally (does not block); `git tag -a v0.28.5 -m "fix: codex agents declare Bash tool so codex exec runs"`; `git push origin main v0.28.5`. Then STOP — `release.yml` runs quality-gate → build → publish → github-release.
- **Scope (out):** NO manual `gh release create` (CLAUDE.md §릴리스 절차).
- **Exit criterion:** `git push` succeeded; `gh run list --workflow=release.yml` shows the v0.28.5 run triggered. (Pipeline completion is monitored, not blocked-on, per release policy.)
- **Fix-forward branch (validator S6, explicit for /hm:execute):** on a RED `release.yml` run → `gh run view <id> --log-failed`. If `quality-gate` failed, note the local Phase 2 gate already passed → investigate env divergence (uv.lock, Python version). Recover by fix-forward with `v0.28.6` — **never re-tag `v0.28.5`, never run `gh release create` manually**. Already-published artifacts are immutable and left as-is (CLAUDE.md §릴리스 절차).
- **Risk:** medium (outward-facing; user-authorized in Interview #6).
- **Rollback point:** Phase 2 (tags/published artifacts are immutable — on pipeline failure, fix-forward with a new patch tag per the branch above, do NOT un-publish).

### Phase 4 — spoton manual remediation (Issues 1, 2, 3) — separate repo
- **depends_on:** []
- **parallel_group:** spoton-remediation (independent of Phases 1–3; different repo, uses installed plugin)
- **merge_hazards:** none (operations confined to `~/spoton`)
- **Scope (in), executed in `~/spoton`:**
  1. **Issue 1:** add `Bash` to `tools:` line of `.claude/agents/{plan-validator,consensus-arbiter,code-reviewer}.md` (immediate codex unblock; accepts hash drift per ADR-003).
  2. **Issue 2:** edit `.claude/settings.json` → remove `Bash(rm:*)` and `Bash(curl:*)` from `permissions.deny` (keep `Bash(curl * | sh)`, `Write(/etc/**)`, `Write(~/.ssh/**)`). Pure JSON, no frontmatter. **Note (validator S7):** the resulting deny is intentionally hand-curated — it equals NEITHER a fresh 0.28.4 render (`deny: []`, since spoton has no `permissions` block → `deny_dangerous=False`) NOR the opt-in dangerous baseline. The two `Write(...)` guards are kept deliberately (harmless, defensible). If the user prefers exact fresh-render parity, removing all four is a one-line variant — leave as conservative default unless asked.
  3. **Issue 3:** `git rm -r --cached .claude/observability .claude/.hm-iter-receipts .claude/.hm-render-manifest.jsonl` then commit (untrack the gitignored churn); delete orphan `.claude/.hm-loop-execute-b50f000b4e93-20260601T1633Z`; remove the stray untracked `work-docs/RESEARCH-product-physical-size.md` if it is not a wanted deliverable (confirm with user first — do not delete a deliverable).
- **Scope (out):** any harness-maker source change for these issues (ADR-002).
- **Exit criterion (in `~/spoton`):** `grep '^tools:' .claude/agents/{plan-validator,consensus-arbiter,code-reviewer}.md` all show `Bash`; `python -c "import json;d=json.load(open('.claude/settings.json'));assert 'Bash(rm:*)' not in d['permissions']['deny'] and 'Bash(curl:*)' not in d['permissions']['deny']"`; `git ls-files .claude/observability .claude/.hm-iter-receipts` empty; orphan marker absent.
- **Note (validator W3):** of the three agents, only `plan-validator` + `consensus-arbiter` are generated (provenance) and will self-heal on a future 0.28.5 re-render; `code-reviewer` is user-customized (no provenance) → its hand-patch is permanent and not upstream-backed.
- **Risk:** low (surgical, reversible; settings.json edit uses Write per WSL2/NTFS policy if applicable).
- **Rollback point:** spoton git restore of the edited files / un-stage the `git rm --cached`.

## 🧪 Testing Strategy

- **Unit:** extend `test_render_codex_permission_injection.py` — assert each of the 3 allow-listed agents renders a `tools:` line containing `Bash` (both enabled and disabled, since the fix is unconditional). Keep the existing `Bash(codex exec:*)` permission assertions intact.
- **Snapshot/regression:** full `uv run pytest` (background) to catch any agent-snapshot deltas from the dogfood re-render; regen snapshots if the only diff is the new `tools:` Bash on the 3 agents.
- **Type/lint:** `uv run mypy --strict src/` + `uv run ruff check`/`ruff format --check`.
- **Integration (advisory):** `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v` before tag (does not block; release.yml re-runs).
- **Manual (spoton):** after Phase 4, run a `/hm:plan`-style codex path in spoton and confirm `codex_status: invoked` (no "validator env had no Bash"); attempt an `rm` in the main session; run an execute worktree cycle and confirm no recurring stash-pop conflict on observability.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Disabled-codex reviewers now carry bare Bash tool | certain | very low | Full M7 interpreter-deny quartet (python/node/sh/bash) verified present on all 3 templates → escape hatch stays blocked; only git-scoped/zero commands allowable (ADR-001, W1). |
| Dogfood re-render produces unexpected agent-snapshot diffs | medium | low | Phase 2 **runnable** bounded-diff guard (`git diff --name-only` ∈ expected set; non-content_hash delta = tools line only) — not an eyeball gate (W4). |
| spoton `code-reviewer` loses Bash on future re-customization | low | low | Documented permanently-manual (no provenance, never upstream-healed); re-check on any spoton agent edit (W3). |
| Release pipeline job fails post-tag | low | medium | Fix-forward with new patch tag; never un-publish (CLAUDE.md §릴리스 절차). Monitor `gh run view --log-failed`. |
| spoton hand-patch lost on next re-render | low | low | Self-correcting once spoton updates to 0.28.5 and re-renders (template now correct); documented in ADR-003. |
| Deleting a wanted deliverable in Phase 4 step 3 | low | medium | Confirm with user before removing `work-docs/RESEARCH-product-physical-size.md`; never delete a deliverable unprompted. |
| plan-validator codex skips during THIS plan (dogfood has same bug) | certain | none | Expected meta-confirmation of Issue 1; surface skip notice, verdict is Claude-only-valid. |

## ✅ Success Criteria

- [x] 3 codex agent templates render `tools:` with `Bash`; unit test asserts it.
- [x] 5 version files at `0.28.5`; CHANGELOG updated; full gate (pytest/mypy/ruff) green.
- [~] `v0.28.5` tagged + pushed; `release.yml` run triggered (no manual `gh release create`). **DEFERRED** — gated on the pre-release codex permission probe (REVIEW advisory) + explicit go; main pushed, tag not yet fired.
- [x] spoton: 3 agents have Bash in `tools:`; `settings.json` deny free of `rm`/`curl:*`; observability + render-manifest untracked; orphan marker gone (commit `4cfae0b`).
- [~] spoton codex path returns `codex_status: invoked`; `rm` permitted in main session; execute worktree cycle has no recurring observability stash conflict. **DEFERRED** — runtime verification (the manual codex probe + a live execute cycle in spoton); statically unverifiable.

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION → **RESOLVED** (5 warnings + 2 suggestions, zero critical). All resolved in-place (plan-precision fixes with clear correct answers; no architectural fork required a follow-up interview round).

**Codex second opinion:** `skipped` — reason: *"plan-validator session lacks the Bash tool to dispatch `codex exec` (the exact Issue 1 condition); warn-and-proceed per ADR-007, Claude-only verdict."* ⚠️ This is a **live meta-confirmation of Issue 1**: the dogfood `plan-validator` carries the same bug this PLAN fixes. Verdict is Claude-derived and valid without Codex.

| # | Severity | Validator finding | Resolution |
|---|----------|-------------------|------------|
| W1 | warning | Unconditional Bash makes deny the sole barrier; verify M7 quartet present | **Verified** all 3 templates carry `python/node/sh/bash` + rm/curl/npm/eval. Added deny-completeness assertion to Phase 1 test. ADR-001 updated. No regression. |
| W2 | warning | Premise inconsistency: if `tools:` gates, `code-reviewer`'s `Bash(git diff:*)` was also inert | **Confirmed** (code-reviewer.md.j2:13-15). Premise is correct (live symptom proves it); fix also restores git-diff capability — documented as a second latent bug in ADR-001. |
| W3 | warning | spoton `code-reviewer` (no provenance) never self-heals | ADR-003 + Phase 4 + Risks updated: only plan-validator/consensus-arbiter self-heal; code-reviewer permanently manual. |
| W4 | warning | Phase 2 "inspect diff" is an eyeball gate | Replaced with runnable `git diff --name-only` bounded-set + non-content_hash delta check. |
| W5 | warning | "self-correcting" framing is KEEP-theirs, not heal-to-template | ADR-003 wording tightened. |
| S6 | suggestion | Phase 3 lacks explicit fix-forward trigger | Added explicit `v0.28.6` fix-forward branch (never re-tag, never manual `gh release create`). |
| S7 | suggestion | spoton partial-deny state matches no template branch | Noted as intentional hand-curation in Phase 4 step 2; all-four-removal offered as variant. |

**Factual audit:** validator confirmed every load-bearing claim (the 3 agents' `tools:` line, the conditional codex permission partial, `security-auditor.md.j2:5` precedent, union-merge + tracked-yet-gitignored mechanics) against source with zero factual errors.

## 🚦 Execute Status (2026-06-02)

| Phase | Status | Notes |
|-------|--------|-------|
| 1 — template fix + test | ✅ DONE | 3 templates → `tools: …, Bash`; 2 new unit assertions (tools-Bash + deny-quartet). A.5 test-reviewer PASS. RED→GREEN confirmed. |
| 2 — version bump + CHANGELOG (+ dogfood) | ✅ DONE (core) | 5 version files + `uv.lock` → 0.28.5; CHANGELOG `[0.28.5]`; snapshot regen clean (version-masked). **Dogfood `.claude/` re-render = OPTIONAL/LOCAL** — `.claude/` is gitignored in harness-maker, so it neither ships nor enters the commit; run `uv run harness-maker make . --update` anytime to refresh local dogfood agents. |
| 3 — release 0.28.5 (tag push) | ⏳ POST-WRAPUP | Execute commits nothing. After `/hm:wrapup` commits the 12 staged files, run the release: advisory boundary tests → `git tag -a v0.28.5` → `git push origin main v0.28.5` → let `release.yml` finish (no manual `gh release create`). |
| 4 — spoton remediation | ✅ DONE | Separate repo `~/spoton`, commit `4cfae0b`: 3 agents → `tools: …, Bash`; deny stripped of `rm`/`curl:*`; observability + render-manifest `git rm --cached` (now untracked+ignored); orphan loop marker already absent. Stray `work-docs/RESEARCH-product-physical-size.md` left untracked per user. |

**Execute deviations from PLAN (surfaced, not silently descoped):**
- The Phase-2 "bounded diff" guard (W4) applied to the pre-render source change; the version bump turned out to churn **nothing** in fixtures (version is masked in snapshots; `_render_agent` SHA is version-independent) — only `uv.lock`'s own version line. Cleaner than the PLAN feared.
- Worktree footgun (failures.md `snapshot-regen-inside-worktree` count:7) enforced: targeted tests only inside the worktree; full suite + snapshot regen run **from main after `finalize stage-only`**.

**Harness-maker stage exit:** 12 files staged on main, full gate GREEN (ruff/format/mypy/pytest), **no commit** (wrapup owns it).
