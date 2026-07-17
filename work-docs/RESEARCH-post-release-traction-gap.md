---
type: research
task_slug: post-release-traction-gap
status: complete
created: 2026-05-22
tags: [harness-maker, research, oss-launch, discovery, marketing, github-traffic]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://github.com/Ecro/harness-maker
  - https://pypi.org/pypi/harness-maker/json
  - https://pypistats.org/api/packages/harness-maker/recent
  - https://github.com/anthropics/claude-plugins-official
  - https://github.com/ccplugins/awesome-claude-code-plugins
  - https://github.com/jmanhype/awesome-claude-code
  - https://github.com/ComposioHQ/awesome-claude-plugins
  - https://github.com/GiladShoham/awesome-claude-plugins
  - https://github.com/jqueryscript/awesome-claude-code
  - https://github.com/hekmon8/awesome-claude-code-plugins
  - https://github.com/Chat2AnyLLM/awesome-claude-plugins
  - https://claudemarketplaces.com/
  - https://www.aitmpl.com/plugins/
related_docs:
  - "[[PLAN-oss-readiness-audit]]"
  - "[[RESEARCH-oss-readiness-audit]]"
  - "[[REVIEW-oss-readiness-audit-2026-05-19]]"
  - "[[wiki:oss-launch-readiness-three-layer]]"
  - "[[wiki:readme-one-prompt-bash-not-slash]]"
summary: "Releases shipped but Phase 3 (announce + aggregator submission) never executed — discovery channels are unactivated."
---

## 🎯 Recommended Direction

**Releasing is not announcing.** The mechanical release pipeline (tag → PyPI → 3 plugin manifests) has fired 11 times since 2026-05-18, but the **Phase 3 "Discovery + announcement" layer** from `PLAN-oss-readiness-audit` was never executed: no aggregator listing, no Show HN, no Twitter/Reddit thread, no blog post. GitHub Traffic referrers show **only `github.com` (self) and `test.pypi.org` (bot)** — there is no external traffic source at all. That is the single binding constraint; everything else (README polish, release cadence concerns) is secondary until at least one external channel is activated.

Informational recommendation for `/hm:plan`: **execute Phase 3 of the existing OSS readiness plan**, starting with the lowest-effort highest-leverage move (submit to `anthropics/claude-plugins-official` + 2-3 community awesome-lists), then a 1-week soak, then a single low-key Show HN. Do not chase additional product polish first — Phase 1 (trust floor) and Phase 2 (positioning surface) are already 100% on GitHub's community health score.

## 🔍 Refinement Decisions

- Phase 0 interview: skipped (`--deep` not set; user gave a concrete, scoped question).
- Discovery lens (Phase 0.75): **User-workflow / product opportunity** + **Technical architecture** (lightly). The question is "why isn't anyone arriving?" — that's a discovery/funnel problem, not an implementation problem.

## 🛠️ Approaches Found

### Approach A — Aggregator submission sprint (lowest effort, broadest coverage)

| Field | Content |
|-------|---------|
| Approach | Submit `harness-maker` to the 7+ awesome-lists + 2 marketplace directories that already exist |
| Assumption | These lists are actively curated and accept PRs; their search/index traffic is non-zero |
| Evidence | `anthropics/claude-plugins-official` is Anthropic-managed (gold standard inclusion); `claudemarketplaces.com` claims daily auto-crawl from GitHub; `ccplugins/awesome-claude-code-plugins`, `jmanhype/awesome-claude-code`, `ComposioHQ/awesome-claude-plugins`, `GiladShoham/awesome-claude-plugins`, `jqueryscript/awesome-claude-code`, `hekmon8/awesome-claude-code-plugins`, `Chat2AnyLLM/awesome-claude-plugins` all surfaced on web search for "awesome-claude-code plugins 2026" |
| Trade-off | Each list has its own PR template + acceptance criteria; can take 1-2 weeks; some lists are dormant |
| Compatibility | Our topics (`claude-code-marketplace`, `claude-code-plugin`) already align with what these aggregators index |
| Risk | low — even rejection is free signal |

### Approach B — Single coordinated launch post (medium effort, concentrated burst)

| Field | Content |
|-------|---------|
| Approach | One launch post (Show HN OR r/ClaudeAI OR /r/cursor + an X/Twitter thread) timed against a "v1.0 ready" tag |
| Assumption | We have a clear hero demo that converts a curious reader into a `claude plugin install` action in <2 minutes |
| Evidence | Existing README hero is a 30-line prompt block (lines 35-65). Memory `[wiki:readme-one-prompt-bash-not-slash]` notes that copy-paste flow is the headline feature, but the wall-of-text precedes the "Why harness-maker?" section |
| Trade-off | One-shot: if the launch lands flat (low upvote count, harsh HN top comment), the post is permanently associated with the project |
| Compatibility | Requires version-freeze discipline — 9 releases in 3 days (0.15.1 → 0.20.2) reads "unstable" to launch-day skimmers |
| Risk | medium — the community has high "another Claude Code wrapper" fatigue; positioning has to be sharp |

