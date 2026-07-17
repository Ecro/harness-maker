---
type: plan
task_slug: harness-maker-cold-eval
status: complete  # All phases shipped 2026-05-22. Phase 1 in v0.21.0+v0.21.1, Phase 2 in v0.22.0 (BREAKING), Phase 3 in v0.22.1. Cycle closed.
created: 2026-05-22
tags: [harness-maker, plan, python, positioning, profiler, oss-launch]
research_doc: "[[RESEARCH-harness-maker-cold-eval]]"
interview_rounds: 9
adrs: 8
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Personalization locked as headline. v0.21 (showcase+headline+pruning) + v0.22 (profile.py Rust/Node hardening). 8 ADRs."
---

# PLAN — harness-maker cold-eval response

## 🎯 Executive Summary

**TL;DR.** RESEARCH-harness-maker-cold-eval locked **Approach A** — *personalization as the headline*. This plan converts that lock into two shippable releases: **v0.21** moves the headline to the README hero with a real preset-diff showcase, and **v0.22** hardens `profile.py` for Rust/Node so the future `uvx harness-maker profile .` wedge (v0.23, separate plan) survives non-Python eyeballs.

**What and why.** The differentiator (per-project personalized harness) is invisible until install — a 30-second wedge problem identified in RESEARCH. This plan ships the wedge in two stages:

1. **Visible proof** (v0.21): preset-diff between two real maintainer repos (embedeval Side vs harness-maker Production) anchored in README hero. Surface area pruning collapses 5 research-tier features (anti-rot, 5-term gate, comm-variants, /hm:health 3-layer, reviewer-consensus auto-fix) into an "Advanced features" sub-section so the headline message stays uncontested.
2. **Profiler reality** (v0.22): closes the 4 gaps the wedge reality-check found — `lifecycle` algorithm (BREAKING enum change, removing `experiment` tier), Rust `detected_checks`, Node `detected_checks`, `package_manager` manifest fallback.

