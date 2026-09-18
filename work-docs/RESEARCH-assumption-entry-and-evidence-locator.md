---
type: research
task_slug: assumption-entry-and-evidence-locator
status: complete
created: 2026-09-18
tags: [harness-maker, research, python, intent-layer, world-model, assumptions, staleness]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://github.com/fiberplane/drift
  - https://fiberplane.com/blog/drift-documentation-linter/
  - https://swimm.io/blog/how-does-swimm-s-auto-sync-feature-work
  - https://github.com/pallaprolus/drift
  - https://zylos.ai/research/2026-08-21-documentation-contract-drift-detection-agent-systems/
related_docs:
  - "[[SPEC-intent-world-model-objective-layer]]"
  - "[[RESEARCH-intent-world-model-objective-layer]]"
  - "[[REVIEW-playbook-alignment-2026-09-16]]"
  - "[[REVIEW-outcome-measure-2026-09-17]]"
  - "[[wiki:architecture] two-roots-versioned-state-vs-operational-events]"
  - "[[wiki:gotcha] one-rendered-command-size-has-four-normative-sites]"
summary: "Add `assume add` + content-fingerprint locator (not @sha); fold the ask into 5.7's existing question"
---

# RESEARCH — Assumption entry point + evidence locator

## 🎯 Recommended Direction

**Ship `hm world assume add` and an optional content-fingerprint `locator` on evidence. Do not use
the `path:line@sha` form as proposed. Fold the new ask into wrapup 5.7's existing assumption
question as an extra option, not a fourth question.**

Rationale. The assumption layer can only be *updated* today (`observe`, `resolve`), never *entered*
(`world.py` `_parser`: `assume` has exactly two subparsers). The dogfood repo has no
`.claude/world/assumptions.yaml` at all. Any `depends_on` and every `revisit_when: {assumption, status}`
therefore has nothing to reference, so this is a structural dead end, not a lack of demand.

A locator makes a recorded claim checkable against the code it cites. The proposed `@sha` form is
broken by this harness's own workflow, for three reasons:
- wrapup 5.7 runs **before** the commit (Step 6), so `HEAD` does not contain the text being cited;
- `task-land` squashes and deletes `hm/<slug>`, so a task-branch SHA becomes unreachable;
- line numbers drift.

The prior art that works, fiberplane/drift, stores a **content fingerprint and no VCS state**. That
is deterministic, LLM-free, git-free, worktree-neutral, and also refuses a citation of a path or
snippet that does not exist when it is recorded.

**Main impact: internal maintainer value first, user-facing second.** Downstream consumers get a
knowledge record that says when its evidence moved. This repo's own motivating incidents are mostly
**not** caught by a code locator (see Pitfall 1). That limitation must be written into the SPEC, not
discovered in review.

## 🔍 Refinement Decisions

- **Discovery lens:** Technical architecture / implementation (primary: `world.py`, wrapup 5.7,
  SPEC Non-Goals); User-workflow (secondary: where this repo's stale knowledge actually lived, which
  was `CLAUDE.md` / `wiki.md` corrections); Prior art (doc-drift tools). No `--deep` interview;
  scope was set in-session (items 1 + 2 of the World-Model comparison).
- **Correction to the in-session framing:** the chat claimed the empty assumption layer "would trip
  the withdrawal criterion". It does not, at least not directly. The criterion (SPEC line 272) is
  *no objective with `observed:` and no `candidate` revisit after 10 wrapups*. Assumptions reach it
  only through `revisit_when: {assumption, status}`, which cannot fire while no assumption exists.
  The layer is unreachable, not "about to be withdrawn".

## 🛠️ Approaches Found

### Part 1 — entry point

