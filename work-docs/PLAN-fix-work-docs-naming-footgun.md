---
type: plan
task_slug: fix-work-docs-naming-footgun
status: complete
created: 2026-05-15
tags: [harness-maker, plan, naming, templates, verify-stage, footgun]
interview_rounds: 4
adrs: 5
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Two-layer guardrail (stage template warning + verify.md.j2 advisory probe) against work_docs/ vs work-docs/ LLM footgun"
---

## 🎯 Executive Summary

**TL;DR**: `harness.yaml` uses YAML key `work_docs:` but value `work-docs/`. LLMs reading the config conflate the two names and occasionally write artifacts to a non-existent `work_docs/` directory. Fix is two-layer: (1) explicit disambiguation in 4 stage-template Outputs sections (preventive), (2) advisory non-blocking probe inside `verify.md.j2` stage body (detective). The `verify-before-completion` skill stays at exactly 6 gating checks — no doc-truth drift. Schema unchanged.

**What/Why**:
- *What*: 5 file edits in `src/harness_maker/templates/` (4 stage templates + verify.md.j2 stage body) + 1 new automated test + version bump 0.11.5 → 0.11.6 + manual cleanup of 2 files in `~/edge_testfarm_os`.
- *Why*: Eliminate LLM footgun without forcing schema migration. Cost is ~30 LoC; benefit is eliminating one recurring confusion class.

**Key Decisions**:
- Schema unchanged; guardrail-only (→ ADR-001).
- Ad-hoc artifacts allowed inside `work-docs/` (→ ADR-002).
- Two-layer defense (prevention + detection); Layer 1 coverage is honestly bounded — only LLMs that read the 4 edited templates are protected by Layer 1 (→ ADR-003).
- User cleanup is manual this session, not tooled. Pre-release, no backward-compat / migration code needed (→ ADR-004).
- Detection layer is WARN-only inside the verify stage (NOT inside the verify-before-completion skill — that stays at 6 checks) (→ ADR-005).

**Estimated Impact**: ~30 LoC across 5 source files + 1 test file. Zero behaviour change for users whose disk is already clean. No risk of regression in existing tests (snapshot diffs limited to the 5 edited files).

---

## 🎙️ Interview Transcript

| # | Round | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | 1 | Architecture | Naming strategy: schema vs rename | A. Schema unchanged + guardrail | ADR-001 |
| 2 | 1 | Scope | Ad-hoc artifacts inside `work-docs/`? | Allowed | ADR-002 |
| 3 | 2 | Implementation | Guardrail mechanism location | Stage templates + verify skill (both) | ADR-003 |
| 4 | 2 | Tooling scope | Migration tool vs manual cleanup | Manual only | ADR-004 |
| 5 | 3 | Failure handling | verify check action on detection | WARN only + migration command | ADR-005 |
| 6 | 4 (validator follow-up) | Architecture | Probe location to preserve "6 checks" contract | A. Move probe to verify.md.j2 stage body | ADR-003, ADR-005 (refined) |
| 7 | 4 (validator follow-up) | Risk acceptance | Layer 1 ad-hoc-invocation bypass | C. Document the limit honestly in ADR-003 | ADR-003 (refined) |
| 8 | 4 (validator follow-up) | Scope | Pre-release backward-compat / opt-out marker | Not needed (pre-release) | ADR-004 (refined) |

---

## 📐 Architecture Decision Records

### ADR-001: Keep `work_docs:` / `work-docs/` naming asymmetry
**Status:** Accepted (2026-05-15, via /hm:plan interview)
**Context:** `harness.yaml` YAML key is `work_docs:` (snake_case) but the value pointing at the directory is `work-docs/` (hyphen). LLMs confuse the two; the recurring footgun is an LLM writing artifacts to a non-existent `work_docs/`.
**Decision:** Keep both as-is. Add guardrails instead of renaming.
**Consequences:**
- ✅ Zero impact on installed harnesses (no migration code, no schema bump).
- ⚠️ Footgun stays latent in the schema; defence relies on the two guardrail layers landing.
**Rejected alternatives:**
- Rename YAML key → `work-docs:` via Pydantic alias — adds alias complexity, harder to grep, weak ergonomic payoff.
- Rename value → `work_docs/` (snake_case) — forces every existing user to migrate disk state via auto-rename; disruptive.
- Generic rename → `plans_dir: plans/` — biggest break, no clear value.
**Source:** Interview Round 1.

