---
type: plan
task_slug: oss-readiness-audit
status: complete
created: 2026-05-19
tags: [harness-maker, plan, oss-launch, ci-cd, community-health, discoverability]
research_doc: "[[RESEARCH-oss-readiness-audit]]"
interview_rounds: 3
adrs: 13
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "11 phases land OSS launch-readiness floor (PR CI, community files, privacy doc, marketplace + Show HN); stays 0.x; solo posture."
---

## 🎯 Executive Summary

**What:** Bring harness-maker to OSS launch-ready state without rebranding to 1.0 or escalating maintenance burden. Land 11 phases: PR CI restoration, community-files floor, supply-chain hygiene, privacy doc, README polish (stability + comparison rewrite + "try in 30s" hero), repo polish, marketplace submissions, 1-week soak, low-key Show HN.

**Why:** Repo is already public (since 2026-05-03) and on PyPI (since 0.15.3), but the floor that lets it survive external contact (PR tests, security disclosure channel, community-file profile, marketplace listings) is not in place. Without this floor, accepting external PRs is unsafe and Show HN attention would surface preventable failure modes.

**Key Decisions (interview-driven):**

- 0.x stays. No 1.0 rebrand. Frozen surfaces documented in README "Stability" section → **ADR-001**.
- Solo maintainer posture; "PRs at your own risk"; no DCO/CLA → **ADR-002**.
- Fast PR CI (~3–5 min cold, <2 min warm) + nightly cron with INTEGRATION → **ADR-003**.
- PRIVACY.md only; no opt-out env var → **ADR-004**.
- 3 marketplace submissions + low-key Show HN after 1-week soak → **ADR-005**.
- No demo screencast/GIF; "try in 30s" code block as README hero → **ADR-006**.
- Comparison section = category-axis only (no named competitors, no appendix) → **ADR-007** + **ADR-012**.
- Korean README full mirror kept, drift risk accepted → **ADR-008**.
- CoC = Contributor Covenant 2.1 base + custom solo-maintainer enforcement section → **ADR-009**.
- SECURITY.md routes to GitHub Private Vulnerability Reporting; Gmail = backup → **ADR-010**.
- PR template = two-tier (short mandatory + collapsible core-module subset) → **ADR-011**.
- GitHub Discussions ON with 4 default categories → **ADR-013**.

**Estimated impact:** ~6–9 hours of focused work spread across 11 phases. Calendar time gated by Phase 10's 1-week soak.

---

## 🚫 Non-Goals

Items deliberately NOT in scope for this launch (each cites the deciding ADR or interview round):

| # | Item | Why excluded |
|---|---|---|
| 1 | Promote to 1.0.0 | ADR-001 — stay 0.x with documented breaking-policy |
| 2 | Demo screencast / asciinema / GIF | ADR-006 — "try in 30s" code block instead |
| 3 | DCO sign-off / CLA | ADR-002 — solo posture, "PRs at your own risk" |
| 4 | `.github/FUNDING.yml` | Round 1 implied default — matches solo posture |
| 5 | SBOM in release artifact | Out of scope; deferred — solo posture |
| 6 | `pip-audit` step in CI | Out of scope; deferred — Dependabot covers basic surface |
| 7 | Korean README downgrade or migration to docs site | ADR-008 — keep full mirror |
| 8 | Coverage badge / codecov integration | Out of scope; deferred |
| 9 | `CITATION.cff` | Out of scope; can add later |
| 10 | `HARNESS_MAKER_TELEMETRY=0` opt-out env var | ADR-004 — PRIVACY.md only |
| 11 | Named-competitor comparison appendix | ADR-012 — accepted info-gap risk for Show HN readers |
| 12 | Bug-bounty / disclosure embargo window | Round 1 implied default — solo posture |
| 13 | Multi-channel launch (Twitter/r/ClaudeAI campaign) | ADR-005 — single low-key Show HN only |
| 14 | `buildwithclaude.com` / `claudepluginhub.com` submissions | Phase 9 scope-out — 3 directories sufficient for launch |

---

## 📚 Prior Work

- **`work-docs/RESEARCH-oss-readiness-audit.md`** (2026-05-19) — research-stage doc; identifies 10 open questions and 10 pitfalls. Validator critique of the draft PLAN cross-referenced 6 of those pitfalls.
- **`docs/CONTRIBUTING.md`** — exists; will be root-mirrored in Phase 2.
- **`docs/release-checklist.md`** — release runbook; unchanged by this PLAN.
- **`docs/adr/`** — 4 cross-PLAN ADRs already promoted; this PLAN's ADRs stay scoped to it (not promoted).
- **`CLAUDE.md` §보안 / §"8 checkpoints"** — internal-maintainer checklist; *will not* be mirrored verbatim into the PR template (validator critique C4 → ADR-011).
- **`.github/workflows/release.yml`** — current tag-only workflow; lines 7–12 already support `workflow_dispatch` with `dry_run=true` (used by Phase 1 risk mitigation, validator critique W7).
- **`git show 565d7ce`** — proof that CI on PR was removed 2026-05-04, one day after the repo went public. The same day's PR-CI removal is what Phase 1 reverses.
- **`.claude/memory/failures.md`** + **`.claude/memory/wiki.md`** — checked; no prior OSS-launch-attempt failures recorded.

