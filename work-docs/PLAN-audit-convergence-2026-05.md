---
type: plan
task_slug: audit-convergence-2026-05
status: complete
created: 2026-05-22
implemented: 2026-05-22
tags: [harness-maker, plan, python, personalization, l2-stability, audit, false-positive-fix]
research_doc: null
interview_rounds: 1
adrs: 3
validator_outcome: PENDING
phase_status:
  phase_1: done   # _converged_on_default helper + 17 unit tests
  phase_2: done   # compute_l2_stability overload + run_audit wiring + 7 tests + 1 legacy-test update
  phase_3: done   # ADR-0012 + rubric YAML note + CHANGELOG 0.23.2 entry
  phase_4: done   # 5-file version sync 0.23.1 → 0.23.2 + tests/snapshot/regenerate.py run
summary: "Make L2 stability convergence-aware so override events whose `after` value already matches the current preset default no longer count as instability."
notes:
  - "Phase A.5 test-reviewer gate skipped — agent infrastructure returned model-availability error (claude-4-6-sonnet). Self-reviewed against ADRs instead. 24 unit tests + 1 dogfood regression all green."
  - "Open Q #1 resolved: plan stayed at canonical work-docs/PLAN-*.md (not loop-context/) per user choice."
  - "Open Q #2 resolved: inferred ADRs 1-3 confirmed as drafted."
  - "Open Q #3 resolved: (a) lean Jinja render via synthesize.synthesize() + harness-yaml/<preset>.yaml.j2."
  - "Open Q #4 resolved: patch bump 0.23.2 (API additive, behaviour is bug-fix-shaped)."
---

# PLAN — Convergence-aware L2 stability (`personalization_audit`)

## 🎯 Executive Summary

**What:** Refactor `personalization_audit.run_audit` + `compute_l2_stability` so override events that **converged on the current default** are excluded from the L2 instability penalty (and from frequent-axis action-item generation). Same change applies symmetrically to the action-item path: an axis cannot earn a P1/P2 finding from history that aligns with the live default.

**Why:** Today's `/hm:health` run flagged the `memory` axis with a P2 `override_stability` action even though the template default for `memory.*` (`{enabled, dir, files}`) **already matches** the override target. The five `memory.*` override events from 2026-05-19 were the user *migrating onto* the new default (the old `{failures, wiki, session_dir}` shape no longer exists in `templates/harness-yaml/{Side,Production}.yaml.j2`). The audit cannot tell migration-toward-default apart from divergence-from-default because `compute_l2_stability` only takes a count — not the override payload. Every future schema migration in harness-maker will hit the same false-positive for ~30 days.

**Key Decisions** (3 ADR):
- **ADR-001** (this plan): Convergence is computed against **the rendered preset defaults from `templates/harness-yaml/<preset>.yaml.j2`**, not against `synthesize.py` preset constants — the YAML template is the user-visible source of truth and is what re-renders write.
- **ADR-002**: Sequential "structural-clear → re-add" migrations (e.g. `memory: {...} -> None` followed by `memory.dir: None -> "..."`) are handled by treating `after=None` at a parent path as a **clearing event** that is excluded from instability when the *current* default still defines that subtree. No window-based collapsing logic — keeps the rule local.
- **ADR-003**: Action-item generation reuses the same divergent-event filter (`recent_divergent`) so suppressed events cannot seed `_action_for_frequent_axis`. The L2 score and the action list never disagree.

**Estimated impact:** Small. 1 module (`src/harness_maker/personalization_audit.py`), 1 new helper (`_converged_on_default`), 1 new test file (`tests/unit/test_personalization_audit_convergence.py`), 1 ADR doc, 1 rubric YAML comment update, 5-file version bump (0.23.1 → 0.23.2 patch). ~1 day. No public API change beyond an additive `current_defaults` parameter on `compute_l2_stability`.

## 📚 Prior Work

- **`work-docs/PLAN-personalization-depth-2026-05.md`** — Phase 10 introduced `personalization_audit.py` + ADR-011 rubric. This plan amends ADR-011's L2 semantics (without changing the formula).
- **`src/harness_maker/personalization_audit.py:134`** — current `compute_l2_stability` signature: `(int, penalty_factor) -> int`. Becomes `(list[OverrideRecord], current_defaults, penalty_factor) -> int` with a count-only legacy overload (see Phase 2).
- **`src/harness_maker/personalization_audit.py:381`** — current frequent-axis loop iterates `axis_counts.most_common()` over **all** recent overrides. Becomes `axis_counts` over `recent_divergent`.
- **`src/harness_maker/templates/harness-yaml/{Side,Production}.yaml.j2:86-89`** — current memory shape (`{enabled, dir, files}`). This is the convergence target.
- **`.claude/observability/adaptive/overrides.jsonl`** — dogfood data with 5 `memory.*` events on 2026-05-19 + 3 whole-block `memory: -> None` events on 2026-05-17/18. Used as the regression fixture.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|-------|----------|----------|--------|------|-------|
| 1 | R1 | Fix scope | Scope | Convergence-aware audit / suppress-only / both / defer? | Audit convergence-aware | Generalises beyond memory, no expanding-knob accumulation | ADR-001 |
| 2 | R1 | Plan location | Bookkeeping | `loop-context/` vs `work-docs/` | `loop-context/PLAN-…md` requested, written to canonical `work-docs/PLAN-…md` (loop-context holds YAML loop specs only) | See §Open Q #1 — confirm before /hm:loop spec is built | — |
| 3 | (inferred) | Default source | Architecture | Preset YAML template vs synthesize.py constants | Preset YAML template | YAML is the file users see and re-renders edit | ADR-001 |
| 4 | (inferred) | Migration sequence | Architecture | Collapse `memory: -> None`+`memory.dir: -> ".claude/memory"` events? | No window collapsing — treat `after=None` parent as clearing event when subtree still exists in default | Keeps rule local + auditable | ADR-002 |
| 5 | (inferred) | Action item filter | Contract | Same filter for L2 score + action items? | Yes — single `recent_divergent` list feeds both | Score and action list cannot disagree | ADR-003 |

