---
type: plan
task_slug: post-release-traction-gap
status: planning
created: 2026-05-22
tags: [harness-maker, plan, oss-launch, discovery, marketing, github-traffic]
research_doc: "[[RESEARCH-post-release-traction-gap]]"
interview_rounds: 4
adrs: 7
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Execute Phase 3 of OSS readiness: README hero flip → 4-aggregator PR sprint → 5-7d soak → r/ClaudeAI + r/cursor."
---

## 🎯 Executive Summary

**TL;DR.** The mechanical release pipeline has fired 11 times in 4 days but no external channel has been activated. This plan executes the missing Phase 3 ("Discovery + announcement") of `PLAN-oss-readiness-audit` with a quality-user goal and a 10h/week budget: flip the README hero, submit to 4 aggregators in parallel, freeze releases for 5-7 days, post to r/ClaudeAI then r/cursor, then run a structured Launch+14d retrospective.

**What.** Six sequential phases over ~3 weeks. Zero code change outside README. No new releases until the soak window closes.

**Why.** GitHub Traffic (last 14 days) shows referrers = `github.com` (self) + `test.pypi.org` (bot), and zero external. Stars = 2, external PRs/issues = 0. The product has shipped; nobody knows it exists. The binding constraint is channel activation, not product polish.

**Key decisions** (linked to ADRs):
- ADR-001 — Goal = quality external engagement signal, not vanity stars.
- ADR-002 — Aggregator scope = `anthropics/claude-plugins-official` + 3 community awesome-lists (NOT all 7+ at once).
- ADR-003 — Soak window = 5-7 day release freeze before launch posts.
- ADR-004 — Launch channel = r/ClaudeAI + r/cursor (NOT Show HN, NOT X thread, NOT dev.to in this cycle).
- ADR-005 — Traction metric = ≥3 external engagement events + ≥2 unique non-bot referrer sources within 14 days of launch. *(Referrer threshold revised down from 3 to 2 per validator Pass 1 — see ADR-005 Revision note.)*
- ADR-006 — README hero restructure: "Why" before install prompt (Phase 1 prerequisite for aggregator traffic).
- ADR-007 — Iteration gate = Launch+14d retrospective spawns next RESEARCH; this PLAN closes.

**Estimated impact.** Net-zero on code (one README PR + four upstream PRs to other repos). Time cost ~25-30h spread over 3 calendar weeks. Downside: if Reddit posts flop, social signal weakly negative but recoverable. Upside: any non-zero external referrer source clears the binding constraint, enabling all future iteration to operate on real data.

## 📚 Prior Work

### Memory entries surfaced

- **`[wiki:oss-launch-readiness-three-layer]` (2026-05-19)** — three-layer launch framework. Phases 1 (trust floor) + 2 (positioning surface) shipped in `PLAN-oss-readiness-audit`. Phase 3 (Discovery + announcement) was scoped but never executed. This PLAN is the execution of Phase 3.
- **`[wiki:per-project-personalization-hero-differentiator]` (2026-05-19)** — positioning is already locked: tagline "A different harness for every project — built from yours, never generic." + 4-tag sub "Per-project personalization · Grade-gated · Self-evolving · Multi-IDE". User has prior-locked this; do NOT re-derive in this PLAN. Use verbatim in every aggregator PR + Reddit post.
- **`[wiki:readme-one-prompt-bash-not-slash]` (2026-05-19)** — the README install prompt is a competitive differentiator (AI-driven `Bash:` install across 3 IDEs from a single paste). Phase 1 (README hero restructure) must preserve this block; the restructure moves "Why" ABOVE it, does not remove it.
- **`[wiki:fresh-install-health-baseline]` (2026-05-19)** — 0.17.0 shipped fresh-install zero-P0. Aggregator-driven first-time visitors will fresh-install; the bar there is good, so no Phase 0 work needed on install path itself.

### Adjacent prior PLANs

- `[[PLAN-oss-readiness-audit]]` — parent plan. This PLAN executes its Phase 3.
- `[[RESEARCH-oss-readiness-audit]]` — 20-item OSS launch checklist still relevant for retrospective rubric.
- `[[REVIEW-oss-readiness-audit-2026-05-19]]` — confirmed Phases 1+2 landed at Grade A.

### Lessons from `failures.md` (relevant patterns)