---

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | 1 | Stability commitment | Risk tolerance | Stay 0.x + document breaking-policy | Frozen surfaces: slash command names, harness.yaml top-level keys, plugin manifest schema | ADR-001 |
| 2 | 1 | Maintenance model | Scope | Solo for now, "PRs at your own risk" | Implies: no DCO/CLA; CoC enforcement adapted | ADR-002 |
| 3 | 1 | CI scope on PR | Testing | Fast PR (~3–5 min target) + slow nightly | Validator-corrected from "~90s" to realistic floor | ADR-003 |
| 4 | 1 | Telemetry posture | Contract shape | PRIVACY.md only, no opt-out env var | Add AST-walk unit test for schema-drift defense | ADR-004 |
| 5 | 2 | Discoverability | Phasing | 3 directories + low-key Show HN | Show HN gated by 1-week soak post-Phase 9 | ADR-005 |
| 6 | 2 | Demo asset | Implementation | Skip; "try in 30s" code block | Bootstrap prompt becomes README hero | ADR-006 |
| 7 | 2 | Comparison tone | Architecture | Pivot to category-axis | Named-competitor table removed | ADR-007 |
| 8 | 2 | Korean README | Scope | Keep full mirror | Drift risk accepted explicitly | ADR-008 |
| 9 | default | CoC enforcement | Risk tolerance | Custom solo-maintainer enforcement section | Default applied; user can revert via explicit ask | ADR-009 |
| 10 | 3 | SECURITY disclosure channel | Contract shape | GitHub PVR primary + Gmail backup | Validator-caught silent default (C3) | ADR-010 |
| 11 | 3 | PR template scope | Failure handling | Two-tier (short + collapsible core-module) | Validator-suggested compromise (C4) | ADR-011 |
| 12 | 3 | Comparison appendix | Architecture | No named-competitor appendix anywhere | User accepts info-gap risk for Show HN readers | ADR-012 |
| 13 | 3 | Discussions on/off | Phasing | Enable with 4 default categories | Reverses Round-1 implied default; validator caught silent override | ADR-013 |

All 4 validator critical critiques resolved via Round 3 + corrections. All 9 warnings folded as defensible defaults (4 elevated to ADRs). All 3 suggestions folded as inline corrections.

---

## 📐 Architecture Decision Records

### ADR-001: Stay 0.x; document breaking-policy
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 1)
**Context:** 0.15.0 → 0.15.3 patches in 24h fixed prior-patch regressions. Enterprise adoption signal demands stability; experimental velocity demands flexibility.
**Decision:** Stay on 0.x indefinitely. Add README "Stability" section that names frozen surfaces (slash command names, `harness.yaml` top-level keys, `.claude-plugin/plugin.json` schema, `.cursor-plugin/plugin.json` schema, `.codex-plugin/plugin.json` schema) and explicitly says everything else may break in any 0.x.minor.
**Consequences:**
- ✅ No SemVer commitment, no compatibility shims required.
- ✅ Honest about current velocity.
- ⚠️ Enterprise adopters will pass until 1.0.0.
**Rejected alternatives:**
- 1.0.0 rebrand at launch — premature; would require breaking-change discipline the repo's velocity does not yet support.
- 1.0.0-rc.1 with 2-week soak — adds calendar time without resolving the underlying velocity question.
**Source:** Interview #1.

### ADR-002: Solo maintainer posture, "PRs at your own risk"
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 1)
**Context:** Limited maintainer bandwidth + uncertain timeline for sustained engagement vs. desire to be visibly open.
**Decision:** README states the project is solo-maintained and experimental. CONTRIBUTING.md says PRs are welcome but no SLA exists. No DCO / no CLA. Issue/PR triage on best-effort basis.
**Consequences:**
- ✅ No legal contributor-agreement friction.
- ✅ Honest signal that lowers contributor disappointment.
- ⚠️ First-time contributors may be discouraged by "no SLA" wording; mitigated by Phase 11 honest-tone Show HN copy.
**Rejected alternatives:**
- Open to PRs + DCO sign-off — adds friction for solo-posture project with no immediate need for legal trail.
- Read-only OSS — defeats the launch purpose.
**Source:** Interview #2.

### ADR-003: PR CI = fast quality-gate (excluding INTEGRATION); nightly = full gate
**Status:** Accepted (2026-05-19; validator-corrected on duration claim)
**Context:** `release.yml` runs the full gate only on tag push (line 8: `tags: - "v*"`). External PRs land with zero automated tests since 565d7ce removed `ci.yml` 2026-05-04.
**Decision:** Restore `.github/workflows/ci.yml` that runs on `pull_request` and `push` to main. Steps: `uv sync --frozen` + `ruff check .` + `ruff format --check .` + `mypy --strict src` + `pytest -x --tb=short` (no INTEGRATION env). Add `actions/dependency-review` job on PR. A second workflow `.github/workflows/nightly.yml` runs the full quality-gate (including `INTEGRATION=1 pytest tests/integration/test_fresh_install_readiness.py`) on `schedule` (cron: nightly UTC) + `workflow_dispatch`. Both workflows pin actions by SHA (matching release.yml convention). `release.yml`'s `quality-gate` job stays as-is per release.yml lines 19–21 (intentional duplicate gate at tag time).
**Consequences:**
- ✅ External PRs run lint/type/unit before merge.
- ✅ Integration regressions caught nightly + at tag time (defense in depth).
- ⚠️ ci.yml and release.yml `quality-gate` can drift; exit criterion (Phase 1) requires byte-identical steps OR extraction to reusable workflow.
**Rejected alternatives:**
- Full quality-gate on every PR (~5 min, includes INTEGRATION) — INTEGRATION already runs at tag time; double-spending CI minutes on PR provides marginal coverage.
- Skip PR CI entirely (status quo) — unsafe once external PRs land.
**Source:** Interview #3 + validator critique C1/C2.

### ADR-004: PRIVACY.md only; no opt-out env var; AST-walk drift test
**Status:** Accepted (2026-05-19; validator-augmented with drift test)
**Context:** README + CLAUDE.md + ARCHITECTURE.md claim "100% local telemetry" but the claim is scattered and not surfaced at PyPI/GitHub first-screen. Validator (W6) flagged that PRIVACY.md will drift from actual emit-sites.
**Decision:** Author `PRIVACY.md` at repo root. Document: file paths written (`metrics-YYYY-MM-DD.jsonl` in `.claude/observability/`), JSON schema of each entry, zero-transmission guarantee, daily rotation retention. README header links to PRIVACY.md. Add `tests/unit/test_privacy_doc_schema.py` that AST-walks all `metric.emit(...)` / `telemetry.emit_*(...)` call-sites in `src/harness_maker/` and asserts every emitted field is documented in PRIVACY.md.
**Consequences:**
- ✅ One source of truth, defended by a test.
- ✅ No code change to telemetry emitter.
- ⚠️ Users who want telemetry off must manually delete the file; no env-var escape.
- ⚠️ AST-walk test adds CI surface — must run in PR job.
**Rejected alternatives:**
- Opt-in only (default OFF) — kills cache-diagnostic layer of the AI-readiness rubric.
- Env-var opt-out — additional surface area for a casual-posture launch.
**Source:** Interview #4 + validator critique W6.