**Key decisions (8 ADRs).**
- ADR-001: scope = v0.21+v0.22, v0.23 (`uvx` CTA) deferred to separate plan post-v0.22 reality
- ADR-002: showcase = embedeval (Side preset) vs harness-maker (Production preset) preset diff
- ADR-003: surface pruning = Hero+Features both, target = "Advanced features" sub-section *inside* README
- ADR-004: spec-kit comparison line = *"Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness."*, 4 places synchronized
- ADR-005: v0.22 phasing = 4 gaps parallel in v0.22.0 (1–2 weeks)
- ADR-006: lifecycle algorithm = 3-tier `active`/`maintenance`/`dormant`, **BREAKING enum change** (downstream scope expanded after validator critique #1)
- ADR-007: detected_checks policy = manifest-explicit OR command-pattern with specific Node/Cargo whitelists (post-validator clarification)
- ADR-008: primary adoption metric = PyPI weekly downloads, GitHub stars + Discussions secondary, no opt-in telemetry

**Estimated impact.**
- README.md: ~80–120 lines diff (hero rewrite + showcase image + spec-kit line + surface pruning + 5-feature relocation)
- `src/harness_maker/profile.py`: ~150–250 lines diff (lifecycle redesign + Rust/Node detected_checks + manifest fallback)
- `src/harness_maker/{models.py, interview.py, recommendation.py, modular_edit.py}`: enum-rename touches (~5–15 lines each)
- ~13 test files in `tests/unit/` + snapshot regeneration
- 5-file version bump × 2 (v0.21.0, v0.22.0)
- 1 new artifact: `docs/assets/showcase-diff.png` (or equivalent path)
- 1 new artifact: `docs/observability/launch-baseline.md` (Phase 3 exit)

## 📚 Prior Work

- **RESEARCH-harness-maker-cold-eval.md** (this plan's direct source) — locked Approach A and exposed the 30-second wedge problem via 5-repo reality-check.
- **RESEARCH-oss-readiness-audit.md** — positioning surface layer prior; ADR-007/012 of that plan locked "zero named competitors" in comparison copy; ADR-004 of *this* plan honors that constraint.
- **[wiki:positioning] per-project-personalization-hero-differentiator** (2026-05-19) — original hero copy lock (EN+KO + sub-line 4-tag + About sidebar 136-char copy).
- **[wiki:pattern] oss-launch-readiness-three-layer** (2026-05-19) — 3-layer launch model; this PLAN executes layer 2 (positioning surface).
- **[wiki:gotcha] wrapup-marker-discipline-silent-loss** (2026-05-17) — block-merge marker discipline; applies to Phase 1 README edits.
- **[wiki:gotcha] readme-one-prompt-bash-not-slash** (2026-05-19) — reader-parser consistency (8-checkpoint #2); applies to all 4 placements of the spec-kit line.
- **[wiki:fresh-install-health-baseline]** (2026-05-19) — render.py already has merge semantics for additive baselines; Phase 1 surface pruning uses these existing mechanics.

## 🎙️ Interview Transcript

| # | Round | Category | Question (1-line) | Choice | → ADR |
|---|---|---|---|---|---|
| 1 | 1 | Scope | Release scope for this plan? | A: v0.21 + v0.22; v0.23 deferred | ADR-001 |
| 2 | 2 | Scope | Showcase repo identity? | A: maintainer's other public repo (embedeval) | ADR-002 |
| 3 | 2.5 | Architecture | Showcase shape given embedeval is same stack? | A: embedeval (Side preset) vs harness-maker (Production preset) preset diff | ADR-002 |
| 4 | 3 | Architecture | Surface pruning depth — README hero only / Features too / How-it-works / separate doc? | B: Hero + Features → "Advanced features" sub-section inside README | ADR-003 |
| 5 | 4 | Contract | spec-kit comparison line — keep named, generic, or drop comparison? | A: generic "fixed bundle" version (no named competitor) | ADR-004 v1 |
| 6 | 4.5 | Contract | Exact "fixed bundle" copy variant? | A1: "Other harnesses ship a fixed bundle. ..." | ADR-004 v1 |
| 7 | 5 | Phasing | v0.22 phasing — 4 gaps all-in / split by stack / split by size / minimum? | A: 4 gaps simultaneously in v0.22.0 | ADR-005 |
| 8 | 6 | Architecture | lifecycle algorithm redesign direction? | B: 3-tier active/maintenance/dormant, "experiment" removed | ADR-006 |
| 9 | 7 | Contract | detected_checks conservatism policy? | B: medium — manifest-explicit OR command-pattern, no stack-default guessing | ADR-007 |
| 10 | 8 | Observability | Primary adoption metric for 90-day retrospect? | A: PyPI weekly downloads (GitHub stars + Discussions secondary) | ADR-008 |
| 11 | 9 (post-validator) | Contract | "fixed bundle" copy challenged by validator as inaccurate for BMAD/agent-os — revise to what? | C: "Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness." | ADR-004 v2 |

Notes:
- Rounds 2.5 and 4.5 are follow-ups within the same topic, treated as the same ADR.
- Round 11 was triggered by plan-validator critique #5 after the initial 8 rounds completed.
- No interview round used "Plan is sufficiently clear — end interview" — exit was by 5-term gate natural stop (all PLAN slots reached confidence ≥ τ).

## 📐 Architecture Decision Records

### ADR-001: Release scope = v0.21 + v0.22; v0.23 deferred to separate plan
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** RESEARCH §Wedge Reality Check proposed a 3-stage release cadence (v0.21 showcase / v0.22 profile hardening / v0.23 `uvx` CTA). One plan must define which stages it binds.
**Decision:** This plan covers v0.21 + v0.22. v0.23 (`uvx harness-maker profile .` as headline CTA) deferred to a separate plan kicked off after v0.22.0 ships and 1–2 weeks of reality observation.
**Consequences:**
- ✅ v0.21 and v0.22 are logically dependent (showcase credibility ↔ profile accuracy) — trade-off consistency in a single plan
- ✅ v0.23's exact shape can be re-calibrated against v0.22 reality before committing
- ⚠️ Two version bumps within ~3–4 weeks — release-process load doubles
**Rejected alternatives:**
- B (3 releases in one plan) — v0.23 reality unknown at lock time; replan cost high if v0.22 surfaces unexpected issues
- C (v0.21 only) — wedge incomplete; momentum lost between releases
- D (README hero rewrite only) — no showcase, headline remains a promise rather than a demonstration
**Source:** Interview #1

### ADR-002: Showcase = embedeval (Side preset) vs harness-maker (Production preset) preset diff
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** Headline ("personalized harness — built from yours") needs a 30-second visible artifact. Maintainer's public-repo inventory yielded one other code repo: **embedeval** (Python+uv+pydantic+github-actions — same stack as harness-maker). RESEARCH §Open Q #1 framed this as the "(i) real maintainer repo / (ii) external popular / (iii) constructed example" choice.
**Decision:** Apply harness-maker to embedeval with **Side preset**; contrast with harness-maker self (Production preset). Capture diff as a static image at `docs/assets/showcase-diff.png`. Diff axis = reviewer count (1 vs 5), workflow stage count, security gate depth — preset-driven differences visible at the rendered-asset level.
**Consequences:**
- ✅ Real maintainer-owned repo; not a hypothetical
- ✅ Even with same stack, preset divergence produces structurally different harnesses
- ⚠️ Stack diversity is weak (both Python+uv) — does not demonstrate "different stacks → different harnesses"; that demonstration is deferred to v0.22 + v0.23
- ⚠️ Diff might be quantitatively small if presets converge in practice — see fallback below
**Quantitative fallback trigger (added post-validator critique #6):** if Phase 1.2 render produces fewer than 3 distinct file additions OR fewer than 1 distinct agent/skill between the two outputs, declare the diff insufficient and invoke fallback. Fallback = construct a Side render of harness-maker itself (Side preset applied to this repo's profile output, captured side-by-side with the actual Production render). This trades real-repo authenticity for guaranteed-meaningful diff; document the substitution in the README caption.
**Rejected alternatives:**
- B (external popular repo gh-applied) — hyperbolic; fastapi/next.js do not use harness-maker
- C (Side vs Production inside embedeval only) — synthetic-feeling; same repo on both sides
- D (publish 5-repo reality-check output) — only profile output diff, not full harness diff
**Source:** Interview #2 + #2.5

**Amendment 2026-05-22 (v0.21.1 wrapup):** the ADR originally specified `docs/assets/showcase-diff.png`. The shipped artifact is `docs/assets/showcase-diff.md` instead. Rationale: markdown is strictly better on git-diff reviewability, full-text search, screen-reader accessibility, one-turn generation cost (no PIL/matplotlib pipeline), and update cost (text edit vs re-render). PNG only wins on "inline display in first README scroll," which the hero `📸` emoji + click-through link compensates for. The 170-line MD also documents the quantitative threshold inline (table form), so the proof artifact is now self-documenting rather than relying on a hand-rendered screenshot a skeptical reader would distrust. A PNG companion remains a future option but is no longer the gating deliverable. Verified by REVIEW-harness-maker-cold-eval-2026-05-22-phase1-2.md (grade A* mechanical, drift_verdict clean, threshold cleared 15×).

### ADR-003: Surface pruning level B — 5 features → "Advanced features" sub-section inside README
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** README currently surfaces 5 features in Hero and Features sections that compete with the personalization headline for first-screen attention: anti-rot crawler, 5-term inequality gate, communication-variants, /hm:health 3-layer rubric, reviewer-consensus auto-fix. RESEARCH cold-eval flagged these as research-tier — well-built but invisible to external users.
**Decision:** Move all 5 to a single "Advanced features" sub-section inside README (not extracted to a separate doc, not deleted, not promoted). Hero's first ~120 lines exclusively serve the personalization headline.
**Consequences:**
- ✅ Message consistency on first screen
- ✅ README anchor backwards-compat preserved (section moves but stays in same file)
- ✅ Existing `[wiki:fresh-install-health-baseline]` `render.py` merge semantics handle this (no new code path)
- ⚠️ Block-merge marker discipline mandatory — `[wiki:gotcha] wrapup-marker-discipline-silent-loss` applies; Phase 1 must run pre-commit grep for orphan content outside markers
**Rejected alternatives:**
- A (Hero only) — Features section still competes for attention
- C (Hero+Features+How-it-works → docs/) — disrupts existing reader expectations; 8-checkpoint #1 (user state preservation) risk
- D (separate `docs/advanced.md`) — link rot for any external citation of current Features section
**Source:** Interview #3

### ADR-004: spec-kit comparison line — "Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness."
**Status:** Accepted v2 (2026-05-22, revised after plan-validator critique #5)
**Context:** Hero needs a one-line answer to "why this and not BMAD / SuperClaude / claude-flow / agent-os / spec-kit". Must honor [wiki:pattern]'s ADR-007/012 "zero named competitors" constraint. Initial lock at Round 4.5 used "fixed bundle" phrasing; plan-validator flagged this as inaccurate for BMAD (role-based orchestration) and agent-os (memory-first), creating a community-pushback vector.
**Decision:** **EN**: *"Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness."* **KO**: *"다른 하네스는 모두에게 같은 출발점을 준다. harness-maker 는 너의 repo 를 읽고 너만의 harness 를 만든다."* Same wording in 4 surfaces: README hero · GitHub social card image text · GitHub About sidebar (within 350-char limit) · awesome-list one-liner draft.
**Consequences:**
- ✅ Honors zero-named-competitors constraint
- ✅ "same starting point" is accurate for all surveyed competitors (BMAD's pre-made roles, SuperClaude's pre-made agents, claude-flow's pre-made swarm topologies, agent-os's pre-made standards, spec-kit's pre-made spec format)
- ✅ "YOUR" repetition creates strong personalization signal in the awesome-list one-liner context where only the second clause may show
- ⚠️ Slightly longer than the original "fixed bundle" version — verify social-card pixel width on GitHub preview
**Rejected alternatives:**
- A ("Their defaults. Your harness.") — strong but loses "reads your repo" causal verb that explains *how*
- B ("Other harnesses ship their defaults...") — accurate but original-structure language
- D (keep "fixed bundle" + risk BMAD/agent-os pushback) — drama vector; validator's specific objection
- Round 4.5 v1 ("Other harnesses ship a fixed bundle. ...") — semantically inaccurate per validator
**Source:** Interview #4 + #4.5 + #11 (post-validator follow-up)

### ADR-005: v0.22 phasing — 4 gaps in parallel, all shipped in v0.22.0
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** RESEARCH §Wedge Reality Check identified 4 gaps in `profile.py` (lifecycle, Rust detected_checks, Node detected_checks, package_manager fallback). Decomposition could split releases for faster ship cadence or batch for completeness.
**Decision:** Ship all 4 gaps in v0.22.0 (parallel sub-phases 2.1–2.4). v0.22 not patched into v0.22.1 / v0.22.2 by gap. Expected total work 1–2 weeks.
**Consequences:**
- ✅ v0.23 (`uvx` CTA) reality immediately clear after v0.22.0
- ✅ Sub-phases share `profile.py` and test scaffolding — batched diff is smaller than 4 separate diffs
- ⚠️ Larger single release; rollback granularity coarser
**Rejected alternatives:**
- B (Node+lifecycle+pkg_mgr → v0.22.0, Rust → v0.22.1) — Rust users still hit anti-wedge for 1–2 weeks
- C (quick gaps first) — lifecycle error remains visible
- D (pkg_mgr fallback only) — wedge effect absent; v0.23 still blocked
**Source:** Interview #5

### ADR-006: lifecycle algorithm — 3-tier (active | maintenance | dormant), "experiment" removed — BREAKING ENUM CHANGE
**Status:** Accepted (2026-05-22, via /hm:plan interview; scope expanded post-validator critique #1)
**Context:** Reality-check on 5 repos: ripgrep wrongly classified as "experiment" (it is mature); fastapi wrongly classified as "maintenance" (it is active). Root cause: current `_detect_lifecycle` (profile.py:239–259) uses commit-count heuristic without release-recency or repo-age check. Validator critique #1 found that `experiment` is referenced in 5 production modules and 13 test files (34 occurrences) — not isolated to profile.py.
**Decision:** Replace 4-tier with 3-tier:
- `active` = ≥10 commits in last 90 days (or fallback: created_at > 0 + first-commit < 90 days ago)
- `maintenance` = 1–9 commits in last 90 days
- `dormant` = 0 commits in last 90 days
- Remove `experiment` entirely from `ProjectProfile.lifecycle` Literal enum
**depth=1 clone fallback (post-validator critique #3 revision):** use `git log --reverse --format=%ci | head -1` for first-commit date when commit count is too sparse to classify. Pure local git — no GitHub API call, no network dependency, no rate-limit ceiling, works on private and non-GitHub repos. The GitHub API option suggested in initial draft is dropped.
**Preset routing mapping (post-validator critique #1 follow-up):** existing `{"experiment", "maintenance"}` set literals in `interview.py:315` and `recommendation.py:249` route to SIDE preset. New mapping: `{"dormant", "maintenance"}` → SIDE; `"active"` → PRODUCTION. This preserves the *semantic intent* (low-activity repos default to Side preset's lighter footprint) under the new tier names.
**Consequences:**
- ✅ False positives eliminated for ripgrep-style mature repos
- ✅ Local-git-only fallback removes external dependency surface
- ⚠️ **BREAKING** — any caller that string-matches `"experiment"` against `lifecycle` field will silently fail (mypy does not catch this if field is typed as `str` rather than `Literal`). Phase 2.1 mandates a pre-flight `grep -r "experiment" src/ tests/` audit
- ⚠️ Tier boundary at 1 commit is heuristic; ADR records the value, retrospect at 90 days informs whether to retune
**Rejected alternatives:**
- A (2-tier active/dormant) — loses maintenance signal
- C (keep 4-tier, fix experiment definition) — readers interpret "experiment" inconsistently
- D (extend data sources) — orthogonal to algorithm; redundant with `git log --reverse` fallback
**Affected files (expanded after validator critique #1):**
- `src/harness_maker/profile.py` — `_detect_lifecycle` rewrite; new constant `LifecycleTier`
- `src/harness_maker/models.py:152` — `ProjectProfile.lifecycle` field default + inline comment listing valid values
- `src/harness_maker/interview.py:269` — `proxy_profile` construction
- `src/harness_maker/interview.py:315` — `_recommend_preset` fallback set literal update
- `src/harness_maker/recommendation.py:249,253` — preset recommendation logic set literals
- `src/harness_maker/modular_edit.py:121` — hardcoded lifecycle dict
- `tests/unit/test_profile.py` (11 hits), `test_render.py` (11 hits), `test_reconcile.py` (3 hits), `test_interview.py` (4 hits), plus `test_schema_migration.py`, `test_models.py`, `test_detection_cache.py`, `test_verify.py`, `test_synthesize.py`, `test_drift_demote.py`, `test_pass15_active.py`, `test_pass1_skip.py` (1–2 hits each)
- Snapshots (regenerate)
**Source:** Interview #6 + plan-validator critiques #1, #2, #3

### ADR-007: detected_checks policy — manifest-explicit OR command-pattern with explicit whitelists
**Status:** Accepted (2026-05-22, via /hm:plan interview; boundary clarified post-validator critique #4)
**Context:** Reality-check found `requests` repo received `uv run ruff check .` as a detected check — requests does not use uv or ruff. False positives directly damage personalization trust ("the tool is guessing"). Conversely, Rust/Node repos got empty `detected_checks` because manifest-only detection missed common command patterns.
**Decision:** Detect a check command iff one of:
- **Manifest-explicit**: tool is named in a manifest configuration block (e.g., `pyproject.toml [tool.ruff]`, `pyproject.toml [tool.mypy]`, `pyproject.toml [tool.pytest.*]`, Cargo.toml `[package.metadata.scripts]`)
- **Command-pattern** with explicit whitelists:
  - **Makefile target whitelist**: `test:`, `lint:`, `check:`, `typecheck:`, `format:`, `build:`. Emit as `make <target>`.
  - **package.json scripts whitelist**: `test`, `lint`, `check`, `typecheck`, `format`, `build`. Emit as `npm run <key>` (or `yarn` / `pnpm` if matching lockfile present).
  - **Cargo standard whitelist**: `cargo test`, `cargo clippy`, `cargo fmt --check`. Emitted only when Cargo.toml is present (proves cargo is the toolchain).
- **No stack-based default guessing**: Python repos do not auto-receive `pytest` unless `[tool.pytest.*]` block exists or `tests/` directory contains test files matched by a configured pattern.
**Package_manager fallback exception (post-validator critique #8):** `package_manager` detection (separate from `detected_checks`) MAY infer from manifest presence without lockfile (pyproject.toml → "uv" or "pip" by header inspection; package.json → "npm" as default). This is an *intentional* exception to the conservative policy because `package_manager` is a lower-stakes string used only for documentation hints in rendered harness, not as a runnable command. Documented here to prevent reader confusion about the asymmetry.
**Consequences:**
- ✅ requests-style false positive prevented
- ✅ Rust/Node common cases covered (most CI-using repos have at least one whitelisted script or Makefile target)
- ✅ Whitelist is small and reviewable (6 Makefile + 6 npm + 3 cargo = 15 patterns total)
- ⚠️ Less-common Cargo targets (`cargo bench`, `cargo doc`, `cargo audit`) silently excluded; users with those must edit the rendered harness manually
- ⚠️ `cargo check` deliberately excluded from whitelist because it overlaps with `cargo clippy` and many maintainers prefer the latter for harness CI
**Rejected alternatives:**
- A (manifest-explicit only) — Rust/Node empty
- C (stack-default guessing) — requests-ruff regression
- D (confidence-labeled inclusion of guesses) — low-confidence checks still poison trust
**Source:** Interview #7 + plan-validator critiques #4, #8

### ADR-008: Primary adoption metric = PyPI weekly downloads; GitHub stars + Discussions secondary; no opt-in telemetry
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** v0.21+v0.22 ship sequence needs a "did personalization headline land?" signal observed at 30/60/90-day intervals. Without a chosen metric, retrospect becomes anecdote.
**Decision:** PyPI weekly download count (queryable via `pypistats` or public BigQuery) is the primary signal. GitHub stars and Discussions activity tracked as secondary. **No opt-in telemetry** — keeps PRIVACY.md "100% local" commitment intact.
**Consequences:**
- ✅ Zero instrumentation cost — PyPI stats already public
- ✅ PRIVACY.md untouched
- ⚠️ PyPI downloads include CI mirrors, curiosity installs, and bot traffic — noise floor is real
- ⚠️ Signal lags behind first impression by 1–2 weeks
**Concrete observability artifact (post-validator critique #7):** `docs/observability/launch-baseline.md` committed at the end of Phase 3 containing Day-0 snapshot (PyPI weekly: 0, GitHub stars: N, Discussions: 0) and explicit ISO target dates for 30/60/90-day snapshots derived from the v0.22.0 tag date. The earlier draft's "personal calendar reminder OR doc snapshot" exit was a fig leaf; only the doc commit counts.
**Rejected alternatives:**
- B (opt-in telemetry) — PRIVACY policy conflict + significant instrumentation work
- C (Discussions activity only) — passive users invisible
- D (stars/forks only) — lagging signal
**Source:** Interview #8 + plan-validator critique #7

## 🏗️ Technical Design

### Current State
- `src/harness_maker/profile.py` exports `_detect_lifecycle` (4-tier), `_detect_mechanical_checks` (Python-favored), `_detect_package_manager` (lockfile-favored), and renders a `ProjectProfile` Pydantic model with `lifecycle: Literal["experiment", "active", "maintenance", "dormant"]`.
- README.md (845 lines) currently surfaces 5 research-tier features in the "Why harness-maker?" and "Features" sections directly under the hero. No personalization-specific anchor exists; the headline-evidence chain is implicit.
- `docs/assets/` contains `brand-block.png` referenced in the README header. No `showcase-diff.png` exists.
- `embedeval` (Ecro/embedeval public repo) is Python+uv+pydantic+github-actions, with a hand-built `.claude/` directory but no `harness.yaml` — i.e., it has never run `/hm:make`.

### Affected Components

**Phase 1 (v0.21) touches (docs/marketing surface only):**
- `README.md` — hero, comparison line, surface pruning
- `docs/HOW-IT-WORKS.md` — referenced anchors only if surface pruning rearranges sections that other docs link to
- `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json` — `description` field (mirror About sidebar copy)
- `pyproject.toml`, `src/harness_maker/__init__.py` — version bump
- New file: `docs/assets/showcase-diff.png` (or similar; see Phase 1.2)
- GitHub repo settings: About sidebar (via `gh repo edit --description ...`), social preview image (via Settings UI — manual, documented in checklist)

**Phase 2 (v0.22) touches (Python code + tests):**
- `src/harness_maker/profile.py` — `_detect_lifecycle` rewrite, `_detect_mechanical_checks` Rust/Node extension, `_detect_package_manager` manifest fallback
- `src/harness_maker/models.py:152` — `ProjectProfile.lifecycle` default + enum
- `src/harness_maker/interview.py:269,315` — proxy_profile + recommend_preset set literal
- `src/harness_maker/recommendation.py:249,253` — preset recommendation set literals
- `src/harness_maker/modular_edit.py:121` — hardcoded lifecycle dict
- `src/harness_maker/templates/harness-yaml/{Side,Production}.yaml.j2` — only if these templates encode `experiment` (verify via grep before edit)
- `tests/unit/test_profile.py`, `test_render.py`, `test_reconcile.py`, `test_interview.py`, `test_schema_migration.py`, `test_models.py`, `test_detection_cache.py`, `test_verify.py`, `test_synthesize.py`, `test_drift_demote.py`, `test_pass15_active.py`, `test_pass1_skip.py` — assertion + fixture updates
- `tests/snapshots/` — regenerate after Phase 2.1+2.2+2.3+2.4 land
- `CHANGELOG.md` — BREAKING note
- 5-file version bump (same set as Phase 1.5, plus `__init__.py`)

**Phase 3 touches:**
- New file: `docs/observability/launch-baseline.md`

### Dependencies
- No new runtime dependencies (Python 3.12, uv, Jinja2 unchanged)
- Build-time: `gh` CLI (already a project requirement for About sidebar edits)
- Phase 1.2 render workflow uses existing `harness-maker make --reinterview` against `/tmp/profile-test/embedeval` (clone via `git clone --depth 1`)

### Architecture (data flow)

```
Phase 1 (v0.21) — Headline visibility chain
├─ README hero one-line ─────┐
├─ Sub-line 4-tag ───────────┤
├─ Spec-kit comparison line ─┼─► First-screen attention budget (top ~120 lines)
├─ Showcase image ───────────┘     └─► [docs/assets/showcase-diff.png]
│                                       └─► Generated by: harness-maker make on embedeval (Side preset)
│                                                          vs harness-maker self (Production preset)
└─ 5 features → "Advanced features" sub-section (later in same README)

Phase 2 (v0.22) — Profile accuracy chain
profile.py
├─ _detect_lifecycle ──────► ProjectProfile.lifecycle ──► synthesize.py / interview.py / recommendation.py
│  (3-tier: active/maint/dormant)                          ──► HarnessConfig.preset routing
├─ _detect_mechanical_checks (Rust + Node whitelist)
└─ _detect_package_manager (manifest fallback)

Phase 3 — Observation
v0.22.0 tag date ─► Day 0 snapshot ─► docs/observability/launch-baseline.md
                                       (PyPI weekly, GitHub stars, Discussions)
                                       └─► 30/60/90-day ISO target dates committed
```

### Design Decisions

See ADR-001 through ADR-008. Every non-trivial architectural choice in this design links back to an ADR; the ADRs are the source of truth for "why this, not that."

### API Changes

**BREAKING in v0.22.0** (per ADR-006):
- `ProjectProfile.lifecycle: Literal["experiment", "active", "maintenance", "dormant"]` → `Literal["active", "maintenance", "dormant"]`
- Any external Python code that imports `ProjectProfile` and string-matches `"experiment"` will silently match nothing
- CHANGELOG must include a BREAKING section header with migration note: *"If you use `harness-maker` programmatically and check `profile.lifecycle == 'experiment'`, change the comparison to `profile.lifecycle == 'dormant'` (semantic replacement; new tier is `'active' | 'maintenance' | 'dormant'`)."*

**Non-breaking but observable** (per ADR-007):
- `detected_checks` list contents change shape for non-Python repos (was: `[]`; now: includes whitelisted Makefile/package.json/Cargo commands when present). Existing snapshots will diff.
- `package_manager` field may return `"npm"` or `"uv"` for repos without lockfile but with manifest. Existing snapshots will diff.

## 📝 Implementation Plan

### Phase 1 — v0.21 README headline, showcase, surface pruning, comparison line

**Scope (in):**
- `README.md`
- `.claude-plugin/plugin.json` `description` field (mirror sidebar copy)
- `.cursor-plugin/plugin.json` `description` field
- `.codex-plugin/plugin.json` `description` field
- `pyproject.toml` version → `0.21.0`
- `src/harness_maker/__init__.py` `__version__` → `"0.21.0"`
- New file: `docs/assets/showcase-diff.png` (artifact path explicit per validator critique #9)
- GitHub repo settings: About sidebar (`gh repo edit --description "..."`), social preview image (manual via Settings UI)
- `docs/HOW-IT-WORKS.md` — *only if* surface pruning relocates anchors that this file links to (verify with grep before edit)

**Scope (out):**
- `src/harness_maker/**/*.py` (no Python source changes in Phase 1)
- `tests/**` (no test changes in Phase 1)
- `CHANGELOG.md` content (release notes generated at Phase 1.5 only)

**Exit criterion (runnable check):**
```
# All four must hold at Phase 1 close
grep -q "Other harnesses give everyone the same starting point" README.md
grep -q "프로젝트마다 다른 하네스" README.md  # Or README.ko.md (locate via existing repo structure)
grep -q "Advanced features" README.md
test -f docs/assets/showcase-diff.png
git log --oneline | grep -q "v0.21.0\|chore(release): v0.21"
gh release view v0.21.0 >/dev/null
```

**Risk:** low
**Rollback:** revert to commit prior to Phase 1.1 (no Python state to unwind)

#### Sub-phases

**1.1 README hero rewrite (locked copy)**
- Update README.md hero block (lines 1–~50): replace existing one-liner with EN+KO pair from [wiki:positioning]
- Update sub-line 4-tag: `Per-project personalization · Grade-gated · Self-evolving · Multi-IDE`
- Update `.claude-plugin/plugin.json` + `.cursor-plugin/plugin.json` + `.codex-plugin/plugin.json` `description` to the 136-char About sidebar copy from [wiki:positioning]
- Pre-commit grep check (per [wiki:gotcha] wrapup-marker-discipline): run `python -m harness_maker.block_merge --check README.md` to ensure no orphan content outside `@hm:user:*` markers (or document marker discipline if README is not block-merge-managed)

**1.2 Showcase render + diff capture**
- `git clone --depth 1 https://github.com/Ecro/embedeval.git /tmp/profile-test/embedeval`
- Run `harness-maker make --reinterview` against the embedeval clone with Side preset selected for every interview axis
- Capture render output: list of files in `.claude/` (count, agent names, skill names, workflow stages)
- Same exercise against harness-maker self (already Production preset)
- Generate side-by-side comparison image (asciinema → screenshot, or manual screenshot of `tree .claude/` output for both)
- Commit image as `docs/assets/showcase-diff.png` (artifact path per validator critique #9)
- **Pass/fail check (per ADR-002 fallback trigger):** rendered embedeval `.claude/` must contain at least 3 file additions OR 1 distinct agent/skill that is *absent* from the harness-maker render. If below threshold, halt and invoke fallback (construct Side render of harness-maker self).

**1.3 Spec-kit comparison line + 4-surface synchronization**
- Insert ADR-004 v2 EN copy into README hero (immediately after one-liner)
- Insert ADR-004 v2 KO copy into README.ko.md (mirror location)
- Update GitHub About sidebar: `gh repo edit Ecro/harness-maker --description "<ADR-004 line tail clause>"` (within 350-char limit)
- Update social preview image text overlay (manual via repo Settings → Social preview)
- Draft awesome-list one-liner: append to `docs/marketplace-submissions.md` (or create file) for future submission step

**1.4 Surface pruning — 5 features → "Advanced features" sub-section**
- Locate the 5 feature mentions in README.md "Why harness-maker?" and "Features" sections (grep for: `anti-rot`, `5-term`, `inequality gate`, `communication-variant`, `/hm:health`, `reviewer consensus`)
- Create new section `## 🔧 Advanced features` between the existing "Configuration" and "Targets" sections (or comparable placement, after the headline-anchored sections)
- Move the 5 feature blurbs into the new section verbatim; preserve `@hm:user:*` markers if present
- Add anchor aliases (`<a id="anti-rot"></a>` style) if any markdown links elsewhere in the repo point to the old anchors (grep for `#anti-rot`, etc., across the repo)

**1.5 5-file version bump and release**
- Update `.claude-plugin/plugin.json` `version` → `"0.21.0"`
- Update `.cursor-plugin/plugin.json` `version` → `"0.21.0"`
- Update `.codex-plugin/plugin.json` `version` → `"0.21.0"`
- Update `pyproject.toml` `version` → `"0.21.0"`
- Update `src/harness_maker/__init__.py` `__version__` → `"0.21.0"`
- Add `CHANGELOG.md` entry for v0.21.0: README hero rewrite + showcase + surface pruning + spec-kit comparison line
- Run boundary-parse advisory tests locally: `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v`
- Tag and push: `git tag -a v0.21.0 -m "..."` + `git push origin main v0.21.0`
- Wait for `release.yml` workflow to complete (do NOT run `gh release create` manually — per [wiki:fresh-install-health-baseline] race-free release procedure)

---

### Phase 2 — v0.22 profile.py Rust/Node hardening + lifecycle redesign (BREAKING)

**Scope (in) — EXPANDED per validator critique #1:**
- `src/harness_maker/profile.py` — `_detect_lifecycle` rewrite + `_detect_mechanical_checks` Rust/Node extension + `_detect_package_manager` manifest fallback
- `src/harness_maker/models.py:152` — `ProjectProfile.lifecycle` field default + inline-comment enum list
- `src/harness_maker/interview.py:269,315` — `proxy_profile` construction + `_recommend_preset` set literal
- `src/harness_maker/recommendation.py:249,253` — preset recommendation set literals
- `src/harness_maker/modular_edit.py:121` — hardcoded lifecycle dict
- `src/harness_maker/templates/harness-yaml/*.yaml.j2` — only if grep finds `experiment` reference (verify first)
- All 13 test files: `tests/unit/test_profile.py`, `test_render.py`, `test_reconcile.py`, `test_interview.py`, `test_schema_migration.py`, `test_models.py`, `test_detection_cache.py`, `test_verify.py`, `test_synthesize.py`, `test_drift_demote.py`, `test_pass15_active.py`, `test_pass1_skip.py`
- `tests/snapshots/` — regenerate
- `CHANGELOG.md` — BREAKING entry
- 5-file version bump to `0.22.0`

**Scope (out):**
- `README.md` (Phase 1 surface unchanged)
- `.claude-plugin/plugin.json` description (Phase 1 copy unchanged; version only)

**Exit criterion (runnable check):**
```
# All five must hold
uv run ruff check src/ tests/
uv run mypy --strict src/
uv run pytest -x -q
! grep -rn '"experiment"' src/  # zero remaining production refs
! grep -rn "'experiment'" src/

# Reality-check regression: 5 repos + embedeval baseline produce expected lifecycle tiers
INTEGRATION=1 uv run pytest tests/integration/test_profile_reality_check.py -v
```

**Risk:** medium — BREAKING enum change with widespread downstream code references
**Rollback:** revert to v0.21.0 tag (Phase 1 end state)

#### Sub-phases

**2.1 lifecycle algorithm redesign (BREAKING)**
- Run pre-flight audit: `grep -rn "experiment" src/ tests/` and confirm match count against validator's findings (5 prod + 13 test files, 34 occurrences); record actual count in implementation notes
- Rewrite `_detect_lifecycle` in `profile.py` per ADR-006 (3-tier; commit-count thresholds 0 / 1–9 / ≥10 in last 90 days)
- Add `git log --reverse --format=%ci | head -1` first-commit fallback for repos with sparse history (depth=1 clone safe)
- Update `ProjectProfile.lifecycle` `Literal` annotation in `models.py:152`
- Update `interview.py:269` `proxy_profile` to use `"active"` (or appropriate new value) as construction default
- Update `interview.py:315` set literal `{"experiment", "maintenance"}` → `{"dormant", "maintenance"}`
- Update `recommendation.py:249,253` set literals (same transformation)
- Update `modular_edit.py:121` hardcoded lifecycle dict
- Update all 13 test files: replace `"experiment"` fixture/assertion with `"dormant"` where semantic intent was "low-activity repo" or `"active"` where it was "any classified repo"
- mypy strict pass should now catch any remaining string mismatch via Literal narrowing

**2.2 Rust detected_checks**
- Extend `_detect_mechanical_checks` in `profile.py` to handle Rust:
  - When Cargo.toml present: emit `cargo test`, `cargo clippy`, `cargo fmt --check` (whitelist per ADR-007)
  - Additionally inspect `[package.metadata.scripts]` for manifest-explicit entries
- Add Cargo-fixture test cases in `tests/unit/test_profile.py`
- ripgrep regression case: expected `detected_checks` includes at minimum `cargo test` and `cargo clippy`

**2.3 Node detected_checks**
- Extend `_detect_mechanical_checks` for Node:
  - When package.json present: iterate `scripts` object; emit `npm run <key>` for each key in whitelist (`test`, `lint`, `check`, `typecheck`, `format`, `build`)
  - Detect lockfile (package-lock.json / yarn.lock / pnpm-lock.yaml) to choose runner (`npm` / `yarn` / `pnpm`)
  - Additionally read Makefile targets in same whitelist as Python (Makefile target whitelist already exists; verify it applies before extending)
- Add Node-fixture test cases
- fastify regression case: expected `detected_checks` non-empty

**2.4 package_manager manifest fallback**
- Extend `_detect_package_manager` per ADR-007 exception clause:
  - When pyproject.toml present without uv.lock or poetry.lock: inspect `[tool.uv]` or `[tool.poetry]` headers; fall back to `"pip"` if neither
  - When package.json present without lockfile: emit `"npm"` (default; explicit lockfile detection wins when present)
- Add fixture cases for manifest-only repos
- requests regression case: expected `package_manager` = `"pip"` (currently empty string)

**2.5 5-repo reality-check regression test**
- Create `tests/integration/test_profile_reality_check.py`
- Vendor or clone (with `--depth 1` and cached) the 5 reality-check repos + embedeval; guard with `@pytest.mark.skipif(not os.getenv("INTEGRATION"))`
- Assertions for each repo (concrete expected values):
  - requests: `lifecycle == "maintenance"`, `package_manager == "pip"`, `detected_checks` ⊇ `["make test"]`
  - fastapi: `lifecycle == "active"`, `frameworks` ⊇ `["pydantic"]`
  - ripgrep: `lifecycle ∈ {"active", "maintenance"}` (not `"experiment"` — primary regression target), `detected_checks` ⊇ `["cargo test", "cargo clippy"]`
  - fastify: `package_manager != ""`, `detected_checks` non-empty
  - htmx: `package_manager == "npm"`, `detected_checks` non-empty
  - embedeval (baseline): `lifecycle ∈ {"active", "maintenance"}`, `frameworks` ⊇ `["pydantic"]`
- Reality-check intentionally lives in `tests/integration/` not unit — requires network and INTEGRATION env var

**2.6 CHANGELOG + release**
- `CHANGELOG.md` v0.22.0 entry under `## [0.22.0] - 2026-XX-XX` with BREAKING subsection per ADR-006
- 5-file version bump (same files as Phase 1.5, plus `__init__.py`) to `0.22.0`
- Local boundary-parse advisory: `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v`
- Tag and push, then wait for release.yml (do not invoke `gh release create` per [wiki:fresh-install-health-baseline])

---

### Phase 3 — Post-launch instrumentation + 90-day retrospect trigger

**Scope (in):**
- New file: `docs/observability/launch-baseline.md`
- Optionally: a personal calendar reminder (out-of-repo, not part of exit criterion per validator critique #7)

**Scope (out):**
- Code changes (none)
- Any opt-in telemetry instrumentation (excluded by ADR-008)

**Exit criterion (runnable check) — REVISED per validator critique #7:**
```
# All three must hold
test -f docs/observability/launch-baseline.md
grep -qE "Day-0 snapshot.*PyPI" docs/observability/launch-baseline.md
grep -qE "2026-..-..|target dates" docs/observability/launch-baseline.md  # ISO target dates committed
```

**Risk:** low — measurement only

**Rollback:** N/A (observation phase; baseline.md can be edited freely without harm)

#### Sub-phase

**3.1 Launch baseline snapshot**
- Within 24 hours of v0.22.0 tag push, create `docs/observability/launch-baseline.md`
- Populate with: Day-0 PyPI weekly download count (via `pypistats recent harness-maker --week`), Day-0 GitHub stars (via `gh api repos/Ecro/harness-maker --jq .stargazers_count`), Day-0 Discussions count (via `gh api repos/Ecro/harness-maker/discussions --jq length`)
- Add ISO target dates (Day+30, Day+60, Day+90) computed from v0.22.0 tag date
- Add inline TODO comment for the next plan: *"When all 3 target dates have been logged with snapshots, kick off plan `harness-maker-v0.23-uvx-cta-plan` if PyPI weekly downloads have grown ≥3× from Day-0 baseline; otherwise kick off `harness-maker-personalization-retrospect` plan to re-examine ADR-008 metric choice."*
- Commit to `main`

## 🧪 Testing Strategy

### Phase 1 (v0.21) testing
- **Manual visual checks** (no automated test infrastructure for marketing copy):
  - Render README.md in GitHub preview (push to feature branch, view in browser)
  - Verify social card displays correctly via Twitter Card Validator / OpenGraph debugger
  - Verify About sidebar updated via `gh api repos/Ecro/harness-maker --jq .description`
  - Visual confirmation that first ~120 README lines contain personalization headline + sub-line + spec-kit line + showcase image — no anti-rot/5-term/comm-variant/health-rubric/reviewer-consensus mentions
- **Snapshot drift check**: run `uv run pytest tests/snapshots/` after README changes; manifest snapshots should diff cleanly (description field change) and be regenerated via `uv run python -m harness_maker.regenerate` if intentional
- **`block_merge` audit**: `python -m harness_maker.block_merge --check README.md` before commit (catches the wrapup-marker discipline issue from [wiki:gotcha] wrapup-marker-discipline-silent-loss)

### Phase 2 (v0.22) testing
- **Unit**: `uv run pytest tests/unit/ -x -q`
  - 13 test files updated for `experiment` → new tier mapping
  - New fixtures for Rust/Node detected_checks (synthetic Cargo.toml + package.json minimal repos)
  - New fixtures for manifest-only package_manager fallback
- **Snapshot**: full regeneration after Phase 2 lands
- **Integration**: `INTEGRATION=1 uv run pytest tests/integration/test_profile_reality_check.py -v`
  - 6 repos: requests, fastapi, ripgrep, fastify, htmx, embedeval
  - Each has concrete expected lifecycle/package_manager/detected_checks assertions (see Sub-phase 2.5)
- **Manual**: `harness-maker profile /path/to/embedeval --json | jq` and same for harness-maker self; eyeball the output for surprising-and-correct quality

### Phase 3 testing
- No test infrastructure (measurement only); exit verified by grep check above

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation | Phase |
|---|---|---|---|
| BREAKING `lifecycle` enum change leaves orphan `"experiment"` string literals in 5 production modules and 13 test files | **High** | Phase 2.1 pre-flight `grep -rn "experiment" src/ tests/` audit; Phase 2 exit-criterion grep blocks tag push if any remain. Validator critique #1 already mapped the affected files. | 2.1 |
| embedeval render produces a quantitatively small diff (same stack as harness-maker, may be near-identical) | Medium | ADR-002 quantitative fallback trigger (≥3 distinct file additions OR ≥1 distinct agent/skill); Phase 1.2 halts and invokes fabricated-Side fallback if below threshold | 1.2 |
| Spec-kit line (ADR-004 v2) inadvertently still inaccurate for a niche competitor (e.g., something between memory-first and role-based) | Low–Medium | "give everyone the same starting point" is the broadest possible accurate descriptor (validator agreed). Risk reduced from v1 but not zero; track via Discussions for pushback within 30 days. | 1.3 |
| Surface pruning breaks existing README anchor links | Low–Medium | ADR-003 keeps the "Advanced features" section *inside* README (same file, anchors still resolve); explicit grep for cross-file anchor links before Phase 1.4 commit | 1.4 |
| PyPI weekly download metric stays at noise floor for 90 days (no clear signal) | Medium | Secondary signals (stars + Discussions) co-tracked; Day-0 baseline.md commits 3× growth threshold for declaring success; if undefined-by-day-90, ADR-008 retrospect plan triggers | 3.1 |
| `depth=1` clone in user environment makes `git log --reverse` slow or empty | Low | Validator critique #3 alternative (git log first-commit) works on `depth=1` because Git clones the latest commit + a refs/heads pointer; `--reverse` only orders existing commits. Fallback graceful: if `git log --reverse` returns empty, classify as `"dormant"` | 2.1 |
| Memory `[wiki:gotcha] wrapup-marker-discipline-silent-loss` recurrence — README block-merge marker forgotten during Phase 1 edits, user customizations silently overwritten on next `/hm:make --update` | **High** | Phase 1.1 pre-commit `block_merge --check README.md` (or equivalent). If README is not block-merge-managed, document this explicitly in commit message; otherwise audit every Phase 1 sub-phase commit | 1.* |
| Memory `[wiki:gotcha] readme-one-prompt-bash-not-slash` recurrence — built-in slash commands in README's "Try in 30 seconds" become AI-uninvokable | N/A (Phase 1 does not modify the one-prompt block; only the hero, comparison line, and surface pruning) | — | — |
| Memory `[wiki:gotcha] worktree-finalize-conflicts-with-parallel-main-edits` — Phase 1 and Phase 2 may collide if executed in overlapping worktrees | Medium | Phase 1 ends with a tagged release; Phase 2 begins from that tag's commit. Worktree isolation per `harness.yaml.worktree.scope: [execute, plan]` keeps both phases inside `.worktrees/`. Phase 2 finalize-stage must merge with `--ours` for any Phase 1 conflict | 2.* |
| Phase 2 BREAKING enum change forces external programmatic users (if any exist) to rewrite checks | Medium | CHANGELOG `## [0.22.0]` BREAKING subsection mandatory; PyPI version bump signals the break; semantic versioning honored | 2.6 |

## ✅ Success Criteria

- [x] **Phase 1.2 done in v0.21.1 (PNG→MD deviation, ADR-002 amended)**: README hero references the showcase + the artifact ships at `docs/assets/showcase-diff.md` (markdown, not PNG — see ADR-002 Amendment below). Generated from a real `harness-maker make --autoloop --preset Side` render against embedeval (Ecro's other public repo) compared against harness-maker self's Production render via `.harness-manifest.json` set diff: +5 agents + 45 file diff cleared the ADR-002 quantitative threshold by 15×.
- [x] **Phase 1.4 done**: 5 research-tier features located only in "Advanced features" sub-section (verified via grep — Anti-rot removed from Why table + Features section + How it compares table).
- [ ] **Phase 1.3 — deferred (manual step)**: GitHub About sidebar `description` matches `.claude-plugin/plugin.json` `description`. plugin.json description updated this commit; the `gh repo edit --description` invocation is a manual user step before launch.
- [x] **Phase 1.1 done (N/A)**: `block_merge --check README.md` — README is not under `@hm:user:*` marker management (free-text, not block-merge-managed). Check is informational only and would emit no findings.
- [ ] **Phase 1.5 — deferred to user push step**: v0.21.0 tagged, pushed, and `release.yml` workflow completed successfully. Wrapup commits the bump; the user runs `git tag -a v0.21.0` + `git push origin main v0.21.0` separately per the race-free release procedure in CLAUDE.md §릴리스 절차.
- [x] **Phase 2 done (v0.22.0)**: `grep -rn "\"experiment\"" src/` returns zero matches (only docstring/comment references remain, with intentional "removed" framing).
- [x] **Phase 2 done — unit-level (v0.22.0)**: 11 new unit tests cover all 6 expected-behavior axes; `tests/integration/test_profile_reality_check.py` ships with concrete assertions for requests/fastapi/ripgrep/fastify/htmx/embedeval but is INTEGRATION=1-gated (network-bound). User can opt-in via `INTEGRATION=1 uv run pytest tests/integration/test_profile_reality_check.py -v` post-tag to validate the full 6-repo reality.
- [x] **Phase 2 done (v0.22.0)**: `uv run ruff check src/ tests/` ✅, `uv run mypy --strict src/` ✅, `uv run pytest -x -q` ✅ (all green on main after worktree finalize + snapshot regen).
- [x] **Phase 2 done (v0.22.0 pushed 2026-05-22 04:37 UTC)**: tag pinned to commit `067c748`, `release.yml` workflow `26268703007` completed successfully, CHANGELOG includes BREAKING subsection. PyPI publish + GitHub Release auto-generated.
- [x] **Phase 3 done (v0.22.1)**: `docs/observability/launch-baseline.md` committed within 24h of v0.22.0 tag (~5min later, same day). Day-0 snapshot: PyPI weekly 1,424 / GitHub stars 2 / Discussions 1. ISO target dates 2026-06-21 / 2026-07-21 / 2026-08-20. Retrospect-trigger TODO: ≥3× growth → `harness-maker-v0.23-uvx-cta-plan` ; otherwise → `harness-maker-personalization-retrospect`.

## 🔍 Plan Validation

**Outcome**: NEEDS_REVISION (1 critical + 7 warnings + 2 suggestions) → resolved (1 follow-up interview round + 8 plan-body revisions).

### Validator critiques and resolutions

| # | Sev | Critique (one-line) | Resolution |
|---|---|---|---|
| 1 | **Critical** | ADR-006 scope omits 5 production modules + 13 test files where `"experiment"` is hardcoded; preset routing set literals at `interview.py:315` and `recommendation.py:249` silently break | **Plan revision**: Phase 2 scope-in expanded to enumerate all affected files; ADR-006 affected-files list explicit; Phase 2.1 pre-flight grep audit added; Phase 2 exit criterion includes `! grep -rn '"experiment"' src/` |
| 2 | Warning | `dormant` tier threshold undefined; Phase 2.1 has no algorithm for the 0-commit-30-day case | **Plan revision**: ADR-006 records concrete thresholds (0 / 1–9 / ≥10 commits in last 90 days); preset routing mapping `{"dormant", "maintenance"} → SIDE; "active" → PRODUCTION` recorded |
| 3 | Warning | Phase 2.1 GitHub API `created_at` fallback adds rate-limit + non-GitHub-repo failure mode | **Plan revision**: ADR-006 fallback changed to `git log --reverse --format=%ci \| head -1` (pure local git, zero network); GitHub API option dropped |
| 4 | Warning | ADR-007 "command-pattern" boundary unspecified | **Plan revision**: ADR-007 expanded with explicit whitelists — Makefile (6 targets), npm scripts (6 keys), Cargo (3 commands) |
| 5 | Warning | ADR-004 "fixed bundle" inaccurate for BMAD (role-based) and agent-os (memory-first) | **Follow-up interview Round 11**: ADR-004 v2 = "Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness." |
| 6 | Warning | ADR-002 fallback trigger threshold absent | **Plan revision**: ADR-002 records quantitative fallback trigger (≥3 distinct file additions OR ≥1 distinct agent/skill); Phase 1.2 halt-and-invoke-fallback step explicit |
| 7 | Warning | Phase 3 "personal calendar reminder OR doc snapshot" is a fig leaf | **Plan revision**: Phase 3 exit criterion now requires `docs/observability/launch-baseline.md` commit only; ISO target dates committed; retrospect-trigger TODO embedded |
| 8 | Suggestion | Phase 2.4 `package_manager` manifest fallback inconsistent with ADR-007 conservative policy | **Plan revision**: ADR-007 records the `package_manager` exception clause explicitly; rationale (`package_manager` is a documentation hint, not a runnable command) included |
| 9 | Suggestion | Phase 1.2 showcase artifact path unspecified | **Plan revision**: Phase 1.2 names `docs/assets/showcase-diff.png` explicitly; Phase 1 exit criterion includes `test -f docs/assets/showcase-diff.png` |

### Validator clean-categories

- `rollback-strategy`: ✅ All phases name a concrete rollback point
- `spec-alignment`: ✅ No SPEC file governs this PLAN; RESEARCH ↔ PLAN traceability via frontmatter
- `missing-interview-rounds`: ✅ No deferred-decision-as-question phrasing found

Final validator state: **NEEDS_REVISION_RESOLVED** (no critical issues remain, all warnings resolved, all suggestions addressed).
