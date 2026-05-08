---
type: plan
task_slug: docs-refresh-readme-revamp
created: 2026-05-07
tags: [docs, readme, drift, marketing]
spec: null  # research/spec skipped — direct doc-update plan
---

# PLAN: Docs refresh + README full-restructure (Astral/uv-style)

> **One-line goal**: Eliminate doc/code drift across `README.md`, `docs/`, `TECH_SPEC.md`, `CLAUDE.md` (cross-refs), and rebuild `README.md` to match well-known OSS conventions (badges + ToC + hero + features grid + comparison + FAQ + roadmap) so the repo reads as a polished public plugin rather than an internal scratchpad.

## 0. Background

`harness-maker` has shipped 0.4.x → 0.5.x with major surface-area additions (Cursor target, dual plugin manifest, refdocs-search skill, per-loop worktree, SessionStart drift hook, English default locale, hybrid Cursor/Claude Code telemetry). Docs lag behind in concrete, verifiable ways (skill count off-by-one, M4 anti-rot source list incorrect, worktree path drift, no Cursor sections in TECH_SPEC, README missing ToC/badges/FAQ/roadmap). User asked: update all docs to current code, and revamp README using famous OSS as reference.

Decisions locked-in via `AskUserQuestion` 2026-05-07:

- **README**: Full restructure, Astral/uv-style. ~250-350 lines.
- **TECH_SPEC.md**: Update to current state (not appendix-only, not skip).

## 1. Drift Inventory (concrete facts to fix)

The phases below all derive from this list. Each row pairs a doc claim with the code reality.

| # | Doc claim (location)                                                                        | Code reality                                                                                                                  | Fix in phase |
|---|---------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|--------------|
| D1 | `docs/ARCHITECTURE.md:78` — "skills/ (10)"                                                  | `src/harness_maker/templates/skills/` has **11** dirs (added `refdocs-search` in commit c27dbe4)                              | P2           |
| D2 | `docs/ARCHITECTURE.md:142` — github_releases crawls 7 repos (superpowers, oh-my-claudecode, Archon, ECC, OpenHarness, wshobson, claude-code-templates) | `crawler/github_releases.py:20` — `DEFAULT_REPOS = ["anthropics/claude-code"]` only                                           | P2           |
| D3 | `docs/ARCHITECTURE.md:198` — "fresh worktree under `.claude/.worktrees/<workflow>-<timestamp>/`" | `CLAUDE.md:74,141`, `worktree.py` — base is `.worktrees/` at project root, **not** `.claude/.worktrees/`                       | P2           |
| D4 | No mention of **SessionStart drift reminder hook** anywhere in `docs/` or README             | Shipped in 0.5.6 + 0.5.8 (templates/hooks/)                                                                                   | P2, P3, P4   |
| D5 | No mention of **per-loop unified worktree + worktree_gate**                                  | Shipped in 0.5.5                                                                                                              | P2, P3       |
| D6 | No mention of **hybrid Cursor stop / Claude Code post_tool_use telemetry schema**            | Shipped in 0.5.4                                                                                                              | P2, P3       |
| D7 | No mention of **`/hm:loop` improve mode + coverage-driven adaptive interview**               | Shipped in 0.4.7 area (commit 5f19ee1)                                                                                        | P2, P3, P4   |
| D8 | `docs/ARCHITECTURE.md:111` — "Locale-first (Korean and English)"                             | `CLAUDE.md` line 25 — "English-default (locale=en 디폴트)" + 0.5.7 makes English the no-fallback default                       | P2           |
| D9 | `docs/CONTRIBUTING.md:29-46` repo layout — no `.cursor-plugin/`, no `templates/cursor/`      | Both exist (Cursor target, 0.5.0+)                                                                                            | P2           |
| D10 | `docs/CONTRIBUTING.md:79,93` — "Skills (10)", "Agents (9)"                                   | 11 skills, 9 agents (agents count OK)                                                                                          | P2           |
| D11 | `TECH_SPEC.md` Section 3 mechanisms — only M1-M13                                            | Cursor target adds either an **M14 (dual-IDE rendering)** or expansions to existing M sections; not reflected                  | P3           |
| D12 | `TECH_SPEC.md` makes no mention of `targets`, `recommended_model`, dual plugin manifest      | All three are first-class concepts in 0.5.x                                                                                   | P3           |
| D13 | `TECH_SPEC.md:1299` — "버전업? (유지 — 0.1.0)"                                                  | Version policy now requires bumping 4 files in lockstep (CLAUDE.md §"버전업 정책")                                              | P3           |
| D14 | `TECH_SPEC.md:111,287,574-580,611` — pinned to "0.1.0"                                       | Mostly OK (these are historical Phase 1 examples) but the §3 mechanism list and §6 ADRs need to reflect through 0.5.x         | P3           |
| D15 | `README.md` — no badges, no ToC, no FAQ, no roadmap, hero is a wall of text                  | Astral/uv-style restructure is the goal of P4                                                                                  | P4           |
| D16 | `README.md` "How It Compares" — only 3 rows, no demo/screenshot, no detail on what we add    | Expand to ≥5 rows (add `aider`, `continue.dev` or `crewai` reference points), add demo block                                  | P4           |
| D17 | `README.md` makes no mention of refdocs-search skill, /hm:loop improve mode, ai-readiness 3-layer scoring detail | All shipped — should be "Features"                                                                                            | P4           |
| D18 | `CLAUDE.md` cross-references to `docs/` are mostly OK but need re-verify after P2 edits       | Validate after P2                                                                                                             | P5           |
| D19 | `docs/reference/autoloop-pattern.md`, `docs/reference/block-merge-spec.md` mention old preset/version-style references | Skim and reconcile small drifts                                                                                               | P2           |