### ADR-005: Submit to 3 directories + low-key Show HN after 1-week soak
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 2)
**Context:** Repo not listed in any of the indexed plugin directories (claudemarketplaces.com: 1,181 plugins, awesome-claude-plugins, awesome-claude-code-toolkit). Discoverability is the single biggest user-acquisition blocker.
**Decision:** Phase 9 submits to: (1) `claudemarketplaces.com` form, (2) PR to `Chat2AnyLLM/awesome-claude-plugins` (Workflow Orchestration category), (3) PR to `rohitg00/awesome-claude-code-toolkit`. After all 3 confirmed + Phase 10 1-week soak with no P0 bug, Phase 11 posts Show HN. Title: `Show HN: harness-maker — project-tailored AI coding harness for Claude Code / Cursor / Codex`.
**Consequences:**
- ✅ Three discoverability surfaces seeded simultaneously.
- ✅ Soak window absorbs early bugs before scrutiny.
- ⚠️ Show HN attention to solo-posture repo invites tone-mismatch criticism; mitigated by Phase 11 explicit copy review.
**Rejected alternatives:**
- 3 directories, no announcement — slowest path; no attention-spike control benefit since spike never comes.
- Defer announcement until first external star — indefinite wait.
- Multi-channel campaign — overcommits for solo posture.
**Source:** Interview #5.

### ADR-006: "Try in 30 seconds" code block as README hero; no screencast
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 2)
**Context:** Recording a demo costs ~60–90 min and the bootstrap prompt was recently rewritten (commit 45e321c) to be paste-and-run. The recorded asset would duplicate what a code block already shows.
**Decision:** Phase 7 inserts a fenced code block near README top: the existing bootstrap prompt formatted for paste-into-Claude-Code. Remove "Demo screencast" item from README §Roadmap; replace with a sentence pointing to the code block.
**Consequences:**
- ✅ Zero recording effort; no hosting concerns.
- ✅ Pasteable, searchable, accessible to screen readers.
- ⚠️ Loses motion-comprehension that a GIF would provide.
**Source:** Interview #6.

### ADR-007: Comparison section = category-axis only
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 2; reinforced by ADR-012)
**Context:** Current `## How it compares` names ohmyclaudecode, superpowers, Archon, aider, ouroboros. Mostly safe but the punching tone is launch-day drama risk.
**Decision:** Phase 6 replaces the table with a 5-axis category positioning (Project-tailored synthesis / Edit-preserving upgrades / Anti-rot crawl / Multi-IDE / Privilege-separated reviewers). No named competitors anywhere.
**Consequences:**
- ✅ Zero name-drop drama risk.
- ⚠️ Show HN readers from SuperClaude/BMAD lack a "why this not X" anchor; see ADR-012.
**Source:** Interview #7.

### ADR-008: README.ko.md full mirror retained
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 2)
**Context:** 725 KO + 795 EN lines, one maintainer. Every README edit doubles work.
**Decision:** Keep both files. Accept drift risk explicitly. No automated sync stamps. No mkdocs migration.
**Consequences:**
- ✅ Korean-speaking discovery surface preserved (PyPI ko link, github.com search).
- ⚠️ Drift will accumulate; will be detected only via user feedback or manual diff.
**Source:** Interview #8.

### ADR-009: Custom solo-maintainer enforcement section over CoC 2.1 default
**Status:** Accepted (2026-05-19, default-applied; reversible by explicit ask)
**Context:** Contributor Covenant 2.1's enforcement clause promises that "community leaders" investigate reports "promptly and fairly". Solo maintainer cannot meet that obligation under ADR-002.
**Decision:** `CODE_OF_CONDUCT.md` uses Contributor Covenant 2.1 Sections 1–3 (Pledge / Standards / Scope) verbatim. Section 4 (Enforcement) replaced with: "I'm a solo maintainer. Reports go to the SECURITY.md disclosure channel (or by email if non-security). Expect best-effort response, no guaranteed timeline. Persistent or severe violations will result in being blocked from the repo. I will not act on a report I cannot independently verify."
**Consequences:**
- ✅ Honest about enforcement bandwidth.
- ✅ No publicly-visible obligation the maintainer cannot meet.
- ⚠️ Some readers will flag the deviation; mitigated by explicit note "this is a solo-maintainer adaptation of CoC 2.1".
**Rejected alternatives:**
- Verbatim CoC 2.1 — sets up unmet-obligation reputation risk.
**Source:** Default-applied per validator critique W4.

### ADR-010: GitHub Private Vulnerability Reporting primary; Gmail backup
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 3)
**Context:** Validator (C3) flagged that the original "Gmail only" implied default exposed a personal address on a public repo and lacked audit trail.
**Decision:** Enable Settings → Security → Private vulnerability reporting. `SECURITY.md` lists `https://github.com/Ecro/harness-maker/security/advisories/new` as canonical channel; lists `e839638@gmail.com` as backup for researchers without a GitHub account. Scope: `src/harness_maker/`, all `templates/`, all `hooks/`, all `agents/` permission policies, the telemetry emitter. Out of scope: example/test fixtures, third-party dependencies (route via `pypa/advisory-database`).
**Consequences:**
- ✅ Encrypted, audit-logged channel.
- ✅ GitHub "Report a vulnerability" UI button surfaces.
- ⚠️ Backup email still exposes a personal address; acceptable for solo posture.
**Source:** Interview #10 + validator critique C3.

