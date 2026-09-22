---
type: review
task_slug: docs-release-sync
status: approved
created: 2026-09-22
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: docs-release-sync
  computed_at: 2026-09-22T07:45:00Z
---

# REVIEW: Release documentation synchronization

## 🎯 Round 1 Summary

- Grade: **C** (`P0=0`, `P1=5`)
- Coverage: all seven mandatory lenses exercised; no coverage blocker.
- Auto-fix pending: five unique consensus-passed P1 findings.
- Manual items: two accepted cross-model P1 findings and two P2 findings.
- Second opinion: `codex` invoked; PIDA accepted 4/4 findings. The mechanical oracle gatherer
  could not associate untracked Python files or Markdown with a configured per-path command;
  PIDA therefore validated them from the frozen diff and SPEC context rather than treating the
  missing oracle as refutation.

## 🔍 Drift Findings

No scope violation or SPEC scenario miss. The changed test selector and live-plugin test are
covered by Phase 4's targeted/full verification scope and the user's explicit instruction to
repair every full-suite failure. No `common_ground_marks` are present.

## ✅ Consensus Findings

### P1

1. `4e3bc064c4213d98` — `docs/HOW-IT-WORKS.md:286`: current English and Korean guides and an
   Architecture sentence still describe seven stages and the retired `plan` stage.
2. `baa9665f860042b3` — `src/harness_maker/documentation_contract.py:238`: required sections
   omit `mechanisms` and `version-files`, so either visible contract can disappear silently.
3. `423ab43f89e6f643` — `src/harness_maker/release_identity.py:148`: postpublication retries
   execute in a tight loop and race remote propagation. Robustness and concurrency agree.
4. `1d6751fcea49a246` — `tests/structural/test_documentation_contract.py:187`: tests mutate
   section contents but never prove deletion of the two omitted required sections fails.
5. `4efb07dc5eb95623` — `tests/unit/test_release_identity.py:178`: workflow assertions never
   execute the CLI adapter whose nonzero status makes both release boundaries blocking.

`ea838a77237c3a03` is the concurrency duplicate of `423ab43f89e6f643`.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

- P1 `eb474138d637a52a` — resolved after explicit human approval: the hermeticity test now
  derives the expected tag from `pyproject.toml` instead of pinning `v0.59.0`.
- P1 `1b76888c7f762929` — resolved after explicit human approval: validation now rejects the
  observed wrong stage order, four-version-file claim, and operational `plan-validator` prose;
  mutations use the real living documents outside marker blocks.
- P2 `1ded9b3a30bc0dae` — the Korean guide retains the seven-stage sequence; this is also covered
  by consensus finding `4e3bc064c4213d98` but cannot be merged across severity tiers.
- P2 `d9818cfdb09fdb70` — backticks inside HTML comments are parsed as visible marker content.

## 🤝 Disagreements

The Korean stale-pipeline defect was P1 from the consistency lens and P2 from Codex. The
cross-tier findings remain independent as required; the P1 lens finding drives repair.

During `confirm-2`, the core reviewer classified `print(json.dumps(...))` in the standalone
release-identity adapter as P1. It was rejected: the repository defines no ban on `print`, Ruff
does not enable `T201`, and multiple peer machine-readable CLI adapters use the same primitive.
No functional, security, or contract failure was identified.

## 🧊 Cross-model findings (frozen @ round 1)

`frozen_at_round: 1`

`models: [codex]`

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---:|---|---|---|---|---|---|---|
| `eb474138d637a52a` | codex | P1 | `tests/unit/test_release_identity.py` | 115 | Hermeticity test pins the real checkout to v0.59.0 | `assert isolated.prepublish_identity("v0.59.0", _ROOT).ok` | false | accepted | A consistent future version bump breaks the hard-coded assertion. | resolved | Expected tag is derived from the checkout's project version; focused and full verification passed. |
| `1b76888c7f762929` | codex | P1 | `src/harness_maker/documentation_contract.py` | 151 | Marker-focused validation allows contradictory current guidance | Known stale current prose forms return no validation errors. | false | accepted | Narrow marker and phrase validation accepts observed stale workflow prose. | resolved | Real-document mutations for stage order, version-file count, and operational validator naming now fail; focused and full verification passed. |
| `1ded9b3a30bc0dae` | codex | P2 | `docs/HOW-IT-WORKS.ko.md` | 240 | Korean guide retains seven stages and plan | Lines 240–243 publish the retired sequence. | false | accepted | Direct file evidence confirms the contradiction. | resolved | Both locale guides now publish the canonical six-stage sequence; focused and full verification passed. |
| `d9818cfdb09fdb70` | codex | P2 | `src/harness_maker/documentation_contract.py` | 126 | HTML-commented catalog content is treated as visible | Commented marker content still validates. | false | accepted | Raw Markdown token extraction does not model rendered visibility. | resolved | Marker extraction now removes nested HTML comments and the hidden-content mutation fails as required. |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init) | C | — | 5 graded P1 + 4 manual | — |
| 2 | A | 5 consensus P1 fixes | 2 manual P1 | 0 |