**Out of scope** (flagged, not fixed by this PLAN):
- Version drift `0.5.7` (4 files) vs commit `03b3fa2` subject "(0.5.8)". This is a code/release issue, not a docs issue. Mention in P6 final report so the user can run a separate `/plugin update`-style bump.
- `work-docs/plans/PLAN-*.md` historical plans — frozen, do not rewrite.
- `tests/cursor-compat/MANUAL_CHECKLIST.md` etc. — covered in Cursor target plan, not here.

## 2. Architectural Touchpoints

Files this plan **writes to** (no code changes):

```
README.md                              [full rewrite — P4]
docs/ARCHITECTURE.md                   [edits — P2]
docs/CONTRIBUTING.md                   [edits — P2]
docs/reference/autoloop-pattern.md     [light edits if drift — P2]
docs/reference/block-merge-spec.md     [light edits if drift — P2]
TECH_SPEC.md                           [edits + new §7 if needed — P3]
CLAUDE.md                              [verify cross-refs only; minimal — P5]
work-docs/plans/PLAN-docs-refresh-readme-revamp.md  [this file]
```

Files this plan **reads but does not modify**:
- `src/harness_maker/**/*.py` (source of truth for drift verification)
- `src/harness_maker/templates/**/*.j2` (skill/agent counts, hook contents)
- `commands/make.md`, `hooks/hooks.json`
- `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py` (version verification)

No code changes. No template changes. No tests touched. Pure documentation.

## 3. Phases

### Phase 1 — Drift verification pass (read-only)

**Scope**: Walk each row of §1 against current code; promote any "suspected" drifts to "confirmed" or drop them. Add any new drifts found during the walk. Output an updated drift table inside this PLAN (in-place edit of §1).

**Actions**:
1. Re-grep `src/harness_maker/templates/skills/` and `src/harness_maker/templates/agents/` for exact count.
2. Read `src/harness_maker/crawler/github_releases.py` — confirm `DEFAULT_REPOS`. Check `interview.py` to see if user can configure additional repos at install time.
3. Read `src/harness_maker/worktree.py` — confirm base path (`.worktrees/` vs `.claude/.worktrees/`).
4. Read `src/harness_maker/templates/hooks/` and `src/harness_maker/hooks/` — list every hook actually rendered + their trigger events. Cross-check against `docs/ARCHITECTURE.md` "M5 Monitoring" + repo-level `hooks/hooks.json`.
5. Read `src/harness_maker/improvement.py` and `src/harness_maker/templates/commands/hm/loop.md.j2` — confirm `/hm:loop` improve-mode surface area.
6. Read `src/harness_maker/i18n.py` and `src/harness_maker/i18n_messages.py` — confirm locale fallback chain (en default, ko explicit, others → en silent).
7. Skim `docs/reference/autoloop-pattern.md` and `block-merge-spec.md` for any reference to `0.1.x`, "Korean-first", `.claude/.worktrees`, or skill-count claims.