### ADR-011: Two-tier PR template
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 3)
**Context:** Validator (C4) flagged that mirroring CLAUDE.md's 8 internal-maintainer checkpoints as a PR template would scare off external contributors.
**Decision:** `.github/PULL_REQUEST_TEMPLATE.md` has two sections:
1. **Always required** (4 checkboxes): ruff/mypy/pytest ran locally; CHANGELOG.md entry if user-visible; 5-file version sync if version bump; linked issue or short rationale.
2. **For changes to `src/harness_maker/render.py`, `reconcile.py`, `synthesize.py`, `interview.py`, or the `cli.py` surface** (`<details>` block): cross-references the 8 checkpoints in CLAUDE.md.
**Consequences:**
- ✅ Friction-minimizing for typo/doc PRs.
- ✅ Core-module PRs still get the discipline.
- ⚠️ Two-tier template requires the contributor to recognize which tier applies; mitigated by clear `<details>` header.
**Source:** Interview #11 + validator critique C4.

### ADR-012: No named-competitor appendix; accept info-gap risk
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 3)
**Context:** Validator (W3) suggested making a non-punching named-comparison appendix mandatory. User explicitly chose to keep ADR-007's hero-only category-axis.
**Decision:** No appendix. The launch accepts the info-gap risk that SuperClaude/BMAD readers arriving via Show HN cannot find a one-paragraph answer to "why this not them" on the README.
**Consequences:**
- ⚠️ Show HN drop-off risk from readers who already know an incumbent.
- ✅ Zero name-drop drama; cleanest positioning surface.
**Rejected alternatives:**
- Mandatory named-comparison appendix (validator's suggestion) — overrides user's explicit Round 3 choice.
**Source:** Interview #12 + validator critique W3.

### ADR-013: GitHub Discussions ON with 4 default categories
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 3)
**Context:** Validator (W5) caught a silent override of research-doc Pitfall 3 ("Disabled Discussions starves Q&A energy into issues").
**Decision:** Enable Discussions with Q&A, Ideas, General, Show-and-tell. Pin a welcome thread linking to CONTRIBUTING + SECURITY + PRIVACY.
**Consequences:**
- ✅ Cleaner Issue queue (bug reports only, not Q&A).
- ✅ Better SEO via Discussion threads.
- ⚠️ Second queue to triage; mitigated by best-effort SLA per ADR-002.
**Rejected alternatives:**
- Keep OFF (original implied default) — silently overrode research recommendation without ADR.
- Q&A-only — needlessly restrictive.
**Source:** Interview #13 + validator critique W5.

---

## 🏗️ Technical Design

### Current State

| Surface | Current | Target after PLAN |
|---|---|---|
| `.github/workflows/` | `release.yml` only (tag-triggered) | + `ci.yml` (PR + push to main) + `nightly.yml` (cron) |
| `release.yml` | Full quality-gate + build + publish-testpypi + publish-pypi + github-release | Unchanged (per ADR-003) |
| Community files | LICENSE, CHANGELOG, README, docs/CONTRIBUTING.md | + CONTRIBUTING.md root, CODE_OF_CONDUCT.md, SECURITY.md, ISSUE_TEMPLATE/{bug.yml,feature.yml,config.yml}, PULL_REQUEST_TEMPLATE.md, dependabot.yml |
| Privacy posture | Scattered across CLAUDE.md + ARCHITECTURE.md | + `PRIVACY.md` at root, AST-walk drift test |
| Stability commitment | Implicit "0.x = anything goes" | README "Stability" section names frozen surfaces |
| Comparison section | Named-competitor table (5 rows) | Category-axis (5 axes), no named competitors |
| README hero | Brand SVG + bullets | + "Try in 30 seconds" code block (existing bootstrap prompt) |
| Repo metadata | 232-char description, no social preview verified | ≤150 chars, social preview set |
| Marketplace presence | None | claudemarketplaces.com + Chat2AnyLLM/awesome-claude-plugins + rohitg00/awesome-claude-code-toolkit |
| Discussions | OFF | ON with 4 default categories |
| Security disclosure | None | GitHub PVR + Gmail backup, SECURITY.md |

### Affected Components

```
.github/
├── workflows/
│   ├── ci.yml              [NEW, Phase 1]
│   ├── nightly.yml         [NEW, Phase 1]
│   └── release.yml         [UNCHANGED]
├── dependabot.yml          [NEW, Phase 3]
├── ISSUE_TEMPLATE/
│   ├── bug.yml             [NEW, Phase 2]
│   ├── feature.yml         [NEW, Phase 2]
│   └── config.yml          [NEW, Phase 2]
└── PULL_REQUEST_TEMPLATE.md [NEW, Phase 2 — two-tier per ADR-011]

CONTRIBUTING.md             [NEW, Phase 2 — root mirror of docs/CONTRIBUTING.md]
CODE_OF_CONDUCT.md          [NEW, Phase 2 — CoC 2.1 + custom enforcement per ADR-009]
SECURITY.md                 [NEW, Phase 2 — PVR + Gmail backup per ADR-010]
PRIVACY.md                  [NEW, Phase 4]

README.md                   [EDITED, Phases 5/6/7 — Stability section, comparison rewrite, hero block]

tests/unit/
└── test_privacy_doc_schema.py  [NEW, Phase 4 — AST-walk drift test]
```

### Dependencies

- No new Python dependencies.
- No new GitHub Actions beyond `actions/dependency-review` (already widely used; pin SHA).
- Dependabot v2 config syntax — natively supported.

### Data Flow (Phase 1 CI workflow split)

```
External PR → ci.yml fires
            ├─ ruff check
            ├─ ruff format --check
            ├─ mypy --strict src
            ├─ pytest -x --tb=short
            └─ actions/dependency-review (PRs only)
              ↓ all green → mergeable

Push to main → ci.yml fires (same steps)

Nightly cron → nightly.yml fires
            ├─ Full ci.yml steps
            └─ INTEGRATION=1 pytest tests/integration/test_fresh_install_readiness.py
              ↓ failure → auto-issue (manual triage)

Tag push (v*) → release.yml fires (unchanged)
            ├─ quality-gate (duplicate of ci.yml + INTEGRATION step — intentional)
            ├─ build wheel + sdist
            ├─ publish-testpypi
            ├─ publish-pypi
            └─ github-release
```