### Iteration 2 (Grade: C → A)

Fixes applied: 5

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Correct current seven-stage prose | `docs/HOW-IT-WORKS*.md`, `docs/ARCHITECTURE.md` | Applied · caused_by=none |
| 2 | P1 | Require complete five-section marker schema | `documentation_contract.py` | Applied · caused_by=none |
| 3 | P1 | Add bounded propagation backoff | `release_identity.py` | Applied · caused_by=none |
| 4 | P1 | Add missing-section and observed-prose mutations | `test_documentation_contract.py` | Applied · caused_by=none |
| 5 | P1 | Test CLI nonzero exit propagation | `test_release_identity.py` | Applied · caused_by=none |

Verification: 72 focused tests, ruff, format, strict mypy, and the full suite
(`9232 passed, 104 skipped, 3 xfailed`) passed. Re-review: skipped — `churn 0.16 < 0.30`.
Remaining: 2 manual P1 | New issues introduced: 0
Churn: 0.15853658536585366 (max: `tests/unit/test_release_identity.py`, measured 7, excluded 0)

Round 2 gate: Grade A; confirmation required.
human_review_needed: true

## 🔒 Confirmation passes

### confirm-1 — FAIL

All seven mandatory lenses returned and coverage was complete. Four new P1 findings were
accepted:

1. `current_changelog()` did not require a unique leading `[Unreleased]` section.
2. Recursive discovery of additional current `docs/**/*.md` files lacked a repository-level
   discrimination test.
3. The `mechanism-count` mutation changed an id while preserving the count.
4. Localized inventory mutations did not span README/HOW-IT-WORKS, both locales, agents/skills,
   and missing/extra cases.

The separately budgeted confirmation repair added the boundary error, recursive discovery
control, a real count mutation, and the complete localized mutation matrix. Focused structural
tests, Ruff, strict mypy, and the full pytest suite all passed.

### confirm-2 — PASS

All seven mandatory lenses returned and coverage was complete. No new consensus-passed P0/P1
finding remained. The unsupported bare-`print` style claim is recorded under Disagreements.

### Human-authorized manual finding repair — PASS

The user explicitly approved repair of both remaining single-model P1 findings. The release
hermeticity test now reads the live project version, and the documentation contract checks the
three observed contradictory operational-prose forms outside marker blocks. The focused 95-test
set, Ruff, strict mypy, and the complete pytest suite passed with exit code 0.

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `docs/ARCHITECTURE.md` | 574 → 574 | null | null | not-python |
| `docs/HOW-IT-WORKS.ko.md` | 2472 → 2472 | null | null | not-python |
| `docs/HOW-IT-WORKS.md` | 2920 → 2920 | null | null | not-python |
| `src/harness_maker/documentation_contract.py` | 300 → 304 | 46 → 47 | 3 → 3 | measured |
| `src/harness_maker/release_identity.py` | 231 → 233 | 25 → 26 | 2 → 3 | measured |
| `tests/structural/test_documentation_contract.py` | 365 → 405 | 60 → 65 | 12 → 15 | measured |
| `tests/unit/test_release_identity.py` | 209 → 246 | 46 → 52 | 3 → 3 | measured |

Final grade: **A**
Iterations used: **2 / 3**
Exit reason: **converged**
Oscillation: none detected

Status: **APPROVED**
human_review_needed: **false** — both accepted single-model P1 findings were explicitly approved,
repaired, and verified.
Counters: unreviewed **0** · prior-fix **0** · unattributed **0**
