---
type: plan
task_slug: install-cmd-cifence
status: complete
created: 2026-05-22
tags: [harness-maker, plan, ci, regression-test, codex, readme]
interview_rounds: 2
adrs: 2
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "ADR-001 Q4 trigger fires (3rd recurrence): CI install-cmd regression test + Codex first-run Skill clarification."
---

## 🎯 Executive Summary

**TL;DR:** The "README overpromises IDE parity" failure class just hit its
3rd occurrence in 6 weeks. The deferred Q4 regression test from
[`PLAN-readme-codex-truthification`](PLAN-readme-codex-truthification.md)
ADR-001 promotes to P0 per its own trigger condition. This PLAN delivers (A) a
minimal Codex first-run doc clarification, and (B) a CI install-command
regression test that mechanically validates every Bash install command we
ship in the README.

**Recurrence count (the trigger):**
1. 2026-05-19 — `[wiki:gotcha] readme-one-prompt-bash-not-slash`. AI agent
   couldn't invoke built-in slash commands; README rewritten to use Bash.
2. 2026-05-22 — `[wiki:gotcha] codex-marketplace-readme-overpromise`.
   `codex plugin marketplace add Ecro/harness-maker` accepted the
   marketplace but `codex plugin add` failed; README truthified.
3. 2026-05-22 (same day, hours later) — Codex first-run Skill tool
   overpromise. README's prompt says "invoke harness-maker:make via the
   Skill tool" but Codex first-run has no `.agents/skills/hm-make/` yet
   (skills are rendered BY `harness-maker make`); the AI agent stalls
   looking for a skill that doesn't exist.

3 occurrences in 4 days. The structural defect — README claims working
multi-IDE parity that no test verifies — is now treated as a P0 systemic
issue.

**What:**
- **Fix A (doc)**: Audit each IDE's first-run prompt (Claude Code, Cursor,
  Codex). Codex needs a Bash-direct fallback when the Skill tool is not yet
  populated. Claude Code + Cursor are confirmed OK (plugin install registers
  commands invokable by Skill tool immediately after reload).
- **Fix B (test)**: New `tests/integration/test_readme_install_commands.py`
  with positive + negative + lint coverage. CI workflow installs `codex` CLI
  via npm + invokes the test job. Positive tests BLOCKING, negative + lint
  ADVISORY (per ADR-002).

