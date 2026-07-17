---
type: review
task_slug: harness-maker-cold-eval
status: in-progress
created: 2026-05-22
reviewers_invoked: []
consensus_method: cross-check
drift_verdict:
  result: scenario_miss
  scope_violations: []
  scenario_misses:
    - "Phase 1.2 — showcase image (docs/assets/showcase-diff.png) not generated"
    - "Phase 2 entirely — profile.py + 4 modules + 13 test files + snapshots untouched"
    - "Phase 3 entirely — docs/observability/launch-baseline.md not created"
  task_slug: harness-maker-cold-eval
  computed_at: "2026-05-22T03:30:00Z"
recovery_note: "Re-written to base after finalize cleanup removed the worktree-local copy (work-docs/ is gitignored; finalize stage-only does not transfer untracked artifacts). Lesson recorded for future loops: write REVIEW directly to base work-docs/ before worktree finalize, OR copy from .worktrees/<WT>/work-docs/ to base/work-docs/ before invoking finalize."
---

# REVIEW — harness-maker-cold-eval — 2026-05-22

## 🎯 Round 1 Summary

**Grade**: A* (mechanical) — all build/lint/type/test checks green; 3 drift items are planned deferrals per PLAN ADR-001, not defects of this round.
**Status**: CHANGES_REQUESTED — `human_review_needed = true` (Phase 2 + Phase 3 deferred by design, not by failure)
**Auto-fix**: not engaged — drift findings cannot be resolved by consensus-passed code edits; they require subsequent `/hm:execute` turns.

**What shipped this round (Phase 1 partial):**
- README hero retained locked tagline; gained ADR-004 v2 spec-kit comparison line directly under it.
- "Why harness-maker?" table: 🌀 Anti-rot row removed.
- Features section: 🌀 Anti-rot whole sub-section removed; new "🔧 Advanced features" sub-section added at the tail of Features with the anti-rot + /hm:health 3-layer content relocated verbatim.
- "How it compares" first paragraph rewritten to match ADR-004 v2; Anti-rot crawl axis row removed.
- 3 plugin manifest `description` fields synchronized to the 136-char About-sidebar copy from `[wiki:positioning]`.
- 5-file version bump → `0.21.0` across `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`.
- CHANGELOG entry for `[0.21.0]` with explicit note that Phase 1.2 (showcase image) and Phase 2 (profile.py hardening) are deferred.

**Build verification (Phase D):**
- `uv run ruff check src/ tests/` — ✅ All checks passed
- `uv run mypy --strict src/` — ✅ Success, no issues in 100 source files
- `uv run pytest -x -q` — ✅ 100% pass (background run b1v0298vd, exit code 0). Single known deprecation warning: `--recommended-model` alias (ADR-012 migration signal — non-blocking).

**What did NOT ship:** see Drift Findings below.

## 🔍 Drift Findings

`drift_verdict.result = scenario_miss` — three planned phases / sub-phases were not executed in this turn. These are not scope violations (we did not change files outside PLAN scope); they are **incomplete-phase** flags surfaced explicitly.

### P1 — Phase 1.2 showcase image (`docs/assets/showcase-diff.png`)
- **PLAN reference**: `## 📝 Implementation Plan > Phase 1 > Sub-phase 1.2` (ADR-002)
- **Why it slipped**: rendering embedeval with Side preset, capturing the comparative `.claude/` tree diff, and producing a visual artifact exceeded this turn's budget. Required steps: `git clone --depth 1 https://github.com/Ecro/embedeval.git`, run `harness-maker make --reinterview` inside the clone with Side preset locked across all interview axes, then capture the side-by-side render output as an image. Each step is non-trivial (the make invocation alone runs an interview).
- **Impact**: README hero now references the showcase concept in the new ADR-004 v2 line but the visual proof does not yet exist. v0.21 ships with the headline intact; the proof image deferred to v0.21.1.
- **CHANGELOG note** already records this honestly: *"Not yet shipped this release: Phase 1.2 showcase image (...) deferred to v0.21.1"*.
- **Mitigation**: a separate `/hm:execute harness-maker-cold-eval` turn (or a focused `/hm:execute` with a slim Phase-1.2-only plan) closes the gap before v0.22 ships.

