---
type: plan
task_slug: pypi-publication
status: planning
created: 2026-05-12
tags: [harness-maker, plan, python, packaging, pypi, release-automation]
interview_rounds: 4
adrs: 12
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Prepare harness-maker for PyPI release with Trusted Publishing"
---

## 🎯 Executive Summary

**TL;DR:** Prepare `harness-maker` for public PyPI distribution with name reservation, Trusted Publishing, release automation, artifact regression tests, and a guarded first `0.11.2` release.

**What:** Add the missing packaging/release surfaces around the existing `pyproject.toml`: PyPI/TestPyPI reservation, metadata cleanup, package-data tests, local smoke script, GitHub Actions release workflow, README/release checklist updates, and first tag-based release procedure.

**Why:** The package already has a CLI and modern build backend, but public PyPI release needs stronger guarantees: the package name must be reserved early, runtime templates must ship in wheels/sdists, and production upload must not depend on long-lived local tokens.

**Key Decisions:** See ADR-001 through ADR-012. The important constraints are: production upload uses GitHub Actions Trusted Publishing, PyPI links stay minimal for the first release, the first public version is `0.11.2`, release is triggered only by `v*` tags, TestPyPI must succeed before PyPI, and bad public releases are yanked then replaced with a new patch version.

**Estimated impact:** Medium-high. Most work is release infrastructure and tests, but a bad PyPI release is hard to undo because same-version reupload is not available.

## 📚 Prior Work

Current package metadata already exists in `pyproject.toml`: name `harness-maker`, version `0.11.1`, Python `>=3.12`, `uv_build` backend, and CLI entrypoint `harness-maker = "harness_maker.cli:main"`.

Existing project docs already anticipate PyPI installation in README but still mark it as future-only. `CHANGELOG.md` has an `Unreleased` section suitable for promotion into `0.11.2`.

Relevant official packaging references:
- PyPI Trusted Publishing docs: `https://docs.pypi.org/trusted-publishers/`
- PyPI Trusted Publisher usage with GitHub Actions: `https://docs.pypi.org/trusted-publishers/using-a-publisher/`
- Python `pyproject.toml` metadata specification: `https://packaging.python.org/en/latest/specifications/pyproject-toml/`
- Python Packaging User Guide TestPyPI guide: `https://packaging.python.org/guides/using-testpypi/`

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Publish auth | Architecture | First PyPI publishing mechanism | Trusted Publishing / manual twine / mixed / Other | GitHub Actions + Trusted Publishing | Avoid long-lived PyPI tokens for production. | ADR-001 |
| 1 | PyPI links | Scope | Public source/project links on PyPI | repo links / docs only / minimal / Other | Minimal links initially | Keep repo/source exposure low for first release. | ADR-002 |
| 1 | Release scope | Scope | First release scope | packaging only / PyPI publish / release automation / Other | Include GitHub Release/tag automation | Release should be repeatable, not one-off manual upload. | ADR-003 |
| 2 | Version | Contract | First public version | 0.11.1 / 0.12.0 / 0.11.2 / Other | 0.11.2 patch | Conservative public release version. | ADR-004 |
| 2 | Verification | Testing | Pre-release verification depth | full / packaging / minimal / Other | Full quality gate | First public release needs broad regression confidence. | ADR-005 |
| 2 | Package data | Testing | Package asset inclusion verification | artifact tests / workflow inspect / rely on backend / Other | Add wheel/sdist content tests | Runtime templates are essential package data. | ADR-006 |
| 2 | Interview exit | Phasing | Is plan clear? | end / security round / release ops round / Other | One more release-ops round | User requested operating policy decisions. | - |
| 3 | Trigger | Contract | GitHub Actions release trigger | `v*` tag / GitHub Release / workflow_dispatch / Other | `v*` tag push only | Reduces accidental publish risk. | ADR-007 |
| 3 | TestPyPI order | Risk | TestPyPI and PyPI sequencing | same tag TestPyPI then PyPI / PR TestPyPI only / rc tags / Other | Same tag: TestPyPI success then PyPI | Chosen by planner as conservative default. | ADR-008 |
| 3 | Failure policy | Risk | Wrong public release response | yank+patch / delete+retry / manual / Other | Yank then patch version | Matches PyPI immutability constraints. | ADR-009 |
| 3 | Release notes | Contract | CHANGELOG / GitHub Release source | CHANGELOG promoted / auto notes / manual body / Other | CHANGELOG promoted and reused | Single source of release truth. | ADR-010 |
| 3 | Interview exit | Phasing | Is plan clear? | end / owner policy / docs UX / Other | End interview | Initial plan sent to validator. | - |
| 4 | Name reservation | Risk | Name reservation policy | actual reservation / API+pending / fallback name / Other | Phase 0 actual reservation | Validator critical issue resolved. | ADR-011 |
| 4 | GitHub environments | Security | GitHub environment policy | both / pypi only / none / Other | `testpypi` and `pypi` environments | Distinct Trusted Publisher subjects and optional protection. | ADR-012 |
| 4 | Validator warnings | Phasing | Resolve validator warnings | reflect / more interview / accept risk / Other | Reflect in plan | ADRs and exit criteria made concrete. | - |

