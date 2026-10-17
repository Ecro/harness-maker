---
type: spec
task_slug: retired-text
status: approved
created: 2026-10-17
tags: [harness-maker, spec, templates, cleanup, tests, overhaul]
test_framework: pytest
interview_rounds: 1
lane: full
parent_spec: "[[SPEC-hm-overhaul-p1]]"
summary: "0.64.0 renders still describe retired autoloop/autopilot/executor machinery in agent, skill, command and hook texts and in Maker; replace them with what runs now, and fix the two tests on main that fail after PR-S's squash merge (eval SHA unreachable) and with the render's temp path length (YAML folding)"
---

# SPEC — retired-text (retired-feature text in 0.64.0 renders, and two tests broken on main)

## 🎯 Intent

0.64.0 (PR #36) retired autoloop, autopilot, the loop and the executor agent, but rendered
text still describes them. On 2026-10-17 the DRI found three cases in this repo's own 0.64.0
render (thread "HM-LIGHT-LANE 기록과 구현"):

- `.claude/agents/consensus-arbiter.md:41`: "Invoked by autoloop iteration boundary …"
- `.claude/agents/code-verifier.md:263`: "Findings are proposals; the executor agent applies them."
  This comes from the reviewer hard-rules partial, which the lens reviewers include too.
- `.claude/settings.json:9,25` and `.codex/hooks.json:62`: `"statusMessage": "Snapshotting autoloop progress..."`

A grep of the same render (main 79b16a99: `.claude/`, `.codex/`, `.agents/`) found more of
the same kind:

- `commands/hm/health.md:152-155`: the "## Autoloop behavior" section and "autoloop must not
  synthesize a default answer".
- `skills/worktree-isolator/SKILL.md:36,64`: the "Autoloop iteration boundaries" trigger and
  "issued by the executor agent".
- `skills/intent-layer/SKILL.md:120`: "the autopilot gate reads the approval you record".
- `skills/maker/SKILL.md`:
  - Maker runs `hm autopilot narrow` when autopilot is active.
  - It lists **autopilot** in the briefing.
  - It says "Never arm autopilot".
  - It grants `Bash(<hm> autopilot narrow:*)`.

  No 0.64.0 stage advances under autopilot, and no rendered hook or command arms it.

None of these changes behaviour on its own. They tell the model about something that no
longer exists: Maker carries a dead step on every start, and an agent prompt names a wrong
trigger. The status message is the only one users see, and only on compaction.

The DRI said "응 진행해" to fixing these as phase 2's first task, together with two tests
found failing on main the same day:

- **`tests/integration/test_overhaul_p1_ship_bar.py::test_ac010_scorecard_meets_bar`** fails
  on main with "no eval rows on a harness SHA reachable from HEAD and not from db19f023".
  - The 72 rows carry `harness_sha` a2fe560a4018, a commit on the PR-S branch.
  - The squash merge (8140dd86) left that commit unreachable from main.
  - Both commits have the same trees, `src` 79827bd4 and `scripts` f18284bf, so the harness
    that was measured is the harness that was merged.
- **`tests/integration/test_overhaul_p1_eval3_replay.py::test_ac006_section_verdicts_match_golden`**
  fails from the main checkout and passes in a worktree.
  - The precondition digest of `.claude/skills/maker/SKILL.md` differs.
  - The render's install ref, a pytest temp path, sits in Maker's YAML `allowed-tools`.
  - YAML folds that line at a width that depends on the path's length.
  - The digest replaces the ref with `<REF>` after folding, so the folded whitespace stays in
    the hashed text.

## 📐 Outcomes

1. Every rendered file that comes from a touched template has no retired-feature token. This
   covers Side and Production, with targets claude-code and codex. Each replaced text states
   what runs now.
2. Re-rendering over an existing `settings.json` or `.codex/hooks.json` replaces the old status
   message in place, in every matcher group the harness owns, and does not duplicate the hook.
   A group the user extended (a mixed group) is kept as it is, old message included. That is
   the existing user-state contract, and this SPEC does not change it.
3. Maker's `allowed-tools` is `world_model`, `tail`, `grep` and `printf`, and its body has no
   autopilot step. The docs that describe Maker's grant or start (CLAUDE.md, `docs/reference/world-model.md`,
   `docs/ARCHITECTURE.md`, both READMEs) say the same.
