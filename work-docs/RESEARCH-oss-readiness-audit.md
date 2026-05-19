---
type: research
task_slug: oss-readiness-audit
status: complete
created: 2026-05-19
tags: [harness-maker, research, oss, community-health, discoverability, ci-cd, positioning]
mtime_warn_days: 14
libs_fetched: []
sources:
  - https://claudemarketplaces.com/
  - https://github.com/Chat2AnyLLM/awesome-claude-plugins
  - https://github.com/rohitg00/awesome-claude-code-toolkit
  - https://github.com/ComposioHQ/awesome-claude-plugins
  - https://github.com/SuperClaude-Org/SuperClaude_Framework
  - https://github.com/bmad-code-org/BMAD-METHOD
  - https://github.com/buildermethods/agent-os
  - https://github.com/ruvnet/ruflo
  - https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories
  - https://launchtry.com/resources/launch-checklist/open-source
  - https://www.aikido.dev/blog/checklist-github-actions
  - https://pypi.org/pypi/harness-maker/json
related_docs:
  - [[README.md#how-it-compares]]
  - [[README.md#roadmap]]
  - [[docs/release-checklist.md]]
  - [[docs/CONTRIBUTING.md]]
  - [[CLAUDE.md]]
summary: "Repo is already public + on PyPI; gap is OSS launch readiness — fix CI/community/discoverability before announcing."
---

## 🎯 Recommended Direction

**Stop calling it "going open source" — the repo has been public since 2026-05-03 and on PyPI since 0.15.3. The real question is OSS *launch* readiness: a project that today survives an external PR, an external security report, an external discovery path. It does not survive any of the three.** Land a tightly-scoped readiness wave (PR CI restored, 6 community files, 1 SECURITY policy, 3 marketplace listings, 1 demo asset) before any public announcement. Hold the launch shot until that floor is in place — competing with SuperClaude (20.4k★) and BMAD on a stack of "1 star, 0 forks, no CI on PR, not in any directory" is a one-attempt event you do not want to spend now.

## 🔍 Refinement Decisions

- `--deep` not set; skipped Phase 0 interview.
- Discovery lenses (Phase 0.75): **User-workflow / product opportunity** (primary — how do harness users actually discover/adopt?), **Risk / compliance / security** (secondary — accepting PRs, supply chain, telemetry posture), **Technical architecture** (audit-only — what mechanical gaps block contributors?). arXiv/benchmark lens deliberately skipped — this is a launch-readiness topic, not a research-frontier topic.

## 📊 Current State Snapshot (as of 2026-05-19, commit `975fa88`, version `0.17.0`)

| Dimension | State | Source |
|---|---|---|
| Repo visibility | Public since 2026-05-03 | `gh api repos/Ecro/harness-maker` |
| GitHub social proof | **1 ★, 0 forks, 0 issues, 0 watchers** | `gh api` |
| PyPI | Published, latest 0.17.0 (2026-05-18) | pypi.org/pypi/harness-maker/json |
| Topics | 10 set (claude-code, cursor, codex, …) | `gh api` |
| License | MIT, `license-files = ["LICENSE"]` in pyproject | `LICENSE`, `pyproject.toml` |
| README | 795 lines EN + 725 lines KO mirror | `README.md`, `README.ko.md` |
| CHANGELOG | 1,028 lines, kept current | `CHANGELOG.md` |
| ADRs | 4 cross-PLAN promoted + many in-PLAN | `docs/adr/` |
| Tests | 143 test files (122 unit / 9 integration / 7 e2e + snapshot/ablation/cursor-compat/codex-compat) | `find tests/` |
| Source LOC | ~21.9k Python | `wc -l src/harness_maker/**/*.py` |
| Test LOC | ~31.5k (1.4× source) | `wc -l tests/**/test_*.py` |
| Release cadence | 9 GitHub releases in past 16 days | `gh release list` |
| GitHub Actions | **`release.yml` only** — CI on PR was deleted 2026-05-04 (commit `565d7ce`, "private solo project, local checks sufficient") | `.github/workflows/` + `git show 565d7ce` |
| Action SHA pinning | Yes (good supply-chain posture) | `release.yml` |
| Trusted Publisher | Yes (PyPI + TestPyPI OIDC, no API tokens) | `release.yml` |
| Dependabot / Renovate | **None** | `.github/dependabot.yml` absent |
| SECURITY.md | **Missing** (both root and `.github/`); `isSecurityPolicyEnabled = false` | `gh api` |
| CODE_OF_CONDUCT.md | **Missing**; `codeOfConduct = null` | `gh api` |
| CONTRIBUTING.md at root | **Missing** (only `docs/CONTRIBUTING.md` exists — GitHub does not surface that location) | `find . -maxdepth 1` |
| Issue templates | **Missing** | `.github/ISSUE_TEMPLATE/` absent |
| PR template | **Missing** | `.github/PULL_REQUEST_TEMPLATE.md` absent |
| Funding metadata | **Missing** (`.github/FUNDING.yml`) | absent |
| Discussions | **Disabled** | `hasDiscussionsEnabled = false` |
| Coverage badge / report | **Missing** | README scan |
| Demo screencast / GIF | **Missing** — already listed in README `## Roadmap` "Standing items" | `README.md:776` |
| Marketplace listings | **Not on** claudemarketplaces.com (1,181 plugins indexed), **not on** `Chat2AnyLLM/awesome-claude-plugins`, **not on** `rohitg00/awesome-claude-code-toolkit` | WebFetch each |

## 🛠️ Approaches Found

### Approach A — Minimum Viable Public Launch (2 days, low risk)

| Field | Content |
|---|---|
| **Approach** | Land community files, restore PR CI, fix discoverability — no announcement |
| **Assumption** | Maintainer treats the project as inviting contributors; will respond to issues within ~1 week |
| **Evidence** | GitHub Community Profile spec; binbash pre-launch checklist; LaunchTry 2026 open-source checklist all converge on this exact floor (README/LICENSE/CONTRIBUTING/CoC/SECURITY/ISSUE+PR templates + CI). Today the repo passes 2 of those 8 |
| **Trade-off** | ~2 days of non-feature work; introduces a CoC commitment to enforce |
| **Compatibility** | High — `docs/CONTRIBUTING.md` already exists, can be re-pointed; `release.yml` already runs the full gate, can be split into `ci.yml` + `release.yml` cheaply |
| **Risk** | low |

### Approach B — Marketing Launch (A + 1–2 weeks)

| Field | Content |
|---|---|
| **Approach** | A + demo screencast + Show HN / r/ClaudeAI / Twitter campaign + submit to 3 marketplaces + 1.0.0 rebrand |
| **Assumption** | First wave of attention can be absorbed without the harness silently breaking on stacks the maintainer has never tested |
| **Evidence** | SuperClaude reached 20.4k★ via marketplace + awesome-list density; BMAD's V6 momentum came from multi-fork ecosystem visibility. No major harness has launched silently and grown |
| **Trade-off** | Reputation risk if the visible bugs outpace fix rate. Today's release cadence (9 patches in 16 days, 5 of which fixed previous patches) signals "moves too fast for first-time adopter trust" |
| **Compatibility** | Medium — current 0.x + `Development Status :: 4 - Beta` classifier contradicts "ready to depend on" messaging |
| **Risk** | medium |

### Approach C — Hardening-First Quiet Launch (A + 2–4 weeks)

| Field | Content |
|---|---|
| **Approach** | A + supply-chain hardening (Dependabot/Renovate + `pip-audit`/`uv` advisory check in CI + SBOM in release artifact) + explicit `PRIVACY.md` for the telemetry claim + 2-week disclosure embargo window before announcement |
| **Assumption** | Trust > visibility for a new entrant in a security-sensitive category (reviewer agents have file-write and Bash) |
| **Evidence** | Reviewer-agent permission split is already non-trivial (CLAUDE.md §보안/권한 lists pinpoint denials of `Bash(python:*)`, `Bash(sh:*)`, etc.). External adopters will probe this. Telemetry is local-only by design but undocumented at root — easy to flag in a Show HN comment |
| **Trade-off** | Delay vs better first impression. Misses the current Claude Code plugin wave's peak attention if pushed too late |
| **Compatibility** | High — fits the project's existing security-conscious posture |
| **Risk** | low |

**Synthesis — what I'd actually do:** A is mandatory regardless. The B-vs-C choice is "growth-first" vs "trust-first" against incumbents with 20k+ stars. For a security-touching project competing on personalization (a hard claim to verify in 30 seconds), C wins — trust is the differentiator harness-maker can credibly own; visibility-spend by a stranger is the differentiator BMAD/SuperClaude already own. So: A immediately, C in week 2, B after the first external contribution lands successfully.

## ⚠️ Pitfalls

1. **CI-on-tag-only is a public-PR landmine.** `release.yml` runs only on `v*` tag push (line 4 of the file). A contributor's PR sees green required-checks list with zero entries — maintainer must remember to run tests locally on every PR. The commit message of `565d7ce` says "private solo project, local checks sufficient", but the repo went public the previous day. *Fix: split `release.yml` into `ci.yml` (PR + push to main) + `release.yml` (tag-only publish). Quality-gate job can be lifted near-verbatim.*
2. **No SECURITY.md = no responsible-disclosure path.** A reporter has to file a public issue or email a personal address inferred from commits. GitHub's "Report a vulnerability" UI button stays hidden until `SECURITY.md` exists. (Source: GitHub community standards docs.)
3. **Disabled Discussions starves Q&A energy into issues.** Issues become a mix of bug reports and "how do I configure preset X" — kills triage signal. Cheap to flip on.
4. **Comparison table that names live competitors.** The current `## How it compares` table names ohmyclaudecode, superpowers, Archon, aider, ouroboros — most maintainers are fine, but punching tone risks drama on launch day. *Fix: rewrite as "What category does this fill?" rather than "Why is X worse?".*
5. **Korean README parity = silent drift surface.** 725 KO + 795 EN lines, maintained by one person. Every README edit doubles. Either commit to a `docs/i18n/` mkdocs build with explicit "last synced" stamps, or downgrade KO to a short "한국어 요약" + link to deepl/translate.
6. **0.x with weekly breaking patches scares enterprise.** 0.15.0 → 0.15.3 inside 24h fixing prior patches' regressions (visible in `git log`). Either commit to a 1.0.0 stability window or document a "we will keep breaking until N projects depend on us" caveat — silence on this is a tell.
7. **Telemetry claim ("100% local") is high-trust, low-discoverability.** It's in `CLAUDE.md` and `docs/ARCHITECTURE.md` but not in README's first screen and not in a `PRIVACY.md`. Will be misread the day someone notices `metrics-YYYY-MM-DD.jsonl` files.
8. **Backup directories `.backup-*/` are gitignored (good) but the directory roots stay visible in `ls`** — fine for the maintainer, mildly noisy for a first-time PR reviewer cloning the repo. Optional cleanup.
9. **`gh api`-visible state: 0 forks, 0 watchers.** External signals contradict the maintenance-quality of the code. The cheapest single fix is a one-paragraph "Why I built this" in the repo description / pinned README section that converts the visible activity into trust.
10. **Removing PR CI under the rationale "local checks sufficient" is a documented anti-pattern** that competitors don't repeat: BMAD, SuperClaude, agent-os, claude-flow all have public CI status badges on README. The repo's CI absence is visible to anyone hunting before they ★.

## 📌 Local capability × user-artifact mapping (Phase 0.75 lens 1)

How do users discover and adopt a new Claude Code harness today? Mapping our existing capabilities to the artifacts they already maintain:

| User artifact | Today's harness-maker behavior | Gap that blocks discovery/adoption |
|---|---|---|
| `~/.claude/settings.json` (Claude Code) | Shallow-merge preserves user keys (0.3.1 fix) | Documented in CLAUDE.md but not in README onboarding flow |
| `.cursor/rules/*.mdc`, `.aider.conf.yml`, `.continue/`, `.github/copilot-instructions.md` | Foreign-config detection + LLM mapping + apply (M17) | **Differentiator** — should be the README hero screencast (currently missing) |
| `AGENTS.md` (Codex) | Block-merge marker preservation | Same |
| Marketplaces (claudemarketplaces.com / buildwithclaude / awesome lists) | Manifests rendered for Claude+Cursor+Codex | **Not submitted to any directory** — biggest single discoverability blocker |
| PyPI search | Listed; classifiers correct | PyPI search rarely surfaces "claude-code" — relies on someone already knowing the name |
| Show HN / r/ClaudeAI / X posts | None | No demo asset to anchor a post |
| GitHub topics search (`topic:claude-code`) | 10 topics set | Repo would appear, but with 1 ★ ranking sorts it to the bottom |

The single biggest gap is **#3 (marketplace submission)** — every plugin ecosystem competitor is in one or more of those indexes; harness-maker is in none.

## ❓ Open Questions (for `/hm:plan` to lock)

1. **Stability commitment** — 1.0.0 rebrand + SemVer guarantee for the user-facing surface (slash commands, `harness.yaml` keys), or stay 0.x indefinitely with a documented "breaking until X" policy? Today's 0.15.0→0.15.3-in-24h cadence cannot survive enterprise scrutiny.
2. **Maintenance model** — solo maintainer indefinitely, or open the door (CoC + CONTRIBUTING + DCO sign-off + maintainer eligibility doc)? Affects whether the floor needs a CLA or just DCO.
3. **Telemetry posture** — is the "100% local, never transmitted" guarantee strong enough that a one-line opt-out env var is unnecessary, or should the launch ship with `HARNESS_MAKER_TELEMETRY=0` + a `PRIVACY.md` documenting the JSON schema of `metrics-YYYY-MM-DD.jsonl`?
4. **Korean README continuation** — preserve full mirror, downgrade to summary + link, or migrate both to a mkdocs/Docusaurus site with sync stamps?
5. **Comparison-section tone** — keep named-competitor table or pivot to "what category does this fill". Affects launch-day blast radius.
6. **Marketplace priority order** — which directory first? (claudemarketplaces.com is baseline; awesome-list PRs are highest-ROI for discoverability per-effort.)
7. **CI scope on PR** — restore the full quality-gate (ruff + ruff format + mypy strict + pytest + INTEGRATION=1 integration test), or split into a fast "PR-fast" job + slow nightly? The current `release.yml` quality-gate runs in ~3–5 min — splittable.
8. **Funding signal** — leave `.github/FUNDING.yml` absent (signals "personal project, no obligation") or add (signals "intend to support long-term")? Either is OK but pick deliberately.
9. **Bug-bounty / disclosure embargo length** — 2 weeks between SECURITY.md ship and any announcement, or skip entirely?
10. **Demo asset format** — terminal recording (asciinema), animated GIF, or hosted screencast? Asciinema is lightweight + copyable but lower visual punch.

## 📊 Concrete OSS Launch-Readiness Checklist (synthesis of A + C)

The "definitely-must-land-before-any-announcement" set, with status today:

| # | Item | Status today | Effort | Source |
|---|---|---|---|---|
| 1 | `.github/workflows/ci.yml` on PR + push (run ruff, ruff format, mypy --strict, pytest) | ❌ removed in `565d7ce` | 30 min | release.yml quality-gate exists, lift it |
| 2 | `CONTRIBUTING.md` at repo root (link/copy from `docs/CONTRIBUTING.md`) | ❌ | 10 min | GitHub community profile |
| 3 | `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) | ❌ | 5 min | github.com/Contributor Covenant |
| 4 | `SECURITY.md` — disclosure email + GPG-key option + scope (telemetry/permissions) | ❌ | 20 min | GitHub Security docs |
| 5 | `.github/ISSUE_TEMPLATE/bug.yml` + `feature.yml` + `config.yml` (disable_blank=true) | ❌ | 20 min | GitHub issue forms |
| 6 | `.github/PULL_REQUEST_TEMPLATE.md` — preflight checklist matching CLAUDE.md "8 checkpoints" | ❌ | 15 min | local |
| 7 | Enable GitHub Discussions (`hasDiscussionsEnabled = true`) + 4 default categories | ❌ | 2 min | repo settings |
| 8 | `.github/dependabot.yml` — weekly `uv` + `github-actions` | ❌ | 5 min | Dependabot v2 |
| 9 | `PRIVACY.md` (or `docs/PRIVACY.md`) — schema of local telemetry, opt-out env var, zero-transmission guarantee | ❌ | 30 min | own |
| 10 | README badges row: PyPI version, PyPI downloads, CI status, license already present | partial | 5 min | shields.io |
| 11 | Submit to `claudemarketplaces.com` (form on site) | ❌ | 10 min | claudemarketplaces.com |
| 12 | PR to `Chat2AnyLLM/awesome-claude-plugins` (category: Workflow Orchestration or Code Quality Testing) | ❌ | 20 min | repo CONTRIBUTING |
| 13 | PR to `rohitg00/awesome-claude-code-toolkit` | ❌ | 20 min | repo CONTRIBUTING |
| 14 | Demo asciinema or GIF in README header (60-second `/hm:make` walkthrough on a fresh repo) | ❌ | 90 min | asciinema.org |
| 15 | Repo description tightened to ~150 chars (current 232 chars — truncates in GitHub search results) | needs trim | 5 min | own |
| 16 | Repository social-preview image (`Settings → Social preview`) | unknown — verify | 10 min | GitHub settings |
| 17 | Optional: `CITATION.cff` for academic-adjacent uses (anti-rot crawls arxiv) | ❌ | 10 min | citation-file-format.github.io |
| 18 | Optional: `.github/FUNDING.yml` (GitHub Sponsors or "no funding requested") | ❌ | 2 min | GitHub funding docs |
| 19 | Optional: `pip-audit` step in `ci.yml` for advisory scan | ❌ | 5 min | pypa/pip-audit |
| 20 | Optional: `actions/dependency-review` job on PR (blocks PRs that introduce vulnerable deps) | ❌ | 5 min | GitHub Actions docs |

**Time-boxed total** (1–14, mandatory): ~5 hours of focused work. (15–20 optional, ~30 min more.)

## 🧭 Competitive positioning (for the comparison section + launch copy)

| Project | Stars (May 2026) | Niche it owns | What it does *not* do that harness-maker does |
|---|---|---|---|
| SuperClaude_Framework | 20.4k | 16 specialist agents + 9 personas as config | No project profiling, no interview, no preset axis, no Cursor/Codex native renders |
| BMAD-METHOD V6 (+ multi-fork ecosystem) | thousands across forks | Agile SDLC roles (PM/Architect/Dev/QA) + 26 workflows | No detection-driven defaults, no anti-rot, no block-merge upgrades, no AI-readiness rubric |
| agent-os v3 (buildermethods) | n/a (Discussions #310 → v3) | Standards + spec-driven workflow | No multi-IDE, no automated review-grade-gate, no foreign-config import |
| claude-flow / Ruflo (ruvnet) | thousands; 6k+ commits | Multi-agent orchestration + swarm + 314 MCP tools | Different category (orchestration platform vs. harness generator); not a direct competitor but absorbs mindshare |
| ohmyclaudecode / awesome-claude-* lists | curation, not framework | Discovery layer | These are where harness-maker needs *to be listed*, not compete with |

**Unique positioning of harness-maker** (defensible claim — verify with at least one external user before relying on it as launch copy):

1. **Project-tailored** synthesis from a real profiler (12+ stack signals, dependency-parsed not keyword-guessed) + 10-dim interview that re-uses prior answers silently. No other harness combines `profile → interview → render`.
2. **Edit-preserving upgrades** via block-merge markers (`@hm:user:*`). SuperClaude/BMAD upgrades overwrite; user customisations rot.
3. **Anti-rot crawlers** across Anthropic blog + GH releases + arXiv + OSV CVEs with adaptive relevance filter. No competitor I found has this loop.
4. **Multi-IDE single source** — Claude Code + Cursor + Codex from one `harness.yaml`. Most competitors are Claude-Code-only.
5. **Grade-gated review with mechanical pre-checks** — ruff/mypy/pytest run *before* burning a single LLM token on review. Saves tokens + filters obvious noise. (BMAD's QA agent doesn't gate this way.)
6. **Reviewer/executor privilege separation** with strict allow/deny (CLAUDE.md §보안 lists pinpoint denials of `Bash(python:*)`, `Bash(sh:*)`, paired `Write`/`Edit` for system paths). Reviewers in BMAD/SuperClaude have full tool access — a differentiator that doubles as a SECURITY.md anchor story.

## 📚 Sources

- [Claude Code Marketplaces directory (1,181 plugins, 73 marketplaces)](https://claudemarketplaces.com/) — harness-maker not listed
- [awesome-claude-plugins by Chat2AnyLLM](https://github.com/Chat2AnyLLM/awesome-claude-plugins) — harness-maker not listed
- [awesome-claude-code-toolkit by rohitg00](https://github.com/rohitg00/awesome-claude-code-toolkit) — 176+ plugins indexed, harness-maker not listed; mobile-spine is the only listed interview-driven tool
- [awesome-claude-plugins by ComposioHQ](https://github.com/ComposioHQ/awesome-claude-plugins) — referenced category structure
- [SuperClaude_Framework](https://github.com/SuperClaude-Org/SuperClaude_Framework) — 20.4k★ benchmark
- [BMAD-METHOD by bmad-code-org](https://github.com/bmad-code-org/BMAD-METHOD) — V6, agile-role workflow
- [agent-os v3 launch discussion](https://github.com/buildermethods/agent-os/discussions/310) — competitor positioning
- [claude-flow / Ruflo by ruvnet](https://github.com/ruvnet/ruflo) — orchestration-platform positioning
- [GitHub community profile docs](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories)
- [GitHub Actions security checklist (Aikido)](https://www.aikido.dev/blog/checklist-github-actions)
- [LaunchTry open-source 2026 checklist](https://launchtry.com/resources/launch-checklist/open-source)
- [PyPI metadata for harness-maker](https://pypi.org/pypi/harness-maker/json)
- `gh api repos/Ecro/harness-maker` — current repo stats
- `git show 565d7ce` — proof of CI removal one day after repo went public

## 🔗 Related Internal Docs

- [[README.md#how-it-compares]] — current competitor table (needs tone review per Pitfall 4)
- [[README.md#roadmap]] — "Standing items" already lists marketplace listings, screencast, PyPI publish (PyPI done)
- [[docs/release-checklist.md]] — release runbook
- [[docs/CONTRIBUTING.md]] — exists; needs root mirror
- [[docs/ARCHITECTURE.md]] — telemetry posture documented but invisible from README
- [[CLAUDE.md#무언가를-고치거나-개선하기-전에--필수-체크리스트]] — the "8 checkpoints" list is a strong PR-template starting point