**Exit criterion**: §1 drift inventory updated in-place; every row tagged either ✅ confirmed (proceed to fix), ❌ false-alarm (drop), or 🆕 newly added. No row left "suspected".

**Risk**: low. Read-only.

### Phase 2 — `docs/` refresh (ARCHITECTURE + CONTRIBUTING + reference/)

**Scope**: Apply confirmed drift fixes from §1 (rows D1-D10, D19) to `docs/ARCHITECTURE.md`, `docs/CONTRIBUTING.md`, `docs/reference/autoloop-pattern.md`, `docs/reference/block-merge-spec.md`.

**Concrete edits**:

`docs/ARCHITECTURE.md`:
- Line 78: `skills/ (10)` → `skills/ (11)` and update the prose to mention `refdocs-search`.
- Line 82: keep `agents/ (9)` (correct).
- Line 142: rewrite M4 anti-rot source list to match `crawler/__init__.py` reality. Anthropic blog/changelog ✅; arxiv ✅; OSV ✅; github_releases — say **"`anthropics/claude-code` by default; user-configurable list in `harness.yaml.refresh.github_repos`"** (verify the config key in P1 first).
- Line 198: `.claude/.worktrees/` → `.worktrees/` everywhere; mention prefix-match cleanup (`phase-*`, `autoloop-*`) for Cursor coexistence.
- New M14 short subsection at end of §3: **"M14 — Dual-IDE Rendering (Cursor target)"**. 8-12 lines: targets axis, single-source `.claude/`, additional `.cursor/rules/*.mdc` + `.cursor/mcp.json`, dual plugin manifest, recommended_model policy, KEEP rule trade-off pointer.
- Update §1 line 11 ("Single command, no subcommand sprawl") — keep as-is.
- Add a 1-line note in §2 data flow diagram pointing at `.cursor/` outputs when targets includes cursor.
- Replace "Locale-first (Korean and English)" (line 111) with "Locale-first; English default with Korean built-in messages, other locales silently fall back to English."
- Mention SessionStart drift reminder hook + per-loop unified worktree + hybrid telemetry schema in M5/M9 respectively (1-2 lines each, with version anchors `(0.5.4-0.5.8)`).

`docs/CONTRIBUTING.md`:
- §"Repo Layout" — add `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `templates/cursor/` (rules + mcp.json templates), `tests/cursor-compat/`.
- §"Adding a New Skill Template" line 79 — `Skills (10)` → `Skills (11)`. Mention that `final_acceptance` count check exists in `.claude-verify.sh`.
- §"Adding a New Agent Template" line 93 — `Agents (9)` stays correct.
- New short subsection: **"Adding Cursor target support to a new template"** — explains when `_render_cursor_mdc()` dispatch applies and the strict-frontmatter quirk.
- §"Pull Request Checklist" — add row: "If version-bumping: 4 files in lockstep (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`)."

`docs/reference/autoloop-pattern.md` and `block-merge-spec.md`:
- Skim for stale references; light edits only. Add a header note "Last reviewed against 0.5.x" with date.

**Exit criterion**:
- `grep -nE "skills.*\\b10\\b|skills/  \\(10\\)" docs/` returns zero hits.
- `grep -n "\\.claude/\\.worktrees" docs/` returns zero hits in normative paragraphs (OK in code-block examples that survive elsewhere).
- `grep -n "Korean and English" docs/` returns zero hits.
- M14 section exists in `docs/ARCHITECTURE.md` and explicitly mentions `.cursor-plugin/plugin.json`.
- File line counts within preset Production limits (CONTRIBUTING ≤ 500, ARCHITECTURE ≤ 500, references ≤ 500).

**Risk**: low. Pure prose; existing structure preserved.

### Phase 3 — `TECH_SPEC.md` update to current state