**Key decisions:** [ADR-001](#adr-001-test-mechanism-positive-plus-codex-negative-plus-readme-lint), [ADR-002](#adr-002-ci-gating-positive-blocking-negative--lint-advisory).

**Estimated impact:** ~5 file edits + 2 new files; ~3-4h. Tagged release
**0.23.5** (5-file version sync + new CI dependency = user-visible change).

## 📚 Prior Work

- **`[wiki:gotcha] codex-marketplace-readme-overpromise` (2026-05-22)** —
  Just-written entry. Final sentence is the literal trigger condition that
  this PLAN executes: *"3회째 발생 시 CI install-command e2e test 즉시
  추가 (ADR-001 의 deferred Q4 P0 promote trigger)."*
- **`PLAN-readme-codex-truthification` ADR-001 (2026-05-22)** — Defers Q4
  CI install-cmd test. Re-open trigger: 3rd recurrence → promote to P0.
  This PLAN IS the promote.
- **`[wiki:gotcha] readme-one-prompt-bash-not-slash` (2026-05-19)** — 1st
  occurrence of the class. Established that "what the AI can actually do"
  must match what README promises.
- **`[wiki:pattern] oss-launch-readiness-three-layer` (2026-05-19)** —
  Layer 2 "Positioning surface" includes README accuracy. This PLAN
  hardens that layer with mechanical defense.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | Test mechanism | Architecture | Positive only / + Codex negative / + README lint | B — Positive + Codex CLI negative (npm install codex in CI) | Most thorough; user picked despite the npm-codex CI dependency cost | ADR-001 |
| 2 | CI gating | Risk | All BLOCKING / All ADVISORY / Mixed (positive=BLOCKING, lint=ADVISORY) | C — Mixed | Round 1: positive BLOCKING, lint + negative ADVISORY | ADR-002 (Round 1) |
| 3 | Release vehicle | Process | Single commit on main / 0.23.5 patch | B — 0.23.5 patch | New CI dependency (codex CLI) is user-visible; release notes appropriate | — |
| 4 | Doc fix scope | Architecture | Codex-only / All-IDE audit | B — All-IDE audit | Verify Claude Code + Cursor first-run also work; if not, document; if yes, pin | — |
| 5 | Lint gate (validator-driven Round 2) | Risk | Accept validator (lint=BLOCKING) / Keep ADVISORY / Stepwise | A — Accept validator | Lint IS the regression-class defense; ADVISORY allows the class through | ADR-002 (Round 2 amend) |
| 6 | release.yml scope (validator-driven Round 2) | Architecture | ci.yml only / Add to release.yml too | A — ci.yml only | PR CI gate is sufficient; tag push trusts main's state after PR merge | — |

## 📐 Architecture Decision Records

### ADR-001: Test mechanism — positive + Codex negative + README lint
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** The "README overpromises IDE parity" failure class has recurred
3 times in 4 days. The deferred Q4 test from the prior PLAN's ADR-001 needs
to land as a P0 follow-up. Question: what should the test actually do?
**Decision:** Three test classes in
`tests/integration/test_readme_install_commands.py`:
1. **Positive** — `test_pypi_install_works`: build local wheel, `uv tool install`
   into temp env, assert `harness-maker --version` returns the local version.
2. **Positive** — `test_cursor_git_clone_path_structure`: simulate the
   `git clone ... ~/.cursor/plugins/local/harness-maker` install into a tmp
   dir; assert `.cursor-plugin/plugin.json` is reachable at the expected
   path Cursor scans.
3. **Negative** — `test_codex_marketplace_add_fails_as_documented`: install
   `codex` CLI via npm in CI; run `codex plugin marketplace add <local-repo>`
   then `codex plugin add harness-maker@harness-maker`; assert exit code
   non-zero AND stderr matches `plugin .* was not found in marketplace`. If
   this test ever starts FAILING (i.e., Codex now finds our plugin), README
   needs to be re-truthified to claim native Codex install.
4. **Lint** — `test_readme_install_commands_in_allowlist`: parse README.md
   + README.ko.md, extract every `Bash:` install command, compare against
   an explicit allowlist `EXPECTED_README_INSTALL_COMMANDS`. Fail (advisory)
   if a new command appears that isn't in the allowlist.
**Consequences:**
- ✅ Mechanical regression defense for the class — any new README install
  command must be added to the allowlist + tested before merge.
- ✅ Negative test catches Codex behavior changes — if Codex CLI ever adds
  native install support, the test starts failing and we know.
- ⚠️ CI now depends on the `codex` CLI being installable via npm. If
  `@openai/codex` is unavailable or auth-gated for plugin commands, the
  negative test is ADVISORY (per ADR-002) so it won't block CI.
- ⚠️ README parser is regex-based and fragile to formatting changes
  (e.g., indentation changes can break extraction). Mitigated by keeping
  the lint check ADVISORY.
- **Re-open trigger:** if the failure class recurs a 4th time despite this
  test in place, the test mechanism itself is insufficient — promote to a
  fully integrated CI runner with all 3 IDE binaries (codex + claude +
  cursor) at that point.
**Rejected alternatives:**
- **Option A** (positive only) — Rejected: insufficient defense after a 3rd
  recurrence; the negative test is the strongest signal that the README is
  still accurate about what doesn't work.
- **Option C** (positive + README-lint, no Codex negative) — Rejected: lint
  catches new commands but doesn't catch "documented broken command silently
  starts working" — the Codex marketplace case specifically.
**Source:** Interview #1

### ADR-002: CI gating — positive + lint BLOCKING, negative ADVISORY
**Status:** Accepted (2026-05-22, via /hm:plan interview Round 1 + amended Round 2 per validator P2-2)
**Context:** What happens when a test in the new file fails? Strict gating
risks CI failure when external tools (codex CLI, Cursor's filesystem
conventions) change for reasons unrelated to our code. Loose gating defeats
the purpose of the P0 trigger.
**Decision (Round 1):** Mixed strategy: positive=BLOCKING, lint+negative=ADVISORY.
**Decision (Round 2 amendment):** Validator P2-2 argued the lint check IS
the regression-class defense — if README adds a new install command
without an allowlist update, lint surfacing only a warning lets the
regression class re-occur. User accepted: lint promotes to BLOCKING. Final:
- Positive install tests (PyPI, Cursor git-clone) → **BLOCKING**.
- README lint (allowlist check) → **BLOCKING** (Round 2 amend). A new
  install command appearing in README without an allowlist update fails CI.
- Negative test (Codex marketplace must fail) → **ADVISORY**. External
  Codex CLI behavior changes shouldn't break our CI.
**Consequences:**
- ✅ Strong defense against the specific regression class (positive + lint).
- ✅ Allowlist drift now hard-fails CI — the canonical defense for this PLAN's stated goal.
- ✅ Resilient to external Codex behavior changes (negative ADVISORY).
- ⚠️ The lint parser is regex-based; a false-positive could block CI. Mitigated by:
  (a) keeping the parser narrow (only matches `Bash:` lines in code blocks);
  (b) allowlist edits are 2-line changes — fast to unblock when intentional;
  (c) the parser MUST be re-tested locally before any PR that touches README install commands.
**Rejected alternatives:**
- **Option A (all BLOCKING including negative)** — Rejected: external tooling
  drift (codex CLI behavior, npm registry availability) shouldn't break our CI.
- **Option B (all ADVISORY)** — Rejected: defeats the P0 trigger purpose.
- **Original Option C (lint ADVISORY)** — Rejected after Round 2 per validator
  P2-2: allowlist drift IS the regression class; ADVISORY allows it through.
**Source:** Interview #2 (Round 1) + Interview #5 (Round 2 validator-driven)

## 🏗️ Technical Design

### Current State

- `tests/integration/` has 11 integration test files (boundary tests, e2e
  preservation tests). New install-cmd file fits the existing pattern.
- `.github/workflows/ci.yml` (parent workflow for PR CI) and
  `.github/workflows/release.yml` (release flow). Quality-gate job runs
  ruff + mypy + pytest. New test job appended after quality-gate.
- README hero one-prompt + README.ko mirror both have the prompt block at
  lines 43-69 / 36-66 respectively (post-truthification 0.23.5 baseline).

### Affected Components

| File | Section | Change kind |
|---|---|---|
| `README.md` | Codex branch in one-prompt | Add Bash-direct first-run instruction |
| `README.ko.md` | Mirror of above | Mirror |
| `tests/integration/test_readme_install_commands.py` | NEW FILE | Create — 4 test functions |
| `tests/integration/_install_helpers.py` | NEW FILE | Create — local wheel build + temp uv-tool sandbox + Cursor structure assertion helpers |
| `.github/workflows/ci.yml` | Quality-gate sibling job | Append `install-cmd-regression` job with `npm install -g @openai/codex` + pytest invocation |
| `pyproject.toml` | `[project] version` | 0.23.4 → 0.23.5 |
| `.claude-plugin/plugin.json` | `version` | 0.23.4 → 0.23.5 |
| `.cursor-plugin/plugin.json` | `version` | 0.23.4 → 0.23.5 |
| `.codex-plugin/plugin.json` | `version` | 0.23.4 → 0.23.5 |
| `src/harness_maker/__init__.py` | `__version__` | 0.23.4 → 0.23.5 |
| `CHANGELOG.md` | new `[0.23.5]` section | Add release notes |
| `.claude/memory/wiki.md` | inside `<!-- @hm:user:entries -->` | Add `[wiki:lesson] install-cmd-cifence-q4-fired` entry |

### Out-of-scope (NOT touching)

- `docs/BOOTSTRAP.md`, MANUAL_CHECKLIST files — these were truthified in
  the previous PLAN; current Codex first-run text is sufficient given
  Fix A here only touches README + README.ko.
- Cursor MANUAL_CHECKLIST Phase 3.3 Codex flow — already updated in the
  prior PLAN.
- Claude Code + Cursor first-run paths — audit confirms they're fine;
  no doc change.
- ADR proposal for native Codex marketplace.json — out of scope; ADR-001
  of the prior PLAN says "no future commitments."

### Data Flow

No production code paths change. Test-only + CI workflow change.

### API Changes

None.

### Design Decisions

- **ADR-001**: 3 test classes (positive / negative / lint), each in its own
  test function for granular CI reporting.
- **ADR-002**: Mixed gating — positive BLOCKING, negative + lint ADVISORY
  via `pytest.mark.xfail(strict=False)` on the ADVISORY tests OR a separate
  pytest mark filter in the CI workflow.
- **Test isolation**: each test uses `tmp_path` for filesystem operations;
  no test pollutes `~/.cursor` or `~/.codex` on the developer machine.
- **CI runner**: GitHub Actions ubuntu-latest. `codex` CLI installed via
  `npm install -g @openai/codex@latest` in the workflow step (pinning to
  a specific version is OUT of scope; if `@latest` breaks, drop to last
  known good via workflow patch).
- **Skill-tool audit findings (Phase 1)** — confirmed in advance:
  - Claude Code: `claude plugin install ...` registers the plugin; its
    commands (including `harness-maker:make`) become available to the
    Skill tool immediately after `/reload-plugins`. OK.
  - Cursor: `git clone → ~/.cursor/plugins/local/`; after Reload Window
    Cursor reads `commands/` and `skills/` from the cloned plugin dir.
    Plugin commands available to Skill tool. OK.
  - Codex CLI: `claude` or `uv tool install` installs the Python package;
    no `.agents/skills/` exist yet; the AI's Skill tool has nothing to
    invoke. **NEEDS FIX** (Phase 2).

## 📝 Implementation Plan

### Phase 1 — All-IDE Skill-tool audit (verification, no edits) — COMPLETE
**Scope IN:** Verification only. Read each IDE's first-run behavior from
docs + memory + prior PLAN review.
**Scope OUT:** No file edits in this phase.
**Exit criterion:** Confirmation written below (see "Skill-tool audit
findings" in Design Decisions). All 3 IDEs assessed.
**Risk:** low (research-only).
**Rollback:** N/A.
**Status:** Done at PLAN-time (audit captured in Design Decisions section).

### Phase 2 — README + README.ko Codex first-run clarification
**Scope IN:** `README.md` and `README.ko.md` — Codex branch in the
one-prompt block (lines ~58-67 / ~51-60). Add explicit instruction that
for Codex first-run, the AI MUST run `harness-maker make` via Bash
directly (the Skill tool's `harness-maker:make` doesn't yet exist
because skills are rendered BY make). **Canonical anchor phrase (used
by both English and Korean files for grep-checkability):** the literal
string `Skill tool not yet populated` appears verbatim in the Codex
branch of both files. Surrounding prose may be translated.
**Scope OUT:** Other branches (Claude Code, Cursor) — already correct
per Phase 1 audit.
**Exit criterion:** Two independent checks (per validator P2-1 — both
must pass):
1. `grep -c "Skill tool" README.md` ≥ 1 AND `grep -c "Skill tool" README.ko.md` ≥ 1
   (existing "invoke ... via the Skill tool" line still present).
2. `grep -c "Skill tool not yet populated" README.md` = 1 AND
   `grep -c "Skill tool not yet populated" README.ko.md` = 1
   (the canonical anchor phrase appears exactly once in each).
**Risk:** low.
**Rollback:** `git checkout HEAD -- README.md README.ko.md`.

### Phase 3 — New test helper module
**Scope IN:** `tests/integration/_install_helpers.py` (new file). Contains:
- `build_local_wheel(repo_root, dest_dir)` → returns wheel path
- `install_via_uv_tool(wheel, tool_dir)` → returns installed binary path
- `simulate_cursor_install(repo_root, target_dir)` → `git clone` analog
  via `shutil.copytree` so test doesn't depend on network
- `extract_bash_install_commands(readme_text)` → list[str]
- `EXPECTED_README_INSTALL_COMMANDS = [...]` (allowlist; explicit)
**Scope OUT:** The test functions themselves (Phase 4); CI workflow (Phase 5).
**Exit criterion (validator P1-2 fix):** the underscore-prefixed module
is intentionally NOT pytest-collected, so `--collect-only` is a no-op
that always returns exit 0 without verifying anything. Use a real
import check instead:
```
uv run python -c "from tests.integration._install_helpers import (
    EXPECTED_README_INSTALL_COMMANDS,
    build_local_wheel,
    install_via_uv_tool,
    simulate_cursor_install,
    extract_bash_install_commands,
); assert len(EXPECTED_README_INSTALL_COMMANDS) > 0"
```
Must exit 0 (verifies the module imports + the allowlist constant loads + all 4 helpers are exported).
**Risk:** low (helper code only).
**Rollback:** delete the file.

### Phase 4 — New test file: `test_readme_install_commands.py`
**Scope IN:** `tests/integration/test_readme_install_commands.py`. 4 test
functions per ADR-001 (gating per ADR-002 Round 2 amend):
- `test_pypi_install_works` — **BLOCKING**
- `test_cursor_git_clone_path_structure` — **BLOCKING**
- `test_readme_install_commands_in_allowlist` — **BLOCKING** (per ADR-002
  Round 2 amend; allowlist drift IS the regression class)
- `test_codex_marketplace_add_fails_as_documented` — **ADVISORY**, marked
  with `pytest.mark.xfail(strict=False, reason="ADR-002 advisory; external Codex CLI behavior may change")`
  **AND** an in-test skip guard (per validator P1-1):
  ```python
  codex_bin = shutil.which("codex")
  if codex_bin is None:
      pytest.skip("codex CLI not installed — negative test cannot run")
  ```
  This converts a missing-binary case into a `skip` (test-time SKIP, advisory)
  rather than an `ERROR` (which `xfail` does not catch).
**Scope OUT:** Modifying existing test files; modifying production code.
**Exit criterion:** Four concrete checks:
1. `INSTALL_CMD_TEST=1 uv run pytest tests/integration/test_readme_install_commands.py::test_pypi_install_works -v` passes locally.
2. `INSTALL_CMD_TEST=1 uv run pytest tests/integration/test_readme_install_commands.py::test_cursor_git_clone_path_structure -v` passes locally.
3. `INSTALL_CMD_TEST=1 uv run pytest tests/integration/test_readme_install_commands.py::test_readme_install_commands_in_allowlist -v` passes locally.
4. The Codex negative test is correctly marked xfail AND has the `shutil.which` skip guard at the top of its body (verify by reading the test source).
**Risk:** medium (test infrastructure; local wheel build must succeed).
**Rollback:** delete the file.

### Phase 5 — CI workflow update: install codex + add test job
**Scope IN:** `.github/workflows/ci.yml`. Append a new job `install-cmd-regression`:
- `needs: quality-gate` (runs after quality-gate succeeds)
- Steps: checkout, install uv, install python, **`npm install -g @openai/codex`**,
  `uv build` (produce wheel), `INSTALL_CMD_TEST=1 uv run pytest tests/integration/test_readme_install_commands.py -v`.
- Job marked as required gate for merge (positive tests BLOCKING).
**Scope OUT:** `.github/workflows/release.yml` (separate workflow, no change needed).
**Exit criterion:** Three concrete checks:
1. `.github/workflows/ci.yml` parses as valid YAML (`yq '.jobs."install-cmd-regression"'`
   returns the new job).
2. The new job's `needs:` field correctly references `quality-gate`.
3. The job includes `npm install -g @openai/codex` as a step (grep check).
**Risk:** medium (CI behavior is hard to test locally; first push will surface
issues; workflow may need iteration).
**Rollback:** revert the file or comment out the new job.

### Phase 6 — 5-file version bump 0.23.4 → 0.23.5 + CHANGELOG + memory entries
**Scope IN:** 5 version files (per CLAUDE.md release procedure) +
`CHANGELOG.md` `[0.23.5]` section + `.claude/memory/wiki.md` new entry
INSIDE `<!-- @hm:user:entries -->` block.
**Scope OUT:** failures.md (this isn't a code failure but a process upgrade).
**Exit criterion:** Three concrete checks:
1. `grep -RE '"version":|^version|__version__' .claude-plugin/plugin.json
   .cursor-plugin/plugin.json .codex-plugin/plugin.json pyproject.toml
   src/harness_maker/__init__.py` shows all 5 at `0.23.5`.
2. `awk '/<!-- @hm:user:entries -->/,/<!-- @hm:\/user:entries -->/'
   .claude/memory/wiki.md | grep -q '\[wiki:.*install-cmd-cifence'` returns 0.
3. `CHANGELOG.md` has new `## [0.23.5]` section above `## [0.23.4]`.
**Risk:** low (mechanical version sync; same pattern as 0.23.4).
**Rollback:** revert the version commits.

### Phase 7 — Commit + tag v0.23.5 + push
**Scope IN:** Single commit on main with all changes from Phases 2-6.
**Scope OUT:** PLAN file (gitignored under `work-docs/`).
**Exit criterion:** Three concrete checks:
1. `git log -1 --stat` shows one commit titled e.g. "feat(ci): install-cmd
   regression test + Codex first-run doc fix (v0.23.5)".
2. `git tag -l v0.23.5` returns the tag.
3. `git push origin main v0.23.5` succeeds; release workflow starts.
**Risk:** low (tag-push only; workflow handles publish).
**Rollback:** see CLAUDE.md release procedure on tag-push race (don't run
`gh release create` manually).

## 🧪 Testing Strategy

- **Unit:** no new unit tests in this PLAN (test infrastructure is the deliverable).
- **Integration:** the new file IS the integration coverage. 2 positive
  tests (BLOCKING), 2 ADVISORY (xfail-strict-false).
- **Manual:** before tag-push:
  - `uv build && INSTALL_CMD_TEST=1 uv run pytest tests/integration/test_readme_install_commands.py -v`
    (local pre-push verification).
  - `gh act push -j install-cmd-regression` (if `act` is installed locally) for
    smoke-testing the new CI job offline. Optional.
- **Post-release manual:** monitor first CI run after tag push — confirm the
  new job runs to completion (not just collection error).

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `@openai/codex` npm package install fails in CI (auth, rate-limit, or unrelated breakage) | medium | medium (negative test can't run) | Negative test is ADVISORY per ADR-002 — CI continues green; surface as workflow warning |
| R2 | `codex plugin marketplace add` requires auth tokens in CI | medium | medium (negative test fails for wrong reason) | Test asserts on exit code != 0 with specific error pattern match (`not found in marketplace`); auth failures use different error → test fails open + advisory |
| R3 | Local wheel build fails in CI for reasons unrelated to this PLAN (build deps, network) | low | high (BLOCKING test can't run) | `uv build` is currently only validated on tag pushes (release.yml `publish-pypi`); adding it to PR CI surfaces build regressions earlier — which is the correct behavior. A wheel-build failure on the new PR job is a BLOCKING signal that something broke between releases; intentional, not a risk needing mitigation. |
| R4 | README parser regex breaks on a new formatting style (e.g., indented code fences) | medium | low (lint ADVISORY) | Lint is ADVISORY; failure surfaces as warning; explicit allowlist edit unblocks merge |
| R5 | Cursor git-clone test uses `shutil.copytree` simulation, not real `git clone` — could miss network-related failures | low | low | Network testing belongs in a real e2e suite; this test focuses on disk-structure assertion |
| R6 | Class recurs a 4TH time despite this defense — test was insufficient | low | high | ADR-001 has its own re-open trigger: promote to fully integrated CI runner with all 3 IDE binaries at that point |
| R7 | Worktree finalize loses the PLAN file (work-docs/ is gitignored) | low | low | Same as prior PLAN — PLAN lives in base only; finalize stage-only doesn't transfer it |

## ✅ Success Criteria

- [x] `grep -nE "first-run.*Bash" README.md README.ko.md` returns matches in BOTH files.
- [x] `tests/integration/test_readme_install_commands.py` exists with 4 test functions.
- [x] `tests/integration/_install_helpers.py` exists with the helper functions + `EXPECTED_README_INSTALL_COMMANDS` allowlist.
- [x] `uv run pytest tests/integration/test_readme_install_commands.py --collect-only` shows 4 tests, 2 BLOCKING + 2 ADVISORY (xfail markers visible).
- [x] `INSTALL_CMD_TEST=1 uv run pytest tests/integration/test_readme_install_commands.py::test_pypi_install_works -v` passes locally.
- [x] `INSTALL_CMD_TEST=1 uv run pytest tests/integration/test_readme_install_commands.py::test_cursor_git_clone_path_structure -v` passes locally.
- [x] `.github/workflows/ci.yml` has new `install-cmd-regression` job with `needs: quality-gate` and `npm install -g @openai/codex` step.
- [x] All 5 version files at `0.23.5`.
- [x] `CHANGELOG.md` has new `[0.23.5]` section explaining the Q4 trigger fire.
- [x] `.claude/memory/wiki.md` has new `[wiki:lesson] install-cmd-cifence-q4-fired` entry INSIDE `<!-- @hm:user:entries -->` block (verify with `awk` range match).
- [x] PR CI run preceding the tag push has `install-cmd-regression` job GREEN (BLOCKING tests pass; ADVISORY test reports a skip or xfail).
- [x] Tag `v0.23.5` pushed; release workflow runs to completion (quality-gate → build → publish-testpypi → publish-pypi → github-release → boundary-advisory all GREEN). **release.yml is intentionally NOT modified** (per Round 2 user decision); install-cmd-regression lives in ci.yml only, gating PRs that land on main BEFORE the tag push.

## 🔍 Plan Validation

**Round 1 outcome:** `NEEDS_REVISION` (3 P1, 2 P2, 1 P3).

**Resolution:** 4 critiques applied directly inline (mechanical fixes);
2 critiques required Round 2 follow-up interview (decisions touching
prior locked-in answers).

| # | Severity | Critique | Resolution |
|---|---|---|---|
| 1 | P1 | `xfail(strict=False)` doesn't catch test ERROR when `codex` binary is missing | Phase 4 amended: added `shutil.which("codex")` skip guard at top of negative test body |
| 2 | P1 | Phase 3 exit criterion `--collect-only` on underscore module is a no-op | Phase 3 amended: replaced with explicit `python -c` import check that asserts allowlist constant loads + 4 helpers export |
| 3 | P1 | Success Criteria mentions `install-cmd-regression` in release flow, Phase 5 scopes OUT release.yml — inconsistent | Round 2 Q6: user confirmed ci.yml only. Success Criteria amended to gate on PR CI; release-flow checklist removed install-cmd-regression entry |
| 4 | P2 | Phase 2 OR exit criterion is ambiguous (translation drift possible) | Phase 2 amended: canonical anchor phrase `"Skill tool not yet populated"` appears verbatim in both README files; two independent grep checks (existing "Skill tool" line + new anchor) each required in BOTH files |
| 5 | P2 | Lint ADVISORY contradicts the regression-class defense purpose | Round 2 Q5: user accepted validator. ADR-002 amended (Round 2) — lint promoted to BLOCKING; only negative test remains ADVISORY |
| 6 | P3 | R3 wording overclaimed "well-validated" build precondition | Risk register R3 reworded — `uv build` in PR CI is a new validation step, surfacing build regressions earlier; the BLOCKING signal is intentional |

Re-validate **not** invoked (procedure: re-run validator only on MAJOR_REVISION
resolutions; NEEDS_REVISION → write PLAN and proceed). Final
`validator_outcome: NEEDS_REVISION_RESOLVED`.