| Field | 1a. `assume add` verb + extra option on 5.7's existing question | 1b. New 4th answer-gated question in 5.7 | 1c. Hand-edit `assumptions.yaml` (status quo) |
|---|---|---|---|
| Assumption | The operator knows at wrapup whether the task produced a new belief | Same | The operator opens YAML voluntarily |
| Evidence | Zero assumptions after the 3 intent-layer tasks that ran with 5.7 live (playbook-alignment, objective-gap-proposal, outcome-measure) | Same | Same data point: that has produced zero |
| Trade-off | One more option label plus one command line inside the existing `@hm:answer-gated:assumption` block | Adds another `AskUserQuestion` and moves four normative size sites (`_ATOMIC_RATCHET`, `surface_baseline.json`, `_CLAUDE_ROUND_TRIPS`, wrapup line pin) by more | None, but it does not work |
| Compatibility | The SPEC's marker contract (question → `If the answer is "yes":` → `Otherwise: write nothing`) is preserved; the option list gains "new" | New marker block `@hm:answer-gated:assumption-add` | — |
| Risk | low | low–medium (surface growth, question fatigue at wrapup) | — |

`add` field set, derived from the existing record validator (`_ASSUMPTION_KEYS`):
- `id` (`[a-z0-9_]+`, must not exist; refuse, never upsert);
- `claim` (non-empty);
- `status ∈ {known, assumed, unknown}` (`conflict` refused; it is only reachable via `contradicts`);
- optional first evidence entry (`text`, `observed_at`, `relation: confirms`, optional `locator`).

The verb must hold the same `_rmw_lock` as `record_value`. `observe` and `resolve` currently
read-modify-write `assumptions.yaml` **without** a lock, and adding a third writer makes that gap
more likely to bite. The lock path is hardcoded to `.hm-world-outcomes.lock`; it can be reused
(one lock for `.claude/world/`) or renamed.

### Part 2 — locator