- Phase 1 (README edit) must use Write tool (full-file rewrite via WSL2 NTFS path), not Edit. Confirmed in 2026-02-15 learned correction.
- 5-file version sync (3 plugin.json + pyproject.toml + `__init__.py`) is the existing release discipline — Phase 3 soak does NOT touch this, but if any PR review demands a release during soak, the freeze gate must hold.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Success definition | Scope/goal | What does this launch optimize for? | quality users / vanity stars / category visibility / passive listing | quality users | external engagement, not vanity | ADR-001 |
| 2 | Time budget | Risk/operational | Weekly time for launch work? | 4h / 10h / 20h+ / unbounded | 10h/week | enables 3-week timeline | — |
| 3 | Author voice | Operational | Identity exposure for social posts? | real name / mixed / anonymous / project-only | real name + own SNS | consistent with public GitHub | — |
| 4 | Aggregator scope | Architecture/scope | Which lists to submit to? | official + 3 / full 7+ / verify-first / official-only | official + 3 community | rejects full sprint & verify-first | ADR-002 |
| 5 | Soak window | Risk tolerance | Release freeze duration? | 5-7d / 2-3d / until-PR-resolves / no freeze | 5-7 days | release-discipline contract | ADR-003 |
| 6 | Launch channel | Contract shape | First launch post target? | r/ClaudeAI+r/cursor / Show HN / X thread / dev.to | r/ClaudeAI + r/cursor | rejects HN & X & dev.to | ADR-004 |
| 7 | Traction metric | Observability | "Quality user N" measured how? | engagement signal / PyPI / hands-on / combo | engagement signal | 3 events + 3 referrer sources in 14d | ADR-005 |
| 8 | README hero | Contract shape | Restructure hero? | Why-first / status-quo / hybrid / decide-later | Why before install prompt | precedes aggregator traffic | ADR-006 |
| 9 | Iteration gate | Phasing | Plan close protocol? | retro+next-research / auto-escalate / ad-hoc / end-interview | Launch+14d retrospective | spawns next RESEARCH | ADR-007 |
| 10 | ADR-005 referrer math | Observability (validator Pass 1) | Threshold ≥3 unreachable from planned channels — how to fix? | lower to ≥2 / add dev.to / accept unreachable | lower to ≥2 | reddit.com + claudemarketplaces.com if listed | ADR-005 Revision |
| 11 | Reddit karma/automod | Risk (validator Pass 1) | Silent automod hold prevention? | Phase 0 pre-check + abort gate / risk row only / build karma 1-2w first | Phase 0 pre-check + abort gate | Phase 0 task 4 + risk row + Phase 4 Task 0(b) | — |
| 12 | 14d window persistence | Observability (validator Pass 1) | Day 1 referrer data ages out at Day 15 — how to preserve? | daily log + exit criterion / log only / move retrospective to Day 7 | daily log + exit criterion | `launch-metrics-log.md` mandatory | — |

## 📐 Architecture Decision Records

### ADR-001: Optimize for external engagement signal, not vanity stars
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** Without an explicit success target, channel + metric + content choices drift toward whatever feels good. Vanity stars are easy to chase but produce a poor selection of users (drive-by stargazers, no contribution).
**Decision:** Goal = quality users who file issues, open PRs, or use the harness in real projects. All downstream choices (channel, metric, content tone) optimize for this.
**Consequences:**
- ✅ Filters out HN/X strategies that maximize impressions over conversion.
- ⚠️ Slower visible feedback loop than star-count chasing.
**Rejected alternatives:**
- Vanity-star metric — Rejected because stars do not predict PR-filing users.
- Category-visibility long-term — Rejected as plan-scope; will revisit in retrospective.
- Passive listing — Rejected; defeats purpose of the plan.
**Source:** Interview #1

### ADR-002: Aggregator submission scope = anthropic official + 3 community lists
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** 7+ awesome-lists and 2 directory sites exist for Claude Code plugins. PR-ing to all of them in parallel is high effort with diminishing returns (dormant lists, conflicting templates). Submitting to only one is insufficient signal.
**Decision:** Phase 2 submits PRs to four targets in parallel: `anthropics/claude-plugins-official` (gold standard) + `ccplugins/awesome-claude-code-plugins` + `jmanhype/awesome-claude-code` + `GiladShoham/awesome-claude-plugins`. The other 3+ awesome-lists and 2 directories deferred to retrospective.
**Consequences:**
- ✅ Concentrated effort, all four are actively maintained.
- ⚠️ Misses long-tail coverage from `ComposioHQ`, `jqueryscript`, `hekmon8`, `Chat2AnyLLM`, `claudemarketplaces.com`, `aitmpl.com`. Retrospective decides whether to extend.
**Rejected alternatives:**
- Full 9-list sprint — Rejected; 10h/week budget can't sustain 9 parallel PR threads with quality.
- Verify-first (check `claudemarketplaces.com` auto-crawl first) — Rejected as scope inversion; Phase 0 already verifies state before committing.
- Anthropic only — Rejected; single submission is unrecoverable if rejected.
**Source:** Interview #4