### ADR-002: Ad-hoc artifacts allowed inside `work-docs/`
**Status:** Accepted (2026-05-15)
**Context:** The triggering artifact (`PLAN-daily-architecture-review-20260514.md`) has non-standard frontmatter (`validator_outcome: SELF_REVIEW`). Question: should non-`/hm:plan` artifacts be banned from `work-docs/`?
**Decision:** Allow free-form artifacts inside `work-docs/` (e.g., `daily_review/`, ad-hoc audit reports, scratch notes). The directory is a workspace, not a strict harness output.
**Consequences:**
- ✅ Doesn't restrict user creativity.
- ⚠️ The detection probe can't assert "every file under `work-docs/` matches a harness schema", so its scope is limited to checking the wrong-directory case (`work_docs/`) and not enforcing file-naming conventions.
**Rejected alternatives:**
- Strict mode (only `PLAN-*.md`, `RESEARCH-*.md`, `REVIEW-*.md`, `loop-context/` permitted) — too rigid; punishes legitimate ad-hoc usage.
**Source:** Interview Round 1.

### ADR-003: Two-layer guardrail (prevention + detection), with honestly bounded Layer 1 coverage
**Status:** Accepted (2026-05-15)
**Context:** The footgun has two attack surfaces: (a) LLM writes to wrong path during stage execution (preventive control needed); (b) post-hoc detection when the LLM bypassed the templates (detective control needed).
**Decision:**
- **Layer 1 (preventive)**: Each of 4 stage templates (`plan.md.j2`, `research.md.j2`, `review.md.j2`, `wrapup.md.j2`) gets a one-line warning under `## Outputs`: a literal callout that the directory is `work-docs/` (hyphen) and that `work_docs` is the YAML config key, NEVER the directory path. Warning text is hard-coded (not Jinja-interpolated) so it stays meaningful even if a user customises `work_docs.dir`.
- **Layer 2 (detective)**: `verify.md.j2` stage body gets a new `## Advisory probes (non-blocking)` section placed AFTER the 6-checks block. The probe shell-snippet WARNs to stderr (with a copy-pasteable migration command) when it detects a `work_docs/` directory, then exits 0. The `verify-before-completion` skill is **not modified** — its "6 checks" contract is preserved verbatim across all 7 doc sites.
**Consequences:**
- ✅ Two layers triggered at different points in the LLM workflow.
- ✅ Skill description / doc-truth invariant ("6 checks") preserved across SKILL.md.j2, verify.md.j2 (lines 3/17/42/142), HOW-IT-WORKS.md, TECH_SPEC.md.
- ⚠️ **Layer 1 honest scope**: it only protects LLMs that actually load and read these 4 stage templates. Ad-hoc LLM invocations (e.g., the empirically-observed offender `PLAN-daily-architecture-review-20260514.md` which had non-standard frontmatter and was not produced via `/hm:plan`) bypass Layer 1 entirely. Against the observed offender class, the only defence is Layer 2's WARN, which the calling agent can ignore. We accept this and will revisit (e.g., escalate to BLOCKING, or add a Layer 3 to CLAUDE.md) only if telemetry of the WARN shows recurrence.
- ⚠️ Layer 2 only fires when the verify stage is run (`/hm:verify` directly, or wrapup invoking the verify stage when applicable). Autoloop flows that skip the verify stage receive no Layer 2 signal.
**Rejected alternatives:**
- `stuck` agent only — only fires after autoloop blocks; too late.
- `context-linter` only — checks our `.j2` source, not user runtime state.
- Putting the probe inside `verify-before-completion` SKILL — breaks "6 checks" contract across 7 doc sites; rejected in Round 4.
- Layer 3 (CLAUDE.md / AGENTS.md / .cursorrules instruction line covering ad-hoc sessions) — rejected this iteration; revisit if WARN telemetry shows the bypass class is real.
**Source:** Interview Round 2, refined in Round 4 (Q6, Q7).