## 📐 Architecture Decision Records

### ADR-001: Production Publishing Uses Trusted Publishing
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** PyPI supports both long-lived API tokens and Trusted Publishing through OIDC. A public release workflow should minimize credential exposure.
**Decision:** Production PyPI publishing will use GitHub Actions Trusted Publishing with `pypa/gh-action-pypi-publish@release/v1`.
**Consequences:**
- ✅ No long-lived production PyPI token needs to live in GitHub secrets or a local `.pypirc`.
- ⚠️ PyPI Trusted Publisher setup must exactly match repository, workflow file, and environment.
**Rejected alternatives:**
- Manual `twine upload` — Rejected because it relies on local token handling and is less repeatable.
- TestPyPI manual + PyPI Trusted Publishing — Rejected because the first release should exercise the same auth path end to end.
**Source:** Interview #1

### ADR-002: Initial PyPI Metadata Minimizes External Links
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** PyPI project URLs improve trust and discoverability but expose repository or homepage details.
**Decision:** The first PyPI release will keep project links minimal and avoid public source repository links unless the owner later decides otherwise.
**Consequences:**
- ✅ Reduces external surface exposed by the first public package page.
- ⚠️ PyPI trust/discoverability signals are weaker until links are added.
**Rejected alternatives:**
- Public GitHub repository URL — Rejected because the user chose link minimization first.
- Rich homepage/docs links — Rejected for first release to keep metadata exposure narrow.
**Source:** Interview #1

### ADR-003: First Release Includes Release Automation
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** A one-off upload can publish the package but leaves future releases error-prone.
**Decision:** The first release scope includes GitHub tag/release automation.
**Consequences:**
- ✅ Future patch releases follow the same repeatable path.
- ⚠️ Initial work is larger than a manual upload.
**Rejected alternatives:**
- TestPyPI-only preparation — Rejected because the user asked to publish.
- Manual production upload only — Rejected because it would not establish a durable release process.
**Source:** Interview #1

### ADR-004: First Public Version Is 0.11.2
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Current metadata version is `0.11.1`; first public PyPI release needs a version that can be tied to packaging/release work.
**Decision:** The first public release will be `0.11.2`.
**Consequences:**
- ✅ Conservative patch release communicates packaging/release polish without implying a feature release.
- ⚠️ All version sources must be synchronized before tagging.
**Rejected alternatives:**
- `0.11.1` — Rejected because it mixes prior local/plugin state with first public packaging changes.
- `0.12.0` — Rejected as too large a semantic bump for release infrastructure only.
**Source:** Interview #2

### ADR-005: Pre-release Gate Is Full Quality
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Public package install failures affect all users and cannot be fixed by overwriting the same PyPI version.
**Decision:** Pre-release verification must include `ruff`, `mypy`, full `pytest`, build/check, wheel install smoke, and TestPyPI install smoke.
**Consequences:**
- ✅ First public release gets broad regression coverage.
- ⚠️ Release CI is slower and may surface existing non-packaging failures.
**Rejected alternatives:**
- Packaging-only gate — Rejected because code regressions can still break the CLI after install.
- Minimal build/check gate — Rejected because first public release risk is high.
**Source:** Interview #2

