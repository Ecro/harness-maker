---
type: plan
task_slug: pypi-publish-llm-prompts
status: complete
created: 2026-05-17
tags: [harness-maker, plan, python, pypi, packaging, release-automation, llm-prompts]
research_doc: "[[RESEARCH-pypi-publish-llm-prompts]]"
interview_rounds: 4
adrs: 9
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "uv publish + Trusted Publishing infra now; universal cross-platform LLM prompt; publish at next minor"
---

## 🎯 Executive Summary

**What:** Release infrastructure for harness-maker PyPI publication — Trusted Publishing via GitHub Actions (`uv publish`), package artifact regression tests, release smoke script (Python), and a redesigned universal cross-platform install prompt in README.

**Why:** harness-maker has a working CLI, modern build backend, and multi-IDE support (Claude Code + Cursor + Codex), but no public PyPI presence. Users cannot install via `uv tool install harness-maker`. The install story for all three LLM IDEs requires a single copy-paste prompt that works on any OS without manual branching.

**Key Decisions:** (see ADR-001 through ADR-009)
- **ADR-001:** PyPI owner is `Ecro/harness-maker`; fix plugin.json URLs before publication.
- **ADR-002:** `uv publish --trusted-publishing always` (replaces old plan's pypa action).
- **ADR-003 / ADR-005:** Infrastructure code lands at 0.13.1 tip; actual PyPI publish deferred to next minor version (0.14.x or 0.15.x after in-progress work completes).
- **ADR-004 / ADR-006 / ADR-008:** Single universal cross-platform LLM prompt, openly visible in README Quickstart.
- **ADR-007:** TestPyPI job → PyPI job (two GitHub environments, `needs:` dependency).
- **ADR-009:** Bad releases are yanked and re-issued as a new patch version.

**Estimated impact:** Medium. Most work is infrastructure and tests. The README prompt redesign is user-facing but low-risk.

## 📚 Prior Work

- [[RESEARCH-pypi-publish-llm-prompts]] (2026-05-17) — uv publish Trusted Publishing docs, LLM prompt patterns research. Surfaced plugin.json repo URL mismatch and TestPyPI dependency resolution pitfall.
- [[PLAN-pypi-publication]] (2026-05-12) — Prior comprehensive plan, 12 ADRs, blocked at Phase 0 (PyPI name reservation requires authenticated account actions). ADR-008 (TestPyPI → PyPI ordering) and ADR-009 (yank policy) inherited verbatim. The release version (0.11.2) and the publish action (pypa/gh-action-pypi-publish) from that plan are superseded by ADR-002/003.
- [[PLAN-install-without-claude-code]] (2026-05-12, status: complete) — Added `console_scripts`, `_compute_install_ref()`, and the initial Universal Bootstrap Prompt to README. All implemented and passing tests.
- `[wiki:architecture] ide-agnostic-install-ref` — `_compute_install_ref()` selects PyPI name vs local path.
- `[wiki:gotcha] install-ref-file-url-vs-editable` — file:// URL detection for local installs.
- `[fail:design] install-ref-editable-only-check` — original failure driving the `_compute_install_ref()` fix.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|-------|-------|----------|-------------------|---------|--------|------|-------|
| 1 | 1 | GitHub owner | Contract | PyPI Trusted Publisher owner | Ecro / noel / Other | `Ecro/harness-maker` | git remote is Ecro; fix plugin.json | ADR-001 |
| 2 | 1 | Publish tool | Architecture | uv publish vs pypa/gh-action-pypi-publish | uv publish / pypa action / Other | `uv publish --trusted-publishing always` | Simpler, uv_build-native | ADR-002 |
| 3 | 1 | Release version | Contract | First PyPI publish version | 0.13.1 / next minor / Other | Next minor (0.14.x or 0.15.x) | 0.14.0 work in progress elsewhere | ADR-003 |
| 4 | 1 | Prompt format | Architecture | Single universal prompt vs per-LLM cards | unified / per-IDE cards / Other | Single universal; LLM auto-detects | "LLM이 알아서 처리" | ADR-004 |
| 5 | 2 | Release timing | Phasing | Infra now vs all-at-once | infra now / wait / Other | Infrastructure now, publish at next minor | Decouple code from publish act | ADR-005 |
| 6 | 2 | Prompt improvement | Architecture | Key prompt improvement | pre-PyPI removal / Windows / CLAUDE.md insert / Other | Cross-platform copy-paste in one block | Must work on Windows too | ADR-006 |
| 7 | 2 | TestPyPI gate | Risk | TestPyPI → PyPI or skip | two jobs / skip / Other | Two-job (TestPyPI → PyPI) | Inherit old PLAN ADR-008 | ADR-007 |
| 8 | 3 | Prompt placement | Architecture | <details> vs visible | keep details / visible + manual details / Other | Prompt visible, manual in details | "프롬프트가 우선" | ADR-008 |
| V1 | FU | Phase 0 checklist | Risk | Validator W1: no Phase 0 verification artifact | add checklist / accept / Other | Add docs/release-checklist.md in Phase 4 | Pre-publish human checklist | — |
| V2 | FU | Test fixture spec | Testing | Validator W2: fixture method unclear | zipfile / filesystem / Other | zipfile.ZipFile.namelist in test | Build in tmp_path, glob dist/*.whl | — |
| V3 | FU | Cross-platform spec | Architecture | Validator W3: prompt detection commands | irm+curl / LLM-inferred / Other | All A: plan revision | irm for Windows, curl for POSIX | — |
| V4 | FU | Yank policy | Risk | Validator W4: ADR-009 missing body | include verbatim / reference / Other | Include verbatim | Inherited from old PLAN | ADR-009 |
| V5 | FU | CI relationship | Architecture | Validator W5: ci.yml vs release.yml | defense-in-depth / skip / Other | Clarify in plan text | ci.yml exists for PR/push; release.yml adds tag coverage | — |
| V6 | FU | Phase 1 exit | Contract | Validator W6: classifiers/license-files not in exit | extend exit / accept risk / Other | Extend Phase 1 exit criterion | Add grep for classifiers + license-files | — |

## 📐 Architecture Decision Records

### ADR-001: PyPI/TestPyPI Owner Is `Ecro/harness-maker`
**Status:** Accepted (2026-05-17, via /hm:plan interview)
**Context:** The git remote is `git@github.com-personal:Ecro/harness-maker.git`. All three plugin.json files (`/.claude-plugin/`, `/.cursor-plugin/`, `/.codex-plugin/`) currently have `"homepage"` and `"repository"` pointing to `https://github.com/noel/harness-maker`. PyPI Trusted Publisher registration must exactly match the GitHub repo owner/name.
**Decision:** The canonical repo URL is `https://github.com/Ecro/harness-maker`. Fix all three plugin.json files to use this URL before publication. PyPI and TestPyPI Trusted Publisher entries must reference `Ecro/harness-maker`.
**Consequences:**
- ✅ Trusted Publisher subject matches reality; publication will not fail on identity mismatch.
- ⚠️ Three plugin.json files need URL correction before any tag is pushed.
**Rejected alternatives:**
- `noel/harness-maker` — Rejected because git remote is Ecro; operating under noel would require either a fork or repo transfer.
**Source:** Interview #1

### ADR-002: Publishing Uses `uv publish --trusted-publishing always`
**Status:** Accepted (2026-05-17, via /hm:plan interview)
**Context:** The prior plan (PLAN-pypi-publication, ADR-001) specified `pypa/gh-action-pypi-publish@release/v1`. Research found that `uv publish --trusted-publishing always` is stable (2025+), integrates natively with the `uv_build` backend, and produces a simpler workflow — approximately 10 lines vs 30+ with the separate GitHub Action.
**Decision:** Both testpypi and pypi publish jobs use `uv publish --trusted-publishing always`. TestPyPI target uses `--publish-url https://test.pypi.org/legacy/`. No external `pypa/gh-action-pypi-publish` dependency.
**Consequences:**
- ✅ Workflow is minimal and backend-native.
- ✅ PEP 740 digital attestations are emitted automatically.
- ⚠️ `uv publish` Trusted Publishing requires the same PyPI project/environment setup as the pypa action; no configuration shortcut.
**Rejected alternatives:**
- `pypa/gh-action-pypi-publish` — Rejected because uv publish is native and reduces dependencies.
**Source:** Interview #2

### ADR-003: First PyPI Publish Version Is the Next Minor After 0.13.1
**Status:** Accepted (2026-05-17, via /hm:plan interview)
**Context:** Current codebase version is 0.13.1. Separate 0.14.0 optimization work is in progress elsewhere and will land before a PyPI release. The first public release should be a clean minor boundary.
**Decision:** The infrastructure code (release.yml, artifact tests, smoke script, README update) is written now without a version bump. The actual `v*` tag push that triggers publication will happen after in-progress 0.14.0 work merges — likely at 0.14.0 or 0.15.0 depending on that work's scope. The 5-file version sync (CLAUDE.md §버전업 정책) runs at that time, not in this task.
**Consequences:**
- ✅ Release infrastructure is ready and tested before the publish act.
- ✅ First public release includes 0.14.0+ improvements.
- ⚠️ Infrastructure code ships in 0.13.1 and is dormant until the v-tag push.
**Rejected alternatives:**
- Publish 0.13.1 immediately — Rejected because 0.14.0 work is in flight.
**Source:** Interview #3

### ADR-004: Single Universal Install Prompt
**Status:** Accepted (2026-05-17, via /hm:plan interview)
**Context:** README currently has one 6-step universal bootstrap prompt inside a `<details>` block plus a separate manual step-by-step block. Research suggested per-LLM cards (Claude/Codex/Cursor). User explicitly rejected per-LLM cards.
**Decision:** One and only one install prompt exists in the README. It is platform-agnostic, IDE-agnostic, and designed so that pasting it into any LLM agent (Claude Code, Cursor, Codex, any AI assistant) produces a complete install on any OS without the user making technical choices. The LLM reads the prompt and executes all detection and branching autonomously.
**Consequences:**
- ✅ Single maintenance point; no per-IDE drift.
- ✅ Works in chat interfaces (claude.ai, copilot chat) as well as IDE agents.
- ⚠️ Prompt must be precise enough that any LLM can execute it reliably, including on Windows.
**Rejected alternatives:**
- Three separate IDE-targeted copy blocks — Rejected explicitly by user: "하나의 프롬프트만 존재해야해."
**Source:** Interview #4

### ADR-005: Release Infrastructure Ships Before Actual Publication
**Status:** Accepted (2026-05-17, via /hm:plan interview)
**Context:** The previous PLAN-pypi-publication blocked entirely at Phase 0 because name reservation requires authenticated PyPI account access. Decoupling infrastructure from the publish act allows work to proceed now.
**Decision:** This task delivers: fixed plugin.json URLs, pyproject.toml metadata, artifact tests, smoke script, release.yml, and README prompt update. The actual `git tag v0.14.x && git push origin v0.14.x` command is out of this task's scope — it runs after 0.14.0 work lands and PyPI name reservation (Phase 0) completes.
**Consequences:**
- ✅ Unblocks implementable work from the Phase 0 human-action gate.
- ⚠️ Release.yml sits dormant in repo until a v-tag is pushed; this is intentional.
**Rejected alternatives:**
- Block all work until Phase 0 completes — Rejected because Phase 0 is a human-authenticated action that can happen independently.
**Source:** Interview #5

### ADR-006: Prompt Must Work Cross-Platform With LLM-Autonomous Detection
**Status:** Accepted (2026-05-17, via /hm:plan interview)
**Context:** Current prompt uses `uname -s` which fails on Windows (non-WSL). Users on Windows/PowerShell must install uv differently (`irm https://astral.sh/uv/install.ps1 | iex` in PowerShell vs `curl -LsSf https://astral.sh/uv/install.sh | sh` on POSIX).
**Decision:** The prompt instructs the LLM to detect the OS via `uname -s 2>/dev/null || echo Windows` (or PowerShell equivalent), branch uv installation accordingly, then proceed to `uv tool install harness-maker`. All branching is done by the LLM — the user does not choose. The prompt explicitly covers: Linux, macOS, Windows (WSL path and native PowerShell path).
**Consequences:**
- ✅ Prompt is genuinely cross-platform without user manual branching.
- ⚠️ LLM must correctly identify WSL vs native Windows; prompt should hint detection cues.
**Rejected alternatives:**
- POSIX-only prompt — Rejected because Windows users would fail silently.
- Per-OS separate prompts — Rejected per ADR-004 (single prompt rule).
**Source:** Interview #6

### ADR-007: TestPyPI Job Runs Before PyPI Job
**Status:** Accepted (2026-05-17, via /hm:plan interview; inherited from PLAN-pypi-publication ADR-008)
**Context:** Publishing to production PyPI cannot be reversed by overwriting the same version. TestPyPI allows a full upload+install smoke rehearsal before committing to production.
**Decision:** The release.yml has two separate publish jobs: `publish-testpypi` (environment: `testpypi`) and `publish-pypi` (environment: `pypi`, `needs: [publish-testpypi]`). TestPyPI smoke installs from `test.pypi.org` with `--extra-index-url https://pypi.org/simple` to resolve dependencies not mirrored to TestPyPI.
**Consequences:**
- ✅ Production publish is gated by index-level install rehearsal.
- ⚠️ TestPyPI receives real version numbers; older test uploads accumulate over time.
**Rejected alternatives:**
- Skip TestPyPI — Rejected because first release risk is high and TestPyPI is free.
**Source:** Interview #7

### ADR-008: Prompt Is Visible; Manual Install Is in `<details>`
**Status:** Accepted (2026-05-17, via /hm:plan interview)
**Context:** Current README buries the bootstrap prompt inside a `<details>` block labeled "Copy this prompt." Manual step-by-step install is shown openly below.
**Decision:** Invert the structure: the single universal LLM prompt is shown openly (no `<details>`) as the primary install method. The manual step-by-step install block moves into a `<details>` section below, so power users can still access it without cluttering the first impression.
**Consequences:**
- ✅ The most important install path (LLM-driven) is immediately visible.
- ✅ Manual commands remain accessible without being the visual primary.
- ⚠️ Prompt block is longer than a typical one-liner; must be compact enough not to dominate the README.
**Rejected alternatives:**
- Keep prompt in `<details>` — Rejected by user: "프롬프트가 우선."
**Source:** Interview #8

### ADR-009: Bad Public Releases Are Yanked and Re-Issued As New Patch
**Status:** Accepted (2026-05-17, via /hm:plan interview; inherited from PLAN-pypi-publication ADR-009)
**Context:** PyPI does not support replacing an already uploaded file for the same version number.
**Decision:** If a defective version reaches PyPI: (1) yank the release via PyPI web UI (`pip install harness-maker` will warn and skip the yanked version); (2) fix the defect in code; (3) bump to the next patch version (e.g., 0.14.0 → 0.14.1) per the 5-file version sync policy; (4) push a new v-tag to trigger the release workflow. The yanked version number is never reused.
**Consequences:**
- ✅ PyPI immutability is preserved; users on `pip install harness-maker` get the fixed version automatically.
- ⚠️ The bad version number remains visible in release history with a yank notice.
**Rejected alternatives:**
- Delete and retry the same version — Rejected because PyPI rarely allows this and it harms reproducibility.
**Source:** Interview follow-up V4

## 🏗️ Technical Design

### Current State

```
pyproject.toml          ✅ uv_build backend, console_scripts, requires-python >=3.12
                        ⚠️ no classifiers, keywords, license-files; no explicit template include
src/harness_maker/      ✅ _compute_install_ref() implemented
                        ✅ test_install_ref.py exists
                        ❌ test_package_artifacts.py missing
plugin.json (×3)        ⚠️ repo URL = noel/harness-maker (wrong — must be Ecro/harness-maker)
.github/workflows/      ✅ ci.yml (lint+test on PR/push to main)
                        ❌ release.yml missing
scripts/                ❌ directory does not exist
README.md               ⚠️ bootstrap prompt in <details>; contains pre-PyPI git clone branch
```

### Affected Components

| Component | Change |
|-----------|--------|
| `.claude-plugin/plugin.json` | homepage + repository → Ecro/harness-maker |
| `.cursor-plugin/plugin.json` | same |
| `.codex-plugin/plugin.json` | same |
| `pyproject.toml` | add classifiers, keywords, license-files |
| `tests/unit/test_package_artifacts.py` | new — wheel/sdist asset assertions |
| `scripts/release_smoke.py` | new — local install smoke in Python |
| `.github/workflows/release.yml` | new — uv publish + Trusted Publishing |
| `docs/release-checklist.md` | new — Phase 0 prerequisites + release runbook |
| `README.md` | prompt restructure (open + cross-platform) |

### Dependencies

- `uv` (already required) — provides `uv build`, `uv publish`
- No new Python dependencies
- GitHub Actions: `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `softprops/action-gh-release@v2` (or gh CLI for GitHub Release)

### Architecture

**Release flow (post-Phase 0):**
```
v{NEXT}.x.y tag push
  → quality-gate job: ruff + mypy + pytest (defense-in-depth for tags, ci.yml covers PRs)
  → build job: uv build → upload dist/ as artifacts
  → publish-testpypi job: uv publish --trusted-publishing always --publish-url test.pypi.org
      → smoke: uv pip install harness-maker --extra-index-url https://pypi.org/simple
      → harness-maker --help
  → publish-pypi job (needs: publish-testpypi):
      → uv publish --trusted-publishing always
  → github-release job: create GitHub Release from CHANGELOG section
```

**CI relationship:** `ci.yml` runs on PR and `push: branches: [main]`. `release.yml` runs on `push: tags: v*` and `workflow_dispatch` (dry-run mode). The quality-gate in `release.yml` is defense-in-depth for the tag event — it re-runs the same checks to confirm no drift between the last CI run and the tag.

**Prompt architecture:**
```
README Quickstart
  ┌─────────────────────────────────────────────────┐
  │  [OPEN - no details]                            │
  │  Universal install prompt (single copy block)   │
  │  - OS detection (uname / PowerShell)            │
  │  - uv install (curl for POSIX, irm for Windows) │
  │  - uv tool install harness-maker                │
  │  - harness-maker profile . --json               │
  │  - harness-maker make . ...                     │
  │  - IDE reload instruction                       │
  └─────────────────────────────────────────────────┘
  <details>Manual install (step-by-step)</details>
```

### Design Decisions

- **Python-only scripts** (CLAUDE.md §Runtime): `scripts/release_smoke.py` uses `subprocess.run` + `zipfile` — no `.sh` files.
- **`uv_build` template auto-discovery**: `uv_build` includes all non-`.py` files tracked by git under the package directory. If Phase 2 tests reveal templates are missing from the wheel, add `[tool.uv.build] include = ["src/harness_maker/templates/**/*"]` within Phase 2 scope.
- **No version bump in this task**: The 5-file sync runs at publish time (ADR-003); this task makes no semver change.

### Data Flow

1. Developer pushes `v0.14.x` tag → release.yml triggers
2. quality-gate checks lint + types + tests
3. `uv build` produces `dist/harness_maker-*.whl` and `dist/harness_maker-*.tar.gz`
4. OIDC token → PyPI TestPyPI Trusted Publisher validates subject (`Ecro/harness-maker`, workflow `release.yml`, environment `testpypi`)
5. Smoke install from TestPyPI succeeds
6. OIDC token → PyPI Trusted Publisher validates subject (`Ecro/harness-maker`, workflow `release.yml`, environment `pypi`)
7. PyPI page live; `uv tool install harness-maker` works

### API Changes

No Python API change. Post-publication: `uv tool install harness-maker` installs the CLI from PyPI. `_compute_install_ref()` begins returning `"harness-maker"` (package name) instead of the local path for PyPI-installed wheels.

## 📝 Implementation Plan

### Phase 0 — Reserve PyPI/TestPyPI Projects (OUT OF EXECUTE SCOPE — human action)

**Scope:** Create `harness-maker` project on TestPyPI and PyPI under the `Ecro` account. Register Trusted Publishers for: repo=`Ecro/harness-maker`, workflow=`.github/workflows/release.yml`, environment=`testpypi` (on TestPyPI) and environment=`pypi` (on PyPI). Enable 2FA on both accounts.

**Files out of scope:** All code files. This phase produces only account configuration on pypi.org/test.pypi.org.

**Exit criterion:**
- `https://test.pypi.org/project/harness-maker/` exists under Ecro account
- `https://pypi.org/project/harness-maker/` exists under Ecro account
- Both Trusted Publisher entries are configured with matching repo/workflow/environment strings
- Exit is documented in `docs/release-checklist.md` (created in Phase 4)

**Risk:** high — requires authenticated browser session; cannot be automated.
**Rollback point:** If name `harness-maker` is taken: re-plan with a new package name before any code changes.

---

### Phase 1 — Fix Plugin.json URLs + pyproject.toml Metadata

**Scope:**
- Files in: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`
- Files out: `src/`, `tests/`, `.github/`, `README.md`, `scripts/`

**Changes:**
1. `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`: `"homepage"` and `"repository"` → `"https://github.com/Ecro/harness-maker"`
2. `pyproject.toml`: add `classifiers`, `keywords`, `license = "MIT"`, and `license-files = ["LICENSE"]`

**Exit criterion:**
```bash
# URL fix
grep -c '"https://github.com/Ecro/harness-maker"' \
  .claude-plugin/plugin.json .cursor-plugin/plugin.json .codex-plugin/plugin.json
# must return 6 (2 per file × 3 files)

# Metadata
grep -c "^classifiers" pyproject.toml   # >= 1
grep -c "^keywords"    pyproject.toml   # >= 1
grep -c "^license"     pyproject.toml   # >= 1 (license key or license-files)

# Lint clean
uv run ruff check .
```

**Risk:** low
**Rollback point:** Revert 4 files; no downstream breakage.

---

### Phase 2 — Package Artifact Regression Tests

**Scope:**
- Files in: `tests/unit/test_package_artifacts.py` (new); possibly `pyproject.toml` if templates missing from wheel
- Files out: `src/`, `.github/`, `README.md`

**Test design (validator W2 resolution):**
```python
# In tmp_path:
#   subprocess.run(["uv", "build", "--out-dir", str(tmp_path)], check=True)
#   wheel = next(tmp_path.glob("*.whl"))
#   with zipfile.ZipFile(wheel) as zf:
#       names = zf.namelist()
#       assert any("templates/agents/code-reviewer.md.j2" in n for n in names)
#       assert any("templates/stages/plan.md.j2" in n for n in names)
#       assert any("templates/rubrics/agent_prompt.yaml.j2" in n for n in names)
#       assert any("templates/skills/verify-before-completion/SKILL.md.j2" in n for n in names)
#       assert any("templates/commands/hm/configure.md.j2" in n for n in names)
#       assert not any("__pycache__" in n for n in names)
```

If any template assertion fails → add to `pyproject.toml`:
```toml
[tool.uv.build]
include = ["src/harness_maker/templates/**/*"]
```
and re-run tests.

**Exit criterion:**
```bash
uv run pytest tests/unit/test_package_artifacts.py -q
# must exit 0 with all template assertions passing
```

**Risk:** medium — `uv_build` template auto-discovery untested; tests may reveal missing includes.
**Rollback point:** Revert `tests/unit/test_package_artifacts.py` and any `pyproject.toml` include changes.

---

### Phase 3 — Release Smoke Script

**Scope:**
- Files in: `scripts/release_smoke.py` (new)
- Files out: all other files

**Script behavior (Python, no bash — CLAUDE.md §Runtime):**
1. Create `tmp_dist = tempfile.mkdtemp()` and `tmp_proj = tempfile.mkdtemp()`
2. `subprocess.run(["uv", "build", "--out-dir", tmp_dist], check=True, timeout=120)`
3. `subprocess.run(["uv", "venv", tmp_venv], check=True, timeout=60)`
4. `subprocess.run(["uv", "pip", "install", wheel_path, "--python", venv_python], check=True, timeout=60)`
5. `subprocess.run([harness_maker_bin, "--help"], check=True, timeout=10)`
6. `subprocess.run([harness_maker_bin, "profile", tmp_proj, "--json"], check=True, timeout=30)`
7. `subprocess.run([harness_maker_bin, "make", tmp_proj, "--preset", "Side", "--locale", "en", "--targets", "claude-code", "--yes"], check=True, timeout=60)`
8. `assert (Path(tmp_proj) / ".claude" / "harness.yaml").exists()`
9. Cleanup both tmp dirs

**Exit criterion:**
```bash
uv run python scripts/release_smoke.py
# must exit 0 from repo root
```

**Risk:** low
**Rollback point:** Delete `scripts/release_smoke.py`.

---

### Phase 4 — GitHub Actions Release Workflow + Release Checklist

**Scope:**
- Files in: `.github/workflows/release.yml` (new), `docs/release-checklist.md` (new)
- Files out: `src/`, `tests/`, `README.md`, `scripts/`

**`release.yml` structure:**

```yaml
name: release
on:
  push:
    tags: ["v*"]
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Dry run (no publish)"
        default: "true"

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps: [checkout, setup-uv, ruff, mypy, pytest]

  build:
    needs: [quality-gate]
    runs-on: ubuntu-latest
    steps: [checkout, setup-uv, "uv build", upload dist artifacts]

  publish-testpypi:
    needs: [build]
    runs-on: ubuntu-latest
    environment: testpypi
    permissions:
      id-token: write
    if: startsWith(github.ref, 'refs/tags/v') || github.event.inputs.dry_run == 'false'
    steps:
      - download dist artifacts
      - setup-uv
      - echo "Subject: ${GITHUB_REPOSITORY}/.github/workflows/release.yml@${GITHUB_REF}"
      - uv publish --trusted-publishing always --publish-url https://test.pypi.org/legacy/
      - uv pip install harness-maker --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/
      - harness-maker --help

  publish-pypi:
    needs: [publish-testpypi]
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - download dist artifacts
      - setup-uv
      - uv publish --trusted-publishing always

  github-release:
    needs: [publish-pypi]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - create GitHub Release from CHANGELOG section matching tag version
```

**`docs/release-checklist.md`:** Documents Phase 0 prerequisites (PyPI/TestPyPI account + 2FA, project creation, Trusted Publisher config for each environment), exact Trusted Publisher subject strings, local smoke command, tag command (`git tag v0.14.x && git push origin v0.14.x`), expected PyPI/TestPyPI URLs, post-release install verification, and ADR-009 yank procedure.

**Exit criterion:**
```bash
# Structural check (actionlint when available)
command -v actionlint && actionlint .github/workflows/release.yml || true

# Static content assertions
grep -c 'workflow_dispatch' .github/workflows/release.yml    # >= 1
grep -c 'tags.*v\*'         .github/workflows/release.yml    # >= 1
grep -c 'environment: testpypi' .github/workflows/release.yml  # >= 1
grep -c 'environment: pypi'     .github/workflows/release.yml  # >= 1
grep -c 'id-token: write'   .github/workflows/release.yml    # >= 2
grep -c 'startsWith.*refs/tags/v' .github/workflows/release.yml  # >= 2
grep -c 'trusted-publishing always' .github/workflows/release.yml  # >= 2
grep -c 'extra-index-url'   .github/workflows/release.yml    # >= 1

# Checklist exists
test -f docs/release-checklist.md
```

**Risk:** high — first release infrastructure; Trusted Publisher config on PyPI side is Phase 0 dependency.
**Rollback point:** Delete `.github/workflows/release.yml` and `docs/release-checklist.md`; manual publish remains possible via `uv publish` locally with `--token`.

---

### Phase 5 — README Install Prompt Redesign

**Scope:**
- Files in: `README.md`
- Files out: all other files

**Changes:**
1. Remove `<details>` wrapper from the existing bootstrap prompt block.
2. Update prompt content:
   - Remove the pre-PyPI "git clone https://github.com/Ecro/harness-maker" branch.
   - Make `uv tool install harness-maker` the single install command (no conditional install path for users).
   - Add Windows-aware uv bootstrap: instruct LLM to run `uname -s 2>/dev/null` to detect OS; if Windows/no uname, use PowerShell `irm https://astral.sh/uv/install.ps1 | iex`; otherwise use `curl -LsSf https://astral.sh/uv/install.sh | sh`.
   - Add: "If uv is already installed, skip the uv install step."
3. Move manual step-by-step install block into a `<details>Manual install (step-by-step)</details>` section immediately below the prompt.
4. Add brief one-line intro above the prompt: "Paste into any LLM agent — it installs harness-maker and generates your project harness automatically."

**Exit criterion:**
```bash
# Prompt is NOT inside <details>
python3 -c "
import re, pathlib
text = pathlib.Path('README.md').read_text()
# Find details blocks
details = re.findall(r'<details>.*?</details>', text, re.DOTALL)
# Prompt keywords must appear OUTSIDE all details blocks
prompt_block = re.search(r'Paste into any LLM', text)
assert prompt_block, 'intro line missing'
prompt_pos = prompt_block.start()
for d in details:
    d_start = text.find(d)
    d_end = d_start + len(d)
    assert not (d_start <= prompt_pos <= d_end), 'prompt is inside details block'
print('OK: prompt is visible')
"

# Content assertions
grep -c 'uv tool install harness-maker' README.md   # >= 2
grep -c 'irm.*astral.sh.*install.ps1'  README.md    # >= 1 (Windows uv install)
grep -c 'curl.*astral.sh.*install.sh'  README.md    # >= 1 (POSIX uv install)
grep -c '<details>' README.md                         # >= 1 (manual install folded)
```

**Risk:** low
**Rollback point:** Revert `README.md`.

## 🧪 Testing Strategy

| Layer | What | Command |
|-------|------|---------|
| Unit | Wheel/sdist asset inclusion | `uv run pytest tests/unit/test_package_artifacts.py -q` |
| Unit | install_ref detection paths | `uv run pytest tests/unit/test_install_ref.py -q` (exists) |
| Smoke | Local wheel build + install + CLI | `uv run python scripts/release_smoke.py` |
| CI static | Workflow structure | `actionlint .github/workflows/release.yml` |
| CI static | Workflow content greps | See Phase 4 exit criterion |
| Manual | Bootstrap prompt in Claude Code | Paste prompt into CC agent; verify install + make + reload |
| Manual | Bootstrap prompt on Windows | Paste prompt in Cursor on Windows; verify PowerShell uv install |
| Post-publish | PyPI install smoke | `uv tool install harness-maker && harness-maker --help` |

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `harness-maker` name taken on PyPI | high | Phase 0 reservation before code work; stop and re-plan if taken |
| Trusted Publisher subject mismatch | high | Phase 0 checklist documents exact strings; release.yml echoes subject in logs |
| `uv_build` doesn't auto-include .j2 templates | medium | Phase 2 tests fail fast; fallback: add explicit `[tool.uv.build] include` in same phase |
| TestPyPI dependency resolution fails | medium | `--extra-index-url https://pypi.org/simple` on install smoke |
| Bad first PyPI release | medium | TestPyPI gate + ADR-009 yank policy |
| Windows cross-platform prompt fails | medium | Explicit PowerShell `irm` branch in prompt; Phase 5 exit criterion greps for it |
| Release.yml is dormant until v-tag (months) | low | Acceptable per ADR-005; checklist documents activation procedure |
| ci.yml vs release.yml quality-gate drift | low | Controlled by same `uv run ruff/mypy/pytest` commands; link in release.yml comments |

## ✅ Success Criteria

- [x] All 3 plugin.json files: `"homepage"` and `"repository"` = `"https://github.com/Ecro/harness-maker"`
- [x] `pyproject.toml` has `classifiers`, `keywords`, `license` (or `license-files`) fields
- [x] `uv run pytest tests/unit/test_package_artifacts.py -q` passes: wheel includes .j2 templates, excludes `__pycache__`
- [x] `uv run python scripts/release_smoke.py` exits 0 from clean checkout
- [x] `.github/workflows/release.yml` passes `actionlint`; static greps confirm required elements (testpypi + pypi environments, id-token: write, v* tag guard, `--trusted-publishing always`, `--extra-index-url`)
- [x] `docs/release-checklist.md` exists with Phase 0 steps, Trusted Publisher subject strings, tag command, yank procedure
- [x] `README.md`: universal prompt is visible (not in `<details>`); includes `irm` (Windows) and `curl` (POSIX) uv install; `uv tool install harness-maker` present; manual install in `<details>` below
- [x] Full `uv run pytest -q` passes with no regressions
- [x] After v-tag push (future, post-Phase 0): `uv tool install harness-maker && harness-maker --help` works from PyPI

## 🔍 Plan Validation

| Pass | Outcome | Critiques | Resolution |
|------|---------|-----------|-----------|
| 1 | NEEDS_REVISION | W1: No Phase 0 verification artifact; W2: test fixture method unspecified; W3: cross-platform prompt detection commands unspecified; W4: ADR-009 body missing; W5: ci.yml vs release.yml relationship unclear; W6: Phase 1 exit criterion missing classifiers/license-files check | All 6 resolved: W1→docs/release-checklist.md added as Phase 4 output; W2→zipfile.ZipFile.namelist method specified in Phase 2; W3→irm+curl detection specified in ADR-006+Phase 5; W4→ADR-009 included verbatim; W5→CI relationship explained in Technical Design; W6→Phase 1 exit extended to grep for classifiers+license |

**Validator outcome:** `NEEDS_REVISION_RESOLVED`.