### ADR-004: User data cleanup is manual this session, no tooling; pre-release skips backward-compat
**Status:** Accepted (2026-05-15)
**Context:** The triggering user (`~/edge_testfarm_os`) has 2 untracked files in `work_docs/`. harness-maker is pre-release (0.11.x), so no backward-compatibility code paths are owed to installed users.
**Decision:** Clean up by hand via `git mv` in this session. Do not add `/hm:doctor`, do not add stage-level self-heal, do not add `.hm-no-work-docs-probe` opt-out marker.
**Consequences:**
- ✅ PR stays small (~30 LoC). No new command surface to maintain.
- ✅ Pre-release status means we are not owed migration code for users with `work_docs/` in their disk state.
- ⚠️ If another pre-release user hits the same footgun, they get the WARN from Layer 2 (when verify stage runs) but must clean up manually. Acceptable given the rarity and the manual remediation is one `git mv` line.
**Rejected alternatives:**
- `/hm:doctor` self-heal command — over-scope; revisit post-release if WARN telemetry shows recurrence.
- Stage self-heal (auto-`AskQuestion` on detection) — adds latency to every stage start.
- `.hm-no-work-docs-probe` opt-out marker for false-positive cases — rejected explicitly by user in Round 4 ("아직 릴리즈 안 됐으니 자동 복구 / 호환 코드 필요 없음").
**Source:** Interview Round 2, refined in Round 4 (Q8).

### ADR-005: Footgun probe is WARN-only, sits in verify.md.j2 stage body (not the SKILL)
**Status:** Accepted (2026-05-15)
**Context:** verify-before-completion SKILL's 6 standing checks all `exit 1` on failure. Question: should the footgun probe halt the workflow, and where does it physically live?
**Decision:**
- **Action**: WARN to stderr + migration command, `exit 0`. Workflow continues.
- **Location**: `verify.md.j2` stage body, in a new `## Advisory probes (non-blocking)` section placed after the existing `## The 6 Checks` block and before `## Output`. **Not** inside `verify-before-completion/SKILL.md.j2` — that stays at exactly 6 checks.
- **Trigger**: probe runs every time the verify stage executes.
- **WARN message**: includes the literal migration command `git mv work_docs/* work-docs/ && rmdir work_docs` so the user can copy-paste.
**Consequences:**
- ✅ Consistent with ADR-002 (ad-hoc artifacts allowed): we can't be certain `work_docs/` is wrong every time, so WARN — not BLOCK — is correct.
- ✅ Preserves verify-before-completion "6 checks" contract; no doc-truth drift across the 7 doc sites referencing that number.
- ⚠️ False-positive risk: any user whose project legitimately has a `work_docs/` directory (from another tool, sibling project, etc.) gets the WARN every verify run. Trade-off accepted — pre-release rarity + WARN-noise wallpaper is acceptable, and (per ADR-004) no opt-out marker.
- ⚠️ Autoloop pipelines that don't invoke the verify stage receive zero Layer 2 signal. Layer 1 (template warnings) is their only defence.
**Rejected alternatives:**
- BLOCKED (exit 1) with migration command — too strict; conflicts with ad-hoc allowance (ADR-002).
- BLOCKED only when files inside `work_docs/` have non-standard frontmatter — too much implementation complexity for the same false-negative class.
- Auto `git mv` from the probe — verify-stage probes are read-only by convention; mutating state from a probe violates that contract.
- Probe inside SKILL.md.j2 — breaks "6 checks" doc-truth; rejected in Round 4.
**Source:** Interview Round 3, refined in Round 4 (Q6).

---

## 🏗️ Technical Design