### ADR-006: Package Data Inclusion Gets Regression Tests
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** `harness-maker` depends on shipped Jinja templates, rubrics, commands, and skill templates at runtime.
**Decision:** Add artifact tests that assert wheel and sdist include representative runtime assets and exclude `__pycache__`.
**Consequences:**
- ✅ Prevents publishing an installable CLI that cannot render harness files.
- ⚠️ Artifact tests add build-time cost and may need adjustment if template paths move.
**Rejected alternatives:**
- Manual release workflow inspection — Rejected because it is weaker against future regressions.
- Relying on `uv_build` defaults — Rejected because runtime package data is too important to leave implicit.
**Source:** Interview #2

### ADR-007: Release Workflow Triggers Only On v* Tags
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Publishing should not happen accidentally from ordinary pushes or PRs.
**Decision:** Production publishing is triggered only by `v*` tag pushes.
**Consequences:**
- ✅ Tag creation is the explicit release act.
- ⚠️ Failed release retries require either fixing and retagging a new version or rerunning the same tag workflow carefully.
**Rejected alternatives:**
- GitHub Release `published` event — Rejected because it adds ordering complexity around tag and release creation.
- General `workflow_dispatch` publish — Rejected because it increases accidental publish risk.
**Source:** Interview #3

### ADR-008: TestPyPI Must Succeed Before PyPI In The Same Tag Workflow
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** TestPyPI should catch upload/install problems before production PyPI receives the same artifacts.
**Decision:** The `v*` tag workflow builds once, publishes to TestPyPI, runs TestPyPI install smoke, then publishes the same `dist/*` to PyPI.
**Consequences:**
- ✅ Production publish is gated by the closest available index-level rehearsal.
- ⚠️ TestPyPI receives the same final version and may need project cleanup over time.
**Rejected alternatives:**
- PR/manual TestPyPI and tag PyPI only — Rejected because tag-time index validation would be missing.
- RC tags for TestPyPI and final tags for PyPI — Rejected as operationally heavier than needed.
**Source:** Interview #3

### ADR-009: Bad Public Releases Are Yanked And Reissued
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** PyPI does not support replacing an already uploaded file for the same version.
**Decision:** If a bad version reaches PyPI, yank that release and publish a new patch version.
**Consequences:**
- ✅ Preserves package index immutability and gives users a clear fixed version.
- ⚠️ A bad version number remains visible in release history.
**Rejected alternatives:**
- Delete and retry same version — Rejected because it is unreliable and harms reproducibility.
- Case-by-case manual policy — Rejected because release failure response must be executable under pressure.
**Source:** Interview #3

### ADR-010: Release Notes Come From CHANGELOG
**Status:** Accepted (2026-05-12, via /hm:plan interview)
**Context:** Release notes should not drift between repository history and GitHub Release.
**Decision:** Promote `CHANGELOG.md` `Unreleased` into `0.11.2 - YYYY-MM-DD` and use that body for GitHub Release notes.
**Consequences:**
- ✅ One source of truth for release contents.
- ⚠️ Release automation needs a reliable way to extract or supply the changelog section.
**Rejected alternatives:**
- GitHub auto-generated notes only — Rejected because they are weaker for curated packaging/release context.
- Manual GitHub Release body only — Rejected because it leaves repo-local release history incomplete.
**Source:** Interview #3

### ADR-011: Package Name Is Reserved In Phase 0
**Status:** Accepted (2026-05-12, via /hm:plan validator follow-up)
**Context:** Validator found that checking name availability only before tagging could invalidate the whole plan after most work was done. On 2026-05-12, PyPI and TestPyPI JSON endpoints for `harness-maker` returned 404, but availability is not a reservation.
**Decision:** Phase 0 must actually reserve/create the `harness-maker` project on both TestPyPI and PyPI before implementation proceeds.
**Consequences:**
- ✅ Name availability becomes a blocking early gate instead of a late release surprise.
- ⚠️ A reservation release or equivalent project-creation step may leave early metadata/release traces on the indexes.
**Rejected alternatives:**
- API check plus pending publisher only — Rejected because it still does not fully reserve the name.
- Immediate fallback to `harness-maker-cli` — Rejected because current evidence says `harness-maker` is available and the user chose reservation.
**Source:** Interview #4

