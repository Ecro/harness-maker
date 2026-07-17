---
type: plan
task_slug: personalization-depth-2026-05
status: planning
created: 2026-05-16
tags: [harness-maker, plan, python, personalization, detection, foreign-config-import, adaptive, telemetry]
research_doc: "[[RESEARCH-personalization-depth-2026-05]]"
interview_rounds: 5
adrs: 11
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Track A+D+B-start: deepen Detect→Recommend pipeline, foreign-AI-config single-source import, opt-out adaptive telemetry, /hm:personalization-audit"
---

# PLAN — Personalization Depth (Tracks A + D + B-start)

## 🎯 Executive Summary

**What:** Implement RESEARCH-personalization-depth-2026-05 as 12 phases. Three tracks land together:

- **Track A (Detection Depth)** — Sub-tracks A1 (stack/framework granularity, 12+ stacks + framework-level), A6 (wrapup-doc auto-detect), A7 (MCP suggestion engine). NO LLM in Track A.
- **Track D (Foreign AI Config Migration)** — Sub-tracks D1 (detect 6 known foreign configs), D2 (LLM-driven mapping), D3 (confirm UI + single-source re-generation with `@hm:harness:*` inverted block markers). One LLM call site (D2 only).
- **Track B start (Adaptive Self-Tuning)** — Sub-tracks B1 (override telemetry, default-on opt-out), B4 (`/hm:personalization-audit` command, separate command but reuses `rubric_loader.py` + `ImprovementPlan`/`ActionItem` from `ai_readiness.py`), B5 (SessionStart drift surface after 30 sessions or 14 days).

Plus shared infrastructure: confidence-bucketed recommendation framework (per-detection heuristic confidence — explicit manifest match → high, inferred → medium, guess → low), detection cache (`~/.cache/harness-maker/profile-<hash>.json`, manifest-mtime invalidation + 24h ceiling), recommendation interface (`recommend_<axis>(profile) -> Recommendation`).

**Why:** RESEARCH-personalization-depth-2026-05 §Step 1 인벤토리 결과 — 21개 personalization axis 중 4개만 detection → recommendation 으로 흐른다 (변환률 ~25%). 새 axis 추가 (Track C) 보다 기존 axis 의 detect→recommend 파이프라인 깊이 늘리는 것이 ROI 우선. 동시에 foreign-AI-config 사용자 (Cursor/Continue/Aider/Copilot/Codex 기존 사용자) 가 brownfield default 라는 시장 가정 인정 — Track D 가 이 onboarding 마찰 해소.

**Key Decisions** (10 ADR):
- ADR-001: Track A + D + B-start 동시 land (not Track-by-Track)
- ADR-002: Balanced sub-track set (A1+A6+A7 + D1+D2+D3 + B1+B4+B5, 한 LLM call site)
- ADR-003: Foreign config import = single source 강제 (재생성 + block-marker 보존)
- ADR-004: Recommendation UI = confidence-bucketed (high silent + comment / medium explicit / low no-recommend)
- ADR-005: Adaptive telemetry = default-on, opt-out, read-only suggestion-only
- ADR-006: `/hm:personalization-audit` 별도 명령 + rubric framework 공유 (`rubric_loader.py`, `ImprovementPlan`, `ActionItem`)
- ADR-007: Confidence = per-detection heuristic (explicit/inferred/guess)
- ADR-008: Detection cache = manifest-mtime + 24h ceiling
- ADR-009: Block-marker = `@hm:harness:*` inverted (우리 영역만 mark, 사용자 영역 outside)
- ADR-010: 3 failure modes (false-positive detection / foreign config 손상 / adaptive noise) 모두 동등 — dogfood + 1 external project test (=`github/spec-kit` per amendment) 가 공통 안전망
- ADR-011: `/hm:personalization-audit` rubric tier semantics — composite-score [0,100] = L1 conversion×40% + L2 stability×30% + L3 cadence×30%; Bronze<40 / Silver 40-65 / Gold 65-85 / Platinum>85; per-ActionItem evidence schema = `{n_observations, top_3_signals, confidence}`

**Estimated impact:** Medium-high. 12 phases. Touches `models.py` (ProjectProfile schema 5 new fields), `profile.py` (STACK_MANIFESTS 5→12+, framework dep parse), `interview.py` (recommendation flow rewire), `block_merge.py` (new `@hm:harness:*` marker family), telemetry pipeline (1 new event type), 4 new modules (`recommendation.py`, `detection_cache.py`, `foreign_config.py`, `personalization_audit.py`), 1 new rubric YAML (`rubrics/personalization.yaml`), 1 new command template (`templates/commands/hm/personalization-audit.md.j2`), 1 SessionStart hook extension. No new Python runtime dependency.

## 📚 Prior Work

- **`work-docs/RESEARCH-personalization-depth-2026-05.md`** — 본 PLAN 의 research_doc. 4-track 구조, 21-축 인벤토리, detection→recommend 변환률 25% 진단, 10개 open question.
- **`work-docs/RESEARCH-harness-gap-cot-2026-05.md`** — Reliability Stack 7 features. 본 PLAN 의 Track B (adaptive) 와 인접 — telemetry/observability infrastructure 공유 가능.
- **`work-docs/RESEARCH-harness-trends-2026-05.md`** — harness synthesis (AutoHarness, MCE) 의 상위 형태가 본 PLAN 의 Track B; meta-evolution 은 본 PLAN scope 밖.
- **`work-docs/PLAN-user-workflow-opportunities-2026-05.md`** — Second Brain R/W 7 phase 완료. 본 PLAN 의 detection→recommendation pattern 모델 — `vault_member` 가 정상 작동하는 단일 사례.
- **`work-docs/PLAN-make-ux-gaps-2026-05.md`** — `HarnessConfig` 확장 + YAML round trip + interview 통합 안전 패턴 (본 PLAN Phase 1/3 동일 패턴 재사용).
- **`src/harness_maker/profile.py`** — 5-manifest STACK detection. 본 PLAN Phase 3 가 직접 확장.
- **`src/harness_maker/ai_readiness.py`** + **`rubric_loader.py`** — 3-layer composite + `ImprovementPlan`/`ActionItem`. 본 PLAN Phase 10 이 reuse.
- **`src/harness_maker/telemetry.py`** + **`review_telemetry.py`** — 기존 hook event pipeline + `ReviewTelemetryRecord`. 본 PLAN Phase 9 가 새 event type (`harness_yaml_override`) 추가.
- **`src/harness_maker/second_brain.py`** — typed config + filesystem backend pattern. Phase 1 의 `Recommendation` dataclass 가 동일 pydantic 패턴.
- **`src/harness_maker/block_merge.py`** — 기존 `@hm:user:*` block marker. Phase 7 가 inverted `@hm:harness:*` family 추가.
- **CLAUDE.md §체크리스트 #2** — 외부 소비자 파서 정합성 (Cursor `.mdc` schema 검증). Phase 7 의 foreign config 재생성에 직접 적용.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|-------|----------|----------|--------|------|-------|
| 1 | R1 | Track scope | Scope | Which tracks land in first release? | C: A + D + B-start | RESEARCH 권장 1+2+B-minimal. Tracks B-extra/C deferred to follow-up PLAN | ADR-001 |
| 2 | R2 | Sub-track set | Scope | Which sub-tracks within A+D+B-start? | A: Balanced (A1+A6+A7 + D1+D2+D3 + B1+B4+B5) | One LLM site only (D2). A2 collapsed into D1 (same op) | ADR-002 |
| 3 | R2 | Foreign config import | Architecture | After import, what happens to external file? | A: Single source — we re-generate, block-marker preserves user edits | RESEARCH Pitfall #7 resolution. Single source of truth | ADR-003 |
| 4 | R2 | Recommendation UI | Architecture | How surface non-default recommendations during /hm:configure? | A: Confidence-bucketed (high silent / medium explicit / low no-recommend) | High → silent + yaml comment; medium → explicit AskUserQuestion; low → stock default | ADR-004 |
| 5 | R2 | Adaptive default | Risk | Telemetry default-on or opt-in? | A: Default-on, opt-out via `harness.yaml.adaptive.disable_telemetry: true` | Read-only, suggestion-only, 100% local. Adaptive layer has data from day 1 | ADR-005 |
| 6 | R3 | Audit rubric model | Architecture | Reuse ai-readiness or build separate? | A: Both — separate cmd + shared `rubric_loader.py` + `ImprovementPlan`/`ActionItem` | Different audience (maintainer self-review vs onboarding eval); shared rubric infra | ADR-006 |
| 7 | R3 | Confidence representation | Contract | Per-detection heuristic vs float vs enum? | A: Per-detection heuristic (explicit/inferred/guess) | No floats. Each detect fn declares own confidence. Exposed via yaml comment `# detected: framework=fastapi (high)` | ADR-007 |
| 8 | R3 | Cache invalidation | Architecture | How does detection cache invalidate? | A: Manifest-mtime + 24h ceiling | Auto-fresh on real changes, bounded staleness | ADR-008 |
| 9 | R3 | Block-marker convention | Contract | When re-generating foreign config, marker family? | A: Inverted `@hm:harness:*` (we mark our content, user content lives outside) | New marker name in `block_merge.py`, separate from existing `@hm:user:*` | ADR-009 |
| 10 | R4 | Failure modes (Layer 2 WRONG probe) | Risk | Primary failure mode? | D (early exit): all 3 failure modes equally weighted | dogfood + 1 external project test catches all three. Phase 12 enforces | ADR-010 |
| 11 | R5 | Rubric tier semantics (validator C1) | Architecture | composite vs per-layer tier; boundary/evidence schema? | A: Composite-score + fixed boundary (Bronze<40/Silver 40-65/Gold 65-85/Platinum>85); evidence = `{n_observations, top_3_signals, confidence}` | Triggered by plan-validator MAJOR_REVISION C1 — rubric design no longer deferred to Phase 10 | ADR-011 |
| 12 | R5 | External e2e repo (validator W6) | Risk | Phase 12 external project? | A: `github/spec-kit` | Triggered by plan-validator W6 — locked to avoid Phase-12-time decision | ADR-010 amendment |