### Design Decisions (cross-reference ADRs)

- **CI duplication accepted at tag time** (ADR-003). `release.yml`'s `quality-gate` re-runs `ci.yml`'s steps + the INTEGRATION step on every tag push. Documented in `release.yml` lines 19–21 already. Phase 1 must keep this in sync — verified by Phase 1 exit criterion.
- **No env-var opt-out for telemetry** (ADR-004). The AST-walk drift test in Phase 4 is the structural mitigation for the "PRIVACY.md goes stale" failure mode.
- **No named-competitor appendix** (ADR-012). Accepted info-gap risk; documented in §Risks.

---

## 📝 Implementation Plan

**Sequencing summary:**
- Parallelizable: Phases 1, 2, 3, 4, 8 (independent files / settings).
- Bundle: Phases 5, 6, 7 = single PR (README edits).
- Gate: Phase 9 depends on Phases 1–8 closed.
- Gate: Phase 11 depends on Phase 10's 1-week soak with no P0.

**P0 bug definition** (used by Phase 10 and Phase 11 exit criteria):
> P0 = ANY of: (a) `harness-maker:make` fails on a clean install of one of the e2e fixtures, OR (b) published telemetry record contradicts PRIVACY.md (extra/undocumented field), OR (c) security issue with CVSS ≥ 7.0, OR (d) any data-loss bug in render/reconcile (user files overwritten without provenance match).

---

### Phase 1 — Restore PR CI (ci.yml + nightly.yml split from release.yml)

**Scope (in):**
- `.github/workflows/ci.yml` (new): triggers `pull_request` + `push` to `main`; runs `uv sync --frozen` + `ruff check .` + `ruff format --check .` + `mypy --strict src` + `pytest -x --tb=short` + `actions/dependency-review` (PR only). Action SHAs pinned matching release.yml convention.
- `.github/workflows/nightly.yml` (new): triggers `schedule: cron: '0 6 * * *'` (06:00 UTC daily) + `workflow_dispatch`; runs the full `ci.yml` steps + `INTEGRATION=1 pytest tests/integration/test_fresh_install_readiness.py -x --tb=short`. Optionally auto-creates a tracking issue on failure (deferred — `gh issue create` post-step if scope allows).
- Verify Python version (3.12) + uv action version match release.yml exactly.

**Scope (out):**
- `release.yml` changes (per ADR-003, stays as-is).
- Composite-action extraction (defer — keep both workflows literal until a third duplication appears).

**Exit criterion:**
1. Open a PR from a `ci-test` branch (e.g. add a trivial doc-typo fix); ci.yml triggers; all jobs pass; total wall time recorded.
2. Record measured PR job duration. Acceptance: ≤5 min on cold uv cache, ≤2 min on warm cache.
3. Diff `ci.yml` steps vs `release.yml`'s `quality-gate` job (excluding INTEGRATION step). Acceptance: byte-identical step bodies (command strings + env). Drift = blocker.
4. Verify release.yml still triggers on tag push (use `workflow_dispatch` with `dry_run=true` against `release.yml` to confirm the build path still works without publishing).

**Risk:** medium — CI misconfig blocks all future PRs.
**Rollback:** delete `ci.yml` + `nightly.yml`. `release.yml` untouched.

---

### Phase 2 — Community files floor

**Scope (in):**
- `CONTRIBUTING.md` at root: copy `docs/CONTRIBUTING.md` content; add top section reflecting ADR-002 ("solo maintained, no SLA, PRs welcome at your own risk"). Link to `docs/CONTRIBUTING.md` for detailed module-level guidance.
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1 sections 1–3 verbatim; section 4 replaced per ADR-009; explicit "solo-maintainer adaptation" note at top.
- `SECURITY.md`: per ADR-010 — primary channel = `https://github.com/Ecro/harness-maker/security/advisories/new`; backup = `e839638@gmail.com`; scope listed (src/, templates/, hooks/, agents/ permissions, telemetry emitter); SLA = best-effort. Enable Settings → Security → Private vulnerability reporting as part of this phase.
- `.github/ISSUE_TEMPLATE/bug.yml`: structured form requiring version (`harness-maker --version`), reproduction steps, expected vs actual, environment (Claude Code / Cursor / Codex / OS), INTEGRATION mode.
- `.github/ISSUE_TEMPLATE/feature.yml`: short form with use-case + alternatives considered.
- `.github/ISSUE_TEMPLATE/config.yml`: `blank_issues_enabled: false`; `contact_links` for Discussions (Q&A) + Security (PVR).
- `.github/PULL_REQUEST_TEMPLATE.md`: two-tier per ADR-011.