**Current state:**
- `harness.yaml` YAML key `work_docs:` (snake_case) → value `work-docs/` (hyphen). Resolved everywhere via `{{ config.work_docs.dir }}`.
- 4 stage templates (`plan.md.j2`, `research.md.j2`, `review.md.j2`, `wrapup.md.j2`) each have an `## Outputs` section listing what they write.
- `verify.md.j2` stage template structure: `## The 6 Checks` (line 42) → `## Output` (line 121) → `## Procedure` (line 168) → `## Outputs` (line 177).
- `verify-before-completion/SKILL.md.j2` body: 6 gating checks (PLAN fulfillment, regression, health score, anti-rot pending, security findings, worktree merge-safe).

**Affected components:**
- `src/harness_maker/templates/stages/plan.md.j2` — add 1-line warning under `## Outputs` (line 361).
- `src/harness_maker/templates/stages/research.md.j2` — add 1-line warning under `## Outputs` (line 284).
- `src/harness_maker/templates/stages/review.md.j2` — add 1-line warning under `## Outputs` (line 362).
- `src/harness_maker/templates/stages/wrapup.md.j2` — add 1-line warning under `## Outputs` (line 229).
- `src/harness_maker/templates/stages/verify.md.j2` — insert new `## Advisory probes (non-blocking)` section between line 120 (end of "The 6 Checks" block) and line 121 (`## Output`).
- `tests/unit/test_verify.py` — add one test asserting (a) rendered SKILL.md still contains exactly 6 checks (regression guard); (b) rendered verify.md contains `## Advisory probes (non-blocking)`; (c) the probe's bash snippet, when executed against a tempdir containing `work_docs/`, exits 0 and emits "WARN" + the migration command on stderr.
- `tests/snapshot/regenerate.py` re-run to update existing snapshots; expected 5 changed snapshots.
- `pyproject.toml`, `src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json` — version 0.11.5 → 0.11.6 (5-file sync per CLAUDE.md §버전업 정책).

**Out of scope (explicitly):**
- `verify-before-completion/SKILL.md.j2` body and frontmatter — unchanged. "6 checks" contract preserved.
- `verify.md.j2` lines 3, 17, 42, 142 — "6 checks" wording preserved (the new section is separately labelled "Advisory probes").
- `HOW-IT-WORKS.md` line 748 and `TECH_SPEC.md` lines 1034 / 1395 — unchanged.
- CLAUDE.md / AGENTS.md / .cursorrules project-level instruction line — rejected this iteration (ADR-003).
- Any `.hm-no-work-docs-probe` opt-out marker — rejected (ADR-004).
- Any `/hm:doctor` command — rejected (ADR-004).
- Auto-migration of `~/edge_testfarm_os` — rejected (ADR-004); manual section below.

**Architecture: Two-layer topology**

```
Layer 1 — Prevention (source-side, fires when LLM reads a template):
  plan.md.j2     ─┐
  research.md.j2 ─┤── ## Outputs section
  review.md.j2   ─┤   ⚠️ hard-coded warning line about hyphen-vs-underscore
  wrapup.md.j2   ─┘   (NOT Jinja-interpolated)

Layer 2 — Detection (runtime-side, fires when verify stage runs):
  verify.md.j2
    ├─ ## The 6 Checks  (unchanged, BLOCKING)
    └─ ## Advisory probes (non-blocking)  (new)
       └─ work_docs/ footgun probe → WARN to stderr → exit 0

Honest scope:
  Layer 1 protects only LLMs that load these 4 templates.
  Ad-hoc LLM invocations bypass Layer 1; their only defence is Layer 2.
  Autoloop flows that skip the verify stage receive zero Layer 2 signal.
```

**Data flow:** No state change. Both layers are pure text in rendered output. Layer 2 probe is a read-only bash check.

---

## 📝 Implementation Plan