**Round-by-round ambiguity score (Layer 3 gate not run — Round 4 early exit per protocol):**
- After R1: Goals 0.7 / Constraints 0.6 / SC 0.4 → 0.59 (NEEDS)
- After R2: Goals 0.85 / Constraints 0.85 / SC 0.5 → 0.74 (NEEDS)
- After R3: Goals 0.9 / Constraints 0.95 / SC 0.55 → 0.81 (PASS — but only 1 streak, gate not exited)
- R4: early exit chosen — gate skipped. SC implicit via ADR-010 (failure modes 명시).
- R5 (validator-driven): plan-validator MAJOR_REVISION trigger; 2 follow-up questions answered; ADR-010 amended + ADR-011 added.

## 📐 Architecture Decision Records

### ADR-001: Track A + D + B-start Co-Land in First Release
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** RESEARCH-personalization-depth-2026-05 surfaced 4 tracks (A Detection / B Adaptive / C New Axes / D Foreign Migration). User must scope first release to avoid 21-sub-track shotgun.
**Decision:** Land Track A (Detection) + Track D (Foreign Migration) + minimal Track B (Adaptive — telemetry + audit cmd + drift surface). Track B-extra (B2 permission freq, B3 reviewer signal) and Track C entirely deferred to follow-up PLAN.
**Consequences:**
- ✅ Brownfield onboarding (D) lands together with detection depth (A) — strongest user-facing value combination.
- ✅ B start collects telemetry from day 1, so `/hm:personalization-audit` (B4) has signal accumulating before later phases ship.
- ⚠️ 12-phase release is large. Worktree isolation + per-phase rollback critical.
**Rejected alternatives:**
- Track A only — drops brownfield migration story (foreign config users still hit conflicts).
- All 4 tracks in one release — 14+ phases, each track shallow, follow-up rework likely.
**Source:** Interview #1

### ADR-002: Balanced Sub-Track Set
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** Within A+D+B-start, 21 sub-tracks possible. Need sub-track inclusion lock-in.
**Decision:** Land A1 (stack/framework granularity), A6 (wrapup-doc auto-detect), A7 (MCP suggestion); D1 (foreign config detection), D2 (LLM-driven mapping), D3 (confirm UI + re-generation); B1 (override telemetry), B4 (`/hm:personalization-audit`), B5 (SessionStart drift surface). A2 collapses into D1 (same file-existence operation). Excluded: A3 commit-style, A4 pkg-mgr/CI, A5 README LLM summary, D4 reimport command, B2 permission freq, B3 reviewer signal.
**Consequences:**
- ✅ Exactly one new LLM call site (D2 foreign config mapping) — bounded LLM cost in `/hm:configure`.
- ✅ Each excluded sub-track has independent merit but isn't blocking — clean follow-up PLAN.
- ⚠️ A3 (commit style) absence means wrapup commit message convention stays generic until follow-up.
**Rejected alternatives:**
- Lean (no LLM at all) — would require manual user mapping of foreign configs, defeating Track D's value.
- Full (all 14+ sub-tracks, two LLM sites) — see ADR-001 ⚠️.
**Source:** Interview #2

### ADR-003: Foreign Config Import = Single Source via Re-generation
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** After we import the user's existing `.cursor/rules/`, `AGENTS.md`, etc. into `harness.yaml`, the external file's future ownership is ambiguous. Three options: single source (we re-generate), preserve external (read-once), hybrid (per-file flag).
**Decision:** Single source. After import, harness-maker re-generates the foreign file on every render. User edits inside the file are preserved via inverted `@hm:harness:*` block markers (ADR-009).
**Consequences:**
- ✅ One source of truth. No drift between user's foreign-config edits and our axis state.
- ✅ Re-render is idempotent — `/hm:configure --reimport-foreign` deferred but easy to add (was D4, excluded in ADR-002).
- ⚠️ User who is a Cursor power-user and wants Cursor-only ownership of `.cursor/rules/` cannot have it without disabling our render. Documented as a Success Criteria entry (README Personalization Architecture section MUST call out this constraint).
**Rejected alternatives:**
- Preserve external (read-once) — drift risk between our config and external file is real and silent. RESEARCH Pitfall #7.
- Hybrid (per-file `preserve` flag) — adds config surface for an edge case; can be added later if user demand emerges.
**Source:** Interview #3

### ADR-004: Confidence-Bucketed Recommendation UI
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** Detection produces 17+ recommendations per `/hm:configure`. All-explicit blows up interview length; all-silent hides decisions.
**Decision:** Each recommendation carries a confidence bucket. **High** confidence → silent default + `# detected: <signal> (high)` comment in `harness.yaml`. **Medium** confidence → explicit `AskUserQuestion`. **Low** confidence → no recommendation surfaced; stock default used.
**Consequences:**
- ✅ Interview length stays moderate (only medium-confidence recommendations ask).
- ✅ Detection depth visible via yaml comments — user can audit silent decisions.
- ⚠️ User who wants to confirm every detection must read `harness.yaml`. Document this in `/hm:configure` exit summary.
**Rejected alternatives:**
- All explicit — interview length blows up to 15-20 questions.
- Top-N explicit only — arbitrary cap unrelated to actual confidence.
- User picks aggressiveness — meta-config (configuring the configurator) feels indirect.
**Source:** Interview #4

### ADR-005: Adaptive Telemetry = Default-On, Opt-Out, Read-Only
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** B1 (override telemetry) needs default state. Default-off means cold-start (`/hm:personalization-audit` useless until N sessions accumulate); default-on means data capture without explicit consent.
**Decision:** Default-on. Opt-out via `harness.yaml.adaptive.disable_telemetry: true`. Read-only local capture (no external network). Suggestion-only — never auto-applies any axis change.
**Consequences:**
- ✅ Adaptive layer has signal from day 1.
- ✅ 100% local matches CLAUDE.md telemetry policy.
- ⚠️ Privacy-conscious user must read docs to find opt-out. Mitigation: `/hm:configure` exit summary mentions adaptive telemetry + opt-out flag.
- 🔒 **Positive obligation (added via validator W4)**: `tests/unit/test_no_network.py` MUST monkeypatch `socket.socket` and assert no outbound connection during `/hm:personalization-audit` and SessionStart hook execution. Phase 9 and Phase 10 test lists include this assertion. CI guard via `pytest-socket` dev-dependency permitted.
**Rejected alternatives:**
- Default-off opt-in — conservative but forces cold-start.
- Default-off + nudge after 30 sessions — hybrid; rejected because it adds an extra UX surface for a binary user choice.
**Source:** Interview #5; positive obligation added Round 5 follow-up to plan-validator W4.

### ADR-006: `/hm:personalization-audit` Separate Command + Shared Rubric Framework
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** Personalization audit needs an output surface. Could live as a 4th layer of `/hm:ai-readiness`, fully separate, or shared infra with separate command.
**Decision:** Separate `/hm:personalization-audit` command (different audience: maintainer self-review). Reuses `rubric_loader.py` + `ImprovementPlan` + `ActionItem` types from `ai_readiness.py`. New rubric YAML `rubrics/personalization.yaml` declares Bronze/Silver/Gold/Platinum tiers.
**Consequences:**
- ✅ Two audiences (external onboarding eval via `/hm:ai-readiness`, internal maintainer review via `/hm:personalization-audit`) stay focused.
- ✅ Rubric loading + scoring + dashboard rendering code shared — no duplication.
- ⚠️ Two commands instead of one. Mitigation: cross-link in both command outputs.
**Rejected alternatives:**
- Reuse as Layer 4 of `/hm:ai-readiness` — couples unrelated audiences, dilutes ai-readiness output focus.
- Fully separate (no shared infra) — duplicates rubric loading and ImprovementPlan-like types.
**Source:** Interview #6

### ADR-007: Per-Detection Heuristic Confidence
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** ADR-004 confidence-bucketed UI requires a confidence assignment mechanism. Options: per-detection heuristic, per-axis float [0,1] + thresholds, or three-bucket enum direct.
**Decision:** Each detection function declares its own confidence bucket. Conventions: explicit manifest match (e.g., `pyproject.toml` has `fastapi` in `dependencies`) → `high`; inferred from filename / dep name pattern → `medium`; pure heuristic guess (e.g., framework guessed from import statements without manifest) → `low`. No global float scale.
**Consequences:**
- ✅ Each detection's confidence rationale is self-documenting in code (the function literally returns the bucket).
- ✅ No tunable threshold to drift over releases.
- ⚠️ Cross-detection confidence comparison harder (no float ranking). Mitigation: ADR-004 silent/explicit decision is per-detection anyway.
**Rejected alternatives:**
- Per-axis float + global thresholds — adds machinery and tunable surface for marginal gain.
- Three-bucket enum direct — same as chosen, just without per-detection logic.
**Source:** Interview #7

### ADR-008: Detection Cache = Manifest-mtime + 24h Ceiling
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** Detection includes file scans + 1 LLM call (D2). Re-running on every `/hm:configure` is wasteful but stale cache misleads.
**Decision:** Cache at `~/.cache/harness-maker/profile-<repo-hash>.json`. Invalid if **any** tracked manifest's mtime > cache's mtime. Hard ceiling: 24h regardless. `repo-hash` = sha256 of absolute repo path.
**Consequences:**
- ✅ Auto-refresh on real project changes (user adds dep → manifest mtime bumps → cache invalidates).
- ✅ Bounded staleness — even if no manifest changes, cache renews daily.
- ⚠️ Manifest list must be exhaustive — missing one means stale cache used. Maintain `CACHED_MANIFESTS` constant; cover all manifests in `STACK_MANIFESTS` plus foreign-AI-config files.
**Rejected alternatives:**
- Manual only — stale forever if user forgets.
- No cache — slow every run (LLM call adds ~3-5s).
- Cache only LLM results — still needs invalidation logic; might as well unify.
**Source:** Interview #8

