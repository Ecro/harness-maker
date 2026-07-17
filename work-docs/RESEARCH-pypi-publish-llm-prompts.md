---
type: research
task_slug: pypi-publish-llm-prompts
status: complete
created: 2026-05-17
tags: [harness-maker, research, python, pypi, packaging, llm-prompts, release-automation]
mtime_warn_days: 7
libs_fetched: [uv-docs, pypi-trusted-publishers, astral-sh/trusted-publishing-examples]
sources:
  - https://docs.astral.sh/uv/guides/package/
  - https://docs.astral.sh/uv/concepts/build-backend/
  - https://docs.pypi.org/trusted-publishers/
  - https://github.com/astral-sh/trusted-publishing-examples
related_docs:
  - "[[work-docs/PLAN-pypi-publication.md]]"
  - "[[work-docs/PLAN-install-without-claude-code.md]]"
  - "[[work-docs/REVIEW-install-without-claude-code-2026-05-12.md]]"
summary: "uv publish + Trusted Publishing; add targeted per-LLM install prompts to README post-release"
---

## 🎯 Recommended Direction

Use `uv publish --trusted-publishing always` (not pypa/gh-action-pypi-publish) for a simpler 10-line release workflow; after publication, replace the existing generic bootstrap prompt with three LLM-targeted prompts (Claude, Codex, Cursor) plus a `uvx` one-liner.

**Rationale:** A prior PLAN (`PLAN-pypi-publication.md`, status: planning, blocked at Phase 0) already locked 12 ADRs for the publishing architecture. The main things that have changed since: (1) version is now 0.13.1 not 0.11.2; (2) `uv publish` is now stable and preferred — it replaces the `pypa/gh-action-pypi-publish` action and cuts the workflow by ~60%; (3) the "Universal Bootstrap Prompt" already exists in the README from `PLAN-install-without-claude-code` (complete). The remaining blockers are identical: Phase 0 name reservation is a human-authenticated action; the release.yml and `scripts/` directory do not exist yet.

## 🔍 Refinement Decisions

Discovery lens: Technical architecture / implementation + User-workflow / product opportunity.

## 🛠️ Approaches Found

### Approach A — uv publish + Trusted Publishing (recommended)

| Field | Content |
|-------|---------|
| **Approach** | `uv build` + `uv publish --trusted-publishing always` in GitHub Actions |
| **Assumption** | PyPI/TestPyPI `harness-maker` project reserved under `Ecro` account before any code changes |
| **Evidence** | Astral docs confirm `uv publish` is stable; `astral-sh/trusted-publishing-examples` repo is the canonical reference (2025). Minimal workflow: checkout → setup-uv → `uv build` → `uv publish` |
| **Trade-off** | Simpler workflow than old plan, but Trusted Publisher setup on PyPI side must reference the correct repo (`Ecro/harness-maker`, NOT `noel/harness-maker` — the plugin.json has the wrong owner, needs fixing) |
| **Compatibility** | `uv_build` is already the build backend in `pyproject.toml`. No change to build system. |
| **Risk** | low |

Minimal release.yml shape:
```yaml
name: release
on:
  push:
    tags: ["v*"]
jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv build
      - run: uv publish --trusted-publishing always
```

For TestPyPI gating (ADR-008 from old plan), split into two jobs: `testpypi` (environment: testpypi) then `pypi` (environment: pypi, needs: testpypi).

### Approach B — pypa/gh-action-pypi-publish (old plan, deprecated path)

| Field | Content |
|-------|---------|
| **Approach** | `uv build` + `pypa/gh-action-pypi-publish@release/v1` |
| **Assumption** | Still requires same Trusted Publisher config on PyPI side |
| **Evidence** | This was the approach in PLAN-pypi-publication.md (2026-05-12). Still works, more established GitHub Action. |
| **Trade-off** | Extra dependency on external action; uv already ships publish natively |
| **Compatibility** | Same as Approach A |
| **Risk** | low |

**Binding trade-off**: Approach A is strictly simpler. The only reason to prefer B is if `uv publish`'s Trusted Publishing has a known regression — no evidence of that as of 2026-05.

### Approach C — Per-LLM prompt design: unified vs targeted

| Field | Content |
|-------|---------|
| **Approach** | Three separate prompts (Claude, Codex, Cursor) vs. one unified prompt |
| **Assumption** | README already has a 6-step universal prompt in a `<details>` block |
| **Evidence** | Current README prompt works but doesn't highlight IDE-specific benefits. Emerging practice (2025-2026): one `uvx <package>` one-liner at the top + IDE-targeted copy blocks below |
| **Trade-off** | Targeted prompts are more actionable; unified prompt is DRY. Targeted prompts become stale when step counts change. |
| **Compatibility** | Both coexist in README — keep unified for "any agent" and add targeted as additional cards |
| **Risk** | low |

Post-PyPI prompt structure recommendation:
- **One-liner** (top of README, all IDEs): `uvx harness-maker make .`
- **Claude Code card**: emphasizes CLAUDE.md, `/hm:*` commands, `--plugin-dir`
- **Cursor card**: emphasizes `.cursor/rules/`, reload window, targets=cursor
- **Codex card**: emphasizes AGENTS.md, `.codex/`, `.agents/skills/`

## ⚠️ Pitfalls

1. **Plugin.json repo URL mismatch** — `.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json` both list `https://github.com/noel/harness-maker` but the actual git remote is `Ecro/harness-maker`. PyPI Trusted Publisher registration uses the GitHub repo owner/name. If the Trusted Publisher is configured for `Ecro/harness-maker` but the plugin.json links to `noel/harness-maker`, documentation will mislead users. Fix plugin.json URLs to `Ecro/harness-maker` before publication. *Source: git remote -v + plugin.json inspection.*

