---
type: plan
task_slug: mission-context-loop
status: complete
created: 2026-09-19
tags: [harness-maker, plan, python, jinja2, memory, knowledge-capture, retrieval]
spec: "[[SPEC-mission-context-loop]]"
research_doc: "[[RESEARCH-mission-context-loop]]"
interview_rounds: 2
adrs: 7
validator_outcome: MAJOR_REVISION
summary: "S0: project-knowledge skill + bounded pointers, fact-safe wrapup 5.1, recall at writer root; 28-day outcome"
spec_need_verdict: add
spec_need_target: mission-context-loop
---

# PLAN — mission-context-loop (World Model S0)

## 🎯 Executive Summary

**TL;DR.** Ship SPEC S0 in six phases:
- a `project-knowledge` skill (both presets, all three hosts). It turns a DRI's explicit
  "remember X" or correction into a `[wiki:fact]` entry via the existing `upsert-wiki` CLI;
- a ≤300-character routing pointer in the six always-loaded templates. The Codex copy names
  the skill file, because Codex starts skills only on mention;
- fact-safe search-before-write in wrapup 5.1. Wrapup never reuses a `[wiki:fact]` slug; the
  skill reuses only fact slugs;
- `fact` + `Supersedes:` in the wiki templates;
- a `/hm:help` row;
- one Python change: `memory_retrieve`'s default memory dir resolves where `memory_md` writes.

The pre-registered 28-day S1/withdrawal criterion becomes a measured outcome in this repo's
`intent.yaml`. It is backed by a tested repo-local script that refuses to measure before the
window closes.

**What / why.** Code-absent DRI knowledge has no capture path. "Remember X" goes to
machine-local host auto-memory. Corrections pile up beside the old truth (9 of 30 sampled wiki
entries superseded). A fact written mid-task is invisible to the worktree reader
([[RESEARCH-mission-context-loop]] §D, [[SPEC-mission-context-loop]]).

**Key decisions.**
- ADR-001: the recall root follows the writer.
- ADR-002: skill plus shared pointer partial, with a Codex path pointer.
- ADR-003: wiki-only storage.
- ADR-004: do not wait for `observed-harness-gaps`.
- ADR-005: the 28-day criterion is a guarded, history-based measurement.
- ADR-006: wrapup/help growth rides a `surface_allowance` declared in P4 and retired in P5.
- ADR-007: slug-reuse rules protect facts from task summaries.

**Impact.**
- Python: one default in `memory_retrieve.main` plus a pure helper, and one repo-local script
  (`scripts/`, not shipped).
- Rendered: a new skill, a new partial, wrapup 5.1, the wiki templates and the help row.
- Zero new state files. Zero changes to path-ownership, dirt-filter or memory-fold code.

## 📚 Prior Work

- [[RESEARCH-mission-context-loop]] §D: the storage inventory, the 30-entry supersession
  sample, and the reader/writer root mismatch.
- `[wiki:convention] a-ledger-reader-must-root-where-the-writer-writes`: the defect class
  ADR-001 closes for memory.
- `[wiki:architecture] two-roots-versioned-state-vs-operational-events`: `intent.yaml` is
  versioned content at the checkout root, so the P5 edit happens in the worktree.
- PLAN-intent-layer-ops / PLAN-outcome-measure ADR-010: the surface procedure. Phase-0 pin →
  allowance in the growth commit → final-phase retirement with delta-doc §3.1, and an own
  invariance test (`tests/structural/test_intent_layer_ops_invariance.py`).
- `[fail:design] surface-allowance-expires-at-wrapup-no-fold` (count 3): P5 retires the
  allowance in-task.
- `[fail:tooling] mutation-gate-timeout-leaves-source-mutated-on-disk`: never kill `mutmut`
  in the worktree; `git diff src/` before commits after a mutation attempt.
- Base memory fold already exists (`worktree.commit_base_memory`, wrapup 7.7 step 4), and
  `.claude/` paths are forgiven by the dirty-base guard. Captures mid-task neither block
  `task-land` nor get lost.
- `context_discipline.md.j2`: precedent for a partial in all `claude-md` variants with a
  per-variant character cap and tokens fixed before the text.
- The `intent-layer` skill precedent covers registration in three constants, the `/hm:help`
  row, the Codex `@mention` note, and the `test_codex_phase7.py` skill count (21 → 22).
- `scripts/measure_workflow_baseline.py`: precedent for a repo-local measurement script.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 0 | Objective | intent | Which objective? / Draft one? | none, LOOP-OPT-IN / yes, no | none; no draft | LOOP-OPT-IN is unrelated loop-surface reduction | — |
| 0 | SPEC need | contract | verdict `add` — author or waive? | author now, waive | author now | SPEC authored + approved; op-check satisfied on re-entry | — |
| 1 | Sibling ordering | phasing | Order vs `observed-harness-gaps`? | proceed, wait, absorb recall | proceed without waiting | Operator asked whether it had landed. Verified NOT landed: no main commit, no `FLOOR_LABEL`, no `proposals.py`; 22 files uncommitted on 0.51.3 since 2026-08-14 | ADR-004 |
| 1 | 28-day anchor | observability | Where does the S1/withdrawal evaluation live? | intent outcome+measure, unknowns line, changelog | intent outcome + measure | Choosing it is consent to edit `intent.yaml` | ADR-005 |
| 2 | Validation bundle | risk | Apply validator C1/C2/C3/C5/C7/C8/C9/C10/C12 as recommended? | A revise all, pick individually | A — revise all | C1 is critical: unbounded reuse destroys facts | ADR-007, ADR-005, ADR-006 |
| 2 | Codex trigger (C4) | architecture | Codex starts skills only on mention | pointer names skill path, mention-only | pointer names skill path | Keeps the three-host promise | ADR-002 |
| 2 | Manual-check contamination (C6) | testing | Manual S1 writes a counted fact | throwaway clone, excluded prefix | throwaway clone | Counted file stays pure; no exclusion rule in the measure | ADR-005 |
| 2 | Help row (C11) | scope | Add `/hm:help` row? | add, don't | add | intent-layer precedent; the only discovery list | ADR-006 |