4. On main, `test_ac010_scorecard_meets_bar` passes. It counts rows whose recorded SHA a
   committed alias maps to a commit on this harness. The alias is checked by tree hash, so it
   holds without the unreachable commit.
5. The eval-3 replay precondition is the same for any install-ref length. Its manifest is
   recomputed from the 36 original eval-3 harness commits, and that provenance is committed.

## 🎬 In-Scope Scenarios

### S1 — A fresh render says what runs now
- **Given** a project rendered with this change (Side and Production; claude-code + codex)
- **When** the files rendered from the touched templates are searched case-insensitively for
  `autoloop`, `autopilot` and `executor agent`
- **Then** nothing is found, and the AC-002 replacement texts are present.

### S2 — An upgrade replaces the status message instead of duplicating the hook
- **Given** a project whose `settings.json` and `.codex/hooks.json` were rendered by 0.64.0
  (old message), plus one user hook in its own group on the event that runs `flush_session`
  (PreCompact in `settings.json`, Stop in `.codex/hooks.json`)
- **When** `make` re-renders it with this change
- **Then** every harness-owned group holding `flush_session` has exactly one `flush_session`
  entry, carrying the new message, and the user's group is unchanged.

### S3 — A user-extended group is left alone
- **Given** the same project, but the user appended their command into our `flush_session` group
- **When** `make` re-renders it
- **Then** that group is kept byte-for-byte (old message included), and the user command survives.

### S4 — Maker no longer touches autopilot
- **Given** a rendered Maker SKILL.md (each `_CONFIGS` variant of the front-door render test)
- **When** its frontmatter and body are read
- **Then** `allowed-tools` is exactly `world_model:*`, `tail:*`, `grep:*` and `printf:*`
  (scoped to this harness's `hm`). The body has no autopilot step, and the routing table checks
  of `test_ac007_ask_to_end_stage` still pass.

### S5 — A squash-merged eval still counts
- **Given** `docs/evals/results.jsonl` rows with `harness_sha` a2fe560a…, and an alias entry
  `{source: a2fe560a…, target: 8140dd86…, src_tree: 79827bd4…, scripts_tree: f18284bf…}`
- **When** the ship-bar test runs on main, with or without a2fe560a in the clone
- **Then** the rows count, because the target is on this harness and its `src`/`scripts` trees
  equal the recorded ones, and the bar is evaluated.
- **And** an alias fails the test when its target is not on this harness or its target's trees
  differ.

### S6 — The replay precondition ignores the temp path's length
- **Given** Maker frontmatter rendered with install refs of different lengths
- **When** `harness_digest`'s normalisation hashes them
- **Then** the digests are equal. The committed manifest equals the recorded digest of the 36
  originals, and when those originals are on disk a recompute matches.

## 🚫 Non-Goals

- **The `autopilot` Python module.** It keeps its CLI, the digest's `autopilot` field and its
  tests. Phase 1 removed prompt surface only.
- **`templates/hooks/hooks.json.j2`.** It is the retirement fingerprint for old
  `.claude/hooks/hooks.json` copies (`render._STALE_HOOKS_JSON_TEMPLATE`), so its bytes must
  not change.
- **`commands/hm/make.md`'s "autoloop defaults".** That names the CLI's `--autoloop` flag,
  which still exists. The template is not touched.
- **Mixed groups.** Changing how mixed user/harness hook groups merge (S3 keeps them).
- **Other text.** The `flush_session.py` docstring, Python code, and history docs (CHANGELOG,
  past SPECs and PLANs).
- **Other phase-2 notes.** The HOW-IT-WORKS rewrite, the ADR-048/049 exit codes, the wrapup
  exit-2 action and the `observe` example.
- **The bench.** Changing how it records `harness_sha`.

## 🔒 Constraints

| Constraint | Value |
|---|---|
| Test framework | pytest (`uv run pytest -n auto`) |
| Gate | ruff check, ruff format --check, mypy --strict src tests, pytest; only the 5 known container failures may remain |
| Merge | CI is not used (Actions quota exhausted); merge says "Merged without CI" |
| Prompt surface | `surface_baseline.json` and the command-size ratchet may only shrink or hold for touched files; any change is recorded in a BASELINE-DELTA |
| Goldens | `tests/fixtures/strictness_reference/*/settings.json` re-captured, not hand-edited |
| Approved oracles | Edits to SPEC-maker-front-door-improvements' tests are limited to the ones AC-004 names |

## ⚠️ Irreversible Decisions

| ID | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Maker's `allowed-tools` drops `Bash(<hm> autopilot narrow:*)`, and Maker no longer narrows autopilot. This reverses SPEC-maker-front-door-improvements IRR-005 ("Maker may narrow the session's autopilot pipeline"). | security/permission boundary | It narrows a pre-approved grant for a retired feature. That is cheap to undo, but it is a permission-boundary change that reverses an approved decision, so the DRI decides it. A user who arms autopilot by hand gets a permission prompt for `narrow` instead of a silent run. |

## ✅ Acceptance Criteria

### AC-001: Touched renders contain no retired-feature token
Render this repo's templates for Side and Production (targets claude-code,codex, default
strictness, `--second-opinion-models codex` so the second-opinion agents render). Then check these rendered files under `.claude/` and `.agents/`, plus
`.codex/hooks.json` and `.codex/agents/*.toml`:

