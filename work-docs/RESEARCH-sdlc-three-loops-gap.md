---
type: research
task_slug: sdlc-three-loops-gap
status: complete
created: 2026-09-27
tags: [harness-maker, research, python, intent-layer, knowledge, mission-loop, sdlc]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[PLAN-world-intent-closed-loop-trial]]", "[[SPEC-intent-feedback-continuity]]", "[[SPEC-intent-world-model-objective-layer]]"]
summary: "Feedback half-right: Mission loop exists and runs; real gaps are unmeasured metrics, unused human-fact channel, no re-run"
---

# RESEARCH — Is "Change strong, Mission/Knowledge empty or weak" accurate?

## 🎯 Recommended Direction

**TL;DR:** The feedback's *direction* (Change loop is the most mature; Mission and Knowledge
are less mature) holds, but both of its *specific diagnoses* are wrong for this repo, and the
Change loop has an open gap at its own human checkpoint.

- "Mission loop: intent layer is empty" — **false here.** 4 intents exist, one was closed
  `missed`, 5 of 8 metrics carry measured values, purpose/vision are filled. The lifecycle the
  feedback draws (Charter → approve → measure → close met/missed/no_data) is the shipped
  `hm intent` verb set, one-to-one. It is empty only in a freshly rendered consumer project
  (`write_skeleton_if_absent` → `not_filled_in`), which is by design.
- "Knowledge loop: 7 scattered stores" — **the count is about right, the diagnosis is not.**
  The stores have assigned roles (the intent-layer "Authoritative record map", project-knowledge
  routing wiki vs auto-memory, Second Brain as a promotion pipeline). The measurable weaknesses
  are different: the human-confirmed fact channel is almost unused (1 `[wiki:fact]` of 276
  wiki entries), there is no "re-run the same task" step that proves a recorded gap changed
  behaviour, and two stores both hold "claims with falsification" (wiki `Supersedes:` vs
  intent questions `confirmed|wrong`).
- The lead/DRI split in the feedback's table conflicts with the project charter (single senior
  developer; team-collaboration features deliberately not built). `approved_by` is an
  unverified git string by design.

Main impact: internal maintainer value (what to invest in next), not user-facing. The binding
trade-off for any follow-up is the project's first goal — add nothing that costs more workflow
than the quality it protects. That argues for *measuring and pruning* the existing Mission and
Knowledge machinery, not building a new layer.

## 🔍 Refinement Decisions

Discovery lens: Technical architecture / implementation (what is shipped and wired) +
User-workflow (what is actually used, from on-disk records of this repo as the dogfood user).
No external search: the question is about this codebase's own state, and internal evidence is
authoritative.

## 🛠️ Approaches Found

### Evidence table — claim by claim

| Feedback claim | Verdict | Evidence |
|---|---|---|
| Change loop is very strong | Mostly true, with an open gap | 7 atomic stages, consensus review, verify gate, SPEC content-hash approval. But the human "can I explain it?" checkpoint is the active intent `UNDERSTANDING-HANDOFF`; `understanding_handoff_rate` = never measured. `post_merge_churn` 16.9 vs target 12 (above). Open question `q_825d374c6331ed22`: fan-out and plan-validator value unproven. |
| Mission loop: intent layer empty | False (this repo); true only in fresh consumer renders | `intent/`: LOOP-OPT-IN (active), SOURCE-PLAN-STEPS (closed, `observed: missed`), UNDERSTANDING-HANDOFF (active), WORLD-INTENT-CLOSED-LOOP (active). `hm intent status --json` → `state: ok`. Verbs: `new / approve / activate / close --observed met\|missed\|no_data`. `cli.py:584` writes an empty skeleton for new projects. |
| Mission loop weak | Partly true — in measurement, not structure | 3 of 8 metrics `never_measured` (`intent_world_closed_loop_cycles`, `wiki_fact_entries_28d`, `understanding_handoff_rate`); 3 above target (`post_merge_churn`, `unsourced_step_share` 45.2/20, `dead_rendered_bytes` 19.8/10). CFR/churn need a manual weekly `/hm:metrics`. Closed-loop trial: collecting, 0/3 enrolled. |
| Lead approves / DRI proposes | Out of charter | CLAUDE.md §제1목표: target is one senior developer; no team-collaboration features. intent-layer skill: distinct `owners` roles only raise an advisory; real separation needs CODEOWNERS + branch protection. |
| Knowledge: 7 scattered stores | Count ≈ right, "scattered" wrong | Census below — 9 live locations, each with an assigned role; plus ~515 lines of dead tier code. |
| Knowledge loop: gap → world model → re-run | Re-run step missing; human "what is a Fact" step nearly unused | 276 wiki entries, 154 failure entries, but 1 `[wiki:fact]` (2026-09-19). Failures with count ≥ 3 do flow to `pending-proposals.md` and were shipped as mechanical guards with mutation receipts (2026-08-07) — the closest thing to "re-run", and it works. No template step re-runs a task after a knowledge update. |

### Knowledge store census (this repo, 2026-09-27)