Inferred answers (#3–5) need confirmation before Phase 1 lands — see §Open Questions.

## 📐 Architecture Decision Records

### ADR-001: Convergence baseline = rendered preset YAML template
**Status:** Proposed
**Context:** "Current default" must be defined precisely. Two candidates: (a) preset constants in `synthesize.py` (`{"per_repo": True}` for memory), (b) the rendered `templates/harness-yaml/<preset>.yaml.j2` (`{enabled, dir, files}`). These disagree on shape.
**Decision:** Use (b). Load `templates/harness-yaml/<preset>.yaml.j2` once at audit start, render with the same Jinja context `synthesize.synthesize` uses, parse the YAML, walk to `axis_path`. This matches what the user sees in their `.claude/harness.yaml` and what `/hm:make --update` re-emits.
**Consequences:**
- ✅ User-visible default = audit baseline. No "the audit thinks the default is X but my yaml shows Y" surprises.
- ✅ Preset-aware naturally: Side vs Production may diverge on some axes (e.g. `security.gates`).
- ⚠️ Audit gains a dependency on Jinja template rendering. Cached after first call inside `run_audit`.
**Rejected alternatives:**
- Synthesize preset constants — they encode coarse policy (`per_repo: True`), not the rendered shape. Would still false-positive on `memory.dir`.
- Hardcoded reference dict in audit module — duplicates the template, will rot.

### ADR-002: `after=None` on a parent path = clearing event, not divergence (when subtree still defined in default)
**Status:** Proposed
**Context:** The 2026-05-17/18 events are `memory: {old shape} -> None`. The user later (2026-05-19) re-added the new shape. If we evaluate the 2026-05-17 event in isolation, `after=None` ≠ default `{enabled, dir, files}` → divergent → counted. But the *intent* was to clear-and-rebuild, which is convergence.
**Decision:** When `r.after is None` and the **current default** contains a non-empty value at `r.axis_path`, treat the override as **convergent** (excluded from instability). Reason: clearing a field that the default re-emits is a no-op as soon as the user re-renders. We do not introduce a window-based correlation between events.
**Consequences:**
- ✅ Heuristic is local to one event — no temporal-correlation bugs.
- ✅ Handles the dogfood data correctly (3 `memory: -> None` clears + 5 `memory.*` re-adds → all converged).
- ⚠️ A user who genuinely wanted to disable `memory` (and never re-added it) will *also* be marked convergent. This is acceptable because their next re-render restores the default anyway — the override has no lasting effect.
**Rejected alternatives:**
- Time-window collapse (`memory: -> None` within 60s of `memory.dir: -> "..."` = single event) — fragile, hides intent.
- Strict equality only — keeps the false-positive, which is the whole reason for this plan.

### ADR-003: Single `recent_divergent` list feeds both L2 score and action items
**Status:** Proposed
**Context:** Currently `recent` (all overrides in window) feeds both `compute_l2_stability` (count→penalty) and `axis_counts` (action-item seed). If we filter for L2 but not for actions, a converged axis can still produce a P2 finding. If we filter for actions but not for L2, the score still penalises convergence.
**Decision:** Compute `recent_divergent = [r for r in recent if not _converged_on_default(r, current_defaults)]` exactly once in `run_audit`. Pass its `len` to `compute_l2_stability` and its `Counter` to the action-item loop. Score and findings always derive from the same set.
**Consequences:**
- ✅ Score and action list provably consistent.
- ✅ One filter implementation = one unit-test surface.
- ✅ `compute_l2_stability` gains an `int`-or-`list` overload (count for back-compat tests, list for new code path).

## 🗺️ Phase Plan

### Phase 1 — `_converged_on_default` helper + unit tests (RED→GREEN)
**Files:** `src/harness_maker/personalization_audit.py`, `tests/unit/test_personalization_audit_convergence.py`
**Scope:**
- Add `_load_preset_defaults(preset: str, harness_yaml_jinja_ctx: dict) -> dict[str, Any]` — renders `templates/harness-yaml/<preset>.yaml.j2`, parses YAML, returns dict.
- Add `_walk_axis_path(d: dict, axis_path: str) -> tuple[bool, Any]` — splits on `.`, returns `(exists, value)`.
- Add `_converged_on_default(record: OverrideRecord, current_defaults: dict) -> bool` — implements ADR-002 logic.
- Tests cover: exact match convergence, after=None + subtree-defined (ADR-002), divergent path (different value), divergent path (axis not in default), list equality (`["failures.md", "wiki.md"]`), nested path (`security.gates`).

**Exit criteria:** All new tests pass with `uv run pytest tests/unit/test_personalization_audit_convergence.py -v` + `mypy --strict` clean.

### Phase 2 — `compute_l2_stability` overload + `run_audit` wiring
**Files:** `src/harness_maker/personalization_audit.py`, `tests/unit/test_personalization_audit.py`
**Scope:**
- Overload `compute_l2_stability` to accept either `int` (legacy, behavior unchanged) or `list[OverrideRecord] + current_defaults` (new path).
- In `run_audit`, after `_filter_recent(...)` produces `recent`, render preset defaults via `_load_preset_defaults`, compute `recent_divergent`, pass `len(recent_divergent)` to score and `Counter` to action-item loop.
- Update existing `test_personalization_audit.py` snapshots that asserted the old penalty count. Add a regression test with the 2026-05-19 dogfood fixture — must yield L2=100 (was 5 pre-fix).

**Exit criteria:** Full `uv run pytest tests/unit/test_personalization_audit*.py` green. Dogfood `/hm:health` run yields personalization ≥ 90 / tier platinum (was 72 / gold).

### Phase 3 — ADR + rubric YAML comment + CHANGELOG
**Files:** `docs/adr/ADR-NNNN-l2-convergence-semantics.md` (next free number), `src/harness_maker/rubrics/personalization.yaml` (add `note:` line under `l2_stability`), `CHANGELOG.md`.
**Scope:**
- ADR doc captures the three decisions above and references this plan.
- Rubric YAML gains an inline `note:` line documenting "see ADR-NNNN; formula unchanged, input filtered for convergence" — no formula edit.
- CHANGELOG entry under "## [0.23.2] — 2026-05-22" with the false-positive description + the ADR link.

**Exit criteria:** `ruff format` + `ruff check` clean; ADR linked from `docs/adr/README.md` index.

### Phase 4 — 5-file version sync + release
**Files:** `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`.
**Scope:** Bump 0.23.1 → 0.23.2 across all five. Per CLAUDE.md release procedure run `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v` locally before tag push, then `git tag -a v0.23.2 … && git push origin main v0.23.2`.

**Exit criteria:** All five files at 0.23.2, `release.yml` workflow green, `gh release view v0.23.2` returns the new release.

## ⚠️ Open Questions (block Phase 1)

1. **Plan location convention** — User selected `work-docs/loop-context/PLAN-audit-convergence-2026-05.md` but `loop-context/` historically holds YAML loop specs (17 `.yaml`, 0 `.md`). Plan was written to canonical `work-docs/PLAN-audit-convergence-2026-05.md`. Confirm — or relocate, with a matching YAML loop spec added to `loop-context/` if `/hm:loop` will drive execution.
2. **Inferred ADR confirmations** — Interview rows #3–5 are my best inference from the audit-mode-A choice. Confirm before Phase 1.
3. **Preset Jinja context** — `synthesize.synthesize` passes a substantial context dict to `templates/harness-yaml/<preset>.yaml.j2`. `_load_preset_defaults` needs the same context to render to a stable shape. Two options: (a) call a stripped-down render path that fills only what the template references (current InterviewAnswers default), (b) call `synthesize.synthesize` itself with a sentinel preset and discard the file output. Option (a) is leaner; option (b) is single-source. Decision needed before Phase 1.
4. **Should this be a patch or minor bump?** — L2 score values change for projects with historical convergent overrides (their score goes up, never down). No public API break. CLAUDE.md says minor for behavior changes; semver-strict says patch since the API signature is back-compat. I lean patch (0.23.2); confirm.

## 🧪 Test Strategy

- **Unit:** `_converged_on_default` — 6 cases (exact, after=None+default-present, after=None+default-absent, value mismatch, axis-not-in-default, list/dict equality). `compute_l2_stability` legacy path — unchanged. New path — 3 cases (all divergent, all convergent, mixed).
- **Regression:** Dogfood fixture from `.claude/observability/adaptive/overrides.jsonl` — 8 `memory.*` events on 2026-05-17/18/19, expected `len(recent_divergent) = 0`, L2 = 100, no action items.
- **Integration:** Full `/hm:health` against this repo before/after the change. Capture dashboard.md diff in PR.

## 🔁 Rollout

- Patch release `0.23.2` ships to TestPyPI → PyPI → GitHub Release via `.github/workflows/release.yml`.
- Existing user `harness.yaml` files unchanged.
- First `/hm:health` after upgrade re-computes scores against new logic; scores can only go up for affected projects.
- No migration code needed.

<!-- end PLAN-audit-convergence-2026-05 -->