### Approach C — Content-led seeding (highest effort, longest tail)

| Field | Content |
|-------|---------|
| Approach | Write 2-3 anchor blog posts on what's actually novel (10-dim interview, grade-gated review, three-target single-source) and let them rank on search before any direct announcement |
| Assumption | The novel mechanics are demonstrable in standalone posts that don't require installing the tool first |
| Evidence | dev.to / Medium / personal blog posts about "Claude Code harness engineering" are dominant in search results for "Claude Code harness 2026" — content is how the category was claimed by the existing 82k-star "Everything Claude Code" guide |
| Trade-off | Slow — weeks-to-months before search ranking. Requires written-content cadence we have not built |
| Compatibility | Each post becomes long-term referrer flow even if Approach A/B fail |
| Risk | medium — writing time is the bottleneck, not code |

## ⚠️ Pitfalls

1. **Naming collision is structural.** Web search for "harness-maker" Claude Code returns 0 references to our project — the dominant brands occupying the "Claude Code harness" mind-space are `Chachamaru127/claude-code-harness`, `revfactory/harness`, `raphaelchristi/harness-evolver`, and the 82k-star "Everything Claude Code" guide. We share a generic noun with both an existing ecosystem AND with industrial wire-harness manufacturing. Any launch post needs to lead with **what we do differently** in the first sentence, not the name.
2. **Release-as-announcement category error.** Tag-push pipelines (5-file version sync → PyPI → 3 plugin manifests) make the artifact retrievable. They do not put it in front of anyone. The 1,424 monthly PyPI downloads + 258 unique cloners in 4 days are almost entirely automated traffic (test.pypi.org bot, CI runners, package mirrors) — not human discovery. (Source: GitHub Traffic referrers show only `github.com` self-referrals and `test.pypi.org`.)
3. **Release-cadence signal damage.** 11 GitHub releases in 4 days (0.15.1 through 0.20.2, including a re-tag of 0.19.3) optically reads as instability to a skimmer who lands on the Releases tab from a Show HN link. The cadence is honest (autoloop iterations + ruff/idna fixes), but the reader has no context. A "soak window" of 5-7 days with no releases before any announcement is cheap insurance.
4. **README hero buries the value prop.** Lines 35-65 are a 30-line Bash-prompt code block; the actual "Why" section starts at line 68. First-time visitors on small screens may scroll past or bounce. The one-prompt install is a competitive moat — but the elevator pitch must precede it.
5. **Phase ordering is being skipped.** `PLAN-oss-readiness-audit` Phase 3 explicitly sequences `marketplace submissions → 1-week soak → low-key Show HN`. Several plans have been written; none of those three tasks have been executed (no entries in `gh release list` correspond to "after soak", no PRs to aggregator repos visible from our git history).

## ❓ Open Questions

These belong in `/hm:plan` (deep interview) before commitment:

1. **Soak vs ship?** Freeze releases for 5-7 days before announcement, or accept the "moves fast" signal? (Recommendation: soak — release pressure feels self-imposed.)
2. **First channel?** Aggregator-list PRs (Approach A) only, or aggregator + one launch post (A+B)? Single Show HN attempt vs sequenced multi-channel?
3. **Submission target priority.** `anthropics/claude-plugins-official` is the gold standard but acceptance criteria are unknown. Should we submit there first (high reward, high rejection risk) or to the community awesome-lists first (lower bar, faster validation)?
4. **Naming defense.** Do we double down on "harness-maker" with stronger SEO (anchor blog posts, GitHub topic curation) or pivot the marketing tagline to lead with a more distinctive phrase like "per-project AI coding harness" / "10-dim interview"?
5. **README hero restructure.** Move the 30-line install prompt below the "Why" section, or keep the current order? (Currently the install prompt IS the differentiator — but visitors who don't yet trust the project won't paste it.)
6. **Metrics threshold for go/no-go.** What does "traction" mean concretely — N stars in M days, N PyPI human downloads (filtered), N GitHub referrer sources outside `github.com`? Without a target, any answer to "is it working" is post-hoc.

## 📚 Sources

### GitHub state (data we collected today)