Defaults taken without a question (stated in the design brief): shared pointer partial and
enabling the skill in both presets (ADR-002); the allowance procedure (ADR-006).

## 📐 Architecture Decision Records

### ADR-001: `memory_retrieve`'s default memory dir resolves to the writer's base root
**Status:** Accepted (2026-09-19, via /hm:spec Round 2 + /hm:plan)
**Context:** `memory_md` writes every tier at `_base_root(root)/.claude/memory`
(`memory_md.py:69-91`). `memory_retrieve` reads `Path(".claude/memory")` relative to cwd
(`memory_retrieve.py:435`). A worktree-cwd stage therefore reads a stale branch copy (SPEC S5).
**Decision:**
- `--memory-dir` defaults to `None`.
- New pure `resolve_memory_dir(explicit: Path | None, cwd: Path) -> Path` returns `explicit`
  unchanged when it is given. Otherwise it returns `memory_md._memory_dir(cwd)`, reusing the
  writer's function.
- `main()` calls it.
**Consequences:**
- ✅ Captures are recallable from any worktree immediately (AC-001), and the rooting rule has
  one source.
- ⚠️ `memory_retrieve` gains an import of `memory_md` (light first-party imports:
  `command_registry`, `io_utils`, `memory._locking`; no cycle — `command_registry` names
  `memory_retrieve` only as a string).
- ⚠️ Worktree-cwd stages now read base memory. This is intended, since `memory_md` never
  writes branch copies.
**Rejected alternatives:**
- A second copy of `_base_root` in `memory_retrieve`: drift.
- Passing `--memory-dir` at every rendered call site: prose has no execution surface.
**Source:** SPEC Round 2.

### ADR-002: capture contract = new `project-knowledge` skill + one shared pointer partial
**Status:** Accepted (2026-09-19, via /hm:spec Round 1, /hm:plan default + interview #2 C4)
**Context:** A skill costs no always-loaded bytes but may not trigger. When it does not, Claude
Code's default routes "remember" to host auto-memory. On Codex, skills start only on an
explicit `@mention` (`templates/skills/intent-layer/SKILL.md.j2:10`).
**Decision:**
- Add `templates/skills/project-knowledge/SKILL.md.j2`.
- Register it in `synthesize._ALL_SKILLS`, `interview._ALL_SKILLS` (which feeds
  `_PROD_ENABLED_SKILLS`, `interview.py:161`) and `interview._SIDE_ENABLED_SKILLS`.
- Add `templates/agents/_partials/project_knowledge_pointer.md.j2` (`config.locale` branch;
  an `is_codex` branch adds "read `.agents/skills/project-knowledge/SKILL.md`"). Include it
  from the four `claude-md/*.md.j2`, `codex/AGENTS.md.j2` and `cursor/rules/harness.mdc.j2`,
  outside every `@hm:user:*` block.
- The skill carries SPEC AC-004's tokens. The pointer satisfies AC-005 (≤300 characters;
  names `project-knowledge` and `auto-memory`; the Codex row also names the skill path).
- The skill body carries the same `is_codex` mention note as `intent-layer`.
**Consequences:**
- ✅ One source per surface; three hosts covered (Cursor reads `.claude/skills/` natively;
  Codex reaches the skill via the `AGENTS.md` path pointer).
- ⚠️ ≤300 characters per host session is always loaded.
**Rejected alternatives:**
- Skill only: the auto-memory default goes unopposed.
- Full always-loaded instruction: about 6× the carry.
- Folding into `intent-layer`: different trigger vocabulary.
- Codex as mention-only: breaks the SPEC's three-host outcome.
**Source:** SPEC Round 1; design brief default; interview #2 (C4).

### ADR-003: S0 stores facts in `wiki.md` only — no new memory file
**Status:** Accepted (2026-09-19, via /hm:spec Round 1)
**Context:** Subject files would need `_HUMAN_MEMORY_TIER_PATHSPEC`, `_path_owner`, both dirt
filters and the retrieve loader updated together. That is the count:3 "every reader must be
updated" class.
**Decision:** `[wiki:fact] <subject-slug>` entries via the existing `upsert-wiki`; the subject
slug is the identity. The body is the current truth, plus one `Supersedes: <old claim> (<date>)`
line on correction. S1 is gated on ADR-005.
**Consequences:**
- ✅ Zero plumbing change; the existing fold/land path carries captures.
- ⚠️ Identity depends on the LLM finding the slug. ADR-007 bounds what a found slug may be
  reused for.
**Rejected alternatives:**
- S1 now: cost and risk before the capture habit is shown.
**Source:** SPEC Round 1.