### ADR-012: TestPyPI And PyPI Use GitHub Environments
**Status:** Accepted (2026-05-12, via /hm:plan validator follow-up)
**Context:** Trusted Publisher subjects must match workflow identity. Environments also allow production protection in GitHub.
**Decision:** Release workflow uses separate `testpypi` and `pypi` GitHub environments for the respective publish jobs.
**Consequences:**
- ✅ PyPI/TestPyPI publisher configuration can match distinct environment subjects.
- ✅ Production `pypi` can require manual approval if desired.
- ⚠️ Environment names become part of the release contract and must not drift.
**Rejected alternatives:**
- `pypi` environment only — Rejected because TestPyPI and PyPI would have different security models.
- No environments — Rejected because it weakens release protection and publisher traceability.
**Source:** Interview #4

## 🏗️ Technical Design

### Current State

`pyproject.toml` already defines a modern package:
- `name = "harness-maker"`
- `version = "0.11.1"`
- `requires-python = ">=3.12"`
- `build-backend = "uv_build"`
- script: `harness-maker = "harness_maker.cli:main"`

There is no `.github/workflows/release.yml`. README still contains "from PyPI (when published)" wording. Runtime render logic depends on files under `src/harness_maker/templates/**`, so package artifact contents are part of the executable contract.

### Affected Components