### Phase 1: Add disambiguation warning to 4 stage templates (Layer 1)
- **Scope (in):**
  - `src/harness_maker/templates/stages/plan.md.j2` (insert directly under `## Outputs` at line 361).
  - `src/harness_maker/templates/stages/research.md.j2` (insert directly under `## Outputs` at line 284).
  - `src/harness_maker/templates/stages/review.md.j2` (insert directly under `## Outputs` at line 362).
  - `src/harness_maker/templates/stages/wrapup.md.j2` (insert directly under `## Outputs` at line 229).
- **Scope (out):** `spec.md.j2` (writes to `specs/`, not work-docs/), `execute.md.j2` (read-only against work-docs/), `verify.md.j2` (handled in Phase 2).
- **Content per file (identical hard-coded text, NO Jinja interpolation in the warning itself):**

  ```markdown
  > ⚠️ **Path note:** the directory is `work-docs/` (with hyphen). The YAML key
  > `work_docs` is the config key in `harness.yaml`, NOT a directory name.
  > Never write artifacts under `work_docs/` (underscore) — that path is a
  > known LLM footgun.
  ```

- **Exit criterion (concrete, runnable):**
  - `git grep -l 'known LLM footgun' src/harness_maker/templates/stages/ | wc -l` returns exactly `4`.
  - `uv run python tests/snapshot/regenerate.py` produces clean diffs limited to the 4 changed templates' snapshots.
  - `uv run pytest tests/unit/test_synthesize_snapshot.py -x` green.
- **Risk**: low (text-only, no logic change).
- **Rollback**: revert this commit; the warning text is purely informational and has no downstream consumer.

### Phase 2: Add Layer 2 advisory probe to verify stage + automated test
- **Scope (in):**
  - `src/harness_maker/templates/stages/verify.md.j2` — insert new section between the end of `## The 6 Checks` block (around line 120) and the start of `## Output` (line 121).

    ```markdown
    ## Advisory probes (non-blocking)

    These do NOT gate completion. They surface latent footguns and continue
    with `exit 0` regardless of outcome.

    ### A1. `work_docs/` (underscore) footgun probe

    ```bash
    if [ -d "work_docs" ]; then
      echo "WARN: work_docs/ (underscore) directory found." >&2
      echo "      The harness-maker directory is work-docs/ (hyphen);" >&2
      echo "      work_docs is only the YAML key in harness.yaml." >&2
      echo "      Migration: git mv work_docs/* work-docs/ && rmdir work_docs" >&2
    fi
    exit 0
    ```
    ```

  - `tests/unit/test_verify.py` — add one new test (~15 LoC) named `test_work_docs_footgun_probe`:
    1. Assert the rendered `verify.md` body contains the substring `## Advisory probes (non-blocking)`.
    2. Assert the rendered `verify-before-completion/SKILL.md` contains exactly the substrings `### 1.`, `### 2.`, `### 3.`, `### 4.`, `### 5.`, `### 6.`, and does NOT contain `### 7.` (6-checks regression guard).
    3. Extract the probe bash block from the rendered `verify.md` body, write it to a temp script, create a tempdir with a `work_docs/` subdir, `subprocess.run` the script with `cwd=tempdir`, assert `proc.returncode == 0` and `b"WARN" in proc.stderr` and `b"work-docs/ (hyphen)" in proc.stderr` and `b"git mv work_docs/* work-docs/" in proc.stderr`.
- **Scope (out):**
  - `verify-before-completion/SKILL.md.j2` — completely unchanged.
  - `verify.md.j2` lines 3, 17, 42, 142 — "6 checks" wording untouched.
- **Exit criterion (concrete):**
  - `git grep -c 'Advisory probes' src/harness_maker/templates/stages/verify.md.j2` returns `1`.
  - `git diff src/harness_maker/templates/skills/verify-before-completion/SKILL.md.j2` shows zero changes.
  - `uv run pytest tests/unit/test_verify.py::test_work_docs_footgun_probe -x` green.
  - `uv run pytest tests/unit/test_verify.py -x` overall green.
- **Risk**: low (additive, non-blocking, isolated to the verify stage).
- **Rollback**: revert; the 6 gating checks are independent and stay green.

