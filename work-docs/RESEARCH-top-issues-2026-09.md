---
type: research
task_slug: top-issues-2026-09
status: complete
created: 2026-09-30
tags: [harness-maker, research, python, review-loop, verification, context-carry, observability]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
  - https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
related_docs:
  - "[[RESEARCH-token-economy-step-pruning]]"
  - "[[RESEARCH-context-carry-economics-2026-07-28]]"
  - "[[PLAN-economics-attribution-and-carry]]"
  - "[[PLAN-token-efficiency-autopilot-ux-speed]]"
  - "[[RESEARCH-harness-diet]]"
summary: "Make review fix-attribution, verify pass-markers and context size measured by code, not prose"
---

# RESEARCH — top 3 problems in harness-maker (2026-09-30)

## 🎯 Recommended Direction

**TL;DR:** the three largest problems share one shape: a load-bearing quantity is decided
by prose, so nothing measures or enforces it. (1) The review loop's premise, "fixes
introduce defects", has never been recorded as data. (2) The verification pass-marker is
self-attested. (3) Context size is linted on the wrong dimension. Fix each by moving that
one quantity into code, and make each fix a small, deterministic slice.

Rationale. Over the last three weeks, 16 real tasks averaged about two review rounds plus
two confirmation passes. Of the 66 confirmation passes, 39 were dirty (59%;
`.claude/observability/stage-agents.jsonl`). About 9 of the 16 tasks still needed fix commits
after they landed. The top recurring failure classes (`fix-introduced-defect-passes-all-gates`
at count:17, `assertion-invariant-over-named-dimension` at count:22) are not bugs in one
module; they are this "decided in prose" pattern. The impact is mostly **internal/maintainer**:
fewer review rounds, fewer red-main incidents, less context carried per turn. Every consumer
harness renders the same review/verify/wrapup stages, so all three fixes also reach users.

### The three problems, ranked

| # | Problem | Evidence (measured this session) | Proposed slice |
|---|---|---|---|
| 1 | **The review loop does not converge, and its root cause is unmeasurable.** | Confirmation pass FAIL 39/66 (59%). `caused_by` is `None` on **all 621 findings** in 69 persisted payloads (`.claude/observability/review-payloads/**`). The cause is structural: `persist-payload` (review.md.j2 ~L459) runs **before** the auto-fix step that "determines `caused_by`" (review.md.j2 L810), and attribution lives only in REVIEW markdown. The confirm-pass prose itself says "fixes introduce defects at close to 1:1", a claim no data supports or refutes. | Compute `caused_by` deterministically from the existing churn refs (`refs/hm-churn/v1/<slug>-r{N}-pre..post`): a new round-N finding whose file:line falls inside round N-1's fix hunks gets `caused_by=fix-r{N-1}`. Stamp it before persistence. Add a report verb for the fix-introduced rate. |
| 2 | **Green locally, red on main; the pass-marker is self-attested.** | Confirmed intent question `verification_marker_is_not_evidence`: on 2026-09-20 a fresh marker skipped the suite and landed an uncollectable test on main. Today's contract (verify.md Check 2, wrapup.md ~L227-263) is `check`, then the **LLM** runs the commands, then the **LLM** calls `mark-pass`. The marker records a claim, not a run. Related churn: 5 "missed by wrapups" cleanup commits and 6 baseline re-freeze commits since 09-08. | A `verification_cache run` verb. It checks freshness, runs the CI-derived commands itself (from `verification_plan`, `shell=False`, with a timeout) and writes the marker **only** when every one exits 0. Templates call that one verb instead of three steps. `mark-pass` stays only for the degraded (no-CI) fallback. |
| 3 | **Context carry is linted on the wrong dimension.** | This repo's `CLAUDE.md` is 429 lines, under the 500-line Production limit, but it is 65,108 bytes (about 18k tokens), paid on every turn of every session and subagent. `context_lint` counts **lines only** (`context_lint.py:66`), and 150-char Korean paragraph lines defeat that. Anthropic guidance: keep an always-loaded body under ~5k tokens and move detail into referenced files read on demand. Carry dominates spend: mean context is 321k tokens in unattributed turns and 617k in `hm:verify`. There were 37 compactions on 2026-09-22 (session notes). | Add a **character budget** to `context_lint` next to the line budget, applied to CLAUDE.md. Then apply progressive disclosure to this repo's CLAUDE.md: move subsystem ADR narratives (second-opinion, multi-session worktree, loop-marker, per-session markers, step sensitivity, second-brain) into `docs/reference/*.md` and leave a short summary and a pointer in their place. Content is moved, not deleted. |