- `pyproject.toml`: metadata, classifiers, keywords, license files, version.
- `src/harness_maker/__init__.py`: runtime `__version__`.
- `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and possibly `.codex-plugin/plugin.json`: version sync and metadata consistency.
- `CHANGELOG.md`: promote `Unreleased` into `0.11.2 - 2026-05-12`.
- `README.md`: update install instructions after PyPI publication.
- `.github/workflows/release.yml`: release automation.
- `tests/unit/test_package_artifacts.py`: wheel/sdist asset assertions.
- `scripts/release-smoke.sh`: local repeatable smoke test.
- Release checklist docs: PyPI/TestPyPI owner, Trusted Publisher subjects, tag command, yank policy.

### Dependencies

Build and check tooling should use existing `uv` workflow where possible. Release workflow uses `pypa/gh-action-pypi-publish@release/v1` with job-level `id-token: write`, matching PyPI Trusted Publishing requirements.

External setup required before code execution:
- TestPyPI account with 2FA.
- PyPI account with 2FA.
- TestPyPI project `harness-maker` reserved under intended owner.
- PyPI project `harness-maker` reserved under intended owner.
- Trusted Publisher entries for repository owner/name, workflow `.github/workflows/release.yml`, and environments `testpypi` and `pypi`.

### Architecture

Release flow:

```text
v0.11.2 tag push
  -> quality gate: ruff, mypy, pytest
  -> build dist once
  -> metadata + artifact content checks
  -> publish dist/* to TestPyPI using environment=testpypi
  -> install smoke from TestPyPI with PyPI extra index for dependencies
  -> publish same dist/* to PyPI using environment=pypi
  -> create GitHub Release from CHANGELOG 0.11.2 body
```

### Design Decisions

Every non-trivial release decision is locked in ADR-001 through ADR-012. The most important constraints for `/hm:execute` are ADR-006 package-data tests, ADR-008 same-artifact TestPyPI-before-PyPI sequence, ADR-011 Phase 0 reservation, and ADR-012 environment names.

### Data Flow

The workflow builds artifacts once and reuses the exact files for both indexes. This avoids "TestPyPI tested one thing, PyPI received another" drift.

### API Changes

No Python API behavior change is planned. Public install behavior changes because users can install through PyPI after release.

## 📝 Implementation Plan

### Phase 0: Reserve Package Names And Trusted Publisher Subjects

**Scope:** Verify and reserve/create `harness-maker` on TestPyPI and PyPI under the intended owner. Configure Trusted Publishers for repository owner/name, workflow `.github/workflows/release.yml`, and environments `testpypi` and `pypi`. Record exact account/project/workflow/environment values in release docs.

**Out of scope:** Full public `0.11.2` release automation and code changes.

**Exit criterion:** Both `https://test.pypi.org/project/harness-maker/` and `https://pypi.org/project/harness-maker/` exist under the intended owner, and both Trusted Publisher entries match the repo, workflow file, and environment names.

**Risk:** high

**Rollback point:** If reservation metadata is wrong, yank the reservation release and correct with a later release. If the name is unavailable, stop and re-plan the package name before changing code.

### Phase 1: Package Metadata And Version Sync

**Scope:** Update `pyproject.toml` classifiers, keywords, `license-files`, and minimal metadata. Bump version to `0.11.2`. Sync runtime and plugin manifest versions. Promote `CHANGELOG.md` `Unreleased` into `0.11.2 - 2026-05-12`.

**Out of scope:** GitHub Actions workflow and publish.

**Exit criterion:** `uv run pytest tests/unit/test_version_sync.py -q` passes, and `uv run harness-maker --version` or `uv run python -m harness_maker --version` returns `0.11.2`.

**Risk:** medium

**Rollback point:** Revert Phase 1 files to `0.11.1` metadata.

### Phase 2: Package Artifact Regression Tests

**Scope:** Add `tests/unit/test_package_artifacts.py`. The test must inspect built wheel and sdist and assert inclusion of:
- `harness_maker/templates/agents/code-reviewer.md.j2`
- `harness_maker/templates/stages/plan.md.j2`
- `harness_maker/templates/rubrics/agent_prompt.yaml.j2`
- `harness_maker/templates/skills/verify-before-completion/SKILL.md.j2`
- representative command/settings templates

It must also assert `__pycache__` files are excluded from wheel and sdist.

**Out of scope:** Release workflow.

**Exit criterion:** `uv run pytest tests/unit/test_package_artifacts.py -q` passes.

**Risk:** medium

**Rollback point:** Revert Phase 2 test file only.

### Phase 3: Local Release Smoke Script

**Scope:** Add `scripts/release-smoke.sh` that:
1. removes/recreates `dist/`;
2. builds wheel and sdist;
3. runs metadata check;
4. creates an isolated temp environment;
5. installs the built wheel;
6. runs `harness-maker --help`;
7. runs `harness-maker profile --json` against a temp project;
8. runs `harness-maker make <temp-project> --preset Side --locale en --targets codex --yes` or the closest existing non-interactive equivalent, then asserts generated `AGENTS.md` and `.agents/skills/hm-plan/SKILL.md` exist.

**Out of scope:** Network uploads to TestPyPI/PyPI.

**Exit criterion:** `bash scripts/release-smoke.sh` completes from a clean checkout.

**Risk:** low

**Rollback point:** Keep Phase 1-2; remove script and related docs.

### Phase 4: GitHub Actions Release Workflow

**Scope:** Add `.github/workflows/release.yml` for `v*` tag pushes and mandatory `workflow_dispatch` dry runs. Non-publish jobs run in dry run. Publish steps are guarded so they only run for `refs/tags/v*`. The workflow must run full quality gates, build once, upload artifacts, publish to TestPyPI in environment `testpypi`, smoke install from TestPyPI, publish same artifacts to PyPI in environment `pypi`, and create a GitHub Release from the CHANGELOG `0.11.2` body.

**Out of scope:** PyPI website configuration itself, which Phase 0 handles.

**Exit criterion:** `actionlint .github/workflows/release.yml` passes when `actionlint` is available, and the YAML contains `workflow_dispatch`, `push.tags: ["v*"]`, `environment: testpypi`, `environment: pypi`, job-level `id-token: write` on publish jobs, and publish guards equivalent to `startsWith(github.ref, 'refs/tags/v')`.

**Risk:** high

**Rollback point:** Delete `.github/workflows/release.yml`; manual TestPyPI/PyPI process remains possible.

### Phase 5: Documentation And Release Checklist

**Scope:** Update README PyPI install language and add a release checklist covering account setup, 2FA, exact Trusted Publisher subjects, environment names, local smoke command, tag command, expected TestPyPI/PyPI URLs, install verification, and yank-and-patch policy.

**Out of scope:** Broad marketing rewrite and public source-link decision changes.

**Exit criterion:** Docs include concrete commands for preflight, tag, verification, and failure response.

**Risk:** low

**Rollback point:** Revert docs only.

### Phase 6: First Release Execution

**Scope:** After implementation/review/verification, create and push `v0.11.2`, verify CI publishes TestPyPI then PyPI, confirm `uv tool install harness-maker` works from PyPI, and create/confirm GitHub Release body from CHANGELOG.

**Out of scope:** Code changes during release except emergency patch work on a new version.

**Exit criterion:** PyPI page exists, install smoke passes from PyPI, CLI runs after `uv tool install harness-maker`, and GitHub Release body matches CHANGELOG `0.11.2`.

**Risk:** high

**Rollback point:** If PyPI publish is wrong, yank `0.11.2`, fix forward, and prepare `0.11.3`.

## 🧪 Testing Strategy

**Unit/structural:**
- `uv run pytest tests/unit/test_version_sync.py -q`
- `uv run pytest tests/unit/test_package_artifacts.py -q`

**Quality gate:**
- `uv run ruff check .`
- `uv run mypy src tests`
- `uv run pytest -q`

**Local release smoke:**
- `bash scripts/release-smoke.sh`

**Workflow checks:**
- `actionlint .github/workflows/release.yml` when available.
- Static assertions or review checks for `workflow_dispatch`, `v*` tags, `testpypi`/`pypi` environments, `id-token: write`, and publish guards.

**Release validation:**
- TestPyPI install smoke before production publish.
- PyPI install smoke after production publish.
- Manual PyPI page check for metadata, version, and files.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|---|---:|---|
| `harness-maker` name becomes unavailable | high | Phase 0 actual reservation before code work; stop and re-plan if unavailable |
| Missing runtime templates in wheel/sdist | high | Artifact tests plus local render smoke |
| Trusted Publisher subject mismatch | high | Record exact repo/workflow/environment values; use `testpypi` and `pypi` environments |
| Production publish from wrong event | high | Restrict publish to `v*` tag refs and protect `pypi` environment |
| Same version cannot be replaced | high | TestPyPI first; yank bad releases and publish a new patch |
| TestPyPI dependency resolution fails | medium | Install from TestPyPI with PyPI extra index for dependencies |
| Minimal project links reduce user trust | medium | Keep README/license/classifiers strong; add public links later by explicit decision |

## ✅ Success Criteria

- [ ] TestPyPI and PyPI projects named `harness-maker` are reserved under the intended owner.
- [ ] Trusted Publishers are configured for `.github/workflows/release.yml` with `testpypi` and `pypi` environments.
- [ ] `uv tool install harness-maker` works from PyPI after release.
- [ ] Installed CLI runs `harness-maker --help` and profile/render smoke.
- [ ] Wheel and sdist include runtime templates, rubrics, stage templates, command templates, and skill templates.
- [ ] Wheel and sdist exclude `__pycache__`.
- [ ] `v0.11.2` tag workflow builds once, publishes to TestPyPI, smoke-installs, then publishes the same artifacts to PyPI.
- [ ] README no longer describes PyPI install as future-only.
- [ ] CHANGELOG contains `0.11.2 - 2026-05-12`, and GitHub Release notes match it.

## 🔍 Plan Validation

| Pass | Outcome | Critiques | Resolution |
|---|---|---|---|
| 1 | MAJOR_REVISION | Missing early PyPI/TestPyPI name reservation; ADRs lacked full consequences/rejections; Phase 2/3/4 exit criteria were too loose; Trusted Publisher subjects were underspecified. | Added Interview #4, ADR-011, ADR-012, Phase 0, concrete Phase 2/3/4 exit criteria, and exact environment policy. |
| 2 | NEEDS_REVISION | ADRs were summarized in validator draft; Phase 3 used deferred phrase "if feasible". | Full ADR-001 through ADR-012 bodies are included above; Phase 3 now requires a concrete render/generation smoke. |

**Validator outcome:** `NEEDS_REVISION_RESOLVED`.

## 🚧 Execution Status

| Phase | Status | Note |
|---|---|---|
| 0 | blocked | `/hm-exec-rev` halted before code edits because Phase 0 requires authenticated PyPI/TestPyPI account actions: reserve/create the `harness-maker` projects and configure Trusted Publishers for `.github/workflows/release.yml` with `testpypi` and `pypi` environments. The current agent session has no PyPI/TestPyPI credentials or browser/account authority, so the Phase 0 exit criterion cannot be proven. |

**Blocker output:** Worktree isolation succeeded at `/home/noel/harness-maker/.worktrees/execute-20260512T0601Z`, but execution cannot advance past Phase 0 until the PyPI/TestPyPI reservation and Trusted Publisher setup are completed or the PLAN is revised to move Phase 0 outside `/hm:execute`.
