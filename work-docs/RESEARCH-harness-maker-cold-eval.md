---
type: research
task_slug: harness-maker-cold-eval
status: complete
created: 2026-05-22
tags: [harness-maker, evaluation, oss, positioning, sustainability]
mtime_warn_days: 14
libs_fetched: []
sources:
  - https://github.com/Ecro/harness-maker
  - https://github.com/github/spec-kit
  - https://github.com/bmad-code-org/BMAD-METHOD
  - https://github.com/ruvnet/claude-flow
  - https://github.com/SuperClaude-Org/SuperClaude_Framework
  - https://github.com/eyaltoledano/claude-task-master
  - https://github.com/buildermethods/agent-os
  - https://github.com/All-Hands-AI/OpenHands
  - https://github.com/cline/cline
  - https://github.com/Aider-AI/aider
related_docs:
  - "[[RESEARCH-oss-readiness-audit]]"
  - "[[wiki:positioning:per-project-personalization-hero-differentiator]]"
  - "[[wiki:pattern:oss-launch-readiness-three-layer]]"
summary: "Personalization locked as headline (2026-05-22). Wedge reality-check on 5 repos: profile is Python-strong, Rust/Node-half-built. Staged wedge plan: v0.21 showcase, v0.22 profile hardening, v0.23 uvx wedge."
---

# RESEARCH — Cold evaluation of harness-maker vs OSS landscape

## 🎯 Recommended Direction

**Maintainer lock-in (2026-05-22): Approach A — `personalized harness` is the headline.** This is the only axis where harness-maker can hold a moat — every other harness chose *not* to build profiler + interview + render. Carbon-copying that takes a competitor months, not days; carbon-copying "reviewer permission separation" or "spec-driven workflow" takes a competitor a weekend.

The lock-in solves the "A vs B" question. It does **not** solve the cold-eval problem this document raised — *personalization is invisible in the first 30 seconds.* Locking the headline creates an immediate second decision: **how do we make the headline verifiable without an install commitment?** That question is the new critical path for `/hm:plan`.

Three immediate consequences of the lock-in:

1. **30-second wedge required**: `harness-maker profile .` (or equivalent) must become the artifact a stranger sees *before* deciding to install. Without it, the headline is a promise; with it, the headline is a demonstration. Approach C in this document is no longer an alternative to A — it is the *proof tool* for A.
2. **Surface area must be cut along a single axis**: keep features that are *evidence* of personalization (profiler depth, interview gating, foreign-config absorption, block-merge for hand-edits, Side vs Production divergence). De-prioritize features that exist for the maintainer's intellectual model but do not visibly demonstrate personalization (anti-rot crawl, 5-term inequality gate, communication-variants markers, /hm:health 3-layer rubric). They can stay in the codebase; they should leave the README hero.
3. **One-sentence answer to spec-kit becomes possible**: *"spec-kit is a spec format. harness-maker reads YOUR repo and builds YOUR harness."* This sentence only works under Approach A. Drill it into README hero + GitHub About + social card.

The code quality (20.3k LOC Python, 174 tests, ruff format + mypy strict, atomic-write everywhere, content_hash provenance) is markedly above the median for this category. With the headline locked, the next 30 days of work is alignment, not engineering: surface ↔ headline, README ↔ proof, roadmap ↔ moat.

## 🔍 Refinement Decisions