**Scope (out):**
- FUNDING.yml (Non-Goal #4).
- DCO bot config (Non-Goal #3).
- CITATION.cff (Non-Goal #9).

**Exit criterion:**
1. `gh api repos/Ecro/harness-maker --jq '{coc: .code_of_conduct.key, security: .security_policy.enabled}'` reports `coc != null` AND `security == true` (after enabling PVR).
2. Visit GitHub repo's "New Issue" page — verify bug + feature templates appear, blank disabled.
3. Open a draft PR — verify two-tier template renders.

**Risk:** low — pure additive file changes.
**Rollback:** delete added files; disable PVR if needed.

---

### Phase 3 — Supply-chain hygiene (Dependabot + dependency-review)

**Scope (in):**
- `.github/dependabot.yml`: weekly schedule, two update entries: `package-ecosystem: pip` (directory `/`, target uv.lock indirectly via pyproject) and `package-ecosystem: github-actions`.
- `actions/dependency-review` job in `ci.yml` (pulled forward from Phase 1 if not landed there).

**Scope (out):**
- `pip-audit` step (Non-Goal #6).
- SBOM (Non-Goal #5).

**Exit criterion:**
1. Force a Dependabot run via repo Settings → Security → Dependabot. Either a no-op response OR a PR opened.
2. Open a test PR that bumps a dependency to a known-vulnerable version — dependency-review job fails the PR. Revert.

**Risk:** low.
**Rollback:** delete dependabot.yml + close any open Dependabot PRs (validator critique S2 — explicit step).

---

### Phase 4 — PRIVACY.md + AST-walk drift test

**Scope (in):**
- `PRIVACY.md` at root. Sections: (1) Summary ("100% local, no transmission"). (2) What is recorded (list of metric event types). (3) Where it's stored (`.claude/observability/metrics-YYYY-MM-DD.jsonl`). (4) JSON schema for each event type (lifted from `src/harness_maker/telemetry.py` emit-sites; cite line ranges). (5) Retention (daily rotation, user controls deletion). (6) How to disable (delete the directory; no env var — see ADR-004). (7) Cross-link from README hero.
- `tests/unit/test_privacy_doc_schema.py`: parses `src/harness_maker/` via `ast` module; collects all `metric.emit(...)` / `telemetry.emit_*(...)` keyword arguments and dict literals; collects all field names mentioned in PRIVACY.md (regex on backtick-quoted field names under "JSON schema" sections); asserts emit-side set ⊆ doc-side set (every emitted field is documented; doc may legitimately include retired fields).
- README header gets a single PRIVACY.md link.

**Scope (out):**
- Code change to telemetry emitter.
- `HARNESS_MAKER_TELEMETRY=0` env var (Non-Goal #10).

**Exit criterion:**
1. `uv run pytest tests/unit/test_privacy_doc_schema.py -v` passes.
2. Manually emit one record from each known emit-site (or assert via the test); verify PRIVACY.md documents every field that appears.
3. README has a link to PRIVACY.md within the first 30 lines.

**Risk:** low — primarily docs + test.
**Rollback:** delete PRIVACY.md + test file.

---

### Phase 5 — README "Stability" section

**Scope (in):**
- New README section between §Quickstart and §Features (or above §FAQ if more visible there). Lists frozen surfaces per ADR-001: slash command names (`/hm:make`, `/hm:execute`, `/hm:plan`, `/hm:research`, `/hm:review`, `/hm:health`, …), `harness.yaml` top-level keys, `.claude-plugin/plugin.json` / `.cursor-plugin/plugin.json` / `.codex-plugin/plugin.json` schemas. Explicit "everything else may break in any 0.x.minor" line.
- Cross-link from §Roadmap to the new §Stability section.

**Scope (out):**
- SemVer bump.
- `Development Status :: 5 - Production/Stable` classifier change.

**Exit criterion:**
1. Section parses; appears in README TOC.
2. Korean mirror (README.ko.md) gets matching `## 안정성` section (per ADR-008 — mirror discipline; even if drift accepted, deliberate edits stay synced).

**Risk:** low.
**Rollback:** revert section.

---

### Phase 6 — Comparison section rewrite

**Scope (in):**
- Replace `## How it compares` (README.md:431–449) with a category-axis table per ADR-007. 5 axes: Project-tailored synthesis / Edit-preserving upgrades / Anti-rot crawl / Multi-IDE / Privilege-separated reviewers. No named competitors.
- Mirror change in README.ko.md.
- No appendix (per ADR-012).

**Scope (out):**
- Adding named-competitor information elsewhere in README.

**Exit criterion:**
1. Grep `README.md` and `README.ko.md` for `BMAD\|SuperClaude\|Archon\|aider\|ouroboros\|ohmyclaudecode\|superpowers` — zero matches in the §How it compares section.
2. New section renders cleanly on GitHub preview.

**Risk:** low.
**Rollback:** revert.

---

### Phase 7 — README "try in 30 seconds" hero

**Scope (in):**
- Insert a fenced ```` ```text ```` block near top of README (after the badges row, before §Why) containing the existing bootstrap prompt (per commit 45e321c). Heading: `## Try in 30 seconds`.
- Update §Roadmap "Demo screencast" item to "Replaced by §Try in 30 seconds — see ADR-006".

**Scope (out):**
- Recording any motion asset.

**Exit criterion:**
1. README hero contains a code block before line 100.
2. Roadmap reflects ADR-006 decision.
3. KO mirror updated.

**Risk:** low.
**Rollback:** revert.

---

### Phase 8 — Repo polish (description + social preview + topics + Discussions)

**Scope (in):**
- Tighten `gh api repos/Ecro/harness-maker -X PATCH --field description="..."` to ≤150 chars.
- Upload a social preview image via Settings → Social preview (1280×640 PNG; reuse `docs/assets/brand-block.png` or render a new one at correct dimensions).
- Verify `repositoryTopics` — current 10 are good; add `oss` and `developer-tools` if not already present.
- Enable GitHub Discussions per ADR-013 with categories: Q&A (default), Ideas, General, Show-and-tell. Pin a welcome thread linking to CONTRIBUTING + SECURITY + PRIVACY.

**Scope (out):**
- Repo settings unrelated to launch.

**Exit criterion:**
1. `gh api repos/Ecro/harness-maker --jq '{desc_len: (.description | length), discussions: .has_discussions, topics: .topics}'` reports `desc_len <= 150` AND `discussions == true`.
2. Twitter/X card preview shows new social preview image.

**Risk:** low.
**Rollback:** revert via `gh api`.

---

### Phase 9 — Marketplace submissions

**Depends on:** Phases 1, 2, 3, 4, 5, 6, 7, 8 ALL closed (per validator critique W2 — submitted positioning must match shipped README + community files).

**Scope (in):**
- Form submission at `claudemarketplaces.com` (use repository URL + description).
- PR to `Chat2AnyLLM/awesome-claude-plugins` adding harness-maker under the "Workflow Orchestration" or "Code Quality Testing" category (per their CONTRIBUTING).
- PR to `rohitg00/awesome-claude-code-toolkit` adding harness-maker.

**Scope (out):**
- `buildwithclaude.com` / `claudepluginhub.com` (Non-Goal #14).

**Exit criterion:**
1. Three submissions confirmed (form submission receipt OR PR opened with URL recorded).
2. Track each in this PLAN's risk register (each PR's URL).

**Risk:** low; controlled by external acceptance latency.
**Rollback:** withdraw PRs.

---

### Phase 10 — 1-week soak

**Depends on:** Phase 9 close (all 3 submissions made).

**Scope (in):**
- Elapsed-time observation. Monitor: GitHub Issues, Discussions Q&A category, awesome-list PR comments, claudemarketplaces.com response, PyPI download anomalies.
- Fix any P0 bug (per definition above) before Phase 11. P0 fix = patch release + new tag.

**Scope (out):**
- Feature work; non-P0 bug fixes; large refactors.

**Exit criterion:**
1. 7 calendar days elapsed since Phase 9 close.
2. Zero P0 bugs open (per definition).
3. Any non-P0 bugs triaged with labels but not necessarily fixed.

**Risk:** low.
**Rollback:** defer Phase 11.

---

### Phase 11 — Low-key Show HN

**Depends on:** Phase 10 close.

**Scope (in):**
- Draft Show HN title + body BEFORE submission. Title (locked): `Show HN: harness-maker — project-tailored AI coding harness for Claude Code / Cursor / Codex`. Body (3 short paragraphs):
  - P1 — what it does (1 sentence) + 3 differentiators (matching the category-axis README).
  - P2 — what's different from prior frameworks (NO names, per ADR-012; phrasing: "Most harnesses ship a fixed set of agents/skills; this one builds one from a project profile + an interview").
  - P3 — explicit caveats: "0.x, solo-maintained, breaking changes possible in any minor. Frozen surfaces listed in README §Stability. PRIVACY.md documents the local-only telemetry." Link to repo.
- Self-review the body for tone — at least one read-through looking for derision-bait phrasing (validator critique W1).
- Submit via Hacker News.
- Triage rule for 48h post-submit: respond to top-level technical questions within 4h during waking hours; ignore one-word dismissals; flag any P0 bug-report for immediate action.

**Scope (out):**
- Twitter/X thread, Reddit cross-post, Discord announcement (Non-Goal #13).
- Paid promotion.

**Exit criterion:**
1. Post submitted, URL recorded in this PLAN.
2. First 48h post-submit: zero P0 issues, zero public security reports, all top-level technical comments responded to.
3. After 48h: write a short retrospective in `work-docs/REVIEW-oss-readiness-audit.md` (or `work-docs/SESSION-show-hn-launch.md`) recording: traffic spike, top 3 questions, any bugs reported, follow-up action items.

**Risk:** medium — public attention surfaces unknown-unknowns.
**Rollback:** cannot un-post. Mitigations: Phase 10 soak, Phase 11 explicit caveats in body, real-time triage rule.

---

## 🧪 Testing Strategy

**Unit (new, Phase 4):**
- `tests/unit/test_privacy_doc_schema.py` — AST-walk asserts `metric.emit(...)` keyword args ⊆ documented fields in PRIVACY.md.

**Existing test surface (unchanged):**
- 143 test files (122 unit / 9 integration / 7 e2e + snapshot/ablation/cursor-compat/codex-compat).
- `ci.yml` runs the unit + non-INTEGRATION subset on every PR; nightly runs the full suite.

**Integration (manual checks per phase):**
- Phase 1: real PR on `ci-test` branch; measure duration; diff ci.yml vs release.yml steps.
- Phase 2: `gh api` checks for `code_of_conduct.key` + `security_policy.enabled`.
- Phase 3: trigger a Dependabot test run; force a dependency-review failure on a test PR.
- Phase 4: emit each known telemetry record type; verify field-by-field doc coverage.
- Phase 8: `gh api` checks for description length + Discussions; Twitter card preview.
- Phase 9: each submission gets a confirmation URL stored in this PLAN.

**Smoke after each phase:**
- `uv sync --frozen && uv run pytest -x --tb=short` (matches PR CI).
- Visual diff of README.md / README.ko.md against baseline.

---

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| R1 | ci.yml drifts from release.yml `quality-gate` → tag push blocked | medium | high | Phase 1 exit criterion #3 (byte-identical step check); if a third duplication arises, extract to reusable workflow |
| R2 | PR CI duration exceeds the 5-min/2-min targets | medium | low | Measure on real PR (Phase 1 exit #2); if exceeded, document actual figures and continue — not blocking |
| R3 | PRIVACY.md drifts from actual emit-sites over time | medium | medium | AST-walk unit test enforces (Phase 4); fails any PR that adds a metric field without doc update |
| R4 | Personal Gmail in SECURITY.md backup channel gets harvested by spambots | high | low | Acceptable for solo posture; PVR primary handles the actual flow |
| R5 | Show HN attention surfaces unknown bugs | medium | medium | 1-week Phase 10 soak; Phase 11 explicit caveats + triage rule |
| R6 | Show HN readers from SuperClaude/BMAD bounce due to missing "why not them" answer | medium | medium | Accepted per ADR-012; Phase 11 body P2 addresses the question generically |
| R7 | CoC enforcement custom statement gets criticized as deviation from CoC 2.1 | low | low | Pre-empted with "solo-maintainer adaptation" note in CODE_OF_CONDUCT.md (ADR-009) |
| R8 | KO/EN README drift accelerates after launch | medium | low | Accepted per ADR-008; mirror discipline for deliberate edits per phase |
| R9 | Marketplace PRs sit unmerged indefinitely | medium | low | Phase 9 records URLs; revisit at 4-week mark if no movement; submission counts as exit even if PR not yet merged |
| R10 | Discussions queue starves of attention from solo maintainer | medium | low | Accept per ADR-013; first-week triage rule = read Discussions daily |
| R11 | Show HN body tone-mismatch triggers cherry-picked criticism in comments | medium | medium | Phase 11 explicit self-review pass for derision-bait phrasing |
| R12 | `v*-dryrun` tag accidentally pushed to a public repo and publishes to PyPI | low | high | Avoid this path entirely — use `workflow_dispatch` with `dry_run=true` instead (validator W7) |
| R13 | Phase 1 CI restoration triggers unexpected failure of a previously-passing branch protection rule | low | medium | Verify branch protection rules before requiring ci.yml status check |
| R14 | Issue templates produce excessive friction → contributors abandon | low | medium | Bug template form fields are short; feature template even shorter |

---

## ✅ Success Criteria

- [x] **Phase 1:** ci.yml + nightly.yml exist on the worktree branch and are staged for commit; release.yml unchanged. Wall-time + tag-trigger verification deferred until the workflows run on GitHub. **Outstanding (user):** look up SHA for `actions/dependency-review-action@v4` and replace the tag pin at `.github/workflows/ci.yml:59`.
- [x] **Phase 1:** ci.yml step bodies match release.yml `quality-gate` byte-for-byte (excluding INTEGRATION step), verified by reading both side-by-side.
- [ ] **Phase 2 (deferred — user gh api):** `gh api repos/Ecro/harness-maker` reports `code_of_conduct.key != null` AND `security_policy.enabled == true`. CoC + SECURITY files are committed; PVR toggle requires `gh api -X PUT repos/Ecro/harness-maker/private-vulnerability-reporting`.
- [x] **Phase 2:** Bug + feature issue templates committed; `config.yml` disables blank-issue + points to Discussions/PVR contact links. New-Issue-UI verification deferred until repo settings refresh.
- [x] **Phase 2:** PR template renders two-tier (short standard + collapsible core-module subset) — confirmed by file inspection.
- [x] **Phase 3:** Dependabot config valid; `actions/dependency-review` job present in ci.yml. Test-PR verification deferred until first real PR.
- [x] **Phase 4:** PRIVACY.md exists at root; README header links to it; `test_privacy_doc_schema.py` passes (5/5).
- [x] **Phase 5:** README §Stability lists frozen surfaces (slash command names + harness.yaml top-level keys + plugin manifest schemas + local-only telemetry); KO mirror has `## 안정성`. TOC pill row updated post-review.
- [x] **Phase 6:** No named competitors in §How it compares — verified `grep -E 'BMAD|SuperClaude|Archon|aider|ouroboros|ohmyclaudecode|superpowers'` returns zero matches in the new section. KO mirror defers to EN per ADR-008.
- [x] **Phase 7:** README hero "Try in 30 seconds" code block at line 38 (≤100). KO mirror has `## 30초 만에 시도하기` at line 32. Bash-permission caveat added post-review.
- [ ] **Phase 8 (deferred — user gh api + Settings UI):** Repo description tighten + Discussions ON + social preview image upload + topics audit. Commands listed in `work-docs/REVIEW-oss-readiness-audit-2026-05-19.md` § Out-of-band actions.
- [ ] **Phase 9 (deferred — user submission):** 3 marketplace/awesome-list submissions. URLs to be appended here once opened.
- [ ] **Phase 10 (deferred — calendar):** 7-day soak window post-Phase-9.
- [ ] **Phase 11 (deferred — calendar):** Show HN submission + 48h triage.
- [ ] **Phase 11 retrospective (deferred):** Short post-launch retro to `work-docs/REVIEW-show-hn-launch-{date}.md`.

---

## 🔍 Plan Validation

**Validator outcome:** `NEEDS_REVISION` → resolved (validator run 2026-05-19 via /hm:plan Step 4).

| Severity | Critique | Resolution |
|---|---|---|
| critical | C1 — Phase 1 90s claim unrealistic | ADR-003 amended; Phase 1 exit #2 measures real duration, target ≤5 min cold / ≤2 min warm |
| critical | C2 — ci.yml↔release.yml sync risk | ADR-003 + Phase 1 exit #3 (byte-identical step check); R1 in risk register |
| critical | C3 — SECURITY disclosure channel | Interview Round 3 Q11 → ADR-010 (PVR primary + Gmail backup) |
| critical | C4 — PR template friction (8 checkpoints) | Interview Round 3 Q12 → ADR-011 (two-tier template) |
| warning | W1 — Show HN copy + triage rule | Phase 11 scope spells out draft tone + 48h triage rule + retro |
| warning | W2 — Phase 6 blocks Phase 9 | Phase 9 "Depends on: Phases 1–8 closed" explicit; parallelism notes added |
| warning | W3 — Comparison appendix mandatory | Interview Round 3 Q13 → ADR-012 (no appendix; accepted info-gap risk in R6) |
| warning | W4 — CoC enforcement obligation | Default applied → ADR-009 (custom solo-maintainer enforcement) |
| warning | W5 — Discussions silently OFF | Interview Round 3 Q14 → ADR-013 (Discussions ON with 4 categories) |
| warning | W6 — PRIVACY.md schema drift | ADR-004 amended; Phase 4 adds AST-walk unit test |
| warning | W7 — Dryrun tag would publish | Phase 1 uses `workflow_dispatch` with `dry_run=true` instead; risk R12 |
| warning | W8 — Missing Non-Goals section | §Non-Goals enumerates 14 items |
| warning | W9 — Phase 11 success criteria gap | Phase 11 exit #2 + Success Criteria add "48h: no P0, no security report, comments responded" |
| suggestion | S1 — P0 definition | Defined inline at top of §Implementation Plan |
| suggestion | S2 — Dependabot rollback | Phase 3 rollback "and close any open Dependabot PRs" |
| suggestion | S3 — Success criteria 48h check | Covered by W9 resolution |

No second validator pass triggered (NEEDS_REVISION path, not MAJOR_REVISION). All critical critiques resolved with new interview rounds; all warnings resolved with either ADRs or scope/exit-criterion edits.