### ADR-003: 5-7 day release freeze before launch posts
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** 11 GitHub releases shipped 2026-05-18 → 2026-05-21. To a launch-day skimmer, the Releases tab signals instability. Autoloop work continues but accumulates as PRs.
**Decision:** From the start of Phase 3 (soak), no `v*` tag pushes for 5-7 calendar days. autoloop branches land as PRs into `main`; CHANGELOG `[Unreleased]` section accumulates entries. After Phase 4 launch posts, normal release cadence resumes.
**Consequences:**
- ✅ Releases tab shows "stable, last release 5+ days ago" at launch moment.
- ⚠️ Urgent security fix mid-soak forces a CHANGELOG-noted patch; allowable exception.
**Rejected alternatives:**
- 2-3 day freeze — Rejected; not enough to flip the optics.
- Until-anthropic-PR-resolves — Rejected; PR could sit 1-4 weeks, gating launch indefinitely.
- No freeze — Rejected; "moves fast" signal works for established projects, hostile for a 2-star repo.
**Source:** Interview #5

### ADR-004: Launch channel = r/ClaudeAI + r/cursor (stagger), no Show HN this cycle
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** Show HN, Reddit, X, and dev.to optimize for different audiences and have different blowback risks. Quality-user goal (ADR-001) prefers concentrated audience + low-noise comment surface.
**Decision:** Phase 4 posts to r/ClaudeAI first; if not removed/flagged within 24h, posts to r/cursor 24-48h later. Show HN, X thread, dev.to anchor post explicitly out of scope for this plan.
**Consequences:**
- ✅ Both subreddits have pre-warm audience for the harness category.
- ✅ Stagger allows learning from r/ClaudeAI comments before r/cursor.
- ⚠️ Misses HN front-page upside potential.
- ⚠️ X and content channels untouched; retrospective decides.
**Rejected alternatives:**
- Show HN — Rejected; permanent association with one top-comment, high critique density, HN audience skews toward "another wrapper" fatigue.
- X thread — Rejected; Ecro account follower structure not yet built; would flop without amplification.
- dev.to anchor post — Rejected as Phase 4 entry; viable as retrospective output if Phase 5 indicates content-led seeding.
**Source:** Interview #6

### ADR-005: Traction metric = ≥3 external engagement events + ≥2 unique non-bot referrers in Launch+14d
**Status:** Accepted (2026-05-22, via /hm:plan interview) · **Revised (2026-05-22, validator Pass 1 follow-up)** — referrer threshold lowered from 3 to 2.
**Context:** "Quality user N" is meaningless without a count + signal definition. PyPI download deltas conflate bots; star count is the rejected vanity metric.
**Decision:** Plan succeeds if, within 14 days of Phase 4 first post:
- **≥3 external engagement events**: external issue OR external PR OR external Discussion comment (not Dependabot, not self).
- **AND ≥2 unique referrer sources** in GitHub Traffic Referrer, excluding `github.com`, `test.pypi.org`, `pypi.org`.
- Both thresholds must hold; either alone is insufficient.

**Channel → expected GitHub Traffic referrer domain (validator Pass 1 mapping):**
| Channel | Expected referrer domain | Counts toward threshold? |
|---|---|---|
| r/ClaudeAI post (Phase 4) | `reddit.com` | ✅ (1 source) |
| r/cursor post (Phase 4) | `reddit.com` | ❌ (collapses into same domain) |
| Anthropic official listing (Phase 2) | `github.com` | ❌ (excluded by ADR-005) |
| ccplugins/jmanhype/GiladShoham awesome-list (Phase 2) | `github.com` | ❌ (excluded) |
| claudemarketplaces.com (if auto-crawled in Phase 0) | `claudemarketplaces.com` | ✅ (1 source if outbound link present) |
| Discord/X organic share (uncontrolled) | varies (`discord.com`, `t.co`, etc.) | ✅ if it lands |

Realistic floor from planned channels: 1 (reddit.com only) if claudemarketplaces.com not indexed. Realistic ceiling: 2-3 (reddit.com + claudemarketplaces.com + one organic). Threshold lowered to ≥2 to reflect this rather than ratchet up scope.

**Consequences:**
- ✅ Hard to false-pass: requires concrete user action AND traffic-source diversity.
- ✅ Achievable from scoped channels (1-2 expected, 2 required = some lift required, not impossible).
- ⚠️ Could under-count private-repo users (people who install but never engage publicly). Accepted trade-off.
- ⚠️ Two Reddit posts collapse to one referrer source — known property of GitHub Traffic API, accepted.
**Rejected alternatives:**
- PyPI human-filtered downloads — Rejected; bot/human filtering is unreliable.
- Hands-on usage signal alone — Rejected; too rare to gate at 14d.
- Combo of all three — Rejected as over-engineered; two-threshold AND is sufficient.
- (Revision) Keep ≥3 referrers + add dev.to anchor post to Phase 4 — Rejected; ADR-004 already rejected dev.to for this cycle, scope creep.
- (Revision) Keep ≥3 as known-unreachable stretch goal — Rejected; vanity gate worse than honest gate.
**Source:** Interview #7 (original), Interview #10 (revision)