- consensus-arbiter;
- every agent that includes the reviewer hard-rules partial;
- `commands/hm/health.md`;
- `skills/worktree-isolator/SKILL.md`, `skills/intent-layer/SKILL.md` and `skills/<handle>/SKILL.md` (Maker);
- `settings.json` and `.codex/hooks.json`.

None of them may contain `autoloop`, `autopilot` or `executor agent`, matched case-insensitively.

### AC-002: The replaced texts say what runs now
The same renders contain these texts:

| File | Required text |
|---|---|
| consensus-arbiter | "Invoked by the review step of `/hm:execute` when second-opinion voters disagree on a finding's severity" |
| code-verifier | "Findings are proposals; the main session applies them." |
| every `flush_session` hook entry in `settings.json` and `.codex/hooks.json` | `statusMessage` "Snapshotting session progress..." |
| health | "## Non-interactive behavior" |
| worktree-isolator | "issued in the task worktree" |
| intent-layer | "`hm intent status` reports the approval you record" |

### AC-003: Re-rendering replaces the status message in harness-owned groups, keeps mixed ones
Start from a project rendered by main 79b16a99 (claude-code + codex).

**Case (a).** Add one user hook in its own group, on the event that runs `flush_session`
(PreCompact in `settings.json`, Stop in `.codex/hooks.json`), to each file, then re-render
with this change. In each file:

- every group that contains `flush_session` contains exactly one `flush_session` entry;
- every `flush_session` entry carries the new `statusMessage`;
- the user's group is unchanged.

**Case (b).** Append the user command into our `flush_session` group instead, then re-render.
That group is kept byte-for-byte, and the user command survives.

### AC-004: Maker grants and runs nothing of autopilot
For every `_CONFIGS` variant in `tests/render/test_render_maker_front_door.py`:

- Maker's `allowed-tools` is exactly `Bash({hm} world_model:*)`, `Bash(tail:*)`,
  `Bash(grep:*)`, `Bash(printf:*)`;
- its body does not contain `autopilot`.

The front-door test changes in exactly two places: `_ALLOWED_TOOLS` loses
`Bash({hm} autopilot narrow:*)`, and `test_ac007_ask_to_end_stage` loses the
`assert _NARROW in text` line. Its other assertions stay and pass.

### AC-005: A tree-checked squash alias counts toward the ship bar
Each entry of `tests/fixtures/overhaul_p1/harness_sha_aliases.json` records `source`,
`target`, `src_tree` and `scripts_tree`. `on_this_harness(sha)` is true when either:

- the SHA is reachable from HEAD and not from db19f023, as today; or
- `sha` is an alias source whose target satisfies that test, and whose `git rev-parse <target>:src`
  and `<target>:scripts` equal `src_tree` and `scripts_tree`.