## 🔍 Refinement Decisions

- Discovery lenses: **technical architecture/implementation** (primary) and
  **user-workflow/product opportunity** (the solo senior DRI's workflow: review rounds,
  red-main incidents, compactions). Research/benchmark was used only for the progressive
  disclosure guidance. Risk/security was not needed.
- The user instructed mid-stage: "절대 멈추지 말고, 너의 추천안대로 wrapup 까지 끝까지 진행해"
  ("don't stop; carry my recommendation through wrapup") and "나에게 묻지말고 진행해" ("don't ask
  me, proceed"). The recommended slices are therefore the direction for spec/execute; each
  open question below has a default that will be applied rather than asked.
- Intent linkage: none of the three maps to an active intent (UNDERSTANDING-HANDOFF or
  WORLD-INTENT-CLOSED-LOOP). All three serve the purpose clause "measure quickly; remove what
  doesn't earn its keep". No intent write is made.
- Trial `world-intent-closed-loop-trial`: status action is `collect_missing_evidence`, and its
  named source is a removed worktree (`.worktrees/intent-feedback-continuity`). That needs an
  explicit user source-review decision. The decision is **pending**; nothing was recorded and
  independent work continues.

### Local capability × user artifact

| User artifact (DRI already maintains) | Harness capability that should read it | Gap today |
|---|---|---|
| `refs/hm-churn/v1/*` fix-delta refs (115 refs) | review auto-fix attribution | pinned, but never joined to findings |
| `.claude/observability/review-payloads/**` (69 files) | replay/verifier corpus | `caused_by` always null |
| `.github/workflows/ci.yml` | `verification_plan commands` | derived correctly; execution plus marker left to prose |
| `CLAUDE.md` (hand-written, always loaded) | `context_lint` | lines only; bytes unbounded |
| `.claude/memory/failures.md` counts | problem ranking | used here as a primary ranking signal |

## 🛠️ Approaches Found

### Problem 1: review convergence

| Field | A. Deterministic attribution first (recommended) | B. Fix-delta micro-review after every fix round | C. Shrink confirm pass to fix delta only |
|---|---|---|---|
| Assumption | We don't know whether dirty confirm passes come from fixes or from round-1 recall misses | Fixes are the main defect source | Same as B |
| Evidence | caused_by null ×621; the confirm pass also "runs lenses that never ran earlier", so part of its yield is not regression by design (review.md C3 prose) | failures.md count:17: "caught only by a focused pass over the fix delta" | none measured |
| Trade-off | No immediate round reduction; unlocks the right B/C choice | Adds a dispatch per round (cost up) | Loses the whole-space sweep that catches round-1 misses |
| Compatibility | Uses existing churn refs and payload schema (`caused_by` key already present) | New step in a 88k-char command | Changes a mandatory-lens contract (`lens_coverage`) |
| Risk | low | medium | high |

### Problem 2: verification evidence

| Field | A. `verification_cache run` owns run + marker (recommended) | B. Record the run's exit codes in the marker, keep LLM mark | C. Drop the cache entirely |
|---|---|---|---|
| Assumption | The marker must be produced by the process that ran the checks | The LLM will pass true exit codes | Cache savings are not worth the risk |
| Evidence | 2026-09-20 incident; the confirmed intent question | Same self-attestation class | The cache saves one suite run on the verify→wrapup handoff (ADR-007) |
| Trade-off | One long Bash call (suite ~2-7 min; Bash cap 10 min) | Still self-attested | Every wrapup re-runs the full suite |
| Risk | low-medium (timeout budget) | high (does not fix the class) | low risk, high time cost |

### Problem 3: context carry

| Field | A. Char budget in lint plus CLAUDE.md progressive disclosure (recommended) | B. Split stage commands (review 88k) into on-demand references | C. Nothing (prior research says stage prose is not the cost) |
|---|---|---|---|
| Assumption | Always-loaded bytes are carried on every turn, in every subagent | Rarely-run branches dominate stage size | [[RESEARCH-token-economy-step-pruning]]: "cut carried context per turn, not stage prose" |
| Evidence | 65KB CLAUDE.md; lint counts lines | review.md 88,249 chars vs ~5k-token guidance | That finding supports A (CLAUDE.md is per-turn carry) |
| Trade-off | Rules moved to references are read only on demand | Large template refactor; high regression surface (render snapshots, structural tests) | — |
| Risk | low (content preserved, pointers kept) | high | — |

## ⚠️ Pitfalls

- **Absent-case black hole** (global Learned Corrections 2026-06-08): `caused_by` shows the
  pattern exactly: the key exists, is never filled, and nobody notices. The new attribution must
  handle "no churn refs" (round 1, `auto_fix` off, pre-existing runs) explicitly as
  `caused_by: "unknown"`, never `None`.
- **Vacuous gate** (`assertion-invariant-over-named-dimension`, count:22): each new test must
  fail when its owning code is removed. For example, the char-budget lint test must fail if the
  char check is deleted, not only if the line check is.
- **Rendered harness pins the released plugin** (memory: `project_rendered_harness_pins_released_plugin`):
  templates that call a new verb (`verification_cache run`) fail in dogfood until the next release.
  Keep a documented fallback until then.
- **Snapshot/baseline churn** (count:14 and count:6): template edits move render snapshots
  and `tests/structural/surface_baseline.json`. Regenerate them inside the task worktree, then run the
  structural suite before land.
- **Timeouts**: `verification_cache run` inherits CI's `pytest -n auto`. Enforce a per-command
  timeout and treat a timeout as not-passed, never as passed.

## ❓ Open Questions (defaults applied under the user's "don't ask" instruction)

1. Attribution granularity: round-level (`fix-r{N-1}`) or per-fix-number?
   **Default: round-level.** The churn refs are per round, and per-fix mapping needs the prose fix log.
2. Should confirm-pass findings be attributed against the cumulative delta (r1-pre..last post)?
   **Default: yes, when the refs exist; otherwise `unknown`.**
3. `verification_cache run` when `verification_plan` is degraded (exit 1)?
   **Default: exit 3 with "degraded" on stderr.** The template then falls back to the existing
   prose path, including `mark-pass`.
4. CLAUDE.md char budget value? **Default: Production 40,000 chars, Side 16,000 chars (warn-only,
   like the line lint).** This repo's CLAUDE.md is trimmed below 40,000 chars by relocation.
5. Unexplained: why the 2026-09-20 marker was fresh after a source+test change. That is not in
   scope; slice 2 removes the self-attestation path, not the fingerprint logic.

## 📚 Sources

- Anthropic, *Skill authoring best practices*:
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices (keep the always-loaded body
  small; move detail into referenced files read on demand)
- Anthropic, *Agent Skills overview*: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Internal measurements (this session): `hm economics stages`, `.claude/observability/stage-agents.jsonl`,
  `review-payloads/**` caused_by tally, `tests/structural/surface_baseline.json` history, `gh run list`.

## 🔗 Related Internal Docs

- [[RESEARCH-token-economy-step-pruning]]: per-turn carry is the cost lever.
- [[RESEARCH-context-carry-economics-2026-07-28]]: main loop 87.9% of spend at 70% carry.
- [[PLAN-economics-attribution-and-carry]], [[PLAN-token-efficiency-autopilot-ux-speed]]: prior carry and attribution work.
- `.claude/memory/failures.md`: `fix-introduced-defect-passes-all-gates` (count:17),
  `assertion-invariant-over-named-dimension` (count:22), `green-module-dead-prose-wiring` (count:7).
- Intent question `verification_marker_is_not_evidence` (confirmed, 2026-09-20).

### Runner-up problems (not selected)

- Dual worktree models: `worktree.py` has 6,324 LOC, and the legacy stash/finalize model now serves only the
  opt-in `/hm:loop`. It is a large simplification candidate, but the risk is high and the render saving is small (~3.5–7k chars).
- Tests grew +45.7k LOC against +9.8k src LOC since 2026-08-30 (4.6×). Suite time is 7–9 min in CI.
- The intent/world/trial layer grew by about +5k LOC in a month, and both of its active intents are still unmeasured.
- 14 stale `.claude/.hm-autopilot-*` markers, because GC is own-key only by design (ADR-013).