### Phase 3: Version bump + full snapshot regen + full test/lint suite
- **Scope (in):** 5 sync points per CLAUDE.md §버전업 정책 — `pyproject.toml`, `src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`. Bump 0.11.5 → 0.11.6. Run `uv run python tests/snapshot/regenerate.py`; commit updated `tests/snapshot/` files.
- **Exit criterion (concrete):**
  - `git grep -l '0\.11\.5' -- pyproject.toml 'src/harness_maker/__init__.py' '.claude-plugin/plugin.json' '.cursor-plugin/plugin.json' '.codex-plugin/plugin.json'` returns no hits.
  - `git grep -l '0\.11\.6' -- pyproject.toml 'src/harness_maker/__init__.py' '.claude-plugin/plugin.json' '.cursor-plugin/plugin.json' '.codex-plugin/plugin.json'` returns exactly 5 hits.
  - `uv run pytest -x` green (full suite).
  - `uv run ruff check` clean.
  - `uv run ruff format --check` clean.
  - `uv run mypy --strict src/` clean.
- **Risk**: low (patch bump, additive content).
- **Rollback**: revert version commit + snapshot commit.

### Manual cleanup steps (outside harness-maker repo — performed by user/Claude in this session, NOT by /hm:execute)

These steps fix `~/edge_testfarm_os` and are NOT a `/hm:execute` phase. Independent of Phases 1–3; run in either order.

```bash
cd ~/edge_testfarm_os
git mv work_docs/PLAN-daily-architecture-review-20260514.md \
       work-docs/PLAN-daily-architecture-review-20260514.md
git mv work_docs/daily_review work-docs/daily_review
rmdir work_docs
git status   # verify clean
git commit -m "chore: migrate work_docs/ → work-docs/ (naming footgun cleanup)"
```

Optional follow-up (content cleanup, not required for fix correctness): the 2 moved files reference themselves via `work_docs/` paths in their bodies (e.g., the daily-review markdown opens with `PLAN: work_docs/PLAN-...md`). After the rename, grep inside the moved files for `work_docs/` text and update to `work-docs/`:

```bash
grep -rln 'work_docs/' work-docs/   # locate references
# manually edit the matches
```

---

## 🧪 Testing Strategy

- **Unit (existing):** snapshot suite catches accidental drift in stage-template rendering. Phase 1 produces 4 changed snapshots (one per stage), Phase 2 produces 1 changed snapshot (verify stage). Phase 3's regen step picks these up.
- **Unit (new, Phase 2):** one test in `tests/unit/test_verify.py` asserting (a) verify stage rendered output contains the advisory section heading; (b) SKILL.md still has exactly 6 checks — regression guard against accidental scope creep into the SKILL; (c) probe bash snippet exits 0 and emits the expected WARN strings on stderr when run against a tempdir containing `work_docs/`.
- **Lint/type:** `ruff check`, `ruff format --check`, `mypy --strict` — Phase 3 exit criteria.
- **Integration:** no new integration test. Existing snapshot suite plus the new unit test cover the failure modes.
- **Manual sanity:** after Phases 1–3 land, in a scratch directory: `mkdir scratch && cd scratch && mkdir work_docs && uv run --with /home/noel/harness-maker python -m harness_maker.cli render --stage verify --out /tmp/verify.md && bash <(sed -n '/work_docs.*footgun probe/,/^exit 0/p' /tmp/verify.md)` — observe WARN on stderr.