### ADR-009: Inverted `@hm:harness:*` Block Markers for Re-generated Foreign Configs
**Status:** Accepted (2026-05-16, via /hm:plan interview)
**Context:** When we re-generate `.cursor/rules/*.mdc`, `AGENTS.md`, etc. (post-import per ADR-003), we must preserve user edits. Existing convention is `@hm:user:*` (user customization wrapped). For files originally 100% user-owned, that's backward.
**Decision:** Use new `@hm:harness:*` marker family. Our generated content lives inside `<!-- @hm:harness:<name> -->` ... `<!-- @hm:/harness:<name> -->`. Anything OUTSIDE these markers is treated as user content and preserved across re-renders.
**Consequences:**
- ✅ Cleaner mental model for files that were user-owned: "the harness only controls clearly-marked regions".
- ✅ `@hm:user:*` (existing) and `@hm:harness:*` (new) have orthogonal semantics; both can coexist in the same file if needed.
- ⚠️ `block_merge.py` gains a second marker family. Tests must cover both independently and combined.
- 🛤️ **Migration policy (added via validator W9)**: existing `0.11.x`-rendered files (frontmatter signature `generated_by: harness-maker` + zero `@hm:harness:*` markers present) are treated as wholly harness-owned on first encounter post-upgrade and re-rendered into the new marker family. Subsequent renders use `@hm:harness:*` semantics. **Phase 6 (post-merge) test scope MUST cover this migration path** (a `.cursor/rules/` file present from `0.11.x` is correctly upgraded). CLAUDE.md §체크리스트 #5 (fingerprint-based discrimination) directly applied.
**Rejected alternatives:**
- Existing `@hm:user:*` — mental model fights file's history (user owned 100%, now we're marking subset as "user customization").
- Whole-file ownership flag — crude, no mid-file granularity.
- Both (markers + frontmatter override) — added complexity for an edge-case escape hatch; can be added in follow-up.
**Source:** Interview #9; migration policy via plan-validator W9 follow-up.

### ADR-010: Three Failure Modes Equally Weighted; Dogfood + 1 External Project as Common Safety Net
**Status:** Accepted (2026-05-16, via /hm:plan interview Round 4 early exit)
**Context:** Layer 2 WRONG probe surfaced 3 candidate failure modes: (a) detection false-positives erode user trust, (b) foreign config import damages user files, (c) adaptive layer produces noise without actionable suggestions.
**Decision:** All three are equally weighted as primary failure modes. Phase 12 (verification) MUST include both (1) dogfood on the harness-maker repo itself and (2) one external project test.

**Amendment (Round 5 / plan-validator W6 follow-up, 2026-05-16):** External project = **`github/spec-kit`** (locked at PLAN time, not Phase 12 time). Selection criteria recorded for follow-up amendments / repo swaps:
- (a) ≥3 of 6 foreign-AI-config types likely present (CLAUDE.md, AGENTS.md, .github/copilot-instructions.md candidates in spec-kit)
- (b) Stack outside the original 5 STACK_MANIFESTS not strictly required for spec-kit (Python only) — Phase 3 expansion still exercised against dogfood
- (c) Public license compatible with `tests/e2e/fixtures/` vendoring (spec-kit MIT)
- (d) Mid-size repo (≤500 tracked files) so e2e test is bounded

**Consequences:**
- ✅ No single failure mode gets disproportionate mitigation budget — phase-level mitigations cover all three (high-confidence-only for false-positive, dry-run + confirm for foreign config, evidence-required output for adaptive noise).
- ✅ External repo locked at PLAN time — `/hm:execute` does not need to make a Phase-12-time decision.
- ⚠️ If `github/spec-kit` lacks a foreign-AI-config type at vendoring time, a synthetic fixture is added under `tests/e2e/fixtures/foreign-configs-supplement/` for that type. Document supplement clearly.
**Rejected alternatives:**
- Pick one as primary — implies the other two are acceptable failure modes.
- No external test — dogfood-only blind spot for foreign config (harness-maker repo has its own `.cursor/`, `.codex/`, `.claude/` but they are *our generated* outputs, not foreign).
- Two repos (spec-kit + Rust/JS for stack diversity) — Phase 12 cost 2× without proportional risk reduction.
**Source:** Interview #10 (failure mode triage), Interview #12 (external repo amendment via plan-validator W6).

### ADR-011: Personalization Audit Rubric Tier Semantics
**Status:** Accepted (2026-05-16, via /hm:plan interview Round 5 / plan-validator C1 follow-up)
**Context:** ADR-006 chose to reuse the rubric framework but did NOT lock the rubric content itself. plan-validator C1 flagged this as a HIGH blast-radius deferred decision (Phase 10 would otherwise pick tier semantics implicitly at implementation time). RESEARCH §Pitfalls #6 explicitly warned about rubric-as-Goodharting-surface.
**Decision:** `/hm:personalization-audit` rubric uses a **composite-score model** with **fixed boundaries**:

- **Layer weights** (sum to 100%):
  - L1 (detection→recommendation conversion rate): **40%**
  - L2 (override frequency / axis stability): **30%**
  - L3 (adaptive opt-in + audit cadence regularity): **30%**
- **Composite score range**: `[0, 100]`. Computed as `L1_score×0.4 + L2_score×0.3 + L3_score×0.3` where each layer score is `[0, 100]`. **Layer-score formulas are locked in this PLAN at Phase 10 scope and embedded into `rubrics/personalization.yaml v0` at execute time. Future calibration is YAML-only (no code change required).**
  - L1: `score = (medium_recommendations_accepted + high_recommendations_silent) / total_recommendations × 100` (NULL safe).
  - L2: `score = 100 - min(100, override_events_last_30d × penalty_factor)` where `penalty_factor = 5`.
  - L3: `score = 100` if last `/hm:personalization-audit` ran within 14 days AND `disable_telemetry == false`; `score = 50` if exactly one condition met; `0` otherwise.
- **Tier boundaries** on composite score:
  - **Bronze**: composite `< 40`
  - **Silver**: composite `40 ≤ x < 65`
  - **Gold**: composite `65 ≤ x < 85`
  - **Platinum**: composite `≥ 85`
- **Per-`ActionItem` evidence schema** (mandatory):
  ```python
  {
      "n_observations": int,         # how many telemetry events back this action
      "top_3_signals": list[str],    # top 3 supporting signal IDs
      "confidence": Confidence,      # high|medium|low (reuses ADR-007 enum)
  }
  ```
  Action items lacking ≥1 observation OR ≥1 supporting signal are dropped from output (RESEARCH ADR-010 mode C mitigation = no noise).

**Consequences:**
- ✅ Rubric is locked, not deferred — `/hm:execute` Phase 10 implements concrete formulas.
- ✅ Goodhart-resistance: composite (not min) means no single-layer optimization unlocks Platinum; evidence schema means actions without data are filtered.
- ✅ Tunable: rubric YAML at `rubrics/personalization.yaml` allows per-layer formula iteration without code change. Tier boundaries pinned in YAML too, so calibration is config-only.
- ⚠️ Initial calibration may produce few Platinum-tier projects in the wild. Acceptable — Bronze→Silver step is the most-trafficked.
- ⚠️ Composite vs per-layer-min trades transparency for resilience. `/hm:personalization-audit` output MUST display per-layer scores alongside composite (already in `ai_readiness.render_terminal_summary` pattern).
**Rejected alternatives:**
- Per-layer tier + composite=min(layers) — emphasizes weakest-link clarity but loses cross-layer averaging; one neglected layer caps overall tier.
- Defer rubric to Phase 10 — exactly what plan-validator C1 rejected (HIGH blast-radius implicit decision).
**Source:** Interview #11 (Round 5 follow-up to plan-validator C1).

## 🏗️ Technical Design

### Current State

`HarnessConfig` (models.py:322) covers 21 personalization axes — see RESEARCH §Step 1 inventory. `ProjectProfile` (models.py:118) detects 7 signals: `stack` (5 manifests), `scale` (3 buckets via file count), `lifecycle` (commit count), `existing_dotclaude`, `spec_only`, `vault_member`, `detected_checks`.

`profile.py` (157 lines) implements the 7 detections. `interview.py` (845 lines) wires `_recommend_preset(profile)` (single one-line heuristic) and `_recommend_dev_mode(preset)` (transitive). 17 of 21 axes have NO `recommend_<axis>(profile)` function — they go straight to default or user-input.

`block_merge.py` implements `@hm:user:*` markers for preserving user customization across template upgrades. No marker family for files we re-generate from external sources (foreign-AI-configs are not currently re-generated).

`telemetry.py` + `review_telemetry.py` write hook events / review records to `.claude/observability/*.jsonl`. No `harness_yaml_override` event type.

`ai_readiness.py` + `rubric_loader.py` + `ImprovementPlan`/`ActionItem` (in models.py — verify) provide the rubric scoring infrastructure. `/hm:ai-readiness` command exists.

### Affected Components