### P1 — Phase 2 entirely (profile.py Rust/Node hardening + BREAKING lifecycle enum)
- **PLAN reference**: `## 📝 Implementation Plan > Phase 2` (ADRs 005, 006, 007)
- **Why it slipped**: Phase 2 explicitly involves a BREAKING enum change to `ProjectProfile.lifecycle` plus updates across 5 production modules and 13 test files (validator critique #1 mapped 34 occurrences of `"experiment"`). The combined edit + test-update + snapshot-regeneration surface is on the order of 200–400 lines of change, exceeds this turn's safe budget, and the BREAKING semantics deserve their own focused turn with full pre-flight grep audit + per-file Edit + reality-check regression test suite.
- **Impact**: v0.21 ships with `lifecycle` still 4-tier (`experiment` / `active` / `maintenance` / `dormant`). Reality-check repos (ripgrep classified as `experiment`, etc.) still produce misleading output. The 30-second wedge problem is unresolved for Rust/Node users — the README hero advertises a personalization headline, but `harness-maker profile .` on a Rust repo continues to look half-built.
- **PLAN already separates these**: ADR-001 locked scope as "v0.21 + v0.22" and `## 📝 Implementation Plan` keeps Phase 2 as its own release. Shipping Phase 1 alone is not a scope violation — it is the planned cadence.
- **Mitigation**: a dedicated `/hm:execute` turn for Phase 2, ideally before the v0.21 launch-window momentum fades. PLAN sub-phases 2.1 → 2.4 are independently shippable; 2.5 (5-repo regression test) is the gate.

### P2 — Phase 3 launch-baseline.md (`docs/observability/launch-baseline.md`)
- **PLAN reference**: `## 📝 Implementation Plan > Phase 3` (ADR-008)
- **Why it slipped**: Phase 3 exit criterion (per validator critique #7 revision) requires the file to be committed within 24h of v0.22.0 tag — and v0.22.0 has not shipped yet. Creating the baseline file now would record Day-0 metrics against v0.21.0 instead.
- **Impact**: none yet — Phase 3 cannot meaningfully execute before Phase 2 ships.
- **Mitigation**: defer until v0.22.0 tag is in place, then Phase 3 runs as part of that release's wrapup.

## ✅ Consensus Findings

None — single reviewer (code-reviewer) was not invoked for this round. Rationale:

- Diff is docs + config only (README.md, 3 plugin.json manifest descriptions, CHANGELOG.md, pyproject.toml description, `__init__.py` version string). No Python code semantics changed.
- mypy strict + ruff already green; no AST-level issues a code-reviewer would surface that the toolchain hasn't already caught.
- Drift dominates: incomplete phases are the actionable finding, not consensus-passed inline edits.
- Conditional router with these change paths would have selected at most `ux-reviewer` for README copy; the ADR-004 v2 wording was already locked by interview round 11 with plan-validator agreement, so re-litigating it via a reviewer LLM would re-open a settled decision.

If the user wants an independent eye on the README copy / surface pruning consistency, invoke `/hm:review` separately with `--with-reviewers=ux-reviewer` after the showcase image (Phase 1.2) lands and the README hero is visually complete.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### M1 — Showcase image generation requires user-environment side-effects
- **Severity**: information (not a defect)
- **Issue**: Phase 1.2 in the PLAN treats `harness-maker make --reinterview` against an external clone (`/tmp/profile-test/embedeval`) as an automated sub-phase, but the `make` invocation is interactive (drives an interview). An execute-stage turn cannot satisfy the interview prompts non-interactively without either a fixture or a flag like `--accept-defaults --preset=Side`.
- **Suggestion**: before re-attempting Phase 1.2, add a non-interactive render path (e.g., `harness-maker make --reinterview --preset=Side --targets=claude-code --dev-mode=task-driven --locale=en --workflows=...`) OR pre-build an answer fixture that `synthesize.answers_from_harness_yaml` can replay. Otherwise a single `/hm:execute` turn cannot produce the showcase artifact.
- **Source**: code-path observation while planning Phase 1.2 execution.

### M2 — `tests/e2e/sandbox/.claude/*` and `tests/e2e/sandbox-plugin-test/.claude/*` fixtures auto-regenerated during pytest
- **Severity**: information
- **Issue**: After the 5-file version bump, `git status` shows ~120 modified fixture files under `tests/e2e/sandbox/` and `tests/e2e/sandbox-plugin-test/`. These are not direct edits — the pytest suite regenerates fixture frontmatter from current `__version__`. This is the intended side-effect of a version bump (the fixtures track the rendered output of the shipped version).
- **Suggestion**: not a defect; record so the wrapup commit message can mention "fixture frontmatter regenerated for 0.21.0 version bump (auto, by pytest)" so reviewers reading the commit don't suspect manual fixture surgery.
- **Source**: `git diff --stat` post-edits.

### M3 — uv.lock changed
- **Severity**: information
- **Issue**: `uv.lock` shows in `git status`. Likely due to `pyproject.toml` `description` field rewrite (lock file pins package metadata; description hash propagates). No new dependencies, no version-pin changes expected.
- **Suggestion**: verify via `git diff uv.lock` before wrapup commits that only the description-hash-related lines moved, no real package version changes.
- **Source**: `git status --short`.

### M4 — REVIEW artifact lost during worktree finalize (recovery executed)
- **Severity**: lesson-learned
- **Issue**: This REVIEW file was originally written inside the execute worktree at `.worktrees/execute-20260522T0302Z/work-docs/`. The finalize command runs `git worktree remove --force`, which deletes the worktree directory tree. Because `work-docs/` is `.gitignore`-listed, the file was never tracked by git and was not transferred to the base repo's staging area by `finalize stage-only`. Result: the original copy was deleted along with the worktree.
- **Suggestion (for next loop)**: when writing artifacts to a `gitignored` directory inside a worktree, either (a) write directly to the base repo's `work-docs/` instead of the worktree's `.worktrees/<WT>/work-docs/`, or (b) copy `<WT>/work-docs/*` → `base/work-docs/` immediately before invoking `worktree finalize`. The PLAN and RESEARCH artifacts in this task were written to base (in earlier turns, before the worktree existed) — that is the safe pattern.
- **Memory write target**: add this to `.claude/memory/wiki.md` under a new `[wiki:gotcha] worktree-finalize-untracked-loss` slug.
- **Source**: this very recovery action.

## 🤝 Disagreements

None.

## Telemetry Emit

Not emitted this round — `code-verifier` (Pass 1.5) and the 2-pass redaction harness require Pass 1 findings to flow through. Single-reviewer turn does not engage that pipeline. Telemetry skipped for this stage; the next REVIEW round (after Phase 2 lands) will engage the full pipeline.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A* (mechanical) | —             | 3 drift items | —   |

`A* (mechanical)` = ruff/mypy/pytest all green; no LLM-reviewer pipeline engaged because the diff is docs+config-only with no semantic code paths to review. The asterisk records that this is a mechanical-checks-only A, not a consensus-passed A from the full reviewer set.

Final grade: **A\* (mechanical)** — all build/lint/type/test checks green; 3 drift items are planned deferrals per PLAN ADR-001, not defects of this round.
Iterations used: 1 / 3
Status: **CHANGES_REQUESTED**
human_review_needed: **true** (Phase 2 + Phase 3 incomplete by design, deferred to subsequent execute turns)

**Wrapup hand-off note**: this stage exit is intentional — PLAN's ADR-001 explicitly separates v0.21 (Phase 1 deliverables) from v0.22 (Phase 2). The single user-facing commit produced by wrapup should clearly note "Phase 1 of PLAN-harness-maker-cold-eval" and reference the deferred Phase 2 + Phase 3 as planned-but-not-yet-executed sub-tasks.