**Scope**: Address rows D11-D14. Update Section 3 (mechanisms) + Section 5 (acceptance) + Section 6 (ADRs) to reflect 0.5.x without rewriting the historical Phase 1-9 task narrative.

**Concrete edits**:
- Section 3 (`(M1)`-`(M13)` block): add **`(M14) Dual-IDE Rendering — Cursor target (0.5.0)`**. 10-15 lines covering: targets enum, dual plugin manifest, single-source `.claude/`, Cursor-only renderer dispatch (`_render_cursor_mdc`, `_render_pure_text` for `.cursor/mcp.json`), KEEP rule for `.cursor/rules/*.mdc` (no content_hash because Cursor strict-rejects unknown frontmatter keys), recommended_model policy.
- Section 3 augmentations (1-line addenda inline, with `(0.5.x)` version anchor):
  - M1 — add `targets` and `recommended_model` to HarnessConfig fields
  - M5 — add SessionStart drift reminder hook + hybrid Cursor/Claude Code telemetry schema
  - M7 — add `/hm:loop` improve-mode + coverage-driven adaptive interview
  - M9 — per-loop unified worktree + worktree_gate enforcement
  - M13 — version-bump-4-files policy (cross-ref CLAUDE.md §"버전업 정책")
- Section 5 acceptance criteria: add an `(M14)` row to the M-mechanism checklist.
- Section 6 ADRs: append three short ADRs covering (a) targets axis + Cursor as native consumer of `.claude/`, (b) recommended_model + no model-agnostic prompt rewrite, (c) version-bump 4-file invariant.
- Section "버전업 정책" / Phase 9 wrapup: replace `버전업? (유지 — 0.1.0)` with cross-reference to CLAUDE.md.
- Add a short "Document health" footer: `Last reconciled against code: 2026-05-07 / version 0.5.x`.

**Exit criterion**:
- `grep -nE "M14|Cursor target|targets axis" TECH_SPEC.md` returns hits in Section 3 and Section 6.
- `grep -nE "recommended_model" TECH_SPEC.md` returns at least 2 hits.
- `grep -nE "0\\.5" TECH_SPEC.md` returns ≥10 hits (version anchors on new 0.5.x mentions).
- File still parses as valid Markdown (no broken table rows / orphan code fences). Manual smoke read.

**Risk**: medium — TECH_SPEC.md is large (1520 lines) and uses Korean prose. Risk of inconsistency between section header style + my new content. Mitigation: read full §3, §5, §6 before editing; match heading depth + bullet style precisely; keep new content additive, never delete historical Phase 1-9 narrative.

### Phase 4 — `README.md` full restructure (Astral/uv-style)

**Scope**: Full rewrite. Replace existing 126-line README with ~280-line README modeled on Astral's `uv` and `ruff`, FastAPI, and `aider`. Hero is one sentence + sub-line; everything else is in a navigable ToC.