- `--deep` not set; Phase 0/0.5 skipped.
- **Discovery lenses (Phase 0.75)**: User-workflow / product opportunity (primary — does anyone outside the maintainer's head need this?), Technical architecture (secondary — is the engineering scoped to the value), Risk / compliance / security (tertiary — is the solo-maintainer + 0.x cadence sustainable for a security-touching tool). arXiv lens skipped — this is a market-reality question, not a research-frontier question.
- Scope: cold-mirror evaluation. The prior `RESEARCH-oss-readiness-audit.md` covered launch-readiness mechanics. This doc deliberately covers the harder question: *should this exist in its current form, given the alternatives?*

## 🔬 Wedge Reality Check (2026-05-22)

Tested option (a) `uvx harness-maker profile .` on 5 diverse external repos before committing to it as the 30-second wedge. Goal: confirm the profile output is *surprising* — i.e., a non-maintainer would react with "you read my repo, not just guessed."

**Method**: `git clone --depth 1` of 5 repos covering Python lib, Python framework, Rust CLI, Node framework, single-file JS lib. Ran `uv run harness-maker profile <repo> --json` on each.

| Repo | Stack output | Notable wins | Notable misses |
|---|---|---|---|
| **requests** (Python lib) | `["python","c-cpp"]` | `lifecycle:"maintenance"` accurate; `detected_checks` extracted `make test` from Makefile | False positive `uv run ruff check .` (requests doesn't use uv); `frameworks:[]`; `package_manager:""` |
| **fastapi** (Python framework) | `["python"]` | `scale:"large"`; `frameworks:["pydantic"]` is real dep parsing | `lifecycle:"maintenance"` debatable for an active framework; `starlette` (core dep) missed |
| **ripgrep** (Rust CLI) | `["rust"]` | `package_manager:"cargo"` correct | **`lifecycle:"experiment"`** — BurntSushi's ripgrep is anything but experimental; `detected_checks:[]`; `frameworks:[]` |
| **fastify** (Node framework) | `["node"]` | `frameworks:["fastify"]` (deps parsed) | `package_manager:""` despite package.json present; `detected_checks:[]` |
| **htmx** (single-file JS) | `["node"]` | `stack` + `package_manager:"npm"` correct | `detected_checks:[]`; `frameworks:[]` |

**Reality verdict**: surprise factor ≈ 5/10. **Strong on Python, half-built on Rust/Node.** Specifically:
- `stack` and `ci_provider` detection: solid across all 5 (10/10).
- `detected_checks`: works on Python via Makefile/pyproject extraction, near-empty on Rust/Node.
- `lifecycle`: produces obvious wrongs (ripgrep="experiment"). Algorithm needs revisit — likely git-log heuristic confused by `--depth 1` clones, but the same UX hit applies to fresh clones in user workflows.
- `frameworks`: dep parsing exists (fastapi→pydantic, fastify→fastify) but doesn't cover Rust Cargo deps or full Node deps.
- `package_manager`: empty string when only `pyproject.toml`/`package.json` present without lockfile — needs to fall back to manifest type, not "low confidence empty."

**Implication for the 30-second wedge**: option (a) `uvx harness-maker profile .` is **anti-wedge for Rust/Node users today**. A Rust developer running it on their repo sees `lifecycle:"experiment"`, empty `frameworks`, empty `detected_checks` and concludes the tool doesn't know their stack. The Python-only audience is too narrow to be the headline.

**Revised wedge strategy (calendar-staged):**

| Release | Wedge form | Cost | Why |
|---|---|---|---|
| **v0.21** | Option (b) — README hero shows real Side ↔ Production render diff on a sample repo (controlled showcase) | ~1 day | profile.py untouched; immediate visible headline; controlled output bypasses profile's stack gaps |
| **v0.22** | profile.py Rust/Node hardening: `detected_checks` for cargo + npm, `lifecycle` algorithm fix, `frameworks` Cargo.toml + package.json deps full parse, `package_manager` manifest-fallback | ~1-2 weeks | Closes the reality gap that blocks (a) |
| **v0.23** | Option (a) shipped publicly — `uvx harness-maker profile .` as headline call-to-action | ~2 days copy + docs | Now wedge survives external Rust/Node eyeballs |

Each release stage ships a real wedge of increasing strength. The headline message ("personalized harness — built from yours") stays constant; the *proof artifact* gets stronger each release.

**Open question this reality-check raises (added to §Open Questions #1)**: should v0.21's option-(b) showcase use a *real public repo* (e.g., one of the maintainer's other projects, or a popular target) or a *constructed example*? Real is more credible; constructed is more controllable.

---

## 🛠️ Approaches Found

Three honest framings of what harness-maker actually is. Pick the one you want to defend; the rest of the project should fold under it.

### Approach A — "Per-project harness synthesizer" ✅ LOCKED 2026-05-22

| Field | Content |
|---|---|
| Approach | The harness is shaped by your project. Profiler + interview produce *structurally different* outputs. |
| Assumption | Users care that their Side experiment and Production service get different reviewer sets. They will pay a 5-min interview cost for it. |
| Evidence (for) | Profiler is real: 12+ stack signals, dependency-parsed not keyword-guessed (`src/harness_maker/profile.py`). Interview is real: 10 axes locked in `harness.yaml`. Side vs Production produces objectively different files. |
| Evidence (against) | **Zero external users have verified that this matters.** 2★, 0 forks, 0 watchers after 19 days public. SuperClaude (22.9k★) and BMAD (47.8k★) prove users will accept a *fixed* harness if it's discoverable. The "personalization" feature, by construction, can only be appreciated *after* you've used >1 project — but day-1 users have 1 project. |
| Trade-off | All the engineering complexity (synthesize.py, profile.py, render.py, block-merge, content_hash) exists to serve this differentiator. If users don't value it, 60% of the codebase is overhead. |
| Compatibility | High — codebase is already shaped around this. Pivoting away wastes the work. |
| Risk | **Medium-high.** Differentiator is real but unverified, and invisible until installed. |

### Approach B — "Best-in-class Claude Code reviewer harness" (de-emphasize personalization)

| Field | Content |
|---|---|
| Approach | Reframe as: the harness where reviewer agents have privilege-separated permissions, mechanical-check gating, and consensus + auto-fix loop. Personalization becomes an implementation detail, not the headline. |
| Assumption | The legible differentiator users can verify in 30 seconds is **trust in the review pipeline**, not personalization. Cite the `Bash(python:*)` / `Bash(sh:*)` denials in the security pitch. |
| Evidence (for) | The `permissions.allow/deny` separation in CLAUDE.md §보안 IS unusual — most competitors give reviewers full tool access. Mechanical pre-checks (lint/tests run before LLM tokens) save real money. Grade-gated auto-fix is genuinely shipped. This story is visible in the CONFIG file, not after 5 minutes of interview. |
| Evidence (against) | Story is harder to compress to one sentence. "Reviewer permission separation" doesn't fit on a social card the way "different harness per project" does. |
| Trade-off | Demotes 40% of recent work (interview gating, profiler depth, foreign-config absorption). Forces a narrower identity. |
| Compatibility | Medium — requires honest re-positioning of README, FAQ, and roadmap. |
| Risk | **Low-medium.** Easier to defend with concrete code; harder to romanticize. |

### Approach C — "The profiler is the product" → re-scoped 2026-05-22 to "Profile is the 30-second proof of Approach A"

| Field | Content |
|---|---|
| Approach | Lead with `harness-maker profile .` — a standalone command that takes any repo and outputs a deep, dependency-parsed `ProjectProfile`. Everything else (interview, render, agents, anti-rot, health) is a follow-on. |
| Assumption | The single thing in this codebase that NO competitor has — and that a stranger can verify in literally 10 seconds — is `harness-maker profile .` running on their repo and producing output that surprises them. |
| Evidence (for) | `profile.py` detects 12+ stacks, frameworks, package managers, CI providers, foreign AI configs. Nothing in BMAD / SuperClaude / spec-kit / claude-flow does this. spec-kit assumes you tell it the project type. This is the *only* axis where harness-maker can produce a wow-moment with zero install commitment. |
| Evidence (against) | Reframes the whole project. Most of the code becomes "supporting infrastructure for the profiler." Hard pivot. |
| Trade-off | Honest about which 20% of features create 80% of the value claim. Loses the "harness lifecycle" framing. |
| Compatibility | Low — major repositioning. But the underlying code stays valid; only README + marketing + roadmap shifts. |
| Risk | **Low.** Easiest claim to verify externally. Hardest to defend if the profile output isn't actually that surprising on real repos — verify on 5 random external repos before committing. |

**Maintainer decision 2026-05-22:** Approach A locked. Approach C downgraded from alternative to *proof tool* for A. Approach B held as fallback if 90 days of Approach A produce no measurable adoption lift — the reviewer-trust angle remains a legitimate second story, just not the headline.

**Why A over B/C in maintainer's words**: *"personalized harness 가 핵심. 이것만이 다른 harness 와 차별될 수 있다."* — locks the bet on the axis where competitors chose not to build, where harness-maker's existing code is already shaped, and where the maintainer has the deepest model. Cold-eval verdict on legibility is acknowledged and reframed as "30-second wedge problem" rather than "wrong headline problem."

## ⚠️ Pitfalls (the cold part)

Each pitfall cites concrete evidence from the codebase, git history, or competitor data.

### 1. Adoption gap is not a marketing problem — it's a market-fit signal

| Project | Stars | Age | Daily commits |
|---|---|---|---|
| github/spec-kit | 104,567 | ~7 months public | active |
| OpenHands (formerly OpenDevin) | 74,439 | mature | active |
| cline | 62,158 | mature | active |
| ruvnet/claude-flow | 53,944 | mature | active |
| bmad-code-org/BMAD-METHOD | 47,810 | mature | active |
| Aider-AI/aider | 45,125 | mature | active |
| hesreallyhim/awesome-claude-code | 44,465 | curated index | active |
| eyaltoledano/claude-task-master | 27,206 | mature | active |
| SuperClaude-Org/SuperClaude_Framework | 22,893 | mature | active |
| buildermethods/agent-os | 4,602 | 2024-launched | active |
| **Ecro/harness-maker** | **2** | **19 days** | **9 patches in 16 days** |

(Source: `gh api`, 2026-05-22.)

The honest interpretation: **19 days is not enough to draw conclusions about adoption** — `agent-os` was at low double-digits at day 19 — but the differentiator claim ("per-project personalization") is something other harnesses *chose not to build*. That's a tell. It's either because (a) it's hard and they will copy when it's proven, or (b) users don't actually want a 5-minute interview before they get a working command. Distinguishing (a) from (b) is the central open question.

### 2. Surface area mismatch (code budget vs adoption budget)

- 20,348 LOC Python (`find src -name "*.py" | xargs wc -l`)
- 174 test files
- 26,314 chars CLAUDE.md (`wc -c`)
- 1,666 lines TECH_SPEC.md
- 17 user-facing `/hm:` commands
- 13 agents shipped
- 11 skills shipped
- Triple plugin manifest (Claude Code + Cursor + Codex)

For comparison, claude-task-master ships <5 user commands; SuperClaude ships ~16 personas but with much simpler config. The harness-maker surface is built for a project with 100x more users than it has. The cost: every new feature adds maintenance load that one person carries. Recent commits (`f3a4d11`, `daf605d`, `c5b7fc6`, `7612be2`) are patches fixing patches — a signal that velocity is exceeding stability budget.

**Evidence**: 0.15.x had 4 patches in 24h fixing prior patches (`git log --grep="0.15"`); 0.19.x and 0.20.x show the same pattern.

### 3. Hard-to-verify claims dominate the README hero

The README's headline differentiators require multi-step verification:

| Claim | What a stranger has to do to verify |
|---|---|
| "Structurally different harnesses for Side vs Production" | Install, run interview twice with different presets, diff output trees |
| "Anti-rot crawl across 4 sources" | Wait for weekly hook to fire, inspect `.claude/observability/` |
| "Edit-preserving upgrades via block-merge" | Edit a generated file, run `--update`, diff |
| "5-perspective consensus reviewer with auto-fix loop" | Make a real PR, run `/hm:review`, watch fixes apply |
| "AI-readiness rubric with 3 layers" | Run `/hm:health`, parse output |

Compare to spec-kit's headline: "Build high-quality software faster with Spec-Driven Development" — one sentence, no install required. The harness-maker pitch demands trust before evidence. That works for an existing audience; it does not work for a strange-eyeball on Day 1.

### 4. Triple-IDE strategy splits maintainer attention

CLAUDE.md openly admits Cursor compat has unverified surfaces ("Phase 1 manual verification", "auto-detect 금지", "Cursor 2.4+ hooks-compat docs apply to CLI only, IDE reads the dedicated `.cursor/` location"). Codex was added in 0.9.0+ per memory. The combinatorics: 3 IDEs × 7 atomic stages × 2 presets × N projects = a test matrix that one person cannot keep green. BMAD chose to be multi-IDE *first* and accepts thinner per-IDE depth. spec-kit pushes the spec-format as IDE-neutral. harness-maker is trying to be deep AND wide in the same release window.

**Concrete failure mode**: `tests/cursor-compat/MANUAL_CHECKLIST.md` referenced in CLAUDE.md is a manual checklist. Manual checklists with one person degrade to "tested once at version X, untested since." Memory entry `[wiki:gotcha] worktree-finalize-conflicts-with-parallel-main-edits` (2026-05-19) shows that integration paths between subsystems are already brittle in the maintainer's own workflow.

### 5. The "anti-rot / AI-readiness / communication-variants" features are research-tier, not product-tier

These are intellectually interesting and well-built. But:

- **Anti-rot crawl**: who has run this and found it useful? Memory says "weekly crawl across 4 sources" but `.claude/observability/health/raw-*.jsonl` is local — there's no public evidence of value-add. It's a feature looking for a confirmed use case.
- **5-term inequality gate (PLAN-deep-interview-question-criteria)**: an elegant formalism for filtering interview questions. But users don't read inequalities. They see a question or they don't. The gate is for the maintainer's confidence, not the user's experience.
- **Communication variants (full/reframe/soft)**: rendered as HTML comment markers (`<!-- @hm:communication_variant: X -->`) per memory. This is invisible to users; it exists to debug the prompt designer's models of agent behavior. Worth keeping internal but not worth shipping as a product feature.

The pattern: **the maintainer is writing this project for the maintainer's intellectual satisfaction.** That's not wrong — most great OSS starts that way. But it makes the README/changelog read like a research log, which is not the format that gets stars from working developers shopping for a tool.

### 6. The cold sustainability question

Solo maintainer + 0 forks + 0 watchers + 0 community issues + 9 patches in 16 days + 174 tests to keep green + triple-IDE + Cursor/Codex still being validated + memory directory full of "8-checkpoint" reminders the maintainer writes to themselves. This is not a balanced load. Either (a) adoption arrives in the next 3 months and pulls in contributors who absorb load, or (b) feature velocity will outrun the maintainer and the project shifts into "stale for 6 months" territory. The CLAUDE.md "필수 체크리스트" section is a leading indicator: the maintainer is already encoding tribal knowledge into prompts because there's no team to encode it into.

### 7. spec-kit (GitHub) is the existential competitor on this axis

- 104,567 stars, GitHub corporate backing, multi-IDE (Claude Code, Cursor, Copilot, Gemini, Codex), spec-driven SDLC, neutral position.
- harness-maker's `dev_mode: spec-driven` axis directly overlaps. The "we also do Cursor + Codex" claim is true on both sides.
- The user's roadmap notes `github/spec-kit external e2e fixture vendoring (currently pytest.skip with TODO)` — meaning even harness-maker's own tests acknowledge spec-kit as the reference point.

If a user already adopts spec-kit, the marginal value of harness-maker over spec-kit must be defensible in one sentence. Currently it isn't.

### 8. Python-and-uv requirement is a real cost for non-Python users

CLAUDE.md FAQ acknowledges this: "Q: Why Python? My project is Rust / Node / Go." The answer ("the plugin runs Python, your project doesn't have to") is technically correct but creates a real install-flow friction: a Go developer who clones a Claude Code plugin and is told to install `uv` will read that as "this is a Python project I have to learn." BMAD ships node-based, claude-task-master ships node-based, spec-kit is CLI-binary — all easier for cross-stack adoption.

### 9. The "Day-1 surprise" budget is being spent on the wrong features

A user opening Claude Code, running `/plugin install harness-maker@harness-maker`, then `/reload-plugins`, then `/hm:make` faces:
- A 10-question interview (locale, preset, dev_mode, targets, workflows, reviewers, skills, ref folders, sibling repos, Second Brain, recommended model).
- A render that produces 30+ files in `.claude/`.
- Plus, if Cursor target enabled, `.cursor/` mirror; plus, if Codex enabled, `.codex/` and `AGENTS.md` and `.agents/`.

The first impression is **"this is a lot."** Compare to SuperClaude's install: pip install, one command, done. The user has not yet seen the differentiator (which requires them to use multiple projects), but has already spent the day-1 attention budget.

## ❓ Open Questions

**Resolved by maintainer 2026-05-22:**
- ~~#5 Personalization vs trust as headline~~ → **Personalization (Approach A).**

**Remaining (Plan stage will pick the binding ones, now reframed under the personalization lock-in):**

1. **30-second wedge form** — partially resolved by §Wedge Reality Check above. Staged: v0.21 ships (b) controlled showcase, v0.22 hardens profile Rust/Node, v0.23 ships (a). **Remaining sub-question**: should v0.21's showcase repo be (i) a real public repo of the maintainer, (ii) a popular non-trivial target (fastapi? next.js?), or (iii) a constructed minimal example? Real ↔ controllable tradeoff. Plan stage picks.
2. **Has any external user successfully completed `/hm:make` end-to-end on a real project they didn't write?** Still the single highest-leverage data point. Personalization lock-in does not change this — it raises the urgency. If no user inside 7 days, the headline is unfalsifiable. Run one observed install with a willing tester before next feature ships.
3. **Surface gate: which features earn their README real estate under the personalization headline?** Keep candidates (evidence of personalization): profiler, interview, foreign-config absorption, block-merge for hand-edits, Side vs Production divergence, content_hash provenance. Cut candidates (orthogonal or research-tier): anti-rot crawler, 5-term inequality gate, communication-variants metadata, /hm:health 3-layer rubric, reviewer consensus auto-fix. *Cut* here means "deprioritize from README hero and roadmap headlines" — the code can stay shipped.
4. **Triple-IDE under the personalization lens.** Personalization-as-headline is *stronger* with multi-IDE because "your harness, every IDE you use" doubles the surprise. But Codex is the youngest and least-validated. Realistic v0.21–0.25 stance: Claude Code + Cursor as the headline pair; Codex stays shipped but is not in the hero. Revisit once Cursor manual checklist is green.
5. **The one-sentence answer to spec-kit.** Lock the wording: *"spec-kit is a spec format. harness-maker reads YOUR repo and builds YOUR harness."* Test it on 3 strangers before committing. Variants in en/ko required (the GitHub About sidebar version + the README hero version + the social-card version must all reduce to the same claim).
6. **Adoption metric to instrument.** Stars lags. Better candidates: (a) opt-in telemetry counting unique `/hm:make` completions, (b) PyPI download stats, (c) GitHub Discussions activity. Pick one before launch so the next 90 days produce data, not anecdotes.
7. **Product or research playground — register lock.** The personalization decision pushes this toward product. README hero, CHANGELOG framing, roadmap headlines must all read as product. Research-tier work continues in `work-docs/` and `docs/` but does not leak into user-facing surfaces. This is a discipline decision, not a code decision.

## 📚 Sources

- `gh api repos/Ecro/harness-maker` (2026-05-22): 2 stars, 0 forks, 0 issues, 0 watchers, 19 days public.
- `gh api repos/<competitor>` for spec-kit (104.5k), OpenHands (74.4k), cline (62.1k), claude-flow (53.9k), BMAD-METHOD (47.8k), aider (45.1k), awesome-claude-code (44.5k), claude-task-master (27.2k), SuperClaude (22.9k), agent-os (4.6k).
- harness-maker `git log` (last 20 commits): patch cadence analysis.
- `wc -l` over `src/harness_maker/` (20,348 LOC), `tests/` (174 test files), `CLAUDE.md` (26,314 chars), `TECH_SPEC.md` (1,666 lines).
- `.claude/commands/hm/*.md` (17 user-facing commands), `.claude/agents/*.md` (13 agents), `.claude/skills/*` (11 skills).
- README.md hero, "Why harness-maker?", "How it compares", "Roadmap" sections.
- CLAUDE.md §보안/권한 (permission separation), §필수 체크리스트 (8-checkpoint), §Targets 정책.
- `work-docs/RESEARCH-oss-readiness-audit.md` competitor positioning table.
- https://github.com/github/spec-kit (existential competitor)
- https://github.com/bmad-code-org/BMAD-METHOD (workflow incumbent)
- https://github.com/SuperClaude-Org/SuperClaude_Framework (Claude-only incumbent)
- https://github.com/ruvnet/claude-flow (orchestration incumbent)
- https://github.com/eyaltoledano/claude-task-master (task-based incumbent)

## 🔗 Related Internal Docs

- [[RESEARCH-oss-readiness-audit]] — prior, defensive launch-readiness framing. This doc is the inverse.
- [[wiki:positioning:per-project-personalization-hero-differentiator]] (2026-05-19) — the marketing claim being stress-tested here.
- [[wiki:pattern:oss-launch-readiness-three-layer]] (2026-05-19) — layered launch model; this doc questions whether layers 2-3 should run at all without first re-evaluating the differentiator.
- [[wiki:gotcha:wrapup-marker-discipline-silent-loss]] (2026-05-17) — example of the kind of multi-layer fix the maintainer is carrying solo.
- [[wiki:gotcha:worktree-finalize-conflicts-with-parallel-main-edits]] (2026-05-19) — example that integration paths are already brittle for a single user.