| Field | 2a. `path:line@sha` + `git diff` (as proposed) | 2b. Content fingerprint of a line range (recommended) | 2c. Symbol anchor (`path#Name`, AST hash) | 2d. Whole-file hash |
|---|---|---|---|---|
| Assumption | The cited text exists in a reachable commit | The cited text exists in the working tree at record time | The claim is about one named declaration | Any change to the file matters |
| Evidence | **Contradicted by the workflow:** 5.7 precedes Step 6's commit; `task-land` deletes `hm/<slug>` | fiberplane/drift: "staleness detection doesn't depend on VCS history" (XxHash3 of normalized content) | drift uses tree-sitter AST fingerprints for 6 languages, and raw content otherwise | — |
| Trade-off | Needs `git` at read time, reachability checks and hunk-to-range mapping | Must search for the snippet when lines drift; store `lines` only as a hint | Python-only via stdlib `ast`; `.j2`/`.md`/`.yaml` (most of this repo's claims) fall back anyway | False positives on hot files (`world.py` 1,635 lines, `worktree.py` ~5k) |
| Compatibility | Breaks the "status is a free read path" property (git shell-out per locator) | Pure file read at the **current checkout root**, the same root as the rest of `.claude/world/` | Adds a parser dependency for one language | Trivial |
| Risk | **high** (records stale-on-arrival SHAs) | low | medium (scope creep) | medium (noise → ignored signal) |

2b shape (inference, to be locked in plan):
- `locator: {path, lines: [a, b], fingerprint}`.
- `fingerprint` = sha256 of the whitespace-normalized text of those lines, computed by the verb,
  never typed by the operator.
- **At record time:** a missing path or an out-of-range line span is refused. This is what catches
  the "cited path does not exist" class (see Pitfall 1).
- **At read time,** with the result derived and never stored:
  - `fresh` if the span at `lines` hashes equal;
  - `moved` if the normalized snippet occurs elsewhere in the file (treated as fresh, with the new
    line reported);
  - `changed` if it occurs nowhere;
  - `missing` if the path is gone.
- `hm world status` gains `stale_evidence: {<assumption_id>: <state>}` for `changed` and `missing`.
  Assumption `status` is never mutated: the SPEC forbids automatic supersession.

### Part 3 — the approach the motivating evidence actually supports (not in scope; surfaced)

**3. Probe-backed assumption** (`check: {cmd, select}`, reusing `run_measure`'s runner, invoked by
an explicit `hm world assume check`, answer-gated recording). Staleness of claims about **external**
systems (Claude Code, Codex, `agy` flags) cannot show up in any repo diff. Only re-asking the system
catches it. Risk: medium, because it runs commands and duplicates the `measure:` design space.
Recorded here because Pitfall 1 shows it covers incidents that 2b does not.

## ⚠️ Pitfalls

1. **The motivating incidents are mostly not code-drift.** Check each against its source:

   | Incident | Where | What kind | Would 2b catch it? |
   |---|---|---|---|
   | "Claude Code reads `.claude/hooks/hooks.json`" | CLAUDE.md:98 | External system behaviour, false when written | No (external; needed a controlled experiment) |
   | Antigravity "no CLI-level enforcement", copied 6× | CLAUDE.md:46 area | External CLI flags | No for 2b; yes for approach 3 (`agy --help` probe) |
   | Ledger hand-computation 30× misread | CLAUDE.md ledger section | Wrong procedure, not a stale claim | No |
   | Permission frontmatter "enforced" | CLAUDE.md:211 | External docs | No |
   | `reviewers.enabled` as a lens lever | CLAUDE.md:248 | Internal code (`lens_dispatch` ignores it), false when written | Only at record time, and only if the claim was cited to `lens_dispatch`'s body |
   | Recovery doc path `templates/commands/hm/wrapup.md.j2` | CLAUDE.md:339 | Internal path that never existed | **Yes, at record time** (path refused) |

   Most of these were false *when written*. A locator detects **change after recording**, and
   external truth does not live in the repo. The honest value of 2b is twofold: record-time
   validation of cited code, and drift detection for internal claims. The plan should either state
   this plainly or weigh approach 3.

2. **Pre-commit recording (the `@sha` trap).** The execute stage never commits
   (`hm:execute` "Stages, never commits"), so at 5.7 time `HEAD` is the base commit the task
   branched from. A `line@HEAD` citation points at text the task has just rewritten, and
   `git diff HEAD -- path` reports "changed" immediately. Any VCS-anchored design must record after
   Step 6, but 5.7 is the only operator touchpoint. Content fingerprints avoid the problem entirely.

3. **Squash-land reachability.** `task-land` squashes `hm/<slug>` into one commit on main and
   deletes the branch (CLAUDE.md "Per-task feature-branch model"). Task-branch SHAs become
   unreachable and are gc-collectable. drift stores no SHA for the same reason.

4. **Root choice.** `.claude/world/` is versioned state read at the **current checkout root**
   (`[wiki:architecture] two-roots-versioned-state-vs-operational-events`). Inside a task worktree,
   locators resolve against the task's modified files. That is desirable: it is exactly the signal
   5.7 needs ("this task rewrote code an assumption cites"). Resolving at base instead would hide it
   until after land.

5. **Noise kills the signal.** Whole-file hashing (2d) on hot files flags constantly, and an
   always-red list gets ignored. Line-span plus relocation search keeps false positives down to
   actual edits of the cited text.

6. **Surface ratchets.** Any wrapup prose change moves four independently frozen numbers
   (`[wiki:gotcha] one-rendered-command-size-has-four-normative-sites`), and
   `surface_allowance` expires at wrapup (`project_surface_allowance_expires_at_wrapup`). Folding
   the ask into the existing question minimizes the delta. The plan still needs a
   `BASELINE-DELTA-*.md` plus an allowance, and a terminal retire phase.

7. **Unlocked writers.** `observe` and `resolve` have no RMW lock today, and a 5.7 write can run
   concurrently with a hand edit or a peer session. Adding `add` without locking all three repeats
   the review-40a36af2 finding that introduced `_rmw_lock` for outcomes.

8. **Tooling precedent is AST-heavy for a reason.** drift normalizes to an AST to ignore formatting.
   Whitespace-only normalization flags a `ruff format` reflow as `changed`. That is acceptable for
   v1 (it is rare on cited spans, and the result is visible), but it is a known false-positive source.

## ❓ Open Questions

1. **Scope of Part 3.** Should the probe-backed check (approach 3) join this task, given Pitfall 1?
   Or should the SPEC state that external claims are out of scope and 2b covers internal ones only?
2. **Which evidence entry is authoritative for staleness?** Candidates: every locator-bearing entry
   evaluated independently (any `changed` → stale), or only the most recent one (a re-`confirms`
   with a fresh locator clears the older one). The second gives a natural "re-stamp" path via the
   existing `observe` verb.
3. **Does evidence staleness propagate?** Should it set `needs_revalidation` on objectives that
   `depends_on` the assumption? Today that is derived only from `conflict` (SPEC line 249). Extending
   it changes a SPEC-defined derivation; leaving it out means status reports a stale assumption
   while its dependent objective reads clean.
4. **5.7 trigger.** Should `stale_evidence` drive the existing question, listing stale ids first,
   or stay a `status`-only report? Driving it is the payoff of Pitfall 4, at a few extra prose lines.
5. **Record-time span entry.** Should `--locator path:a-b` be CLI syntax, with the verb reading the
   span and computing the fingerprint? The alternative is a snippet the LLM pastes, which the verb
   then locates. The first is deterministic; the second tolerates imprecise line numbers but lets the
   LLM paraphrase.
6. **Lock naming.** Should the world directory keep reusing `.hm-world-outcomes.lock` for
   `assumptions.yaml`, or rename it to a directory-wide lock? A rename touches the gitignore and churn
   prefix set.

## 📚 Sources

- fiberplane/drift — anchors markdown to code via content fingerprints in `drift.lock`, no stored
  SHAs; `drift link` restamps: https://github.com/fiberplane/drift
- Fiberplane blog, "We built a linter for documentation rot":
  https://fiberplane.com/blog/drift-documentation-linter/
- Swimm Auto-sync — diff-driven snippet tracking; unresolvable changes become a human "reselect"
  task: https://swimm.io/blog/how-does-swimm-s-auto-sync-feature-work
- pallaprolus/drift — doc block ↔ code anchor pairing, AST-based:
  https://github.com/pallaprolus/drift
- Zylos Research, documentation-contract drift in agent systems (2026-08-21):
  https://zylos.ai/research/2026-08-21-documentation-contract-drift-detection-agent-systems/
- Internal: `src/harness_maker/world.py` (`_parser`, `observe`, `resolve`, `derive`,
  `_status_payload`, `_rmw_lock`); `templates/stages/wrapup.md.j2` §5.7 (lines 569–592);
  `specs/SPEC-intent-world-model-objective-layer.md` lines 206–229 (Non-Goals), 249 (derived
  state), 272 (withdrawal); `CLAUDE.md` lines 46, 98, 211, 248, 339.

## 🔗 Related Internal Docs

- [[SPEC-intent-world-model-objective-layer]] — assumption record contract, Non-Goals
  ("automatic supersession", "fact identity beyond a human-chosen id"), derived-state rules
- [[RESEARCH-intent-world-model-objective-layer]] — the tri-state was identified as "the genuinely
  novel bit"; codex's merged design required provenance + timestamp + refutation on every fact
- [[REVIEW-playbook-alignment-2026-09-16]] — open: `new_objective` without `O_EXCL`, no CLI test of
  `changed:` lines (both apply to `assume add`)
- [[REVIEW-outcome-measure-2026-09-17]] — `_rmw_lock` origin, `run_measure` runner (approach 3 reuse)
- `[wiki:architecture] two-roots-versioned-state-vs-operational-events`
- `[wiki:gotcha] one-rendered-command-size-has-four-normative-sites`
- `[fail:design] blocker-diagnosis-unretested-goes-stale` — a recorded diagnosis carried forward
  unchecked; the failure mode approach 3 targets