An alias whose target fails either check makes the test fail. When git knows the source, the
source's trees must equal the recorded ones too. With this change on main,
`test_ac010_scorecard_meets_bar` passes.

### AC-006: The replay digest is independent of the install ref's length
- **Normalisation.** `harness_digest` collapses whitespace runs inside the YAML frontmatter of
  `.md` files only.
- **Property.** For any install ref of 8 to 200 characters drawn from `[A-Za-z0-9/._-]`, render
  Maker's `allowed-tools` with PyYAML's dump and normalise it. Every ref gives one digest.
- **Provenance.** `tests/fixtures/hm_check_eval3/harness_manifest_provenance.json` records the
  36 originals' run ids and harness commit SHAs, and the digest that each one produced under
  the new normalisation.
  - The test asserts that the committed manifest equals every recorded digest.
  - When `/var/tmp/hm-eval-3/runs` exists, the test recomputes each digest and compares it.
  - A committed script regenerates the provenance.
- **Replay.** `test_ac006_section_verdicts_match_golden` passes from both the main checkout and
  a worktree.

### AC-007: Docs describe Maker without the autopilot grant
None of these mentions `autopilot narrow` as something Maker runs or is granted:

- CLAUDE.md's World model section;
- `docs/ARCHITECTURE.md`;
- `README.md` and `README.ko.md`;
- `docs/reference/world-model.md`'s grant list and Start section.

`docs/reference/world-model.md` may still describe the Python `hm autopilot narrow` command,
marked as no longer used by Maker.

## 🧪 Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit (render) | AC-001, AC-002: new render test over Side + Production |
| S2, S3 | unit (render) | AC-003: upgrade over the 79b16a99 render, cases (a) and (b), both hook files |
| S4 | unit (render) | AC-004: `tests/render/test_render_maker_front_door.py` |
| S5 | unit + integration | AC-005: alias unit tests + `test_ac010_scorecard_meets_bar` on main |
| S6 | unit + integration | AC-006: property test, provenance test, replay test |
| Outcome 3 | unit (docs) | AC-007: a grep test over the named docs |

## ❓ Open Questions

(none open. The spec-validator's 9 critiques of 2026-10-17 were all folded in: the AC-003
predicate and mixed-group case; AC-004's named test edits and the IRR-005 reversal; AC-007 for
the docs; case-insensitive tokens in AC-001; the tree-hash alias; committed replay provenance;
`.agents/` in scope; frontmatter-only collapse; `.codex/hooks.json` in AC-003.)

## 🔧 Refinement Decisions

- **Interview.** The DRI scoped the task in the thread: the three phrases they found, the ones
  the grep found, and the two tests, with "응 진행해". The remaining choices below are defaults,
  and they go to the DRI on the approval card.
- **Lane: full.** About 20 files across templates, tests, fixtures and docs, plus a permission
  change (IRR-001).
- **Intent: none.** No active or proposed intent covers retired-text cleanup. HM-LIGHT-LANE is
  about cost, and UNDERSTANDING-HANDOFF is about the wrapup summary.
- **Maker is in scope (default).** It is the same kind of text as the agent texts, and its dead
  step runs on every Maker start. Leaving it for the HOW-IT-WORKS rewrite would keep a
  permission grant for a retired feature.
- **Mixed groups stay as they are (default).** Refreshing a field inside a group the user owns
  would change the merge contract for a cosmetic string.
- **Alias, not a data rewrite (default).** Rewriting `harness_sha` in `results.jsonl` would
  change recorded measurement data. A tree-hash alias keeps the record and states the squash
  mapping in a form git can check without the lost commit.
- **Frontmatter-only whitespace collapse (default).** YAML folds a plain scalar only at a space,
  so collapsing whitespace runs in frontmatter makes the digest independent of where the fold
  falls. Body text, JSON and `harness.yaml` stay pinned byte for byte.
- **Status message text.** "Snapshotting session progress..." says what `flush_session` does
  (it snapshots the progress file) without naming its event. It runs on PreCompact in
  Claude Code and on Stop in Codex, so "before compaction" would be wrong for Codex.
  Amended after the RED run showed the Codex event (re-approval needed).