### ADR-006: README hero = "Why" section before install prompt (precedes aggregator traffic)
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** README current order (lines 35-65 = 30-line install prompt; lines 68+ = "Why harness-maker?") buries value proposition. Aggregator visitors land here and bounce if value isn't visible in 5 seconds. Install prompt is a competitive moat (`[wiki:readme-one-prompt-bash-not-slash]`) but must not precede the elevator pitch.
**Decision:** Phase 1 restructures README.md (and README.ko.md mirror) so that "Why harness-maker?" + the 5-line principle table appears before the 30-line install prompt block. The tagline + 4-tag sub stay at top (positioning anchor). Install prompt is preserved verbatim, just demoted in position.
**Consequences:**
- ✅ First-paint shows value, not paste-target.
- ✅ Cursor / Codex visitors who don't yet trust the project see "why" before being asked to paste.
- ⚠️ Loses the "instant install" feel for return visitors. Acceptable; they can use bookmark / direct link.
**Rejected alternatives:**
- Keep current order — Rejected; install-first works for products with brand, not for unknown 2-star repos.
- Hybrid (tagline + 1-line summary at very top, then install prompt, then Why) — Rejected as half-measure; the install prompt is too visually heavy to fit above Why.
- Decide after Phase 4 — Rejected; the launch traffic IS the conversion test, so the README must be ready before traffic arrives.
**Source:** Interview #8

### ADR-007: Iteration gate = Launch+14d structured retrospective spawns next RESEARCH; this PLAN closes
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** After Phase 4 launch posts go live, the next move (more channels? content seeding? README iteration?) depends on observed traction. Auto-escalation rules drift from real signal.
**Decision:** Phase 5 = mandatory 14-day measurement window + structured retrospective document (`RESEARCH-launch-retrospective.md` or similar). This PLAN closes at retrospective; next-cycle decisions become a new RESEARCH/PLAN pair.
**Consequences:**
- ✅ Clean plan boundary; no scope creep.
- ✅ Forces evidence-based next-cycle decision.
- ⚠️ Adds a ~30 minute writing task at day 14.
**Rejected alternatives:**
- Metric-pass-or-auto-escalate — Rejected; "auto Show HN if Reddit fails" pre-commits to a channel we already rejected (ADR-004).
- 1-post then ad-hoc — Rejected; ad-hoc decisions skip evidence-gathering.
**Source:** Interview #9

## 🏗️ Technical Design

### Current State

- **Repo:** public, MIT, 14 topics set, Discussions enabled, 100% community health score, 2 stars, 0 external PRs.
- **README.md:** 845 lines. Hero (lines 1-32): brand image, badges, tagline, 4-tag sub, nav links. Lines 35-65: 30-line install prompt block. Lines 68+: "Why harness-maker?" + principle table. README.ko.md mirrors the structure (389 lines).
- **Releases:** 11 tags between 2026-05-18 and 2026-05-21 (latest v0.20.2).
- **Traffic referrers (14d):** github.com (self), test.pypi.org (bot). Zero external.
- **PyPI downloads:** 304 day / 1,424 week / 1,424 month — likely dominated by mirrors + CI bots.

### Affected Components

This PLAN modifies one in-repo file (`README.md` + `README.ko.md`) and opens PRs to four upstream repos. No code, no tests, no harness asset templates.

| Component | Change | Scope |
|---|---|---|
| `README.md` | Hero restructure (move Why before install prompt) | Phase 1 |
| `README.ko.md` | Mirror restructure | Phase 1 |
| `tests/test_render_snapshots.py` | (Likely no impact — README is not rendered) | Phase 1 verify |
| Upstream PR #1 | `anthropics/claude-plugins-official` submission | Phase 2 |
| Upstream PR #2 | `ccplugins/awesome-claude-code-plugins` submission | Phase 2 |
| Upstream PR #3 | `jmanhype/awesome-claude-code` submission | Phase 2 |
| Upstream PR #4 | `GiladShoham/awesome-claude-plugins` submission | Phase 2 |
| `CHANGELOG.md` `[Unreleased]` | Accumulates during soak (no tag) | Phase 3 |
| Reddit post `r/ClaudeAI` | New post, lead with positioning | Phase 4 |
| Reddit post `r/cursor` | New post (24-48h after r/ClaudeAI), tailored | Phase 4 |
| `work-docs/RESEARCH-launch-retrospective.md` | Day-14 measurement doc | Phase 5 |