---

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| LLM still writes to `work_docs/` despite Layer 1 warning text | medium | Layer 2 probe catches at verify stage. If both fail (verify stage skipped + LLM didn't read templates → ad-hoc invocation case), telemetry of repeat occurrences will trigger an ADR revisit (Layer 3 CLAUDE.md instruction or BLOCKING escalation). ADR-003 explicitly bounds the coverage. |
| `verify-before-completion` SKILL accidentally edited (6-checks regression) | medium | Phase 2 Test (b) asserts SKILL has exactly 6 checks and no `### 7.` heading. Snapshot regen plus this test together block the regression. |
| Snapshot regen produces unrelated drift | low | Phase 3 runs full suite before commit. Diff review limited to the 5 expected changed snapshots (4 stage templates + 1 verify stage). |
| `git mv` in user project loses git history | low | `git mv` preserves rename detection. Verify with `git log --follow work-docs/PLAN-daily-architecture-review-20260514.md` post-move. |
| User has stale `work_docs/` text references inside file content | low | Documented in Manual Cleanup as optional content cleanup; not required for the fix's correctness, but advised. |
| False positive when user legitimately has a `work_docs/` from another tool | low | Acknowledged in ADR-005. WARN-only; user can ignore. No opt-out marker added (ADR-004, pre-release). |
| Autoloop flows that skip the verify stage receive no Layer 2 signal | medium | Acknowledged in ADR-003. Layer 1 is their only defence; if telemetry shows ad-hoc bypass still recurs, revisit ADR-003 to add a Layer 3 (CLAUDE.md instruction). |

---

## ✅ Success Criteria

- [x] 4 stage templates (`plan.md.j2`, `research.md.j2`, `review.md.j2`, `wrapup.md.j2`) contain the disambiguation warning under `## Outputs` (`git grep -l 'known LLM footgun' src/harness_maker/templates/stages/ | wc -l` == 4).
- [x] `verify.md.j2` contains `## Advisory probes (non-blocking)` section after `## The 6 Checks` block.
- [x] `verify-before-completion/SKILL.md.j2` is unchanged; "6 checks" doc-truth preserved across all 7 doc sites.
- [x] New test `tests/unit/test_verify.py::test_work_docs_footgun_probe` green.
- [x] Full test/lint/type suite green: `uv run pytest -x`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy --strict src/`.
- [x] Version bumped to 0.11.6 in all 5 sync points; no remaining `0.11.5` references in those 5 files.
- [x] Snapshot regen committed; diff limited to the 5 expected files.
- [x] `~/edge_testfarm_os/work_docs/` directory removed; its 2 files relocated under `~/edge_testfarm_os/work-docs/` with git history preserved (rename detection via `git log --follow`).
- [x] Manual sanity probe (scratch tempdir with `work_docs/`) prints WARN + migration command on stderr and exits 0.

---

## 🔍 Plan Validation

- **Pass 1 (plan-validator agent, 2026-05-15):** **NEEDS_REVISION** with 2 critical + 3 warning + 1 nit critiques.
  - Critical #1: 6-checks contract divergence across 7 doc sites if probe added to `verify-before-completion` SKILL — **Resolved** by Round 4 Q6: probe relocated to `verify.md.j2` stage body (ADR-003, ADR-005 refined). SKILL stays unchanged.
  - Critical #2: Layer 1 doesn't cover ad-hoc LLM invocations (the empirical offender class) — **Resolved** by Round 4 Q7: limit acknowledged honestly in ADR-003 Consequences; revisit if telemetry shows recurrence.
  - W3 Phase 1 exit criterion vague / invented paths — **Resolved** by rewriting Phase 1 exit criterion with real paths (`git grep`, real regen script, real test file).
  - W4 "no new test files needed" overstated — **Resolved** by adding the named test in Phase 2 scope (`tests/unit/test_verify.py::test_work_docs_footgun_probe`, ~15 LoC).
  - W5 false-positive risk without opt-out mechanism — **Resolved** by Round 4 Q8: pre-release, no opt-out marker; trade-off acknowledged in ADR-005 Consequences.
  - N6 warning text uses Jinja interpolation that breaks if user customised `work_docs.dir` — **Resolved**: Phase 1 warning text is now hard-coded literal `work-docs/` (no Jinja interpolation in the warning sentence itself).
- **Final outcome:** **NEEDS_REVISION_RESOLVED**. Validator was not re-run (per /hm:plan procedure: NEEDS_REVISION runs one follow-up round, then writes — no mandatory re-validation for non-MAJOR outcomes).