**Reference READMEs to mirror structure** (do not copy text):
- [astral-sh/uv](https://github.com/astral-sh/uv) — hero + features grid + comparison
- [astral-sh/ruff](https://github.com/astral-sh/ruff) — badges, ToC, "Why" section
- [tiangolo/fastapi](https://github.com/tiangolo/fastapi) — features list, tagline cadence
- [paul-gauthier/aider](https://github.com/paul-gauthier/aider) — Claude-adjacent positioning, install paths
- [BurntSushi/ripgrep](https://github.com/BurntSushi/ripgrep) — comparison table style

**New README skeleton** (in order):

```markdown
# harness-maker

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-orange)](https://code.claude.com)
[![Cursor 2.4+](https://img.shields.io/badge/Cursor-2.4+-black)](https://cursor.com)
[![Made with uv](https://img.shields.io/badge/built_with-uv-261230)](https://docs.astral.sh/uv/)

> **A meta-plugin for Claude Code + Cursor that builds a project-tailored
> `.claude/` harness — agents, skills, hooks, observability — and keeps it
> fresh against the moving Claude/Cursor ecosystem.**

[Quickstart](#quickstart) ·
[Features](#features) ·
[How it works](#how-it-works) ·
[Comparison](#how-it-compares) ·
[Configuration](#configuration) ·
[FAQ](#faq) ·
[Roadmap](#roadmap)

## Why harness-maker?

Two-paragraph framing. Explain (a) every project needs a `.claude/`, (b) hand-rolling it has a half-life, (c) we treat the harness itself as a deployable artifact with a lifecycle.

## Table of Contents
- [Quickstart](#quickstart)
- [Requirements](#requirements)
- [Features](#features)
- [How it works](#how-it-works)
- [Slash commands the harness exposes](#slash-commands-the-harness-exposes)
- [How it compares](#how-it-compares)
- [Configuration](#configuration)
- [Cursor target](#cursor-target)
- [Reconcile rules (re-rendering an existing harness)](#reconcile-rules-re-rendering-an-existing-harness)
- [Observability](#observability)
- [Marketplace](#marketplace)
- [FAQ](#faq)
- [Roadmap](#roadmap)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Quickstart
[Three-line install + first /harness-maker:make + first /hm:loop]

## Requirements
[Python 3.12, uv, Claude Code CLI ≥ X / Cursor IDE ≥ 2.4, git]

## Features
[Feature grid — 8-10 bullets with bold lead + 1-2 sentence body. Order:
  1. Single command (`/harness-maker:make` + flags)
  2. Two presets, deep override (Side / Production + 10 dims)
  3. Dual IDE (Claude Code + Cursor, single-source .claude/)
  4. AI-readiness scoring (3-layer: deterministic + LLM + cache)
  5. Anti-rot pipeline (4 sources, manual confirm only)
  6. Worktree isolation per /hm:execute (and per /hm:loop iter)
  7. 5 security gates (secrets, perms, hook injection, CVEs, prompt injection)
  8. Privilege separation (reviewer deny-Write / executor allow .worktrees only)
  9. Brownfield-safe reconcile + provenance frontmatter
  10. /hm:loop autoloop with improve mode + coverage-driven adaptive interview]

## How it works
[Mermaid flowchart of profile → interview → synthesize → render → reconcile → /hm:* runtime → weekly /hm:refresh.]

## Slash commands the harness exposes
[Table of /hm:* commands with one-line purpose, grouped by atomic / fused / utility.]

## How it compares
[Expanded table — keep ohmyclaudecode + superpowers + Archon, add aider (positioning) + plain hand-rolled .claude/. 5 rows minimum.]

## Configuration
[Show a real harness.yaml excerpt + the 10 override dims as a list with one-line each.]

## Cursor target
[Keep current section, condensed.]

## Reconcile rules
[Keep current trade-off explainer.]

## Observability
[New section. Mention metrics.jsonl, dashboard.md, refresh raw, security findings — all local. Cite /hm:ai-readiness as the report surface.]

## Marketplace
[Keep current. Note status: pending listing.]

## FAQ
[6-10 Q&As — write below in §"FAQ candidates"]

## Roadmap
[Bullet list — pulled from work-docs/plans/PLAN-*.md and CLAUDE.md open items: PyPI publish, sidecar .hm-meta.yaml for Cursor hash-tracking, marketplace listings, additional refdocs sources.]

## Development
[Keep current.]

## Contributing
[1-paragraph + link to docs/CONTRIBUTING.md]

## License
[Keep current.]
```

**FAQ candidates** (final 6-10 to be picked at write time):
1. Why Python? My project is Rust/Node/Go.
2. Why does it require `uv`?
3. Will harness-maker overwrite my hand-edits when I re-run it?
4. What's the difference between `Side` and `Production`?
5. Does anti-rot ever auto-apply?
6. Can I use only Claude Code? Only Cursor? Both?
7. Do my prompts/telemetry leave my machine?
8. How do I bump the harness after a `/plugin update`?
9. Why is "How It Compares" so opinionated?
10. What if my preferred IDE isn't supported?

**Concrete edits**:
- Replace `README.md` wholesale.
- Keep all factually-correct content from current README; reorganize + expand.
- Remove the inline "Reconcile KEEP rule trade-off" prose (still preserved as its own §).
- Mermaid diagrams: only one (in "How it works"). Avoid >3 mermaid blocks total — keep render-time cheap.
- All claims must be code-verified during P1 (no hallucinated features).

**Exit criterion**:
- README has each of: badges row, ToC, hero one-liner, ≥10 features, mermaid in "How it works", ≥5-row comparison table, ≥6-item FAQ, ≥3-item roadmap.
- All version anchors match 0.5.x (or whatever current version after the out-of-scope bump).
- `grep -c '^## ' README.md` ≥ 14 (matches ToC).
- All cross-links resolve (`docs/ARCHITECTURE.md`, `docs/CONTRIBUTING.md`, `LICENSE`).
- Line count between 250 and 380 (lower than 250 = under-built; over 380 = scroll fatigue).

**Risk**: medium. Largest single deliverable. Risk of (a) hyped-up claims that aren't true, (b) shadow-of-uv stylistic mismatch with our actual tone (CLAUDE.md user voice = "직접적, no preamble"), (c) link rot with internal anchors. Mitigations:
- Every feature bullet must point to a verified mechanism in `docs/ARCHITECTURE.md` (post-P2).
- Hero tagline: write 3 candidates, pick the most specific.
- Render the README locally with `glow` or GitHub preview before declaring done.

### Phase 5 — `CLAUDE.md` cross-ref re-verification

**Scope**: Walk every link/cross-reference in `CLAUDE.md` and confirm targets exist post-P2/P3. Update only if broken. Add a **"Last reviewed"** date footer.

**Actions**:
1. `grep -E "TECH_SPEC|docs/|README" CLAUDE.md` → check each path.
2. Verify `docs/reference/autoloop-pattern.md` reference (CLAUDE.md "Autoloop 빌드 중 모호함 발생 시" §3) is still accurate after P2.
3. Verify version-bump §"버전업 정책" matches the new `docs/CONTRIBUTING.md` checklist row added in P2.
4. No new content — just cross-ref hygiene.

**Exit criterion**:
- All `docs/...` and `TECH_SPEC...` references in CLAUDE.md resolve.
- "Last reviewed: 2026-05-07" footer added.

**Risk**: low. Read-mostly + tiny edits.

### Phase 6 — Final consistency pass + report

**Scope**: One read-through of all 4 doc files in sequence (README → ARCHITECTURE → CONTRIBUTING → TECH_SPEC), watching for cross-document inconsistencies (e.g., README claims "11 skills", ARCHITECTURE says "11 skills", CONTRIBUTING says "11 skills" — all three must match).

**Actions**:
1. Build a small consistency matrix (skill count, agent count, version anchor, M-mechanism count, preset names, target names, worktree path) — assert each row matches across all 4 files.
2. Run `grep -nE "M[0-9]+" README.md docs/*.md TECH_SPEC.md | sort` and ensure no broken M-references.
3. Run `wc -l README.md docs/*.md TECH_SPEC.md` and confirm context-lint thresholds:
   - README: 250-380 lines
   - ARCHITECTURE: ≤ 500
   - CONTRIBUTING: ≤ 500
   - TECH_SPEC: no hard cap, but flag if > 1700 (was 1520; small additions only).
4. Surface the **out-of-scope version drift** (0.5.7 in 4 files vs commit subject "(0.5.8)") in the final report so the user can decide on a version bump.
5. Optional: run `bash .claude-verify.sh final_acceptance` to ensure no `.claude-verify.sh` checks regressed (none should — pure docs).

**Exit criterion**:
- Consistency matrix is uniform across all docs (no row has divergent values).
- No broken M-references.
- Line counts within thresholds.
- Final report committed inline at the bottom of this PLAN.

**Risk**: low.

## 4. Risk Register

| ID | Risk                                                                   | Severity | Mitigation                                                                                                                              |
|----|------------------------------------------------------------------------|----------|------------------------------------------------------------------------------------------------------------------------------------------|
| R1 | README claim drift — easy to over-promise on features that don't exist | High     | P1 verifies every feature bullet in advance. P4 only writes claims that map to an `M` mechanism + a verified `src/` path.                |
| R2 | TECH_SPEC structural breakage when adding M14 + ADRs                   | Medium   | Read all of §3 + §6 before editing. Match exact heading depth and bullet style. Pure additive — no deletions.                            |
| R3 | Tone mismatch — Astral-style polish vs CLAUDE.md "직접적, no preamble"   | Medium   | Hero/FAQ written in user voice (terse, no flattery). No "we believe" / "blazingly fast" cliches. Concrete claims with code anchors.       |
| R4 | Mermaid renders break GitHub preview                                   | Low      | One mermaid block max in README. Validate via raw GitHub preview before declaring done. Keep ASCII fallback in `docs/ARCHITECTURE.md`. |
| R5 | Korean/English mix becomes inconsistent                                | Medium   | TECH_SPEC stays Korean (matches project history); README + docs/ stay English (matches public-facing role); CLAUDE.md stays Korean (matches existing voice). |
| R6 | Internal anchor links break (`#feature-grid` etc.)                     | Low      | GitHub auto-generates anchors from `## Headers` — verify by URL after first render.                                                      |
| R7 | Version-anchor staleness post-bump (0.5.7 → 0.5.8 → 0.6.0)             | Medium   | Use generic `0.5.x` instead of `0.5.7` in long-lived prose. Pin exact version only in installation example.                              |
| R8 | "How it compares" comparison being unfair to other projects            | Medium   | Each row sources to that project's own README. Frame as "what harness-maker adds on top" — additive, not denigrating.                    |

## 5. Rollback Strategy

Each phase is a separate commit. Phase boundaries are rollback points:

- After P1: `git diff` shows only this PLAN file edited. Rollback = `git restore work-docs/plans/PLAN-docs-refresh-readme-revamp.md`.
- After P2: `git diff` shows `docs/`. Rollback = `git checkout HEAD -- docs/`.
- After P3: `git diff` shows `TECH_SPEC.md`. Rollback = `git checkout HEAD -- TECH_SPEC.md`.
- After P4: `git diff` shows `README.md`. Rollback = `git checkout HEAD -- README.md`.
- After P5: `git diff` shows `CLAUDE.md`. Rollback = `git checkout HEAD -- CLAUDE.md`.

Commit messages follow the project convention `docs: <subject>` (per CLAUDE.md §"Git 정책"). Suggested subjects:

```
docs(plan): docs refresh + README revamp plan
docs(arch): reconcile docs/ to 0.5.x reality (skill count, anti-rot sources, worktree path, M14)
docs(spec): TECH_SPEC §3 M14 + 0.5.x mechanism addenda
docs(readme): full restructure to Astral/uv-style with ToC, badges, FAQ, roadmap
docs(claude): refresh cross-refs after docs revamp
```

No code, no templates, no tests changed at any phase — `bash .claude-verify.sh final_acceptance` should be invariant before/after.

## 6. Out-of-scope (mentioned for awareness)

- **Version bump 0.5.7 → 0.5.8 (or 0.5.9)**: commit `03b3fa2` subject claims `(0.5.8)` but the 4 version files weren't bumped. Should be a separate `chore(release)` commit, not folded into this docs PR.
- **PyPI publish path**: README will list this in Roadmap, but the actual publish work is its own task.
- **Cursor Marketplace listing submission**: same — Roadmap row, not done in this plan.
- **Demo gif/screencast**: skipping. Adds release-engineering complexity. Mention in Roadmap.

## 7. Quality Bar

A reader who hasn't seen this PLAN should be able to:

1. Read each phase's §"Concrete edits" and predict the file diff line-for-line.
2. Run each exit criterion as a `grep` or `wc -l` and get a binary pass/fail.
3. Find a mitigation in §4 for every risk that crosses their mind on first read.

If any of those three fail for a given phase, that phase needs another rev before execution.

## 8. Execution order

Recommended single autoloop or sequential `/hm:execute`:

```
P1 (read-only verify)
  → P2 (docs/)
    → P3 (TECH_SPEC.md)
      → P4 (README.md)
        → P5 (CLAUDE.md cross-refs)
          → P6 (final consistency pass)
```

P2 must precede P4 because P4's "Features" section cross-links to ARCHITECTURE.md mechanisms — those need to be correct first.

P3 can run in parallel with P4 in principle (no shared file), but sequencing is cleaner since both need the §1 drift inventory finalized.