### ADR-004: proceed without waiting for `observed-harness-gaps`
**Status:** Accepted (2026-09-19, via /hm:plan interview #1). Supersedes the SPEC's sequencing
note.
**Context:** That sibling also edits `memory_retrieve.py` (count floor), wrapup and execute. It
is unlanded: its work is uncommitted in `.worktrees/observed-harness-gaps/` on 0.51.3, last
touched 2026-08-14.
**Decision:** This task lands first; the later lander rebases. The `memory_retrieve.py` edit
is confined to `main()`'s default and a new helper, to minimise overlap with the sibling's
floor code.
**Consequences:**
- ✅ No indefinite block.
- ⚠️ The sibling's rebase must keep ADR-001's default. AC-001's subprocess test fails loudly
  if it does not. The CHANGELOG and the land commit name the obligation.
**Rejected alternatives:**
- Wait: resume date unknown.
- Absorb its recall work: contradicts SPEC Non-Goals.
**Source:** Interview #1.

### ADR-005: the 28-day criterion is a guarded, history-based `intent.yaml` outcome
**Status:** Accepted (2026-09-19, via /hm:plan interview #1 + #2 C5/C6)
**Context:** The SPEC pre-registers:
- "28 days from the release tag that ships S0: ≥5 `[wiki:fact]` headings → S1 candidate;
  0 → remove skill + pointers; 1–4 → keep S0".

Validation found that a live-file count would be wrong in three ways:
- It is recorded early, because wrapup 5.7 runs `measure --all` every wrapup.
- It drops after the fact, because `upsert-wiki` re-dates a heading on every correction
  (`memory_md.py:196-198, 352`).
- It is anchored to any tag, not a release tag.

Separately, a manual dogfood check writing a fact would make "0 → remove" unreachable.

**Decision:**
- New repo-local `scripts/measure_wiki_fact_window.py` (not shipped). Pure functions plus a
  `main()`:
  1. Find the first commit adding `src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2`.
  2. Find the earliest `v*` tag containing it, by creator date. If none exists, exit 2 with
     `not released`.
  3. The window is whole **UTC calendar dates**. `tag_day` is the UTC date of the tag's creator
     date, and the window is `tag_day` … `tag_day + 28` inclusive. While today's UTC date is
     `<= tag_day + 28`, exit 3 with `window open (<n> days left)`, where
     `n = (tag_day + 28) - today_utc + 1`; nothing is recorded. From 00:00Z on `tag_day + 29`
     it measures. Membership uses the same comparison, `tag_day <= earliest_date <= tag_day + 28`.
     *(Amended 2026-09-19, before any release — Phase 5 A.5 escalation, operator chose path A.
     The original `[tag_date, tag_date + 28d]` left the unit undefined. Heading dates are UTC
     days (`memory_md` stamps `datetime.now(tz=UTC)` as `%Y-%m-%d`), so an instant-based guard
     could measure at 10:01Z on the last day and then see same-day headings appear, which is
     the post-deadline drift this ADR forbids.)*
  4. Otherwise scan `git log -p --format=%H -- .claude/memory/wiki.md` on the current branch
     for added lines `+## [wiki:fact] <slug> | <YYYY-MM-DD>`, **plus the headings in the
     current working-tree `.claude/memory/wiki.md`**. Take each slug's **earliest** date across
     both, and count slugs whose earliest date is inside the window. Print the count.
     *(Amended 2026-09-19, before any release — A.5 round 3, operator's choice. The
     working-tree half was always the intent but was missing from this text. `memory_md`
     writes captures to the base checkout, where they stay uncommitted until a land folds them,
     and the measure runs with `cwd: base`. A git-history-only scan would miss an in-window
     capture that has not yet been folded.)*

  Earliest-date-per-slug makes post-deadline corrections and late folds harmless to the
  count.

  *(Amended 2026-09-19 by `/hm:review` Codex P1 `4444994ec2c7ab6f`, before any release.) A
  capture that is never committed and is corrected after the window loses its original heading
  from every input. Two changes close that gap:*
  - *the correction's `Supersedes:` line now carries `(first recorded <YYYY-MM-DD>)`, which the
    skill carries forward across corrections;*
  - *the script reads that date as a candidate for its slug.*

  *To attribute body lines to headings, the scan now parses every committed version of the file
  in full, not only its diff lines. On this repo's 270 versions that takes about 2 s.*
- Outcome `wiki_fact_entries_28d` in this repo's `.claude/intent.yaml`:
  - `target: 5`, `higher_is_better: true`;
  - `how_measured` carries the three-way rule verbatim, the non-re-interpretation clause, and
    the evaluation owner;
  - `measure: {cmd: "uv run python scripts/measure_wiki_fact_window.py", select: last-number,
    cwd: base}`.
- Owner and trigger: the operator at the first `/hm:wrapup` after the window closes. 5.7's
  existing "Measure outcomes now?" question lists the outcome, and a successful measure
  records the value in `.claude/world/outcomes.yaml`. The operator then applies the rule and
  records the chosen action (file S1 / remove / keep) as that follow-up task's
  `/hm:research` or PLAN.
- Manual S1–S3 verification runs in a **throwaway clone**, never in this repo's base wiki.
**Consequences:**
- ✅ There is no partial-window value, no drift after the deadline, and no contamination.
  The counting branch is unit-tested before it fires.
- ⚠️ The "0 → remove" branch lives in prose, because `higher_is_better` cannot express it.
- ⚠️ The measurement covers this repo only.
**Rejected alternatives:**
- A live-file `python -c` count (drifts, untested).
- An `unknowns` line or CHANGELOG only (never fires).
- An excluded-prefix rule for dogfood entries (extra rule; the verification entry still sits
  in the wiki).
**Source:** Interview #1; interview #2 (C5, C6).

### ADR-006: wrapup + help growth rides a `surface_allowance` declared in P4, retired in P5
**Status:** Accepted (2026-09-19, via /hm:plan default + interview #2 C2/C3/C8/C11)
**Context:** The aggregate ratchet only counts `.claude/commands/hm/*.md` and
`.agents/skills/hm-*/SKILL.md` (`tests/structural/_surface_baseline.py:132-140`). The skill,
the pointers and the wiki templates are outside it, so they have no measured growth, and
`_parse` rejects `chars <= 0`. Wrapup 5.1.0 adds one counted round trip per variant (`!uv run`
/ `Bash(`, `_surface_baseline.py:146-167`). The help row grows `help`. Two earlier invariance
tests pin wrapup at 0.57.1 until a later delta doc exists
(`test_assumption_entry_invariance.py:92-99`, `test_intent_layer_ops_invariance.py:73-80`).
**Decision:**
- P0 pins plan/review sha plus wrapup/help length per arm in
  `work-docs/BASELINE-DELTA-mission-context-loop.md`.
- P4 (the only ratchet-measured growth) declares, in the same commit as the growth:
  `surface_allowance: {chars, commands: {wrapup, help}, round_trips: {wrapup, hm-wrapup},
  reason, delta_doc: BASELINE-DELTA-mission-context-loop.md}` (basename, resolved from
  `work-docs/`). No `commands.hm-wrapup`: `command_headroom` is only called with Claude
  names.
- P4 adds `tests/structural/test_mission_context_loop_invariance.py`. It pins plan and review
  byte-for-byte and bounds wrapup and help by the allowance, per the intent-layer-ops
  precedent.
- The two earlier invariance tests are **expected red** from P4 until P5's delta doc quotes
  `aggregate_chars` in the format `_current_delta_doc` matches. The executor does not "fix"
  them.
- P5 re-freezes the baselines, writes §3.1 attribution, deletes the allowance and exits green
  with zero allowances.
- Skill, pointer and wiki-template budgets are AC-005's 300-character cap and context-lint's
  300-line skill limit, not the aggregate.
- 5.1.0 is a blockquote (like 5.2.0), so `step_sensitivity.REGISTRY` is untouched.
**Consequences:**
- ✅ Main is green after land, every ratchet-measured byte is attributed, and the
  unratcheted surfaces have explicit caps.
- ⚠️ A window of expected-red earlier invariance tests between P4 and P5.
**Rejected alternatives:**
- Declaring the allowance in P2: zero measured growth, rejected by `_parse`.
- Regenerating `surface_baseline.json` directly: destructive.
**Source:** design brief default; interview #2 (C2, C3, C8, C11).

### ADR-007: slug-reuse rules protect facts from task summaries
**Status:** Accepted (2026-09-19, via /hm:plan interview #2 C1 — critical)
**Context:** `memory_md._upsert` rebuilds the heading with the caller's category and replaces
the whole body (`memory_md.py:352-353`). Unbounded "find and reuse" would let wrapup overwrite
a `[wiki:fact]` with a task summary, and let the skill rewrite a gotcha or architecture entry
as a fact.
**Decision:**
- Wrapup 5.1.0 may reuse only **non-fact** slugs and states `never reuse a [wiki:fact] slug`.
  When it reuses one, the new body carries forward what is still true in the old one, because
  upsert replaces rather than appends.
- The skill states `reuse only a [wiki:fact] slug`. A non-fact best match gets a new fact slug.
- Facts change only on the DRI's explicit correction.
- AC-004 and AC-006 assert the tokens. A unit regression records that a different-category
  upsert on a fact slug rewrites the heading, so the hazard is pinned.
- *(Amended 2026-09-19 by `/hm:review` Codex P1 `19b3f7f1f0100b4f`.)* The search is top-k, so a
  fact it does not surface can still own the slug a writer picks. Before using a **new** slug,
  both the skill and wrapup 5.1.0 must check the exact slug against the base wiki's headings.
  They do this with the Grep tool, so the slug never enters a shell line, and pick another slug
  if it is taken. This is pinned by
  `test_render_project_knowledge.py::test_new_slug_is_checked_for_an_existing_heading`.
**Consequences:**
- ✅ Captured facts survive every wrapup.
- ⚠️ A subsystem may carry both a `[wiki:fact]` and a `[wiki:architecture]` entry. That is
  accepted; they answer different questions.
**Rejected alternatives:**
- A Python category guard in `upsert-wiki`: changes the writer the SPEC fixes as the reference
  (Contract Boundaries), and it is a judgement the LLM makes with context.
**Source:** Interview #2 (C1).

## 🏗️ Technical Design

**Current state.**
- `memory_md` (write) is base-rooted.
- `memory_retrieve` (read) is cwd-rooted.
- Only wrapup 5.1 writes wiki, without searching first. 5.2 searches first (5.2.0).
- The wiki templates list `pattern/convention/gotcha/architecture/tooling/api/other`.
- No skill or always-loaded text routes "remember X".

**Affected components.**
- `src/harness_maker/memory_retrieve.py`: `resolve_memory_dir` and the `main()` default.
- `scripts/measure_wiki_fact_window.py` (new, repo-local).
- `src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2` (new).
- `src/harness_maker/templates/agents/_partials/project_knowledge_pointer.md.j2` (new).
- `src/harness_maker/templates/claude-md/{Production,Side}.{en,ko}.md.j2`,
  `templates/codex/AGENTS.md.j2`, `templates/cursor/rules/harness.mdc.j2`: include the pointer.
- `src/harness_maker/templates/stages/wrapup.md.j2` §5.1: a `> **5.1.0 — search-before-write
  (fact-safe)**` blockquote with a `memory_retrieve` call in both `is_codex` branches.
- `src/harness_maker/templates/memory/wiki.{en,ko}.md.j2`: `fact` category and a
  `Supersedes:` note.
- `src/harness_maker/templates/commands/hm/help.{en,ko}.md.j2`: a `project-knowledge` row
  (with the Codex mention note, like the `intent-layer` row at `help.en.md.j2:49`).
- `src/harness_maker/synthesize.py` `_ALL_SKILLS`; `src/harness_maker/interview.py`
  `_ALL_SKILLS` and `_SIDE_ENABLED_SKILLS`.
- `tests/unit/test_codex_phase7.py:166` (22 → 23).
- `.claude/intent.yaml` (dogfood outcome); `CHANGELOG.md`; rendered snapshots.

**Skill body contract** (AC-004; the text is written to these tokens):
1. **Trigger**, only when the DRI explicitly asks to remember or record a project fact not
   derivable from the code, or says a recorded fact is wrong. `never record an inferred fact`.
2. **Route.** Shared project facts go to `.claude/memory/wiki.md`; personal preferences are
   left to host `auto-memory`.
3. **Search first** with `memory_retrieve --topic "<subject>"`, then `reuse only a [wiki:fact]
   slug`. A non-fact match gets a new fact slug.
4. **Write** with `hm memory_md upsert-wiki --root . --category fact --slug <subject>
   --body-file <mktemp outside repo>`. The body is the current truth, plus `Supersedes: <old
   claim> (<date>)` on correction.
5. **On non-zero exit**, `surface the stderr`; do not fall back to auto-memory.

The Codex render uses `Bash("…")` and the `@project-knowledge` mention note.

**Data flow.**
```
DRI ──"remember X"/correction──▶ agent (skill) ──memory_retrieve──▶ base/.claude/memory/wiki.md
                                   └─upsert-wiki (fact slug only)──▶ base wiki (flock)
wrapup 5.1.0 ── search; reuse NON-fact slug only ──▶ base wiki
task-land ──commit-base-memory──▶ squash commit (existing)
any stage (cwd = worktree) ──memory_retrieve (default = base, ADR-001)──▶ sees the capture
first wrapup after tag+28d ──5.7 measure──▶ scripts/measure_wiki_fact_window.py ──▶ outcomes.yaml
```

**API change.**
- `memory_retrieve` CLI: the `--memory-dir` default becomes base-rooted; an explicit value is
  unchanged.
- New public `resolve_memory_dir`.
- No schema change.

## 📝 Implementation Plan

### Phase 0 — Pin the surface and confirm main is green
- **Status:** DONE (2026-09-19, /hm:execute): both structural gates green (32 passed); pin at dfc9d37c in the delta doc §1
- **depends_on:** []
- **parallel_group:** serial-surface
- **merge_hazards:** `work-docs/BASELINE-DELTA-mission-context-loop.md` (new)
- **Scope in:**
  - From `<WT>`, run `uv run pytest tests/structural/test_surface_baseline.py
    tests/structural/test_command_size_budget.py` and confirm green. If red because a prior
    expired allowance was never folded, fold it and record it in §2.
  - Write delta doc §1: a fenced JSON pin `{arms{arm:{plan,review}}, wrapup_len{arm},
    help_len{arm}, harness_maker_version}` via the recipe of
    `tests/structural/test_intent_layer_ops_invariance.py`.
  - §2: inherited-fold note. §3: placeholder.
- **Scope out:** src, templates.
- **Exit:** delta doc exists with a parseable JSON pin; both structural files green.
- **Risk:** low
- **Rollback:** none (docs only).

### Phase 1 — Recall root follows the writer (AC-001, AC-002, AC-003; ADR-001, ADR-007)
- **Status:** DONE (2026-09-19, /hm:execute): A.5 PASS on round 1. The targeted set (68) and its neighbours (40) are green; ruff and mypy are clean.
- **Execution notes:**
  - **A.4:** the root module was RED (ImportError). The supersede module had 2 passing tests,
    justified as regression pins on the Do-not-change writer; A.5 accepted this.
  - **D.5:** the newly reachable window is "base has no `.claude/memory`, the worktree does".
    Before the fix the worktree copy was read; now the reader degrades gracefully on the base
    path. It is pinned by `tests/unit/test_memory_retrieve_root.py::test_d5_base_without_memory_dir_reports_the_base_path`.
  - **Tooling defect found, not fixed here.** The `spec_gate` PreToolUse hook roots at the hook's
    cwd (the base), so it cannot see an in-flight task's worktree `specs/`. It blocked every
    test-file Write even though this task's machine SPEC names the exact test ids. With the
    operator's approval, test files in this task are written with Bash heredocs. The gate should
    resolve the worktree that contains `file_path`. This is recorded for wrapup 5.2 and as a
    follow-up candidate.
- **depends_on:** []
- **parallel_group:** serial-python
- **merge_hazards:** `src/harness_maker/memory_retrieve.py` (also edited by the unlanded
  `observed-harness-gaps`; ADR-004)
- **Scope in:**
  - RED first:
    - `tests/unit/test_memory_retrieve_root.py::test_ac_001_default_memory_dir_is_writer_root`:
      Hypothesis over worktree names and depth 0..3 under a tmp base, asserting
      `resolve_memory_dir(None, cwd) == memory_md._memory_dir(cwd)`, plus one subprocess run
      of `python -m harness_maker.memory_retrieve --topic x` with `cwd=<base>/.worktrees/w/`
      that surfaces an entry present only in the base wiki.
    - `::test_ac_002_explicit_memory_dir_wins`.
    - `tests/unit/test_memory_md_fact_supersede.py::test_ac_003_same_slug_upsert_replaces_and_keeps_supersedes`:
      Hypothesis over canonical bodies with no heading-shaped lines and no markers; asserts
      body equals `body2.strip("\n")`.
    - `::test_cross_category_upsert_on_fact_slug_rewrites_heading` (ADR-007 hazard pin).
  - GREEN: add `resolve_memory_dir`; `main()` uses it; `--memory-dir` default `None`.
- **Scope out:** templates.
- **Exit:**
  - `uv run pytest tests/unit/test_memory_retrieve_root.py tests/unit/test_memory_md_fact_supersede.py tests/integration/test_memory_retrieve_cli.py` green;
  - `uv run pytest tests/unit -k memory_retrieve` green;
  - `uv run ruff check src/harness_maker/memory_retrieve.py && uv run mypy --strict src/harness_maker/memory_retrieve.py` clean.
- **Risk:** low
- **Rollback:** Phase 0.

### Phase 2 — `project-knowledge` skill + registration (AC-004; ADR-002, ADR-007)
- **Status:** DONE (2026-09-19, /hm:execute)
  - A.5 PASS in round 1.
  - Inventory constants updated at 5 sites: `synthesize._ALL_SKILLS`, `interview._ALL_SKILLS`,
    `_SIDE_ENABLED_SKILLS`, `test_codex_phase7` 22 → 23, and `test_synthesize_codex` base
    12 → 13.
  - Snapshots regenerated in the worktree (8 files, +1 skill each).
  - 185 inventory/snapshot/structural tests passed (2 skipped); ruff and mypy are clean.
  - D.5 does not apply: new feature.
- **depends_on:** [0]
- **parallel_group:** serial-surface
- **merge_hazards:** `src/harness_maker/synthesize.py`, `src/harness_maker/interview.py`;
  rendered snapshots; every test enumerating skills
- **Scope in:**
  - RED: `tests/render/test_render_project_knowledge.py::test_ac_004_skill_carries_capture_contract`.
    Render Production + Side × targets `[claude-code, cursor, codex]`. Assert every
    REQUIRED_TOKEN (SPEC AC-004, 8 tokens) in `.claude/skills/project-knowledge/SKILL.md` and,
    with codex, in `.agents/skills/project-knowledge/SKILL.md`. `expected_copy_count` is 2
    with codex, 1 without.
  - GREEN:
    - write the skill to the Technical-Design contract. Its frontmatter `description` names
      "remember / record / 기억해 / 정정 / correct a recorded fact"; the body stays under 300
      lines.
    - add it to `synthesize._ALL_SKILLS`, `interview._ALL_SKILLS` and
      `interview._SIDE_ENABLED_SKILLS`;
    - set `tests/unit/test_codex_phase7.py:166` to 23 with a dated comment;
    - update every other enumerating test found by
      `rg -l -e 'intent-layer' -e '_ALL_SKILLS' -e '_SIDE_ENABLED_SKILLS' tests`;
    - regenerate snapshots in the worktree.
  - No allowance here: the aggregate ratchet does not see skills (ADR-006).
- **Scope out:** pointers, wrapup, wiki templates, help.
- **Exit:**
  - `uv run pytest tests/render/test_render_project_knowledge.py -k ac_004` green;
  - separately, `uv run pytest tests/structural/test_surface_baseline.py tests/structural/test_command_size_budget.py tests/unit/test_codex_phase7.py` green;
  - every file listed by the `rg -l` above passes `uv run pytest <files>`.
- **Risk:** medium (hand-maintained inventories)
- **Rollback:** Phase 0.

### Phase 3 — Pointer partial in six always-loaded templates (AC-005; ADR-002)
- **Status:** DONE (2026-09-19, /hm:execute)
  - A.5 PASS in round 1.
  - Rendered pointer lengths: en 259, codex 224, ko 182 characters.
  - Phase D surfaced two issues, both fixed:
    - `test_codex_phase4` renders `AGENTS.md.j2` without `is_codex` or `config.locale`, so the
      partial now guards both;
    - a sixth enumeration constant, `test_synthesize.test_side_file_count_in_range` (60 → 61),
      had been missed by the P2 `rg` sweep.
  - 609 tests passed.
- **depends_on:** [2]
- **parallel_group:** serial-surface
- **merge_hazards:** the six templates; rendered snapshots
- **Scope in:**
  - RED: `::test_ac_005_pointer_present_and_bounded`, parametrised over SPEC AC-005's golden
    table. Slice the pointer section by its heading; assert ≤300 characters, the names, and
    the skill path in the `AGENTS.md` row.
  - GREEN: write the partial (`config.locale` + `is_codex` branches) and include it in the six
    templates outside `@hm:user:*`.
  - Regenerate snapshots.
- **Scope out:** skill text, wrapup, help.
- **Exit:**
  - `uv run pytest tests/render/test_render_project_knowledge.py -k ac_005` green;
  - separately, `uv run pytest $(rg -l -e context_discipline -e 'AGENTS.md' -e 'harness.mdc' -e 'user:project-rules' tests)` green (render + user-block preservation);
  - both structural gates green.
- **Risk:** low
- **Rollback:** Phase 2.

### Phase 4 — Wrapup 5.1.0, wiki templates, help row, allowance + own invariance (AC-006, AC-007; ADR-006, ADR-007)
- **Status:** DONE (2026-09-19, /hm:execute)
  - A.5 FAIL in round 1: AC-007 used a substring `fact` test. Repaired to a token match; PASS
    in round 2.
  - Measured growth:
    - wrapup +725 in every arm;
    - help +159 (ask arms) / +102 (auto_safe arms);
    - aggregate claude +827, codex +858;
    - round trips +1 per wrapup variant.

    All are declared in `surface_allowance`.
  - Own invariance test added. Its "later task owns the surface" skip now fires only after
    retirement: in flight, `_current_delta_doc` names the previous task's doc and the test would
    otherwise be vacuous. A mutation receipt was recorded (deleting `plan.md.j2:80` turns it
    red). The receipt row is in the BASE `mutation-receipts.jsonl`; commit it on main at land,
    per the `feedback_release_verify_in_fresh_clone` precedent.
  - Four further hand-maintained sites the PLAN did not name were updated:
    - `test_roundtrip_budget._CLAUDE_ROUND_TRIPS['wrapup']` 30 → 31;
    - the `project-knowledge` row in `work-docs/MATRIX-native-redundancy.md`;
    - an `autopilot_gate_golden.json` re-capture (verified only help + wrapup moved in all four
      arms), with a dated docstring entry;
    - the mutation receipt above.
  - Exit: `tests/structural tests/render tests/snapshot` gives 984 passed, 1 failed. The failure
    is the expected `test_assumption_entry_invariance`; `test_intent_layer_ops_invariance`
    already skips on the later-task rule.
- **depends_on:** [2]
- **parallel_group:** serial-surface
- **merge_hazards:** `wrapup.md.j2`; `wiki.{en,ko}.md.j2`; `help.{en,ko}.md.j2`; snapshots;
  `test_command_size_budget` goldens; this PLAN's frontmatter
- **Scope in:**
  - RED:
    - `::test_ac_006_wrapup_51_searches_before_write` over every rendered wrapup arm
      (preset × dev_mode × claude/codex). Slice `#### 5.1`…`#### 5.2`; assert the index order,
      `reuse`, and `never reuse a [wiki:fact] slug`.
    - `::test_ac_007_wiki_template_documents_fact_and_supersedes`.
    - `::test_help_lists_project_knowledge`.
  - GREEN:
    - add the 5.1.0 blockquote (both branches), the wiki template edits and the help rows
      (en/ko, Codex mention note);
    - measure the deltas;
    - in the same commit declare `surface_allowance` per ADR-006 (chars, `commands.wrapup`,
      `commands.help`, `round_trips.wrapup`, `round_trips.hm-wrapup`, reason, basename
      `delta_doc`);
    - add `tests/structural/test_mission_context_loop_invariance.py`: plan and review sha
      equal the P0 pin; wrapup and help length ≤ pin + allowance;
    - gate golden re-capture for `wrapup` and `help` only; regenerate snapshots.
  - **Expected red until P5:** `tests/structural/test_assumption_entry_invariance.py` and
    `tests/structural/test_intent_layer_ops_invariance.py` (their 0.57.1 wrapup/help pins).
    Do not edit them.
- **Scope out:** 5.2–5.7 text; plan/review templates.
- **Exit:**
  - `uv run pytest tests/render/test_render_project_knowledge.py tests/structural/test_mission_context_loop_invariance.py` green;
  - separately, `uv run pytest tests/structural/test_step_sensitivity_registry.py tests/structural/test_command_size_budget.py tests/structural/test_surface_baseline.py` green;
  - the two expected-red invariance tests are the only structural failures
    (`uv run pytest tests/structural -q -rf` lists exactly them).
- **Risk:** medium (the largest command; delegated-body parity)
- **Rollback:** Phase 2.

### Phase 5 — Measurement script + dogfood outcome, CHANGELOG, allowance retirement (ADR-005, ADR-006)
- **Status:** DONE (2026-09-19, /hm:execute)
  - The script passes all 9 of its tests.
  - `wiki_fact_entries_28d` was added to `.claude/intent.yaml`. Run against the base it
    reports `not released`, exit 2, as expected before release.
  - CHANGELOG (Unreleased): Added + Fixed, including the rebase note for
    `observed-harness-gaps`.
  - Baseline re-frozen: aggregate claude 435 224 / codex 370 304. `render_sha` is the
    merge-base 555ca933, because the generator refuses a task-branch HEAD and this branch
    carries doc commits.
  - `_ATOMIC_RATCHET['wrapup']` moved 45646 → 47084. Delta doc §1 re-pinned; §3 and §3.1
    written. The allowance is deleted, leaving 0 active allowances.
  - Full suite: 8765 passed and 2 failed (RC=1 read from the output file; the background
    notification said exit 0). Both failures were the wrapup body-line pins in
    `test_render_wrapup_delegation.py`, a seventh hand-maintained site. Updated 713/746 →
    726/759 and re-run green (16 passed).
  - `ruff check .`, `ruff format --check .` and `mypy --strict src/harness_maker` are clean.
- **Earlier status:** unblocked 2026-09-19. The operator chose stuck path A: ADR-005 (3) now uses UTC
  calendar dates with the end day included, the SPEC wording matches, and two boundary tests
  were added. A.5 round 3 (operator-granted) failed only on ADR-005 (4) omitting the
  working-tree scan the test assumes. The operator chose to amend the ADR text and proceed to
  Phase C without a round 4. The history below is kept.
- **Earlier status:** BLOCKED (2026-09-19, /hm:execute) — Phase A.5 retry exhausted.
  - Round 1 FAIL: ADR-005 clauses (1) first-add and (2) earliest-by-creator-date `v*` tag had no
    discriminating tests. Two tests were authored for them, and round 2 accepted both.
  - Round 2 FAIL: `test_window_boundary[last-window-day]` expects the window still open at
    2026-10-18 23:59 with the tag created 2026-09-20 10:00. That holds only if the window is
    compared by calendar DATE. ADR-005 says `[tag_date, tag_date + 28d]` without stating the
    granularity, and a literal instant comparison closes the window at 2026-10-18 10:00.
  - Root cause: ADR-005 leaves window granularity undefined. Heading dates are day-granular
    (`| YYYY-MM-DD`), so the window must be compared at some granularity, and the ADR never
    says which.
  - `[boundaries] comparison not performed — blocked exit`
- **depends_on:** [1, 3, 4]
- **parallel_group:** serial-surface
- **merge_hazards:** `scripts/measure_wiki_fact_window.py` (new); `.claude/intent.yaml`;
  `CHANGELOG.md`; `surface_baseline.json` + command-size goldens; this PLAN's frontmatter;
  the delta doc
- **Scope in:**
  - RED: `tests/unit/test_measure_wiki_fact_window.py` on a tmp git fixture repo:
    - no `v*` tag → exit 2 `not released`;
    - a non-`v` tag is ignored;
    - `v0.0.1` tag with the clock inside the window → exit 3 `window open`;
    - clock after the window: headings added across commits, including one re-dated after
      the deadline and one first dated before the tag, count = the slugs whose earliest date
      is in-window;
    - the clock is injected, never read from the real time.
  - GREEN: the script (pure functions + `main()`; subprocess `git` with `shell=False` and a
    timeout).
  - Add outcome `wiki_fact_entries_28d` per ADR-005.
  - `uv run hm world outcome measure wiki_fact_entries_28d --dry-run` from the worktree
    reports `not released`, the expected pre-release state.
  - CHANGELOG (Unreleased) names ADR-004's rebase obligation and the manual clone check.
  - Re-freeze the surface baseline and the wrapup/help goldens. The delta doc quotes
    `aggregate_chars` in `_current_delta_doc`'s format, plus §3.1 attribution (5.1.0,
    help row; skill/pointer/wiki sizes listed as unratcheted).
  - Delete `surface_allowance`.
  - Run the full suite in the background (about 6 min).
- **Scope out:** src behaviour.
- **Exit:**
  - full `uv run pytest` green, including both earlier invariance tests now skipping on
    this delta doc;
  - `uv run python -c "from harness_maker.surface_allowance import load_active_allowances as L; from pathlib import Path; assert not [a for a in L(Path('.')) if a.slug=='mission-context-loop']"`;
  - `uv run ruff check . && uv run mypy --strict src/harness_maker` clean;
  - `hm world status` lists `wiki_fact_entries_28d`.
- **Risk:** medium (fold order; a peer landing between re-freeze and land)
- **Rollback:** Phase 4.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/memory_md.py` — the writer's rooting and upsert semantics are the reference ADR-001/007 and AC-003 test against
- `src/harness_maker/worktree.py` — path-ownership, dirt filters, `_HUMAN_MEMORY_TIER_PATHSPEC`, `commit_base_memory` (ADR-003)
- `src/harness_maker/wrapup_land.py` — staging manifest; captures ride the existing fold
- `src/harness_maker/step_sensitivity.py` — no new headings are introduced
- `src/harness_maker/templates/stages/execute.md.j2` — execute warm-tier recall belongs to `observed-harness-gaps` (SPEC Non-Goal)
- `tests/structural/test_assumption_entry_invariance.py` — expected red P4→P5, released by P5's delta doc, never edited
- `tests/structural/test_intent_layer_ops_invariance.py` — same
- Advisory: wrapup 5.2–5.7 text stays byte-identical; only 5.1 gains the 5.1.0 blockquote
- Advisory: `@hm:user:*` blocks in `CLAUDE.md`, `AGENTS.md` and the wiki are never moved or edited by the partial include
- Advisory: manual S1–S3 verification never writes to this repo's base `wiki.md` (throwaway clone only)

## 🧪 Testing Strategy

- **Unit (Python):**
  - AC-001: Hypothesis plus a subprocess test from a worktree cwd.
  - AC-002: explicit dir wins.
  - AC-003: canonical-body property.
  - ADR-007 hazard pin.
  - `test_measure_wiki_fact_window.py`: fixture git repo with an injected clock.
  - `mutmut` on `memory_retrieve.py` at tier-2 threshold 70. Never kill it mid-run; check
    `git diff src/` after.
- **Render:** AC-004–AC-007 plus the help row in `tests/render/test_render_project_knowledge.py`,
  across presets × dev_modes × targets. Snapshot regeneration in the worktree.
- **Structural:**
  - own invariance test;
  - surface baseline and command-size budget (including round trips);
  - step-sensitivity registry;
  - context lint (skill under 300 lines);
  - two earlier invariance tests expected red P4→P5.
- **Manual (post-release; SPEC S1–S3).** In a throwaway clone of this repo, after
  `/harness-maker:make --update` there, in **Claude Code and Codex**:
  - "기억해: <fact>" → a `[wiki:fact]` entry in the clone's `wiki.md` and no new auto-memory
    file;
  - correct it → one heading plus a `Supersedes:` line;
  - state a preference → `wiki.md` unchanged.

  Record the outcome in the wrapup of the first task after the release.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Skill never triggers; auto-memory keeps winning | medium | S0 dead | Always-loaded pointer (ADR-002); ADR-005 measures it; 0 in 28 days → remove (pre-registered) |
| Wrapup or skill overwrites the wrong entry via slug reuse | low (after ADR-007) | fact loss | Fact-only / non-fact-only reuse rules asserted by AC-004/006; hazard pinned by unit test |
| LLM writes a new slug instead of reusing (duplicates persist) | medium | stale duplicates | Search-first in skill and 5.1.0; AC-003 guards mechanics |
| Codex never reaches the skill | medium | Codex capture dead | `AGENTS.md` pointer names the skill path (AC-005 Codex row); Codex manual arm |
| `observed-harness-gaps` rebase drops ADR-001's default | low | S5 regresses | AC-001 subprocess test; CHANGELOG + land commit name it |
| Measurement fires early, drifts, or is buggy | low (after ADR-005) | wrong pre-registered decision | window-open guard, earliest-date-per-slug over history, `v*` tags, fixture-repo tests |
| Hand-maintained skill inventories missed | medium | red test / missing skill | P2 `rg -l -e …` sweep; three named constants; codex count |
| Allowance expires before fold | low | main red after land | P5 retires in-task; exit asserts zero allowances |
| Inferred or personal data recorded into a git-shared file | low | privacy/noise | Trigger limited to explicit request/correction; routing rule; S3/S4 tokens |

## ✅ Success Criteria

- [x] AC-001 default memory dir equals `memory_md`'s dir from any worktree depth
- [x] AC-002 explicit `--memory-dir` unchanged
- [x] AC-003 same-slug upsert → one heading, body == canonical latest including `Supersedes:`
- [x] AC-004 skill carries all eight tokens in every rendered copy
- [x] AC-005 six variants carry a ≤300-char pointer naming `project-knowledge` + `auto-memory`; Codex row names the skill path
- [x] AC-006 wrapup 5.1 searches before writing, reuses only non-fact slugs, forbids fact reuse, in every arm
- [x] AC-007 both wiki templates document `fact` and `Supersedes:`
- [x] `/hm:help` lists `project-knowledge` (en/ko, Codex mention note)
- [x] `scripts/measure_wiki_fact_window.py` tested; `wiki_fact_entries_28d` in `intent.yaml`
- [x] Full suite green, zero active allowances, ruff + mypy clean
- [x] Manual S1–S3 in a throwaway clone (Claude Code + Codex) recorded after release — deferred to post-release (follow-up)

## 🔍 Plan Validation

### Pass 1 — MAJOR_REVISION (plan-validator + Codex, 2026-09-19)

Codex (invoked, 9 findings) was reconciled by the validator: all 9 accepted after verification
against code. One sub-point was rejected: the "config reload test" half of 524c2f23, because
`synthesize` renders every `_ALL_SKILLS` skill regardless of `enabled`. Validator critiques:
C1 (critical), C2–C8 (warnings), C9–C12 (suggestions). `plan_rounds plan` queued all 12, with
0 skipped.

| Critique | Resolution | Where |
|---|---|---|
| C1 unbounded slug reuse destroys facts | A — revised | ADR-007; SPEC S1/S6, AC-004/006 tokens; P1 hazard pin; P4 assertion |
| C2 P2 allowance has zero measured growth; delta_doc path doubled | A | ADR-006: allowance moved to P4, basename `delta_doc` |
| C3 undeclared round trips; inert `commands.hm-wrapup` | A | ADR-006 `round_trips.{wrapup,hm-wrapup}`; `commands.hm-wrapup` dropped |
| C4 Codex skills start only on mention | A (pointer names skill path) | ADR-002; SPEC AC-005 Codex row |
| C5 measurement early / drifting / any tag / untested | A | ADR-005: window guard, earliest-date history scan, `v*`, fixture tests, owner |
| C6 manual check contaminates the count | A (throwaway clone) | ADR-005; Testing Strategy; Contract Boundaries |
| C7 exit commands skip checks | A | P2/P3/P4 exits split; `rg -e`; no `head`; codex count 23 |
| C8 earlier invariance pins red P4→P5; P0 pin unread | A | ADR-006: own invariance test; expected-red list; `aggregate_chars` quoted in P5 |
| C9 memory_md not stdlib-only | A | ADR-001 wording |
| C10 pre-filled verdict | A | frontmatter |
| C11 name lists; help row | A (add help row) | ADR-002 constants; P4 help row |
| C12 AC-003 vs writer normalisation | A | SPEC AC-003 canonical body; P1 strategy |

### No pass 2 (operator policy)

Per the standing operator decision (2026-08-21), plan-validator runs once per `/hm:plan`: no
pass 2 and no Step 4.5 terminal re-validation. `validator_outcome` records the single pass's
verdict, `MAJOR_REVISION`. Every critique was resolved by revision (A) in interview round 2.
The accepted cost: defects introduced by this revision surface at `/hm:execute` A.5 or
`/hm:review`, not here. The Codex second opinion was invoked (not skipped).
