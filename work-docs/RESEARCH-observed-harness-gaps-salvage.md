---
type: research
task_slug: observed-harness-gaps-salvage
status: complete
created: 2026-09-19
tags: [harness-maker, research, python, memory-retrieval, escalation, telemetry, salvage]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[RESEARCH-observed-harness-gaps]]", "[[PLAN-observed-harness-gaps]]", "[[SPEC-observed-harness-gaps]]", "[[PLAN-memory-retrieve-lexical-recall]]", "[[PLAN-failure-memory-recurrence-dedup]]"]
summary: "Port the vetted observed-harness-gaps work onto main; move the backlog warning out of the delegate"
---

# RESEARCH — Salvage of the abandoned `hm/observed-harness-gaps` task

## 🎯 Recommended Direction

**Port the old task's Python and tests nearly verbatim, re-apply its five small template edits
against current main, and change one design point: the backlog warning must move out of wrapup
Step 5.3. That step now runs inside `stage-delegate`, so a line printed there never reaches the
user.**

On 2026-08-14 the old task wrote RESEARCH, SPEC and PLAN, including a MAJOR_REVISION pass by
codex and two plan-validator passes. Execute finished all five phases. The task never reached
review or land: its PLAN says `executed`, its 37 files are uncommitted, and the branch is now
103 commits behind main. It was abandoned, not refuted. Re-checked on 2026-09-19, **every
defect it targeted is still present on main**, and two have grown worse:

| # | Defect | Main today | Salvage cost |
|---|---|---|---|
| 1 | `pending-proposals.md` has no reader; wrapup never warns | **27 open** (was 16), oldest 2026-05-17. No `proposals` module and no `hm` verb. | `proposals.py` is new, so no conflict. Run against main's backlog it parses cleanly (**27 open / 6 triaged / 1 other heading**), so the parse rule still fits the file. |
| 2 | `memory_retrieve` ignores `count` | **Unchanged file** (0 commits since base `6a5378e4`). Live repro: the topic "repair round broke something new while the suite stayed green" → `(no entries matched)`, although `fix-introduced-defect-passes-all-gates` (count:13) is its paraphrase. This stage's own warm-tier call returned **2** candidates, both weak. | The old diff should apply as-is. |
| 3 | `/hm:execute` loads slugs, not bodies | `execute.md.j2:58` is identical ("first 60 lines; `rg -F "[fail:"`"). | Re-apply 22 template lines. The file has 8 new commits, and the anchor line is unchanged. |
| 4a | `wall_time_ms` required but documented as omit-able | `review_telemetry.py:99` `Field(ge=0)`. **This session's own review emit hit it** and a guessed `600000` went into the ledger. | The schema is a one-line change. `review.md.j2` doc text moved to `:1187`, so re-anchor the edit. |
| 4b | plan `--barrier-index '<segment>'` has no integer note | `plan.md.j2:680/684` unchanged in substance. `execute.md.j2:379` has the note. Plan still runs pass 2 (`:590`), so the old "`1` on pass 1, `2` on pass 2" text is still correct. | 4 lines. |

### What changed on main that the port must absorb

1. **Wrapup delegation (the design change).** Since `86556c6a` (2026-07-26), wrapup Steps
   1–5.6 run in `stage-delegate`, and the main loop keeps Steps 6+. The old PLAN placed the
   warning in Step 5.3 (inside the delegate). The delegate's prose is not relayed.
   `WrapupReceipt` has no warnings field; its fields are slugs, counts, `documents_updated`
   and `steps_skipped`. So the old design fires, prints, and is never seen. That is the same
   write-only failure the task exists to fix, one level up. **Inference:** the old
   integration test (`test_wrapup_backlog_degrade.py`) exercised the CLI's degrade branches,
   not visibility to the user, which is why this was not caught.
2. **Surface ratchets moved.** `surface_baseline.json`, `_ATOMIC_RATCHET`, the round-trip
   table, the snapshots and `test_render_wrapup_delegation.py` line pins have all been
   re-based many times since. The old versions of these files are unusable. Re-derive them
   through a BASELINE-DELTA doc, with the `_current_delta_doc()` hand-off that landed in
   `374a5125`.
3. **Rendered-harness pin.** Dogfood `/hm:` commands run the released 0.57.1 cache. A new
   `hm proposals` verb fails there until the next release. The old wrapup text already
   degrades loudly on "not found". That behaviour must survive the relocation.

## 🔍 Refinement Decisions

`--deep` not set.

**Discovery lens:** Technical architecture / implementation. Every claim is checked against
this repo's source and its abandoned worktree. User-workflow lens (secondary): the "user" of
this loop is the maintainer running `/hm:wrapup` and `/hm:execute`. Their artifacts are
`failures.md` (159 `[fail:*]` entries), `pending-proposals.md` (27 open), and the review
telemetry JSONL. No external sources: the question is "does vetted work still fit this repo",
and only the repo can answer it.

**Local capability × User artifact:**

| Artifact the maintainer maintains | Capability | Loop closed today? | After salvage |
|---|---|---|---|
| `failures.md` (`count:N`) | wrapup count++; `memory_retrieve` lexical rank | write ✅ / read ⚠️ lexical-only | read ✅ (count floor) |
| `pending-proposals.md` | wrapup Step 5.3 write | write ✅ / read ❌ | read ✅ **only if the warning reaches the main loop** |
| execute warm tier | head-skim + slug `rg` | bodies ❌ | bodies ✅ |
| `review-*.jsonl` | `review_telemetry emit` | first emit rejected without a measured value | ✅ |

## 🛠️ Approaches Found

### Approach A — Faithful port + relocate the warning (recommended)

| Field | Content |
|---|---|
| Approach | Copy `proposals.py` and the 10 new test files. Apply the `memory_retrieve.py` and `review_telemetry.py` diffs. Re-apply the execute/plan/review template edits at their current anchors. Put the backlog check in the **main-loop** part of wrapup (one `hm proposals count --open` call after receipt reconciliation, printed with the end-of-stage summary) instead of Step 5.3. Re-derive every baseline from scratch. |
| Assumption | The old ADR-001..005 still hold. Nothing in the 103 commits touched their premises (`memory_retrieve.py` and `stage_agent_ledger.py` are unchanged; the backlog format still parses). |
| Evidence | Parser run on main: 27/6/1. `git log 6a5378e4..main -- memory_retrieve.py` is empty. Old execute notes measured the floor at +3121 B (+35.8%) and admitted count:13/11/7 entries that the lexical pass missed. |
| Trade-off | The relocated warning is a new, un-validated design point. It costs one more main-loop CLI call, which the delegation work exists to minimise (tiny: a bare integer). |
| Compatibility | Additive CLI verb (`command_registry` + `hm._DISPATCHABLE`). Optional schema field (`None` = not measured, same rule as the verifier counters). Floor ON by default (ADR-003, absent-case rule). |
| Risk | **medium**: the large surface ratchet churn is the main hazard, not the logic. |

### Approach B — A + fix the default byte-cap starvation

| Field | Content |
|---|---|
| Approach | Also make the lexical section's default cap large enough to deliver `k`. This is the old task's own filed-but-never-landed proposal ("default retrieval byte-cap discards 90% of the pre-filtered set"). |
| Assumption | A count floor is worth little if the lexical path delivers fewer than `k` entries anyway. |
| Evidence | Measured today, topic `worktree review telemetry failure memory proposal`, `--k 6 --pre-k 30`: **byte-cap 10240 → 3 entries**, 40960 → 9, 200000 → 30. Every stage asks for 6 and gets 3. |
| Trade-off | Every stage that retrieves memory grows its per-call context (up to ~2–3× at a k-sized cap). That is the carry cost CLAUDE.md "Context discipline" measures. `test_memory_retrieve.py:348-360` pins `<= 10240`. |
| Compatibility | Additive (default change only). But it changes all five stages' warm-tier output at once, so it makes the salvage harder to review. |
| Risk | **medium**: a budget decision, not a logic one. It needs its own number. |

### Approach C — Contracts only (4a/4b + execute), defer the memory loop

| Field | Content |
|---|---|
| Approach | Ship only the telemetry schema, the barrier-index note and the execute warm-tier switch. |
| Assumption | The small fixes are enough, and the loop can wait. |
| Evidence | 4a has bitten real runs twice (2026-08-14, 2026-09-18). |
| Trade-off | Leaves the 27-proposal backlog unread and the count:13–15 failures unreachable. The execute switch also delivers less without the floor. |
| Risk | **low** |

## ⚠️ Pitfalls

- **A warning printed by a subagent is write-only.** This is the concrete flaw in the old
  design (see above). Any user-visible signal from wrapup must be emitted by the main loop or
  carried in the receipt. Test the *placement*, not only the CLI branch.
- **Permanent warnings train blindness.** With 27 open and a threshold of 5, the warning
  fires on every wrapup until someone triages. Whether it stays useful depends on the backlog
  actually shrinking, which this task does not do. Triage itself is separate work.
- **Aggregate-size gates, not only text pins.** The old execute notes record missing the
  surface budget, the round-trip table and the comprehension golden on the first pass ("third
  instance of scoped the search narrower than the claim"). This session's own task repeated
  it with `_ATOMIC_RATCHET`. Enumerate the ratchets up front.
- **Byte-pin collision with a same-release peer.** Use the `_current_delta_doc()` hand-off
  (`[fail:*] byte-pin-needs-current-delta-hand-off`). A peer landing mid-task means rebase and
  re-derive (`peer-lands-mid-task-shared-files`).
- **Head-truncating a failure body inverts it.** Keep ADR-002's tail-biased excerpt. The
  count:13 entry's head is guidance its own later block marks SUPERSEDED.
- **Do not copy the old worktree's `pending-proposals.md` edit blindly.** It appends the
  byte-cap proposal, which the old task measured. Re-measure (done above: still 3/30) and
  record it only if Approach B is not taken.
- **The old worktree is another session's state.** Read and copy only. Never edit, reset or
  delete it without the user's confirmation (project rule).

## ❓ Open Questions

1. **Where does the backlog warning surface?** Options: (a) a main-loop CLI call after Step
   0.5 reconciliation, printed in the stage summary; (b) a new `WrapupReceipt` field
   (`open_proposals: int | None`) that the delegate fills and the main loop prints; (c) both.
   (a) is the simplest. (b) keeps one owner but adds a receipt field that reconciliation
   cannot verify.
2. **Include the byte-cap fix (Approach B) now, or keep it a filed proposal?**
3. **Threshold 5 vs a 27-entry backlog:** keep the fixed 5, or also show the oldest age so
   the line carries new information each time?
4. **Old worktree disposal:** after this task lands, remove `.worktrees/observed-harness-gaps`
   and branch `hm/observed-harness-gaps`? This requires explicit user confirmation, and its
   work would then live only in this task.

## 📚 Sources

No external sources. Adjudicated against main `555ca933` and the abandoned worktree
(base `6a5378e4`, uncommitted state as of 2026-09-19):

- `src/harness_maker/memory_retrieve.py` (unchanged since base); old diff adds `floor_candidates`, `_excerpt_recent_blocks`, the two-section `render_candidates_block`
- `src/harness_maker/review_telemetry.py:99`; `templates/stages/review.md.j2:1185-1196`
- `templates/stages/execute.md.j2:58, 379`; `templates/stages/plan.md.j2:590, 680, 684`
- `templates/stages/wrapup.md.j2:485-489` (Step 5.3); `src/harness_maker/wrapup_receipt.py:59-91` (`WrapupReceipt` fields); `86556c6a` (delegation, 2026-07-26)
- `.worktrees/observed-harness-gaps/src/harness_maker/proposals.py` (159 lines), 10 new test files, `work-docs/PLAN-observed-harness-gaps.md` (ADR-001..005, execution notes :505-545, validation :616+)
- `.claude/memory/pending-proposals.md` (29 `## ` headings: 27 proposals, 1 RESOLVED batch, 1 backlog note)
- `.claude/memory/failures.md` (159 `[fail:*]`; top counts 15/14/13/12/11)
- `tests/unit/test_memory_retrieve.py:348-360` (`<= 10240` pins)

## 🔗 Related Internal Docs

- [[RESEARCH-observed-harness-gaps]] / [[SPEC-observed-harness-gaps]] / [[PLAN-observed-harness-gaps]]: the salvage source (in `.worktrees/observed-harness-gaps/`). Scenarios S1–S7 and ADR-001..005 carry over, apart from the S2 placement.
- [[PLAN-memory-retrieve-lexical-recall]]: ADR-001 (no embeddings) binds the floor; it is deterministic and lexical-free.
- [[PLAN-failure-memory-recurrence-dedup]]: the `count:N` machinery the floor weights; its `_HEADING_RE` / `previous_count` gap is adjacent and stays out of scope.
- [[PLAN-assumption-entry-and-evidence-locator]]: source of the `_current_delta_doc()` hand-off this task's baselines must use.