2. **Version drift** — PLAN-pypi-publication.md was written for version 0.11.2. Current version is 0.13.1. The 5-file version sync rule (CLAUDE.md §버전업 정책) requires: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`. All currently say 0.13.1 — no action needed. The release version question is whether to publish 0.13.1 directly or bump to 0.14.0 for the PyPI-launch milestone. *Source: codebase inspection.*

3. **Phase 0 still a human-action gate** — PLAN-pypi-publication.md Phase 0 (create `harness-maker` projects on PyPI + TestPyPI and register Trusted Publishers) is blocked because it requires an authenticated web browser session. This research cannot resolve it. It must happen before any code changes. *Source: PLAN-pypi-publication.md §Execution Status.*

4. **`uvx harness-maker` pre-reservation behavior** — `uvx harness-maker` before PyPI publication will fail with "No solution found" (same failure class as `[fail:design] install-ref-editable-only-check`). The README must clearly mark the PyPI one-liner as post-release only, or gate it behind a version check. *Source: [wiki:gotcha] install-ref-file-url-vs-editable.*

5. **TestPyPI dependency resolution** — Dependencies (`anthropic`, `jinja2`, `pyyaml`, etc.) are on PyPI but not TestPyPI. Install from TestPyPI requires `--extra-index-url https://pypi.org/simple`. The `uv publish` workflow must set `UV_INDEX` or pass flags when running the install smoke. *Source: PLAN-pypi-publication.md ADR-008.*

6. **Scripts directory does not exist** — PLAN-pypi-publication.md Phase 3 specifies `scripts/release-smoke.sh` but the `scripts/` directory was never created. Either create it or replace with a Python-based smoke script (CLAUDE.md §Bash 사용 금지). *Source: codebase ls.*

7. **`uv_build` pure-Python only** — `uv_build` cannot build C extensions. harness-maker has no C extensions, so this is not a current constraint. Do not add any C extension without switching build backends. *Source: web research.*

## ❓ Open Questions

1. **Target version for first PyPI release** — Publish `0.13.1` directly (conservative, existing tests pass) or bump to `0.14.0` (signals the PyPI-launch as a milestone)? This is a policy decision for `/hm:plan`.

2. **GitHub account for PyPI** — Trusted Publisher must exactly match repo owner. Actual remote is `Ecro/harness-maker`. Plugin.json links say `noel/harness-maker`. Which GitHub account is registering on PyPI? Fix plugin.json before publication. `/hm:plan` must lock the exact owner string.

3. **TestPyPI gate: separate job or same job?** — Old plan (ADR-008) specified same tag → TestPyPI smoke → then PyPI. With `uv publish`, this means two jobs with `needs:` dependency. Or skip TestPyPI gate for initial release (faster, riskier). Plan must decide.

4. **Per-LLM prompt format** — Should the three targeted prompts be separate `<details>` blocks? Or a tabbed layout (GitHub Markdown doesn't support tabs)? Or a single unified prompt that remains, plus a brief "Quick one-liner" at the top? Needs a concrete proposal in `/hm:plan`.

5. **`uvx` vs `uv tool install` in prompts** — `uvx harness-maker make .` runs in a temp environment (ephemeral). For hooks and `uv run --with harness-maker`, the package must be installed, not just run via uvx. The prompts must distinguish: uvx for a quick test, `uv tool install` for persistent use. This affects `_compute_install_ref()` behavior too (uvx installs may not have `direct_url.json`).

6. **scripts/ as .sh or .py** — CLAUDE.md prohibits Bash. `scripts/release-smoke.sh` from the old plan needs to be `scripts/release_smoke.py` or a `Makefile`-equivalent. Which format? `/hm:plan` should lock.

## 📚 Sources

- [uv packaging guide](https://docs.astral.sh/uv/guides/package/)
- [uv build backend docs](https://docs.astral.sh/uv/concepts/build-backend/)
- [astral-sh/trusted-publishing-examples (GitHub)](https://github.com/astral-sh/trusted-publishing-examples)
- [PyPI Trusted Publishers docs](https://docs.pypi.org/trusted-publishers/)
- [PyPI Trusted Publishing usage with GitHub Actions](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [Automate uv with Trusted Publisher](https://dump.zech.sh/automate-uv-with-trusted-publisher)
- Internal: `PLAN-pypi-publication.md` (12 ADRs, status: planning/Phase-0-blocked)
- Internal: `PLAN-install-without-claude-code.md` (status: complete — console_scripts, _compute_install_ref, Universal Bootstrap Prompt)
- Internal: `[wiki:architecture] ide-agnostic-install-ref` — _compute_install_ref() behavior
- Internal: `[wiki:gotcha] install-ref-file-url-vs-editable` — file:// URL detection

## 🔗 Related Internal Docs

- [[work-docs/PLAN-pypi-publication.md]] — prior comprehensive plan, 12 ADRs, blocked Phase 0
- [[work-docs/PLAN-install-without-claude-code.md]] — console_scripts + Universal Bootstrap Prompt (complete)
- [[work-docs/REVIEW-install-without-claude-code-2026-05-12.md]] — review of completed install-without-cc
- [[.claude/memory/wiki.md#ide-agnostic-install-ref]] — _compute_install_ref() architecture
- [[.claude/memory/wiki.md#install-ref-file-url-vs-editable]] — pitfall: editable-only check
- [[.claude/memory/failures.md#install-ref-editable-only-check]] — original failure that drove the fix