| # | Store | Role (who writes) | Size / state |
|---|---|---|---|
| 1 | `.claude/memory/wiki.md` | domain + dev knowledge (agent at wrapup; DRI via project-knowledge for `fact`) | 276 entries, 447 KB; 1 `fact` |
| 2 | `.claude/memory/failures.md` | recurring failure patterns with counts (agent) | 154 entries, 362 KB |
| 3 | `.claude/memory/pending-proposals.md` | count ≥ 3 failures → harness change proposals | 602 lines |
| 4 | `.claude/memory/session/` | session logs (`flush_session` hook) | 69 files |
| 5 | `.claude/intent.yaml` questions | claims with `open\|confirmed\|wrong` + observe/contradicts (human-consented) | 8 open, 2 confirmed |
| 6 | Obsidian Second Brain | cross-project promotion target of 1–2 | enabled, filesystem backend |
| 7 | Host auto-memory (`~/.claude/projects/.../memory/`) | personal preferences — host-owned, not harness | 33 files |
| 8 | `CLAUDE.md`, `docs/reference/` | human-curated rules | — |
| 9 | `work-docs/` RESEARCH/SPEC/PLAN/REVIEW | task-scoped decisions | — |
| dead | `src/harness_maker/memory/{semantic,episodic,profile,retrieval}.py` | JSONL 3-layer tier; only `_locking` is imported by live code; `MemoryRetriever` used only by its own test | ~515 lines |

The roles are distinct; the real overlap is between #1 (`fact` + `Supersedes:` line) and #5
(`confirmed|wrong` + `contradicts`) — two places that both answer "what is true and what was
refuted".

### Candidate directions (informational — `plan` decides)

| Approach | Assumption | Evidence | Trade-off | Compatibility | Risk |
|---|---|---|---|---|---|
| A. Measure and prune (no new layer) | The machinery exists; what's missing is evidence of its effect | 3 never-measured metrics; dead tier code; 1 fact entry | Some metrics need new collectors (handoff rate, closed-loop cycles) | Uses existing `hm intent metric record` and trial | low |
| B. Merge the two claim stores | "Fact" and "question" are one concept at two maturity levels | wiki `fact` (1 entry) vs intent questions (10) with overlapping falsification semantics | Migration + reader updates (count:3 "new field must update every reader" class) | Touches memory_retrieve, intent, project-knowledge skill | medium |
| C. Build the feedback's model (two-person Mission loop, 5 shared artifacts, re-run step) | The product targets small teams | Contradicted by charter; no team user on record | Large surface; conflicts with first goal | Low | high |

### Correction (2026-09-27, found at /hm:spec Step 1)

Two claims above read mid-window values as verdicts:

- `wiki_fact_entries_28d` has a **pre-registered window** (v0.58.0 2026-09-19 .. 2026-10-17;
  `scripts/measure_wiki_fact_window.py` exits 3 "window open, 21 days left") and a
  pre-registered decision (≥5 → S1, 0 → remove project-knowledge, 1–4 → keep S0). "1 fact of
  276 = channel unused" is a mid-window count and must not be treated as the outcome.
- `understanding_handoff_rate` is defined as a batch user judgment over the 10 wrapups after
  UNDERSTANDING-HANDOFF ships; `intent_world_closed_loop_cycles` is the active trial (0/3).
  All three `never_measured` metrics are unmeasured **by design** (open windows), not neglect.

Net effect: the "Mission loop is weak in measurement" finding shrinks to the three above-target
metrics, and the Knowledge-loop "human fact channel unused" finding is deferred to 2026-10-17.
What survives unconditionally: no "re-run" step, the fact/question overlap, and the dead
`memory/` JSONL tier.

## ⚠️ Pitfalls

- **Reading "empty" from a fresh render.** A newly made harness always shows `not_filled_in`;
  judging the Mission loop from that misses the populated dogfood state.
- **Counting stores as the problem.** Store count is a proxy; the failure mode that matters is
  a claim recorded in one store and refuted in another with no link. Measure that, not the count.
- **Hand-computing ledger metrics.** CLAUDE.md records a 30x error from hand-counting the
  second-opinion ledger without the exclusion list; any new Mission metric must ship its reader.
- **Treating the closed-loop trial as done.** `WORLD-INTENT-CLOSED-LOOP` is active with 0/3
  tasks enrolled; implementation checks cannot close it as met (intent-layer skill).
- **Assuming wiki volume = knowledge quality.** 800+ KB of agent-written memory is retrieved
  top-6 by lexical prefilter + rerank; whether it changes behaviour is unmeasured.

## ❓ Open Questions

1. Which reading of the feedback is intended — this repo's state, or the default state of a
   consumer project? The verdict on "Mission is empty" flips between them.
2. Is a two-person (lead + DRI) mode in scope at all? The charter says no; the feedback's table
   assumes yes. This is a WHY/WHAT decision for the owner.
3. Should `[wiki:fact]` and intent questions be merged, or should their boundary be written
   down (e.g. fact = settled, question = under test)?
4. What counts as the Knowledge loop's "re-run": the existing failure → proposal → guard path,
   or a new check that replays a task after a knowledge write?
5. Delete the dead `memory/` JSONL tier, or keep it for a planned use? (No live caller found.)

## 📚 Sources

Internal only (no external sources needed for a self-state question):
- `hm intent status --json` output, 2026-09-27
- `intent/*.md` frontmatter; `.claude/intent.yaml`; `.claude/intent/metrics.yaml`
- `.claude/memory/wiki.md`, `failures.md`, `pending-proposals.md`, `session/`
- `src/harness_maker/cli.py:584` (intent skeleton), `src/harness_maker/world.py`,
  `src/harness_maker/memory/`, `src/harness_maker/memory_retrieve.py`
- `.claude/skills/intent-layer/SKILL.md` + `references/workflow-feedback.md`;
  `.claude/skills/project-knowledge/SKILL.md`
- `CLAUDE.md` §제1목표, §Second Brain 승급 파이프라인

## 🔗 Related Internal Docs

- [[PLAN-world-intent-closed-loop-trial]] — active trial, 0/3 enrolled
- [[SPEC-intent-feedback-continuity]]
- [[SPEC-intent-world-model-objective-layer]]
- `[wiki:fact] mission-context-loop-outcome` (2026-09-19)
- `intent/UNDERSTANDING-HANDOFF.md`, `intent/WORLD-INTENT-CLOSED-LOOP.md`