### Dependencies

- `gh` CLI for PR creation + traffic monitoring (already installed).
- No new Python deps.
- No external API keys.

### Architecture

This is a launch sequence, not a software architecture. The "data flow" is the funnel:

```
[Aggregator listing]  →  [Visitor lands on README]  →  [Reads "Why" (Phase 1 flip)]
                                                                  ↓
                                                       [Decides to install or bounce]
                                                                  ↓
                                                       [Paste install prompt]
                                                                  ↓
                                                       [/hm:make interview]
                                                                  ↓
                                                       [Becomes engagement signal]
```

```
[Reddit post]         →  [Same README path]
[Reddit comment]      →  [GitHub issue or Discussion]  ←  engagement signal counter
```

### Design Decisions

All architectural decisions are captured in ADRs above. No tacit choices in the technical design.

### Data Flow / API Changes

None. No API. No data persistence beyond the PLAN and retrospective Markdown files.

## 📝 Implementation Plan

### Phase 0 — Verify discovery state baseline
**Scope (files in):** Create `work-docs/launch-phase0-verify.md` capturing baseline state.
**Scope (files out):** No code edits.
**Tasks:**
1. Check `claudemarketplaces.com` for existing harness-maker listing (search "harness-maker", "Ecro"). Capture whether listing exists, whether outbound link is present (needed for ADR-005 referrer count).
2. Search each of the 4 target awesome-lists (anthropic official, ccplugins, jmanhype, GiladShoham) for existing harness-maker entries (avoid duplicate PRs).
3. Read each target's CONTRIBUTING.md / PR template / acceptance criteria. Note divergences (alphabetical order, tagline length, required metadata).
4. **Reddit posting pre-flight (validator Pass 1):** read `r/ClaudeAI` and `r/cursor` rules. Capture: minimum karma threshold, account age requirement, self-promotion / promotional-content rules, required flair, post-format requirements, AutoModerator notes. Verify the intended posting account meets every criterion. Record account current karma + account age in the verify doc.
5. Snapshot baseline GitHub metrics: stars=2, external PRs=0, referrers={github.com, test.pypi.org}, PyPI day=304.
**Exit criterion:** `work-docs/launch-phase0-verify.md` exists, contains: per-target acceptance criteria + baseline metrics + go/no-go per PR + Reddit karma/age verification (PASS or FAIL with remediation path) + claudemarketplaces.com listing status with outbound-link verdict.
**Risk:** low.
**Rollback point:** N/A — read-only.

### Phase 1 — README hero restructure
**Scope (files in):** `README.md`, `README.ko.md`.
**Scope (files out):** No template changes (this is project-root README, not in `templates/`).
**Tasks:**
1. Move "Why harness-maker?" + principle table (current lines 68-79) to immediately AFTER the nav links (current line 31), BEFORE the "Try in 30 seconds" install prompt block.
2. Preserve the install prompt block verbatim — only its position changes.
3. Add a 1-line "What it is in 10 words" between tagline (line 15) and the 4-tag sub-line (line 17). Suggested: `> **What:** A harness shaped by your project — not a fixed template.` (English) and Korean mirror.
4. Mirror the structure in `README.ko.md`.
5. Run `uv run pytest tests/ -k readme` to confirm no snapshot tests broke (expected: none reference README structure).
6. Open a PR with title `docs: hero restructure — "Why" before install prompt (PLAN-post-release-traction-gap Phase 1)`.
**Exit criterion:** PR merged to `main`. Visual check: scrolling from line 1, "Why harness-maker?" heading appears before the install prompt code fence.
**Risk:** low — README-only.
**Rollback point:** revert the merge commit. README returns to status quo.

### Phase 2 — Aggregator PR sprint (parallel, ETA 1-2 weeks for merges)
**Prerequisite (validator Pass 1):** Phase 1 PR merged to `main`. Do not open any Phase 2 PR until the README restructure is live on the default branch — aggregator visitors clicking the listing must land on the restructured hero, not the install-prompt-first old layout.
**Scope (files in):** No in-repo changes. Four upstream PRs.
**Scope (files out):** Do NOT submit to dormant lists, do NOT touch claudemarketplaces.com unless Phase 0 confirms a manual submission path.
**Tasks (each PR uses the locked positioning from `[wiki:per-project-personalization-hero-differentiator]`):**
1. PR to `anthropics/claude-plugins-official` — follow their CONTRIBUTING exactly (likely requires manifest validation, plugin.json check). Submission must use the standardized tagline.
2. PR to `ccplugins/awesome-claude-code-plugins` — appropriate section, alphabetical insert, link to README.
3. PR to `jmanhype/awesome-claude-code` — same approach.
4. PR to `GiladShoham/awesome-claude-plugins` — same approach, verify their Marketplace-spec alignment.
**Submission template (all four):**
```
- **[harness-maker](https://github.com/Ecro/harness-maker)** — A different harness for every project — built from yours, never generic. Per-project personalization · Grade-gated · Self-evolving · Multi-IDE (Claude Code · Cursor · Codex).
```
**Exit criterion:** 4 PRs opened, URLs recorded in `work-docs/launch-phase0-verify.md`. Wait for merge / response in Phase 3.
**Risk:** low — no code change, rejection is free signal.
**Rollback point:** close PRs.