| Component | Change type | Phase |
|-----------|-------------|-------|
| `src/harness_maker/models.py` | Extend `ProjectProfile` (5 new fields: `frameworks`, `package_manager`, `ci_provider`, `foreign_ai_configs`, `detection_confidence`); add `Recommendation` dataclass + `Confidence` enum | Phase 1 |
| `src/harness_maker/recommendation.py` | NEW — `recommend_<axis>(profile) -> Recommendation` interface, registry, confidence-bucketed dispatcher | Phase 1 |
| `src/harness_maker/detection_cache.py` | NEW — `~/.cache/harness-maker/profile-<hash>.json` read/write, manifest-mtime + 24h invalidation | Phase 2 |
| `src/harness_maker/profile.py` | Extend `STACK_MANIFESTS` (5 → 12+ entries), framework dep parser, `package_manager` + `ci_provider` detection, returns `ProjectProfile` with new fields | Phase 3 |
| `src/harness_maker/recommendation.py` | Add `recommend_wrapup_docs(profile)` (CHANGELOG.md/TODO.md/docs/ADR-*.md detect), `recommend_mcp_servers(profile)` (framework→MCP mapping table) | Phase 4 |
| `src/harness_maker/foreign_config.py` | NEW — detect 6 known foreign configs (`.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`, `.github/copilot-instructions.md`), return list with confidence + path | Phase 5 |
| `src/harness_maker/foreign_config.py` + `block_merge.py` + `templates/foreign-configs/` (NEW) + `src/harness_maker/templates/commands/hm/configure.md.j2` | Merged D2+D3 (validator W5): LLM-driven mapping (read foreign config → Anthropic → axis JSON, sha256 cache + 24h TTL) AND confirm UI + `@hm:harness:*` inverted marker family + idempotent re-render with 0.11.x migration handler (ADR-009 amendment) | Phase 6 (merged) |
| `src/harness_maker/interview.py` | Wire confidence-bucketed UI: high → silent + yaml comment; medium → explicit `AskUserQuestion`; low → stock default. Migrate existing 4 transitive recommends to new framework | Phase 8 |
| `src/harness_maker/telemetry.py` | New event type `harness_yaml_override` (triggered by SessionStart hook detecting git diff on `.claude/harness.yaml`). Storage `.claude/observability/adaptive/overrides.jsonl` | Phase 9 |
| `src/harness_maker/personalization_audit.py` | NEW — read overrides.jsonl + current harness.yaml + ProjectProfile; score against `rubrics/personalization.yaml`; output `ImprovementPlan` with ranked `ActionItem` list. Reuses `rubric_loader.py` | Phase 10 |
| `rubrics/personalization.yaml` | NEW — Bronze/Silver/Gold/Platinum tier rubric. Layer 1 = detection→recommendation conversion rate; Layer 2 = override frequency; Layer 3 = adaptive opt-in + audit cadence | Phase 10 |
| `templates/commands/hm/personalization-audit.md.j2` | NEW — `/hm:personalization-audit` command template (Cursor + Claude Code + Codex tri-IDE) | Phase 10 |
| `src/harness_maker/templates/hooks/session_start_drift.py.j2` (or equivalent existing) | Extend SessionStart hook — after 30 sessions OR 14 days, hint "X personalization recommendations queued. /hm:personalization-audit to review" | Phase 11 |
| `README.md` + `TECH_SPEC.md` | Update — personalization architecture section, foreign config import flow, adaptive opt-out flag | Phase 12 |
| `tests/unit/test_*.py` | NEW: `test_recommendation.py`, `test_detection_cache.py`, `test_foreign_config.py`, `test_personalization_audit.py`. Extend: `test_profile.py`, `test_models.py`, `test_block_merge.py`, `test_interview.py`, `test_telemetry.py` | Per-phase |
| `tests/e2e/test_personalization_dogfood.py` | NEW — full `/hm:configure` on harness-maker repo + 1 sample external repo | Phase 12 |

### Dependencies

**No new Python runtime dependency.** Reuse existing `pydantic`, `pyyaml`, `jinja2`, `anthropic` (for D2 LLM mapping; Phase 6 — already a dependency for ai_readiness LLM judge), `httpx` (already used).

### Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│  /hm:configure  (Phase 8 wiring)                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
                ┌────────────────┐
                │ ProjectProfile │  ← Phase 1 schema extension
                │  (Phase 3 deep)│  ← Phase 3 12+ stacks/frameworks
                └────────┬───────┘
                         │
                ┌────────v────────┐
                │ detection_cache │  ← Phase 2 (manifest-mtime + 24h)
                └────────┬────────┘
                         │
        ┌────────────────┼────────────────┐
        v                v                v
┌──────────────┐ ┌──────────────┐ ┌────────────────┐
│ recommend_*  │ │ foreign_     │ │ second_brain   │  ← existing
│ functions    │ │ config       │ │ (untouched)    │
│ (Phase 1+4)  │ │ (Phase 5-7)  │ └────────────────┘
└──────┬───────┘ └──────┬───────┘
       │                │
       │           ┌────v────────┐
       │           │ LLM mapping │  ← Phase 6 (1 LLM site)
       │           │ + cache     │
       │           └────┬────────┘
       │                │
       │           ┌────v────────────┐
       │           │ Confirm UI +    │  ← Phase 6 (block_merge inverted markers; merged D2+D3)
       │           │ @hm:harness:*   │
       │           └─────────────────┘
       │
       v
┌──────────────────────────────┐
│ Confidence-bucketed dispatch │
│  high  → yaml comment        │
│  medium→ AskUserQuestion     │
│  low   → stock default       │
└──────────────┬───────────────┘
               │
               v
        harness.yaml (final)

   ┌──────────────────────────────────┐
   │ Adaptive layer (parallel)        │
   │  Phase 9: telemetry capture      │  ← .claude/observability/adaptive/overrides.jsonl
   │  Phase 10: /hm:personalization-  │  ← rubric scoring + ImprovementPlan
   │           audit                  │
   │  Phase 11: SessionStart hint     │  ← after 30 sessions or 14 days
   └──────────────────────────────────┘
```

### Design Decisions

- **Single recommendation interface**: every `recommend_<axis>(profile) -> Recommendation` returns the same dataclass. Dispatcher handles confidence bucket → UI route. Adding a new recommendation later = add one function + register it (no UI plumbing change).
- **Detection cache key = repo absolute path sha256**: avoids collision on machines hosting multiple clones. Per-machine cache (not synced across users — adaptive telemetry policy).
- **Foreign config LLM cache key = file content sha256 + harness-maker version**: invalidates on user editing the foreign config OR our prompt template changing.
- **`@hm:harness:*` marker semantics**: outside markers = user owns; inside markers = we re-generate. On render, we replace ONLY marked regions; outside regions copied byte-for-byte.
- **`/hm:personalization-audit` output schema**: parallel to `/hm:ai-readiness` — composite score / 100, layer scores, ranked ActionItem list. Dashboard rendering via shared `ai_readiness.render_*` functions (refactor in Phase 10 if needed).
- **Adaptive event type minimalism**: `harness_yaml_override` event records only `(timestamp, axis_path, before_value, after_value)` — no diff body, no PR-like metadata. Schema-versioned for future extension.
- **No Track C (new axes) ground laid**: deliberately. Schema additions for team/privacy/code-style would commit us before we have data. Track C lives in follow-up PLAN.

### Data Flow

```text
┌─ Time: /hm:configure run ─────────────────────────────────────┐
│                                                                │
│  user invokes /hm:configure                                    │
│    ↓                                                           │
│  detection_cache.load_or_run(profile_dir)                      │
│    ↓ [cache miss or stale]                                     │
│  profile.profile(project_dir) → ProjectProfile                 │
│    ↓                                                           │
│  foreign_config.detect(project_dir) → list[ForeignConfig]      │
│    ↓                                                           │
│  for each foreign config:                                      │
│    foreign_config.llm_map(file) → AxisMapping (cached)        │
│    ↓                                                           │
│  recommendation.collect_all(profile) → list[Recommendation]    │
│    ↓                                                           │
│  detection_cache.write(profile, mappings, recommendations)     │
│    ↓                                                           │
│  interview.confidence_bucketed_dispatch(recommendations)       │
│    high  → yaml comment (silent)                               │
│    medium→ AskUserQuestion → user choice → harness.yaml        │
│    low   → stock default (no surface)                          │
│    ↓                                                           │
│  render harness.yaml + foreign config files (with @hm:harness:*)│
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌─ Time: every session SessionStart ────────────────────────────┐
│                                                                │
│  SessionStart hook (Phase 11 extension)                       │
│    ↓                                                           │
│  git diff HEAD~1..HEAD .claude/harness.yaml (if recent commit)│
│    ↓ [override detected]                                      │
│  telemetry.emit("harness_yaml_override", axis, before, after) │
│    ↓                                                           │
│  → .claude/observability/adaptive/overrides.jsonl             │
│    ↓ [if session_count >= 30 OR days_since_last_audit >= 14]  │
│  drift surface: "X personalization recommendations queued.    │
│                  /hm:personalization-audit to review"         │
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌─ Time: /hm:personalization-audit run ─────────────────────────┐
│                                                                │
│  load .claude/observability/adaptive/overrides.jsonl          │
│  load .claude/harness.yaml                                     │
│  load ProjectProfile (from cache)                              │
│    ↓                                                           │
│  rubric_loader.load("rubrics/personalization.yaml")           │
│    ↓                                                           │
│  score each layer:                                             │
│    L1: detection→recommendation conversion rate                │
│    L2: override frequency / axis stability                    │
│    L3: adaptive opt-in + audit cadence                        │
│    ↓                                                           │
│  ImprovementPlan with ranked ActionItem list                   │
│    ↓                                                           │
│  render_terminal_summary() (reused from ai_readiness)         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### API Changes

**ProjectProfile** (models.py) — 5 new fields, all default-ed for backward compat:
```python
frameworks: list[str] = Field(default_factory=list)
package_manager: str = ""
ci_provider: str = ""
foreign_ai_configs: list[str] = Field(default_factory=list)
detection_confidence: dict[str, str] = Field(default_factory=dict)  # {axis: "high"|"medium"|"low"}
```

**HarnessConfig** (models.py) — 1 new typed sub-config:
```python
class AdaptiveConfig(BaseModel):
    disable_telemetry: bool = False  # opt-out per ADR-005
    audit_session_threshold: int = 30
    audit_days_threshold: int = 14

adaptive: AdaptiveConfig = Field(default_factory=AdaptiveConfig)
```

**InterviewAnswers** — adaptive field round-trip via `answers_from_harness_yaml`.