- Repo created `2026-05-03`, public, MIT, 14 topics, Discussions enabled, community health 100%.
- Stars: 2 · Watchers: 0 · Forks: 0 · External issues/PRs: 0 (all 7 PRs are Dependabot, all closed).
- Traffic (last 14 days): **105 views / 13 unique** (peak 2026-05-17: 38/12); **616 clones / 258 unique** (concentrated 2026-05-17 → 2026-05-20 — almost certainly bot/mirror activity).
- **Referrers (last 14 days): `github.com` (67 / 2 unique) and `test.pypi.org` (10 / 1) — zero external referrers.**
- Releases: 11 tags between 2026-05-18 and 2026-05-21 (0.15.1, 0.15.2, 0.15.3, 0.17.0, 0.18.0, 0.19.0, 0.19.1, 0.19.3, 0.20.0, 0.20.1, 0.20.2).
- Events past page: 152 PushEvent, 14 ReleaseEvent, 17 IssueCommentEvent, **2 WatchEvent** (matches star count), 1 DiscussionEvent (the welcome thread we created).
- PyPI: latest `0.20.2`. Downloads — day `304`, week `1,424`, month `1,424`. (Combined with the bot-heavy clone pattern, these are likely dominated by package mirrors + CI bots, though they're not separable from upstream counters.)

### Aggregator landscape (where we are not)

- [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) — Anthropic-managed directory (gold standard inclusion).
- [ccplugins/awesome-claude-code-plugins](https://github.com/ccplugins/awesome-claude-code-plugins) — community plugin awesome-list.
- [jmanhype/awesome-claude-code](https://github.com/jmanhype/awesome-claude-code) — plugins + MCP + editor integrations.
- [ComposioHQ/awesome-claude-plugins](https://github.com/ComposioHQ/awesome-claude-plugins) — Composio-curated plugins index.
- [GiladShoham/awesome-claude-plugins](https://github.com/GiladShoham/awesome-claude-plugins) — Claude Plugin Marketplace spec-aligned list.
- [jqueryscript/awesome-claude-code](https://github.com/jqueryscript/awesome-claude-code) — broad resources index.
- [hekmon8/awesome-claude-code-plugins](https://github.com/hekmon8/awesome-claude-code-plugins) — plugin-focused.
- [Chat2AnyLLM/awesome-claude-plugins](https://github.com/Chat2AnyLLM/awesome-claude-plugins) — marketplaces + plugins curated list.
- [claudemarketplaces.com](https://claudemarketplaces.com/) — daily auto-crawled directory of skills/plugins/MCP (we should verify whether we already appear in their index).
- [aitmpl.com/plugins](https://www.aitmpl.com/plugins/) — plugins + marketplace collections.

### Adjacent / competing brand-space (search for "Claude Code harness")

- `Chachamaru127/claude-code-harness` — "dedicated development harness, autonomous plan→work→review cycle" (similar tagline).
- `revfactory/harness` — "meta-skill that designs domain-specific agent teams".
- `raphaelchristi/harness-evolver` — "iteratively optimizes system prompts, routing, retrieval, and orchestration code".
- "Everything Claude Code" — Medium guide, 82k stars (referenced category-defining brand).

### Web search verification

- `"harness-maker"` + `Claude Code plugin Ecro` query — **zero results pointing to our project**; results dominated by adjacent brands above.
- `harness-maker site:news.ycombinator.com OR site:reddit.com OR site:twitter.com OR site:x.com` — **no links found**.

## 🔗 Related Internal Docs

- [[PLAN-oss-readiness-audit]] — the 11-phase three-layer plan whose Phase 3 (Discovery + announcement) was never executed.
- [[RESEARCH-oss-readiness-audit]] — original 20-item OSS launch-readiness checklist.
- [[REVIEW-oss-readiness-audit-2026-05-19]] — review snapshot when Phases 1+2 landed.
- [[wiki:oss-launch-readiness-three-layer]] — three-layer framing (trust floor → positioning → discovery+announce) that diagnoses today's gap precisely.
- [[wiki:readme-one-prompt-bash-not-slash]] — README "one-prompt install" rationale (the hero block on lines 35-65 that may need re-positioning).
- [[wiki:fresh-install-health-baseline]] — fresh-install zero-P0 work from 0.17.0 (relevant because aggregator-driven visitors will fresh-install; the bar there is good).

---

## Research saved → RESEARCH-post-release-traction-gap.md

**Topic:** Why no traction after recent releases — investigate via GitHub
**Recommended:** Phase 3 of `PLAN-oss-readiness-audit` (aggregator submissions + soak + one launch post) — never executed; binding bottleneck is zero external referrers, not product polish
**Sources fetched:** 13 web URLs + 1 PyPI metadata + 6 GitHub API endpoints + 6 internal docs
**Open questions for plan:** 6