### Phase 3 — Release freeze (soak window, 5-7 calendar days)
**Scope (files in):** None. Discipline gate.
**Scope (files out):** No `v*` tag pushes; no `.claude-plugin/plugin.json` / `.cursor-plugin/plugin.json` / `.codex-plugin/plugin.json` / `pyproject.toml` / `src/harness_maker/__init__.py` version bumps.
**Tasks:**
1. Mark soak start: write `work-docs/launch-soak-window.md` with start date.
2. autoloop work continues on feature branches; lands as PRs into `main` with no follow-up tag.
3. CHANGELOG `[Unreleased]` section accumulates entries — do NOT cut a release for them.
4. Exception path: a P0 security fix (CVE with active exploit affecting our deps) may release; note the exception in the soak doc.
**Exit criterion:** ≥5 calendar days elapsed since Phase 3 start with no `v*` tag pushed. (`gh release list --repo Ecro/harness-maker --limit 1` shows the v0.20.2 (or last-pre-freeze) tag still as Latest.)
**Risk:** low — discipline only.
**Rollback point:** lift freeze, push tag. Trivially reversible.

### Phase 4 — Launch posts (r/ClaudeAI then r/cursor, staggered)
**Scope (files in):** No code changes. Two Reddit posts.
**Scope (files out):** No Show HN, no X thread, no dev.to post in this phase.
**Tasks:**
0. **Pre-flight gate (validator Pass 1) — do not proceed to Task 1 unless ALL three confirm:**
   - (a) `gh release list --repo Ecro/harness-maker --limit 1` shows the pre-soak tag (last v* before Phase 3 start) still as Latest, and ≥5 calendar days have elapsed since Phase 3 start date in `work-docs/launch-soak-window.md`.
   - (b) `work-docs/launch-phase0-verify.md` contains `r/ClaudeAI` and `r/cursor` rule capture + posting-account karma verification = PASS.
   - (c) Phase 1 README restructure is live on the default branch (`gh api repos/Ecro/harness-maker/contents/README.md | jq .sha` matches the merge commit recorded in Phase 1).
   If any (a)/(b)/(c) fails, abort Phase 4 and log the failure in `launch-soak-window.md`; do not post.
1. Draft r/ClaudeAI post:
   - Title: lead with differentiator (e.g., "harness-maker — a Claude Code plugin that builds a different harness per project from a profiler + 10-dim interview").
   - Body: 3-4 short paragraphs (problem → mechanism → install in one paste → link to README). Include 1 asciinema or screenshot.
   - Pre-emptively address "another wrapper" critique in the body.
2. Post to r/ClaudeAI Day 1.
3. Monitor + engage for 24h (respond to every top-level comment within 4h business-hours, neutral tone).
4. If r/ClaudeAI not removed/locked, tailor to r/cursor on Day 2-3 (emphasize Cursor target rendering).
5. Post to r/cursor.
6. Continue engagement another 24h.
**Exit criterion:** Both posts live (or r/ClaudeAI removal documented + r/cursor decision made). Comment engagement completed within 4h windows for first 24h.
**Risk:** medium — irreversible social association if posts flop. Mitigation: pre-emptive critique handling + neutral tone.
**Rollback point:** can delete own Reddit posts; social signal already cast (downvote signal partially permanent via Pushshift archives, but mainstream impact decays).

### Phase 5 — Measure + structured retrospective (Launch+14d)
**Scope (files in):** Create `work-docs/launch-metrics-log.md` (daily snapshot log) + `work-docs/RESEARCH-launch-retrospective.md` (final retrospective; slug finalized at write time).
**Scope (files out):** No code, no template changes.
**Tasks:**
1. **Days 1-14 from Phase 4 post-1 — daily 5-minute snapshot, persisted to `work-docs/launch-metrics-log.md` (validator Pass 1):**
   - Run `gh api repos/Ecro/harness-maker/traffic/popular/referrers` and capture every referrer domain seen.
   - Count external issues / PRs / Discussions added since last snapshot (exclude Dependabot + self).
   - Capture star delta.
   - Append one row to `launch-metrics-log.md` in format: `| YYYY-MM-DD | referrer domains (comma-sep) | cumulative unique non-bot referrers | engagement events today | cumulative engagement events | stars |`. This file is the source of truth — GitHub Traffic Referrer retains only 14 rolling days, so without daily persistence Day 1 data is lost by Day 15.