**block_merge.py** — new `@hm:harness:*` marker family. Existing `@hm:user:*` API unchanged.

**CLI** — no new top-level Typer command. `/hm:personalization-audit` invokes `python -m harness_maker.personalization_audit` directly from command template.

## 📝 Implementation Plan

### Phase 1: Confidence + Recommendation Infrastructure

**Scope:** `src/harness_maker/models.py` (add `Confidence` enum, `Recommendation` dataclass, `AdaptiveConfig`, extend `ProjectProfile` with 5 new fields), `src/harness_maker/recommendation.py` (NEW — registry, dispatcher, base `recommend(axis, profile)` signature), `tests/unit/test_models.py` (new field defaults), `tests/unit/test_recommendation.py` (NEW — registry, lifecycle).

**Out of scope:** any actual `recommend_<axis>()` function bodies (Phase 3-4), interview wiring (Phase 8), foreign config (Phase 5+).

**Exit criterion:** `uv run pytest tests/unit/test_models.py tests/unit/test_recommendation.py -q && uv run mypy --strict src/harness_maker/models.py src/harness_maker/recommendation.py`

**Risk:** low. Pure schema/types, no behavior change.

**Rollback point:** Revert Phase 1 files; existing schema unaffected.

### Phase 2: Detection Cache

**Scope:** `src/harness_maker/detection_cache.py` (NEW — `load_or_run(repo_path) -> ProjectProfile | None`, `write(profile, repo_path)`, manifest-mtime + 24h invalidation, sha256 keyed cache path). **All cache writes MUST use `harness_maker.io_utils.atomic_write`** (CLAUDE.md §실행 패턴 mandate; validator C2). Last-writer-wins on concurrent runs; documented behavior. `tests/unit/test_detection_cache.py` (NEW — manifest mtime invalidation, 24h ceiling, hash collision via path normalization, **explicit corruption recovery test** (write truncated JSON → load → returns None + logs warning, downstream re-runs fresh detection), **concurrent-write smoke test** (two threads `write()` interleave → no torn JSON, both files parse OK on read).

**Out of scope:** wiring into `profile.profile()` (deferred to Phase 3). Advisory file lock (`fcntl`) deferred unless concurrent-write smoke test reveals corruption — accepted as last-writer-wins per ADR-008 + CLAUDE.md atomic_write guarantee.

**Exit criterion:** `uv run pytest tests/unit/test_detection_cache.py -q && uv run mypy --strict src/harness_maker/detection_cache.py`. Specifically must pass `test_corruption_recovery` and `test_concurrent_writes_no_tear`.

**Risk:** medium. File I/O, cross-platform path handling. Cache corruption recovery (read fails → run fresh, log warning) is now an asserted test, not just a comment.

**Rollback point:** Revert Phase 2 files; downstream Phase 3 falls back to live detection. **Cache files on disk become orphaned** — `/hm:refresh` (or manual `rm -rf ~/.cache/harness-maker/`) cleans them up. Document in rollback procedure.

### Phase 3: A1 — Stack + Framework Granularity

**Scope:** `src/harness_maker/profile.py` (expand `STACK_MANIFESTS` 5 → 12+: java/kotlin/swift/dart/ruby/php/c#/elixir/scala/c-cpp/zig/haskell; framework detection via dep parsing for python/node/rust; populate new `frameworks`/`package_manager`/`ci_provider`/`detection_confidence` fields), wire `detection_cache` from Phase 2, `tests/unit/test_profile.py` (extend — per-stack fixtures, framework precedence, confidence bucket assignment).

**Out of scope:** A6 wrapup-doc (Phase 4), A7 MCP suggest (Phase 4), foreign config (Phase 5).

**Exit criterion:** `uv run pytest tests/unit/test_profile.py -q && uv run mypy --strict src/harness_maker/profile.py`. Manual: run on harness-maker repo itself, assert detected `frameworks=[...] package_manager="uv" ci_provider="github-actions"`.

**Risk:** medium. Per-stack fixture coverage easy to leave incomplete.

**Rollback point:** Revert Phase 3; `STACK_MANIFESTS` reverts to 5 entries; `profile()` returns sparse `ProjectProfile` with new fields empty.

### Phase 4: A6 (Wrapup-Doc Auto-Detect) + A7 (MCP Suggest)

**Scope:** `src/harness_maker/recommendation.py` (extend — `recommend_wrapup_docs(profile)` detects `CHANGELOG.md`/`TODO.md`/`docs/ADR-*.md`/`HISTORY.md`; `recommend_mcp_servers(profile)` frame-work→MCP mapping table — frontend → playwright; data-sci → jupyter; firmware → none), `tests/unit/test_recommendation.py` (extend — wrapup_docs detection cases, MCP suggestion table coverage).

**Out of scope:** Interview wiring (Phase 8). MCP suggestion produces `Recommendation` only — actual installation deferred to user.

**Exit criterion:** `uv run pytest tests/unit/test_recommendation.py -q`. Manual: dogfood detection on harness-maker repo itself.

**Risk:** low.

**Rollback point:** Revert Phase 4 functions; recommendation registry stays.

### Phase 5: D1 — Foreign AI Config Detection

**Scope:** `src/harness_maker/foreign_config.py` (NEW — `detect(project_dir) -> list[ForeignConfig]`; 6 paths checked: `.cursor/rules/`, `AGENTS.md` (root only — codex format), `CLAUDE.md` (root only — claude code format, NOT child files), `.continue/config.json`, `.aider.conf.yml`, `.github/copilot-instructions.md`; returns dataclass with path/type/size/confidence), `tests/unit/test_foreign_config.py` (NEW — per-file detection, glob handling for `.cursor/rules/*.mdc`).

**Out of scope:** LLM mapping + confirm UI (both in Phase 6 post-merge).

**Exit criterion:** `uv run pytest tests/unit/test_foreign_config.py -k detect -q && uv run mypy --strict src/harness_maker/foreign_config.py`.

**Risk:** low. Pure file-existence checks with glob.

**Rollback point:** Revert Phase 5 files; no other code depends yet.

### Phase 6: D2 + D3 — Foreign Config LLM Mapping + Confirm UI + Re-generation (MERGED, validator W5)

> **Merge rationale (validator W5):** Original Phase 6 (LLM mapping) was internal-only — the mapping sat in cache and was never surfaced. Original Phase 7 (confirm UI + re-generation) depended on Phase 6 output. Landing them together aligns with "each rollback point is a meaningfully reachable milestone" — D2 alone has zero user value.

**Scope:**

- `src/harness_maker/foreign_config.py` (extend):
  - `llm_map(foreign_config) -> AxisMapping`: reads file body, calls Anthropic via existing client (same pattern as `ai_readiness.py:_build_judge_client`), prompt requests strict JSON schema mapping to harness axes. Result cached at `~/.cache/harness-maker/foreign-map-<sha256>.json` with 24h TTL + content-sha256 invalidation. `harness_maker.io_utils.atomic_write` for cache writes.
  - `apply(mapping, profile, harness_yaml) -> ChangeSet`: idempotent re-render of foreign configs wrapped with `@hm:harness:*` markers.
- `src/harness_maker/block_merge.py` (extend): new `@hm:harness:*` marker family. Parser recognizes both `@hm:user:*` and `@hm:harness:*`. Inverted-marker merge logic — outside `@hm:harness:*` = preserve, inside = replace. **Migration handler (ADR-009 amendment + validator W9):** files matching `0.11.x` signature (frontmatter `generated_by: harness-maker` + zero `@hm:harness:*` markers) → treated as wholly harness-owned on first encounter, re-rendered into the new marker family.
- `templates/foreign-configs/` (NEW directory) — Jinja2 templates for each of 6 foreign config types.
- `src/harness_maker/templates/commands/hm/configure.md.j2` (extend) — interview round for foreign config import: show LLM mapping table + per-axis accept/reject, then write into `HarnessConfig` + render foreign files.

**Test scope:**

- `tests/unit/test_foreign_config.py` (extend):
  - `mock_anthropic_client` fixture from `tests/unit/conftest.py` per CLAUDE.md (validator W1).
  - Golden fixtures at `tests/unit/fixtures/foreign_configs/<type>.{mdc,md,json,yaml}` enumerated for all 6 types.
  - **Assertion shape**: subset match — every axis key in golden mapping MUST appear in LLM-output mapping; extra axes allowed but logged.
  - Round-trip test: write user content outside markers → re-render → user content preserved byte-for-byte.
- `tests/unit/test_block_merge.py` (extend) — 6 test cases per validator W2:
  1. Only `@hm:user:*` markers (regression baseline; existing 0.11.x corpus snapshot byte-for-byte zero-churn).
  2. Only `@hm:harness:*` markers (new family alone).
  3. Both families coexist in same file (orthogonal semantics).
  4. Neither family present (foreign-config import path).
  5. **Mismatched/nested markers** (e.g., `@hm:user:X` opened but `@hm:/harness:X` closed) → parser raises typed `MarkerMismatchError`, never silent drop.
  6. **Literal `@hm:` string inside fenced code block** → parser correctly skips (no false-positive marker detection).
- `tests/integration/test_foreign_map_live.py` (NEW, gated by `INTEGRATION=1`): real Anthropic call against each of 6 fixtures. Assertion: JSON parseable + at least 1 axis mapping per file type. NOT brittle exact-match.
- **Migration regression test** (ADR-009 amendment): a `.cursor/rules/test.mdc` file with `0.11.x`-style frontmatter and no `@hm:harness:*` markers → first re-render upgrades into new marker family; second re-render is no-op (idempotent).

**Out of scope:** Interview UI confidence bucketing (Phase 8). Automatic application without confirm (deferred — confirm UI is mandatory per ADR-003).

**Exit criterion:** `uv run pytest tests/unit/test_foreign_config.py tests/unit/test_block_merge.py -q`. Manual: import `.cursor/rules/test.mdc` with custom user line, re-render, diff shows zero churn outside markers; existing 0.11.x `.mdc` upgrades cleanly.

**Risk:** high. block_merge.py is core infrastructure; new marker family must not break existing `@hm:user:*` regression baseline. LLM determinism requires careful prompt design; mitigation = strict JSON schema in prompt + parse fail → empty mapping graceful degrade.

**Rollback point:** Revert Phase 6 changes; existing `@hm:user:*` infrastructure unaffected; foreign configs no longer re-generated; Phase 5 detection still produces `foreign_ai_configs` list. Cache JSON files orphaned on disk — `/hm:refresh` or `rm ~/.cache/harness-maker/foreign-map-*.json` cleans up.

### Phase 7: ⊘ MERGED INTO PHASE 6

This phase number is intentionally retained as a marker. Original D3 work (confirm UI + `@hm:harness:*` markers + re-generation) is now in Phase 6 above per validator W5 merge.

### Phase 8: Recommendation UI Integration in `interview.py`

**Scope:**
- `src/harness_maker/interview.py` (refactor):
  - New helper `_dispatch_recommendation(rec: Recommendation, *, target: Target)` central function. **Helper name fixed (validator N1 — tri-IDE drift guard)**: single dispatch site, three render paths (`AskUserQuestion` for Claude Code, `AskQuestion` for Cursor, structured prompt block for Codex). Backed by `tests/unit/test_dispatch_recommendation.py` asserting all three target IDEs receive equivalent payload from one call.
  - Bucket routing: high → emit yaml comment line + apply default; medium → dispatched question; low → silent stock default.
- **Backward-compat assignment for existing 4 transitive recommends (validator W3 — UX regression guard)**:
  - `_recommend_preset(profile)` → assigned **`medium`** confidence on first release. Rationale: today this is always asked; silent flip to `high` would surprise 0.11.x users on upgrade.
  - `_recommend_dev_mode(preset)` → assigned **`medium`** confidence (same reasoning).
  - `detected_checks(profile)` → assigned **`high`** confidence (already silent today via `mechanical_checks` template — behavior parity with current).
  - `vault_member(profile)` → assigned **`high`** confidence (current behavior is silent detection → second_brain default suggestion).
  - Documented in `recommendation.py` registry as inline confidence comments. Conservative migration; tighten in follow-up release once telemetry shows zero override pattern.
- `tests/unit/test_interview.py` (extend — confidence bucket dispatch, yaml comment format).
- `tests/unit/test_dispatch_recommendation.py` (NEW — tri-IDE payload equivalence per validator N1).
- **Backward-compat regression test** (validator W3): load fixture `harness.yaml` written by 0.11.x → run `answers_from_harness_yaml` reuse path → re-render → assert zero diff on the 4 axes' rendered values.

**Out of scope:** New `recommend_<axis>()` bodies (Phase 3/4). Telemetry hookup (Phase 9).

**Exit criterion:** `uv run pytest tests/unit/test_interview.py tests/unit/test_recommendation.py tests/unit/test_dispatch_recommendation.py -q`. Manual: `/hm:configure` on a fresh test repo shows confidence-bucketed dispatch in action; load 0.11.x-style `harness.yaml` and re-render shows zero churn on preset/dev_mode axes.

**Risk:** medium. Touches main interview flow. Existing-user upgrade must produce no surprise silent-default changes on preset/dev_mode (asserted by regression test above).

**Rollback point:** Revert Phase 8 to legacy direct calls; recommendation framework still callable from outside.

### Phase 9: B1 — Override Telemetry Capture

**Scope:**
- `src/harness_maker/telemetry.py` (extend):
  - New event type `harness_yaml_override` with schema `{schema_version: 1, ts: iso8601, axis_path: str, before: Any, after: Any, source: "session-start"|"configure-exit"|"git-fallback", reason?: str}`. **`schema_version` field mandatory on every record (validator C3)**. Loader in Phase 10 skips unknown versions with a warning.
  - Storage: `.claude/observability/adaptive/overrides.jsonl`. Atomic jsonl append via `harness_maker.io_utils.atomic_write` (full-file rewrite on each append for small files; switch to `O_APPEND` semantics if file grows past 100KB).
- **Capture sites (validator W8 — eliminate uncommitted-edit hole)**:
  - **Primary**: `/hm:configure` exit hook — compares pre-run and post-run yaml content (no git dependency). Captures all axis changes including those committed AND uncommitted. Always-fires regardless of git state.
  - **Secondary**: SessionStart hook (extend existing per commit `64bf5b9`) — detects `git diff HEAD~1..HEAD .claude/harness.yaml` since last recorded override `ts` (no fixed `HEAD~5` window). Captures yaml edits committed outside `/hm:configure`.
  - **Both paths share a dedup key** (`ts + axis_path + after`): same override never recorded twice if both paths fire.
- `harness.yaml` `AdaptiveConfig` (Phase 1 schema) wired to runtime: if `disable_telemetry` is `true`, both capture sites skip emit.
- **Phase 1 ↔ Phase 9 schema migration discipline (validator C3)**: if Phase 9 reverted while `AdaptiveConfig` schema (Phase 1) remains, `AdaptiveConfig` writes to `harness.yaml` are **dead config** (no consumer). Add a startup warning emitted by `/hm:status` when `adaptive` block is present but no telemetry events recorded in last 30 days. **Rollback procedure** explicit: if Phase 9 fully reverted, also delete `.claude/observability/adaptive/` directory in a `/hm:refresh` step.
- `tests/unit/test_telemetry.py` (extend): override event format incl. `schema_version`, jsonl atomic append, opt-out flag honored, dedup key correctness, both capture sites tested with same trigger.
- `tests/unit/test_no_network.py` (NEW per ADR-005 amendment / validator W4): monkeypatch `socket.socket`, run telemetry emit + audit + SessionStart hook, assert no outbound socket connection. Optional dev-dep: `pytest-socket`.

**Out of scope:** Audit consumption (Phase 10), drift hint (Phase 11).

**Exit criterion:** `uv run pytest tests/unit/test_telemetry.py -k override -q && uv run pytest tests/unit/test_no_network.py -q`. Manual: edit `.claude/harness.yaml` axis manually (no commit) + run `/hm:configure` → verify event recorded with `source: "configure-exit"`. Then commit + start session → verify event recorded once (dedup) with `source: "session-start"`.

**Risk:** medium. Two capture sites means more code paths; dedup is essential. Hook detection of yaml diff is fragile but secondary — primary `/hm:configure`-exit path always fires.

**Rollback point:** Revert Phase 9; no event recorded; downstream Phase 10 sees empty jsonl (still functions, no actionable items, scores Bronze). Cleanup: `rm -rf .claude/observability/adaptive/` if Phase 1 `AdaptiveConfig` also reverted; otherwise leave (Phase 10 will warn dead config via `/hm:status`).

### Phase 10: B4 — `/hm:personalization-audit` Command

**Scope:**
- `rubrics/personalization.yaml` (NEW): rubric content fully specified per **ADR-011** (composite-score model, fixed boundaries):
  - Layer weights: L1×0.4 + L2×0.3 + L3×0.3.
  - L1 (conversion): `score = (medium_recommendations_accepted + high_recommendations_silent) / total_recommendations × 100`. NULL safe (zero recommendations → 0).
  - L2 (override stability): `score = 100 - min(100, override_events_last_30d × penalty_factor)` where `penalty_factor = 5` (i.e., 20+ overrides → 0).
  - L3 (cadence): `score = 100` if `/hm:personalization-audit` last ran within 14 days AND `disable_telemetry == false`; `score = 50` if one condition met; `0` otherwise.
  - Tier boundaries: Bronze<40, Silver 40-65, Gold 65-85, Platinum>85.
- `src/harness_maker/personalization_audit.py` (NEW):
  - `run_audit(project_dir) -> ImprovementPlan`. Reuses `rubric_loader.load(...)` + `ImprovementPlan` + `ActionItem` from `ai_readiness.py`.
  - Reads `.claude/observability/adaptive/overrides.jsonl` (with `schema_version` filter — skip unknown versions, log warning), current `.claude/harness.yaml`, ProjectProfile from `detection_cache`.
  - Emits ranked `ActionItem` list; each item carries `evidence: {n_observations, top_3_signals, confidence}` per ADR-011. Items with `n_observations == 0` OR empty `top_3_signals` are dropped (mode C noise mitigation).
  - Updates `.claude/observability/adaptive/last-audit.txt` with current ISO timestamp on success (consumed by Phase 11).
- `templates/commands/hm/personalization-audit.md.j2` (NEW) — tri-IDE command template.
- **Calibration milestone (validator W7 follow-up)**: rubric is `v0` for first release. Follow-up PLAN reviews calibration after 30+ projects have run audit. v0 boundaries are conservative; if many projects score Platinum on day 1, boundaries tighten.
- `tests/unit/test_personalization_audit.py` (NEW): rubric scoring per tier (4 fixtures: pure Bronze / Silver / Gold / Platinum project state), action item ranking, evidence emission per ADR-011 schema, dropped-item filter, schema_version filter on jsonl reader.
- **No-network test extension** (validator W4): `tests/unit/test_no_network.py` covers `/hm:personalization-audit` invocation.

**Out of scope:** SessionStart drift hint (Phase 11). Calibration after 30+ projects (follow-up PLAN).

**Exit criterion:** `uv run pytest tests/unit/test_personalization_audit.py tests/unit/test_no_network.py -q && uv run mypy --strict src/harness_maker/personalization_audit.py`. Manual: run `/hm:personalization-audit` on harness-maker repo, output prints composite score + per-layer scores + ranked actions; exit code 0.

**Risk:** medium. Rubric calibration (v0 boundaries) is a conservative guess; iteration in follow-up PLAN. ADR-011 fixed boundaries reduce Goodharting surface vs Phase-10-time decision.

**Rollback point:** Revert Phase 10 files; ai-readiness untouched. Telemetry from Phase 9 still accumulates in jsonl but no consumer.

### Phase 11: B5 — SessionStart Drift Surface

**Scope:** SessionStart hook template (extend — read `.claude/observability/adaptive/overrides.jsonl` line count + last `/hm:personalization-audit` run timestamp from `.claude/observability/adaptive/last-audit.txt`; if line count >= AdaptiveConfig.audit_session_threshold OR days since last audit >= AdaptiveConfig.audit_days_threshold, emit hint via `additionalContext`), `tests/unit/test_session_start_drift.py` (NEW — threshold logic per condition).

**Out of scope:** Documentation (Phase 12).

**Exit criterion:** `uv run pytest tests/unit/test_session_start_drift.py -q`. Manual: simulate >30 sessions overrides + start session, verify hint shown.

**Risk:** low.

**Rollback point:** Revert Phase 11 hook extension; existing SessionStart drift visibility (commit ca48462) unaffected.

### Phase 12: Verification + Documentation + Version Bump

**Scope:**
- `tests/e2e/test_personalization_dogfood.py` (NEW): `/hm:configure` on harness-maker repo itself; assert detected `frameworks/package_manager/ci_provider`; assert no churn on existing `harness.yaml` axes; assert foreign-config import path works on synthetic test fixture.
- `tests/e2e/test_personalization_external.py` (NEW per ADR-010 amendment, validator W6): clone or vendor **`github/spec-kit`** into `tests/e2e/fixtures/external-project-spec-kit/` (locked at PLAN time). Run full `/hm:configure` flow. Assert all 3 ADR-010 failure modes have their mitigations fire (low-confidence detection produces no recommendation; foreign-config import shows confirm UI before any write; `/hm:personalization-audit` output filters items with zero observations). If spec-kit lacks any of the 6 foreign-AI-config types, supplement under `tests/e2e/fixtures/foreign-configs-supplement/<type>` per ADR-010 amendment.
- `README.md` (extend): Personalization Architecture section — detection depth, foreign config import (single-source policy + Cursor power-user constraint per ADR-003 Success Criteria), adaptive layer, opt-out flags.
- `TECH_SPEC.md` (extend): confidence-bucketed UI semantics, `@hm:harness:*` marker family, rubric tier definitions per ADR-011.
- **5-file version bump (validator W11)**: `0.11.6 → 0.12.0` synchronized across:
  1. `.claude-plugin/plugin.json`
  2. `.cursor-plugin/plugin.json`
  3. `.codex-plugin/plugin.json`
  4. `pyproject.toml`
  5. `src/harness_maker/__init__.py`
  - CLAUDE.md §버전업 정책 explicit; 0.4.9 / 0.9.0 footgun. Verification step in exit criterion below.
- `CHANGELOG.md` (extend): 0.12.0 entry covering all sub-tracks landed.

**Out of scope:** Track B-extra (B2/B3) and Track C — follow-up PLAN.

**Exit criterion:**
- `uv run pytest tests/e2e/test_personalization_dogfood.py tests/e2e/test_personalization_external.py -q`
- `uv run ruff check src tests && uv run mypy --strict src`
- `python -c "import json; from pathlib import Path; v=set(); v.add(json.loads(Path('.claude-plugin/plugin.json').read_text())['version']); v.add(json.loads(Path('.cursor-plugin/plugin.json').read_text())['version']); v.add(json.loads(Path('.codex-plugin/plugin.json').read_text())['version']); import tomllib; v.add(tomllib.loads(Path('pyproject.toml').read_text())['project']['version']); from harness_maker import __version__; v.add(__version__); assert v == {'0.12.0'}, f'version drift: {v}'"`
- Manual: read README diff, verify Personalization Architecture section present + Cursor power-user constraint stated.

**Risk:** low. Verification only.

**Rollback point:** Revert Phase 12 e2e tests + docs + version bump; implementation from Phases 1-11 stays. **Note**: leaving Phase 12 reverted while Phases 1-11 land would publish 0.11.x marketplace metadata for 0.12.x runtime — DO NOT release without Phase 12 complete.

### Execution Status

| Phase | Status | Evidence |
|-------|--------|----------|
| 1     | not started | — |
| 2     | not started | — |
| 3     | not started | — |
| 4     | not started | — |
| 5     | not started | — |
| 6     | not started | (Phase 6 = merged D2+D3 per validator W5) |
| 7     | merged | — (folded into Phase 6 above; phase number retained as marker for cross-references) |
| 8     | not started | — |
| 9     | not started | — |
| 10    | not started | — |
| 11    | not started | — |
| 12    | not started | — |

## 🧪 Testing Strategy

**Unit tests** (per-phase exit criteria above):
- `Confidence` enum + `Recommendation` dataclass schema validation.
- `ProjectProfile` 5 new fields default + round-trip via `answers_from_harness_yaml`.
- `detection_cache` mtime invalidation, 24h ceiling, sha256 keying, corruption recovery.
- `profile.profile()` per-stack fixture (each of 12+ STACK_MANIFESTS), framework precedence, confidence bucket assignment.
- `recommendation` registry, dispatcher, lifecycle for `recommend_wrapup_docs`/`recommend_mcp_servers`/all 4 migrated transitive recommends.
- `foreign_config.detect()` per-file (6 known config types), glob handling.
- `foreign_config.llm_map()` mocked Anthropic, golden mappings per file type.
- `block_merge.py` `@hm:harness:*` marker family parser, merge logic, mixed with existing `@hm:user:*`.
- `foreign_config.apply()` round-trip (user content outside markers preserved byte-for-byte).
- `interview._dispatch_recommendation()` confidence-bucketed routing, yaml comment format, locale-aware AskUserQuestion text.
- `telemetry` `harness_yaml_override` event format, atomic jsonl append, `disable_telemetry` opt-out honored.
- `personalization_audit` rubric scoring per Bronze/Silver/Gold/Platinum tier, action item ranking, evidence-required output per ADR-010.
- SessionStart drift threshold logic (30 sessions OR 14 days).

**Integration-style** (with temp directories):
- Synthetic repo fixtures with each combination of `pyproject.toml` + framework deps; assert correct detection.
- Synthetic foreign-AI-config fixtures (`.cursor/rules/sample.mdc`, `AGENTS.md`, etc.) → mock LLM mapping → confirm UI flow → re-render preserves user content.

**End-to-end** (Phase 12):
- `/hm:configure` dogfood on harness-maker repo itself — full flow, assert no breakage.
- `/hm:configure` on one external OSS project (selection at Phase 12) — full flow, assert mitigations fire for each ADR-010 failure mode (e.g., low-confidence detection produces no recommendation, foreign config dry-run shown before apply, adaptive output requires evidence).

**LLM testing policy** (per CLAUDE.md):
- All LLM calls in unit tests use `mock_anthropic_client` fixture pattern.
- Phase 6 integration test gated by `INTEGRATION=1` env var; default-skipped in CI.

**Snapshot tests** (validator W10 — names + freeze_time pinned):
- `tests/snapshot/test_foreign_config_templates.py` — covers Phase 6 foreign-config Jinja2 templates. `freeze_time = "2026-05-16T00:00:00Z"` (constant, project-wide) so `generated_at` is masked deterministically.
- `tests/snapshot/test_personalization_audit_dashboard.py` — covers Phase 10 command template + dashboard rendering. Same `freeze_time` constant.
- **User-content region rule**: in any round-trip snapshot containing both our templated regions (inside `@hm:harness:*` markers) AND user content (outside markers), user-region content is asserted via `input == output` byte-for-byte (NOT compared as snapshot, which would falsely require freezing user data).

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Detection false-positive erodes user trust (ADR-010 mode A) | high | Per-detection heuristic confidence (ADR-007); only `high` becomes silent default; `medium` always asks; Phase 12 e2e on external project asserts mitigation |
| Foreign config re-generation damages user `.cursor/rules/` (ADR-010 mode B) | high | `@hm:harness:*` inverted markers preserve everything outside (ADR-009); Phase 6 (post-merge) round-trip test enforces; Phase 12 e2e includes synthetic foreign config fixture with custom user content |
| Adaptive layer produces noise without actionable suggestions (ADR-010 mode C) | high | `/hm:personalization-audit` output requires evidence per action item (n observations, top-3 conviction signals); low-signal recommendations filtered before output; rubric calibration in Phase 10 |
| LLM mapping (D2) non-determinism produces incorrect axis mappings | medium | Prompt requests strict JSON schema; parse fail → empty mapping (graceful degrade); golden fixtures cover 6 file types; user explicit confirm UI in Phase 6 (post-merge) means any LLM mistake is caught before write |
| `detection_cache` stale due to missing manifest in `CACHED_MANIFESTS` constant | medium | Exhaustive constant aligned with `STACK_MANIFESTS` + foreign-AI-config files; Phase 2 test asserts every `STACK_MANIFESTS` key has a `CACHED_MANIFESTS` entry |
| `block_merge.py` regression: new `@hm:harness:*` marker family breaks existing `@hm:user:*` | medium | Parser tests must cover all 4 cases (only user / only harness / both / neither); existing `@hm:user:*` test suite kept as regression baseline |
| Telemetry capture missed because SessionStart hook doesn't fire | medium | Fallback poll on next `/hm:configure` invocation reads git diff HEAD..HEAD~5 to backfill recent overrides |
| `/hm:personalization-audit` rubric calibration off — Bronze too forgiving or Platinum unreachable | medium | Rubric in YAML (not code) — easy to tune via `rubrics/personalization.yaml` edit + version pin; initial values conservative |
| 12-phase scope underestimated, slips beyond two release cycles | medium | Phase decomposition is independent — incremental land per phase; each phase has rollback point; phases 1/2 standalone (rebase-friendly); Track A and Track D land independently usable |
| Privacy-conscious user surprised by default-on telemetry (ADR-005) | low-medium | `/hm:configure` exit summary mentions adaptive telemetry + opt-out flag; README Personalization Architecture section explicit |
| Cursor power-user wants to keep `.cursor/rules/` solely under their control | low-medium | Document the constraint in README (single-source means we re-generate); future follow-up PLAN can add ADR-003-hybrid escape hatch |
| Track B-extra (B2/B3) follow-up PLAN deferred indefinitely | low | Open RESEARCH-personalization-depth-2026-05 §Open Questions stays a backlog reference |
| **Concurrent `/hm:configure` runs corrupt detection cache JSON** (validator C2) | medium | Phase 2 mandates `harness_maker.io_utils.atomic_write` (CLAUDE.md §실행 패턴); explicit `test_corruption_recovery` + `test_concurrent_writes_no_tear` in Phase 2 test list; last-writer-wins documented |
| **`@hm:harness:*` marker family disambiguation in mixed/nested files** (validator W2) | medium | Phase 6 test scope expanded: 6 explicit cases incl. mismatched-pair raises typed error, literal `@hm:` inside fenced code skipped, nested markers forbidden |
| **Phase 9 partial rollback leaves dead `AdaptiveConfig` in `harness.yaml`** (validator C3) | low-medium | `/hm:status` warns when `adaptive` block present but no telemetry events recorded in 30 days; rollback procedure documented (delete `.claude/observability/adaptive/` directory if Phase 9 reverted) |
| **`harness_yaml_override` schema_version drift between Phase 9 emitter and Phase 10 reader** (validator C3) | low | `schema_version: 1` mandatory on every record; Phase 10 reader skips unknown versions with warning; future bump requires explicit migration table |
| **0.11.x → 0.12.0 silent surprise: existing-user upgrade flips preset/dev_mode to silent default** (validator W3) | medium | Phase 8 assigns existing 4 transitive recommends `medium` confidence one release; backward-compat regression test asserts zero diff on round-trip; tighten in follow-up release after telemetry shows zero override pattern |
| **`/hm:personalization-audit` emits HTTP traffic (privacy violation)** (validator W4) | low | `tests/unit/test_no_network.py` monkeypatches `socket.socket`; ADR-005 positive obligation; CI guard via `pytest-socket` dev-dep optional |
| **Existing `0.11.x` `.cursor/rules/*.mdc` mis-handled on first encounter post-upgrade** (validator W9) | medium | ADR-009 amendment locks migration policy; Phase 6 test scope explicitly covers 0.11.x → 0.12.0 file upgrade |
| **5-file version-sync footgun (0.11.6 → 0.12.0 partial bump)** (validator W11) | medium | Phase 12 exit criterion includes Python one-liner asserting all 5 files report `0.12.0`; CLAUDE.md §버전업 정책 cited |
| **External e2e repo (`github/spec-kit`) lacks foreign-AI-config types at vendoring time** (ADR-010 amendment) | low-medium | Supplement under `tests/e2e/fixtures/foreign-configs-supplement/<type>` per ADR-010 amendment; documented as expected fallback |

## ✅ Success Criteria

- [ ] `ProjectProfile` carries 5 new fields (`frameworks`, `package_manager`, `ci_provider`, `foreign_ai_configs`, `detection_confidence`); old YAML loads via default fallback.
- [ ] `STACK_MANIFESTS` covers 12+ stacks; framework detection populates `frameworks: list[str]` for python/node/rust at minimum.
- [ ] `detection_cache` invalidates on manifest mtime change AND after 24h hard ceiling.
- [ ] Each `recommend_<axis>(profile)` returns a `Recommendation` with explicit `Confidence` bucket per ADR-007.
- [ ] `/hm:configure` confidence-bucketed dispatch: high → silent + yaml comment, medium → AskUserQuestion, low → stock default.
- [ ] Foreign config detection covers all 6 known files (`.cursor/rules/`, `AGENTS.md`, `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`, `.github/copilot-instructions.md`).
- [ ] Foreign config LLM mapping returns axis mapping with content-sha256 caching.
- [ ] `block_merge.py` parses both `@hm:user:*` and `@hm:harness:*` marker families; round-trip preserves user content outside `@hm:harness:*` markers byte-for-byte.
- [ ] `harness_yaml_override` telemetry event recorded on each axis edit; opt-out honored.
- [ ] `/hm:personalization-audit` produces Bronze/Silver/Gold/Platinum composite score + ranked `ActionItem` list.
- [ ] SessionStart drift hint surfaces after 30 sessions OR 14 days since last audit.
- [ ] Phase 12 dogfood + 1 external project e2e tests pass.
- [ ] No new Python runtime dependency added.
- [ ] All ADR-010 failure mode mitigations have a test asserting them (not just risk-register entries).
- [ ] **Existing 0.11.x users upgrading see no surprise silent-default changes on `preset`/`dev_mode`** (validator W3 backward-compat guard).
- [ ] **`/plugin update` advertises 0.12.0 across Claude Code / Cursor / Codex marketplaces** (validator W11 5-file sync).
- [ ] **`tests/unit/test_no_network.py` passes** — monkeypatched `socket.socket`, no outbound traffic during `/hm:personalization-audit` or SessionStart hook (ADR-005 positive obligation, validator W4).
- [ ] **README Personalization Architecture section explicitly documents the Cursor power-user constraint** — single-source means we re-generate `.cursor/rules/`; opt-out requires disabling our render (ADR-003 Consequences).
- [ ] **`tests/snapshot/*` use the project-wide `freeze_time = "2026-05-16T00:00:00Z"` constant** (validator W10).
- [ ] Rubric YAML at `rubrics/personalization.yaml` matches ADR-011 (composite-score model, fixed boundaries, evidence schema).

## 🔍 Plan Validation

**First-pass validator outcome:** `MAJOR_REVISION` (3 critical + 11 warning + 1 nit critiques).

**Resolution log:**

| # | Validator critique | Severity | Resolution |
|---|-------------------|----------|------------|
| C1 | Phase 10 rubric tier semantics not designed | critical | **R5 Q1 interview** → ADR-011 (NEW) — composite-score model with fixed boundaries; Phase 10 scope updated |
| C2 | Phase 2 cache concurrency / atomic_write | critical | Patched — Phase 2 mandates `io_utils.atomic_write`; explicit corruption + concurrent-write tests added; risk register row added |
| C3 | Phase 9 rollback trapped state / schema_version drift | critical | Patched — Phase 9 schema_version=1 mandatory; `/hm:status` warns on dead AdaptiveConfig; rollback procedure documented; risk register rows added |
| W1 | Phase 6 LLM fixture name + assertion shape unspecified | warning | Patched — `mock_anthropic_client` fixture explicit; golden fixture file paths enumerated; subset-match assertion locked |
| W2 | Phase 7 marker disambiguation cases incomplete | warning | Patched — Phase 6 (post-merge) test scope expanded to 6 cases (mismatched/nested/escaped) |
| W3 | Phase 8 backward compat for existing 4 transitive recommends | warning | Patched — existing 4 axes assigned `medium` confidence one release; backward-compat regression test added; Success Criteria entry |
| W4 | ADR-005 missing no-network test | warning | Patched — ADR-005 positive obligation amendment; `tests/unit/test_no_network.py` added to Phase 9 + Phase 10 test lists; Success Criteria entry |
| W5 | Phase 5/6/7 serial chain — D2 alone has no user value | warning | Patched — Phase 6 + Phase 7 MERGED into single "Phase 6: D2+D3"; Phase 7 retained as marker for cross-references; ADR-002 dependency chain clarified inline |
| W6 | Phase 12 external repo selection deferred | warning | **R5 Q2 interview** → ADR-010 amendment locking `github/spec-kit` with selection criteria recorded for future swaps |
| W7 | Multiple deferred decisions throughout PLAN | warning | Patched — each deferred decision either folded (R5) or converted to explicit Success Criteria / scope item / amendment |
| W8 | Phase 9 yaml-override capture hole for uncommitted edits | warning | Patched — primary capture site = `/hm:configure`-exit pre/post comparison (no git dependency); SessionStart secondary; dedup key shared |
| W9 | ADR-009 missing migration policy for existing 0.11.x files | warning | Patched — ADR-009 amendment locks migration policy; Phase 6 test scope covers explicit upgrade path |
| W10 | Snapshot test names + freeze_time + user-region rule unspecified | warning | Patched — Testing Strategy names files (`test_foreign_config_templates.py`, `test_personalization_audit_dashboard.py`); `freeze_time = "2026-05-16T00:00:00Z"` constant; user-region byte-for-byte rule explicit |
| W11 | 5-file version sync (0.11.6 → 0.12.0) missing | warning | Patched — Phase 12 scope adds 5-file version bump; exit criterion includes Python one-liner asserting `{0.12.0}`; Success Criteria entry |
| N1 | Phase 8 tri-IDE dispatch helper unnamed | nit | Patched — helper named `_dispatch_recommendation(rec, *, target)`; tri-IDE payload-equivalence test added |

**Second-pass validator outcome:** `NEEDS_REVISION` (2 warnings, 0 critical). All first-pass critical/warning items confirmed resolved. Two new warnings surfaced as fallout of revision pass:

| # | Second-pass critique | Severity | Resolution |
|---|---------------------|----------|------------|
| W12 | Risk register stale "Phase 7" references (round-trip + confirm UI) post-merge | warning | Patched directly — both cells updated to "Phase 6 (post-merge)"; no additional interview needed (mechanical consistency fix) |
| W13 | ADR-011 wording "Phase 10 owns layer-score formulas" inconsistent with formulas being PLAN-locked | warning | Patched directly — ADR-011 Decision section now embeds the L1/L2/L3 formulas inline + states they are "locked in this PLAN... Future calibration is YAML-only" |

**Final outcome:** `MAJOR_REVISION_RESOLVED` (3 critical + 11 warning + 1 nit from first pass + 2 warning from second pass, all resolved). No third validator pass invoked per protocol (NEEDS_REVISION resolves with single revision; only MAJOR_REVISION triggers re-validation).