2. Day 14: write retrospective at `work-docs/RESEARCH-launch-retrospective.md` with:
   - Final metric values vs ADR-005 thresholds (read from `launch-metrics-log.md`, not from a fresh API call which would already be missing Day 1).
   - Pass/fail/inconclusive verdict.
   - Hypotheses for next cycle (more channels? content seeding? README iteration? Pivot tagline?).
   - Specific items to feed into next `/hm:research` invocation.
3. Lift release freeze (if not already lifted earlier).
4. Close this PLAN (`status: complete` in frontmatter).
**Exit criterion:** ALL of:
- `work-docs/launch-metrics-log.md` exists with ≥12 entries (covering ≥12 of the 14 days).
- `work-docs/RESEARCH-launch-retrospective.md` exists, verdict recorded against ADR-005.
- This PLAN's frontmatter `status` set to `complete`.
**Risk:** low.
**Rollback point:** N/A — measurement only.

## 🧪 Testing Strategy

### Unit / integration tests

- Phase 1 (README edit): `uv run pytest tests/` to ensure no test depends on README structure. Expected outcome: green, no test references README internals.
- Phases 0, 2, 3, 4, 5: no automated tests. Discipline + measurement.

### Manual verification

- Phase 0: open each target awesome-list, confirm acceptance criteria are extractable.
- Phase 1: render README.md preview locally (or use GitHub's preview after push) — confirm "Why" heading appears above install prompt.
- Phase 2: each PR is opened with correct alphabetical position + standardized tagline. Confirm via `gh pr view` on each PR.
- Phase 3: `git log --oneline --tags` shows no new `v*` tag for 5+ days.
- Phase 4: each Reddit post URL recorded in soak doc; comment engagement timestamps captured.
- Phase 5: retrospective document follows RESEARCH frontmatter convention.

### What is NOT tested

- We do NOT test the install prompt against fresh Cursor / Codex IDE installs in this plan. That work belongs to `tests/cursor-compat/` and is out of scope. (Fresh-install baseline already at zero-P0 per `[wiki:fresh-install-health-baseline]`.)

## ⚠️ Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Anthropic official PR rejected (criteria miss) | medium | medium | Phase 0 reads CONTRIBUTING fully. If rejected, retrospective decides whether to revise + resubmit vs deprioritize. |
| All 4 aggregator PRs sit unmerged through soak | high | low | OK — listing is not a launch gate. Phase 4 proceeds regardless. Retrospective notes acceptance lag as data. |
| r/ClaudeAI post removed by mod (rule violation) | low | medium | Pre-read subreddit rules in Phase 0. Tag as "self-promotion" if required. If removed, skip r/cursor and reassess. |
| **Reddit AutoModerator silent karma/age hold** (validator Pass 1) | depends on account age — check in Phase 0 | high (silent zero-engagement failure, indistinguishable from no post) | Phase 0 task 4 verifies karma + account age against both subreddit rules; Phase 4 Task 0 gate (b) blocks posting if Phase 0 verdict was FAIL. If below threshold, options: (1) build karma via comment activity for 1-2 weeks then re-enter Phase 4, (2) accept the risk explicitly and post anyway, (3) switch to alternate posting account. Decision recorded in `launch-phase0-verify.md`. |
| **ADR-005 referrer threshold reachable only with claudemarketplaces.com cooperation or organic share** (validator Pass 1) | medium | low | Phase 0 task 1 captures whether claudemarketplaces.com lists us with outbound link. Threshold revised to ≥2 (ADR-005 Revision) reflects realistic floor. If even ≥2 unreachable at Day 14, retrospective drives next cycle. Plan still closes cleanly. |
| **GitHub Traffic 14d rolling window loses Day 1 by Day 15** (validator Pass 1) | high if log not persisted | medium (data integrity) | Phase 5 task 1 mandates daily append to `launch-metrics-log.md` — the persisted log is the source of truth, not the API at retrospective time. Phase 5 exit criterion requires ≥12 of 14 days logged. |
| r/ClaudeAI post downvoted to oblivion | medium | medium | Acceptable — quality-user metric (ADR-005) does not require upvotes, only engagement events. One curious commenter who files an issue clears the metric. |
| Soak window broken by urgent fix during soak | low | low | Allowed exception (P0 only). Document in soak doc. Does not invalidate launch. |
| README PR (Phase 1) breaks snapshot tests | low | low | Phase 1 task #5 catches this; revert + iterate if needed. |
| Launch+14d traction below ADR-005 threshold | medium-high | low | Expected possibility. Retrospective spawns next RESEARCH with concrete hypotheses; PLAN itself still closes cleanly. |
| Cursor / Codex visitors install via README path and hit a bug | low | high | Out of scope here, covered by fresh-install baseline. If discovered during launch, file P0 in main project, document in retrospective. |
| Naming collision (harness-maker vs "Everything Claude Code" 82k★) overshadows post | medium | medium | Post body leads with mechanism differentiator + 10-dim interview demo, not name. Retrospective measures whether naming is the bottleneck. |

## ✅ Success Criteria

Plan succeeds when ALL of the following hold at Phase 5 day 14:

- [ ] Phase 0 verify doc written, all 4 PR acceptance criteria captured.
- [ ] Phase 1 README PR merged; "Why" precedes install prompt in `main` branch README.
- [ ] Phase 2: 4 PRs opened (regardless of merge status); URLs recorded.
- [ ] Phase 3: 5+ calendar days with no `v*` tag between Phase 3 start and Phase 4 first post.
- [ ] Phase 4: r/ClaudeAI post live (or removal documented); r/cursor post live (or skip decision documented).
- [ ] Phase 5: retrospective doc written with verdict against ADR-005 metric.
- [ ] PLAN frontmatter `status` set to `complete`.

Plan also "passes" on its quality goal (ADR-001) when ADR-005 thresholds hold at day 14:

- [ ] ≥3 external engagement events (issue / PR / discussion, excluding Dependabot + self).
- [ ] ≥3 unique non-bot referrer sources (excluding github.com, test.pypi.org, pypi.org).

If the quality goal fails but all phases completed, the plan still closes cleanly; the retrospective drives next iteration.

## 🔍 Plan Validation

**Validator outcome:** `NEEDS_REVISION_RESOLVED` (`plan-validator` agent — Sonnet, Pass 1, 2026-05-22)

**Critiques resolved:**

| # | Severity | Section | Issue (summary) | Resolution |
|---|---|---|---|---|
| 1 | warning | ADR-005 + Risks | ≥3 referrer source threshold unreachable from planned channels (GitHub Traffic aggregates by domain; Reddit collapses to one source; awesome-list traffic via github.com is excluded; PyPI excluded). Plan would always fail metric. | **ADR-005 amended (Revision 2026-05-22)** — threshold lowered to ≥2, with explicit channel→referrer-domain mapping table added. Engagement event threshold (≥3) unchanged. Resolution via Interview #10. |
| 2 | warning | Phase 0 + Risks | No Reddit account karma/age pre-check; AutoModerator silent-hold is high-probability failure path indistinguishable from "no post" and not in risk register. | **Phase 0 task 4 added** (capture both subreddit rules + verify account karma/age = PASS or FAIL), **Phase 0 exit criterion expanded** (must record Reddit verdict), **Phase 4 Task 0 gate (b)** blocks posting if FAIL, **risk row added** ("Reddit AutoModerator silent karma/age hold"). Resolution via Interview #11. |
| 3 | warning | Phase 5 | GitHub Traffic Referrer 14-day rolling window means Day 1 data ages out before Day-14 retrospective; daily check has no persistence, so missed days lose data permanently. | **Phase 5 task 1 rewritten** to mandate daily append to `work-docs/launch-metrics-log.md` (with explicit row format), **Phase 5 exit criterion expanded** to require ≥12 of 14 days logged + log used as source of truth (not fresh API at retro). Resolution via Interview #12. |
| 4 | nit | Phase 2 | No explicit prerequisite that Phase 1 (README restructure) must merge before Phase 2 PRs open. | **Phase 2 Prerequisite line added** at top of phase scope. |
| 5 | nit | Phase 4 | Direct draft→post with no pre-flight gate (soak elapsed? Phase 0 rules captured? Phase 1 live?). | **Phase 4 Task 0 added** — three-item pre-flight gate (a) soak elapsed via `gh release list`, (b) Phase 0 Reddit verdict = PASS, (c) Phase 1 README live on default branch via README sha match. Posting blocked on any failure. |

**Validator NOT re-run.** Per `/hm:plan` Step 4: validator re-runs only on MAJOR_REVISION. NEEDS_REVISION resolution is in-loop, one follow-up round per warning (Interviews #10-#12) plus mechanical nit application. No infinite-loop risk.

**Independent quality verification:** PLAN structure verified (frontmatter present, Interview Transcript 12 rows, ADR count 7 matches frontmatter, all 6 phases have scope/exit/risk/rollback fields). Per Step 6 self-check.
