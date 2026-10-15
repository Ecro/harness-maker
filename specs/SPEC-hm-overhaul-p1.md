---
type: spec
task_slug: hm-overhaul-p1
status: draft
created: 2026-10-15
tags: [harness-maker, spec, python, overhaul, stages, hooks, cli, cursor, brownfield]
test_framework: pytest
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
summary: "Overhaul phase 1: 4 stages, one hm check gate, Cursor removed, only COMP/HOST steps cut"
---

# SPEC: harness-maker overhaul, phase 1 (stage collapse)

## 🎯 Intent
In eval 3 (tiers 1–2, 36 runs per arm), hm cost 26.4x plain on tier 1 and 22.7x on tier 2. It solved
34/36 tasks against plain's 36/36. Its one measured quality lead was fewer new type errors per run
(0.27 → 0.07 on t1), and that lead came from the deterministic gates. About 73% of the cost is carried
context, and the stage prose drives it: the five eval-path stage prompts carry about 207k chars into
the main session and about 70k into subagents.

The DRI approved the overhaul draft (`PLAN-overhaul-draft.md`, section 6) on 2026-10-15, then refined it
in typed corrections the same day. The governing rule (23:15Z) frames this SPEC. harness-maker keeps
production-level code quality, keeps shipped products maintainable, and keeps raising the DRI's
understanding. Every net-positive function stays. Only two kinds of thing go: what model progress made
unnecessary, and areas the model or the host already handles well. The repo's own classification
(`step_sensitivity.py`) makes that rule checkable:
- **COMP** (compensating prose) and **HOST** (the host does it natively) are cut.
- **INV** (cross-session state, deterministic oracles, human lock-in, heterogeneous models) is kept.
- **TUNE** is decided only on a measurement.

## 🌅 Outcomes
- Four stages ship: `/hm:research`, `/hm:spec`, `/hm:execute` and `/hm:wrapup`. Each is one
  self-contained file, so no helper prose is read at run time. Every deterministic check runs as one
  exit code, `hm check`, whose result the prompt relays.
- SDD and TDD stay intact.
  - The SPEC and its `.machine.yaml` stay the durable, accumulating artifact: schema v3, the approval
    stamp, oracle fields, `test_ids` and `mark-tested`, all unchanged.
  - `/hm:execute` writes the AC tests first, shows them RED through the CLI, implements to GREEN, and
    binds them to the SPEC.
  - `hm check` refuses an AC that has no passing mapped test.
- The per-task worktree lifecycle, the full `/hm:spec` interview, the spec-validator, memory capture,
  `permission_gate`, the PreCompact flush and the approval stamps behave as they do at db19f023.
- One reviewer runs by default.
- These stay opt-in: the cross-model second opinion, mutation testing (`hm check --mutation`), Second
  Brain promotion and delegation.
- CVE scanning runs in `hm check`.
- The Cursor target is gone. An existing Cursor install upgrades without errors and without losing
  user edits.
- The eval re-run meets the ship bar. On tier 1 the cost ratio is ≤ 8x, and hm's hidden-test pass rate
  is no lower than plain's.

## 📋 In-Scope Scenarios

### S1: render per target (AC-001, AC-004)
**Given** `hm make <dir> --autoloop --preset Side|Production` with targets `[claude-code]` or
`[claude-code, codex]`, worktree on or off, and comprehension depth `standard` or `deep`
**When** the render completes
**Then** exactly the AC-004 file set exists, within its char budgets.
**And** no rendered file names a removed command, except inside a retirement notice.

### S2: one gate, one exit code (AC-005, AC-006)
**Given** a project with a SPEC for `<slug>` and a change in the working tree
**When** `/hm:execute` or `/hm:wrapup` runs `hm check --slug <slug>`
**Then** it prints one JSON line, exits per the AC-005 table, and leaves the tree byte-identical.

### S3: RED before code (AC-005)
**Given** AC tests written from the SPEC and recorded in `test_ids`, with no implementation yet
**When** `hm check --red --slug <slug>` runs
**Then** it exits 0 only if every testable AC has a test that fails for a real reason.

### S4: brownfield upgrade (AC-002, AC-007, AC-008)
**Given** a 0.62 rendered tree, which may be pristine, user-edited, or carry a Cursor target
**When** the user re-runs `/hm:make`
**Then**:
- Retired files are deleted only when pristine.
- Edited ones are kept with one warning each.
- User blocks and user hooks survive.
- No hook command left on disk errors.

### S5: kept behaviour (AC-009)
**Given** the same inputs at db19f023 and after this change
**When** a kept hook, kept CLI or kept stage invocation runs
**Then** its observable output is the same.

### S6: the classification rule holds (AC-003)
**Given** every stage heading registered at db19f023
**When** the cut ledger below is checked against the registry
**Then** every cut cites COMP, HOST, a TUNE measurement, a vacuous precondition, or a DRI lock-in.
**And** no INV heading is cut.

### S7: ship bar (AC-010)
**Given** the eval re-run on tiers 1–2, 3 runs per cell
**When** the scorecard is published
**Then** the t1 cost ratio is ≤ 8x and hm's hidden-test pass rate is at least plain's.

## ✔️ Acceptance Criteria

PR tags: **[C]** is the Cursor-removal PR and **[S]** is the stage-collapse PR (see Constraints, *Split*).

### AC-001: Cursor leaves the render and the code without changing any other output
**[C]** The render of targets T at HEAD equals the db19f023 render of T minus `cursor`, where an empty
result becomes `[claude-code]`. Comparison ignores provenance fields, and every other changed hunk
removes a line that mentions Cursor. These are deleted:
- the Cursor-only paths in `render.py` and `synthesize.py`;
- `templates/cursor/`;
- `.cursor-plugin/plugin.json`.

Version sync spans four files. `hook_host` and the `.cursor` sweep root stay.

### AC-002: An existing Cursor install upgrades with one warning and no lost edits
**[C]** The golden table below covers `targets` holding `cursor`, `agent_models.*.cursor`, pristine,
edited and merged `.cursor/` files, and a cursor-only target list.

### AC-003: Every 0.62 stage heading is disposed of according to its class
**[S]** The cut ledger in this SPEC covers every `step_sensitivity.REGISTRY` key at db19f023.
- No INV heading is cut.
- A COMP or HOST cut cites its class.
- A TUNE decision cites a measurement.
- A vacuous heading names the change that removed its input.
- A DRI override names the lock-in.

### AC-004: The rendered surface per target holds the kept set within its char budgets
**[S]** The file set, the hook commands and the budgets in the AC-004 tables below hold on the render.
Each stage file is self-contained. The DRI-decided defaults appear as table rows, so flipping one
changes only its rows.

### AC-005: hm check exits per its contract and never writes the tree
**[S]** The exit codes, sections and modes are as tabled. The gate subprocesses run with
`PYTHONDONTWRITEBYTECODE=1`. The project tree's tracked and unignored bytes are the same before and
after a run.

### AC-006: hm check on the 36 eval-3 hm trees reproduces the recorded section verdicts
**[S]** The run uses copies of the eval-3 hm work trees. Golden per-section verdicts were recorded on
2026-10-15 before implementation, and the negative controls flip exactly their own section.

### AC-007: Upgrading a 0.62 tree sweeps only pristine retired files and keeps every user edit
**[S]** Retired stage, command, helper, agent and skill files go only when pristine. User-edited files
and `@hm:user:*` blocks survive. Settings hooks lose only the retired invocations.

### AC-008: No hook command a 0.62 render shipped errors after the upgrade
**[C, S]** This covers every command in any 0.62 `.claude/settings.json`, `.codex/hooks.json` or
`.cursor/hooks.json`. Each one, run with the new package on any payload, exits 0, or exits 2 only where
db19f023 also exited 2, and never prints a traceback.

### AC-009: Kept behaviour is unchanged from db19f023
**[S]** These match db19f023 on the same inputs:
- `permission_gate`, `flush_session`, `sessionstart_drift`, `sessionid_envfile`, `worktree_gate` and
  `loop_gate --mode stop-hook`;
- `hm world_model digest`;
- `spec_machine approve`, `approval-status` and `mark-tested`;
- the worktree, land and memory CLI invocations the stages emit;
- the bench contract.

### AC-010: The eval re-run meets the ship bar
**[S]** On tier 1 the cost ratio is ≤ 8x, and on tiers 1–2 hm's hidden-test pass rate is ≥ plain's.

## AC-004 tables (the rendered surface)

**Defaults as rows.** Each line below is one row. Flipping a decision edits only its own row.

| Id | Decision | Default | Rows it owns |
|---|---|---|---|
| D-1 | One reviewer runs by default (DRI, Q1, 2026-10-15) | on | `code-reviewer` agent; review step in execute |
| D-2 | Targets claude-code + codex (DRI correction 22:54Z) | both | the codex rows |
| D-3 | spec-validator stays as one advisory pass (DRI card b) | on | `spec-validator` agent; dispatch in spec |
| D-4 | Second Brain promotion is opt-in (DRI card a) | off | the wrapup promotion block renders only when `second_brain.enabled` |
| D-5 | Mutation is opt-in through `hm check --mutation` (DRI card c) | off | no mutation call in execute |
| D-6 | `/hm:metrics` stays as a slim command (default pending the DRI's card) | on | the `metrics.md` row |
| D-7 | `/hm:research` stays: INV under the 23:15Z rule (see Open Questions) | on | the `research.md` row |

**Rendered for `[claude-code]`**, rows marked † only when the condition holds:

| Path | Budget (chars, measured with `wc -c` on the render) |
|---|---|
| `.claude/commands/hm/spec.md` | ≤ 6,500 base; +1,500 when worktree on; +800 at depth `deep` |
| `.claude/commands/hm/execute.md` | ≤ 7,000; +1,500 when worktree on |
| `.claude/commands/hm/wrapup.md` | ≤ 3,500; +2,800 when worktree on |
| `.claude/commands/hm/research.md` (D-7) | ≤ 8,000 |
| `.claude/commands/hm/metrics.md` (D-6) | ≤ 3,000 |
| `.claude/commands/hm/{make,help,health,uninstall}.md` | ≤ db19f023 size; help lists only rendered commands |
| `.claude/agents/code-reviewer.md` (D-1) | ≤ 3,000 |
| `.claude/agents/spec-validator.md` (D-3), `judgment-reviewer.md` | ≤ db19f023 size |
| † `.claude/agents/{code-verifier,consensus-arbiter}.md` | `second_opinion.models` non-empty |
| † `.claude/agents/stage-delegate.md` | `delegation.stages` non-empty |
| `.claude/skills/{maker,intent-layer,project-knowledge,agent-quality-rubric,ai-readiness-rubric,context-linter,worktree-isolator}/` | unchanged content |
| † `.claude/skills/second-opinion-gate/` | `second_opinion.models` non-empty |
| `.claude/{settings.json,harness.yaml,intent.yaml}`, `.claude/memory/*`, `.claude/rubrics/*`, `.claude/observability/dashboard.md`, `CLAUDE.md` | present; CLAUDE.md names no removed command |

Opt-in blocks (second opinion, delegation, Second Brain) add ≤ 1,500 chars each to their stage and are
outside the base budget.

**Not rendered, on any target:**
- `.claude/commands/hm/{review,verify,configure,loop,loop-p5-batch}.md`;
- `.claude/stages/`;
- `.claude/hm/`;
- the agents `test-reviewer`, `stuck`, `security-auditor`, `executor`, `autoloop-coder` and the five
  lens reviewers;
- the skills `security-scanner`, `verify-before-completion`, `targeted-test-selection`,
  `conditional-router`, `autoloop-driver` and `refdocs-search`;
- `.cursor/`.

**Codex additions (D-2):**
- `.agents/skills/hm-{research,spec,execute,wrapup,help}/SKILL.md`, which inline the same text under
  the same budgets +3% (the `Bash("…")` wrappers);
- `.agents/skills/` for each kept skill;
- `.codex/agents/<name>.toml` and its `[agents.<name>]` entry in `config.toml`, for each rendered agent;
- `.codex/hooks.json`;
- `AGENTS.md`.

Absent: `.agents/skills/hm-{review,verify,loop}`.

**Hook commands rendered:**

| File | Commands |
|---|---|
| `.claude/settings.json` | PreToolUse Bash `permission_gate --subordinate-to-deny-dangerous`; PreToolUse Write\|Edit\|MultiEdit `worktree_gate`; Production only: `spec_gate`; PreCompact auto+manual `flush_session` and `worktree span-end`; Stop `loop_gate --mode stop-hook` and `worktree span-end`; SessionStart `sessionid_envfile` |
| `.codex/hooks.json` | PermissionRequest and PreToolUse Bash `permission_gate`; SessionStart `sessionstart_drift` and `sessionid_envfile`; Stop `loop_gate --mode stop-hook` and `flush_session` |
| plugin `hooks/hooks.json` | unchanged (`sessionstart_drift`) |

**Stage content (substring golden):**
- `spec.md`:
  - `hm worktree task-preflight` (worktree on);
  - the six categories;
  - "Approve this SPEC and end interview";
  - `oracle_source`;
  - `irreversible_decisions`;
  - the design brief and round-state blocks;
  - at depth `deep`, the per-question envelope and the closing readback;
  - `spec_machine check --all`;
  - the `spec-validator` dispatch (D-3);
  - `spec_machine approve`;
  - the `uv run --with <path> hm ` prefix.
- `execute.md`:
  - `task-preflight` (worktree on);
  - `hm check --red`, then `hm check`;
  - `spec_machine mark-tested`;
  - the `code-reviewer` dispatch (D-1);
  - no `spec_mutation` (D-5).
- `wrapup.md`:
  - `hm check`;
  - `memory_md upsert-wiki` and `memory_md upsert-failure`;
  - `find-unjudged` and `mark-judged`;
  - `wrapup_land`;
  - `task-land` and `commit-base-memory` (worktree on);
  - `second_brain promote` only when enabled (D-4).

## AC-005 table (`hm check` contract)

`hm check --slug <slug> [--root .] [--red [--green-ok AC-NNN]...] [--mutation] [--offline] [--harness]`
prints one JSON line. The line holds `{exit, sections: {approval, gates, ac, review, security, cve,
mutation?, harness?}}`, and each section is `{ok, ...detail}`.

| Exit | Meaning | Prompt's action |
|---|---|---|
| 0 | every gating section ok | proceed |
| 1 | a gate, AC test, RED check, scoped security finding, blocking CVE, open review finding or opted-in mutation failed | fix what it names and rerun (execute caps this at 2 rounds) |
| 2 | usage error (argparse) | fix the call |
| 3 | degraded: no runnable gate could be derived, or `--red` found no testable AC | report; never read it as a pass |
| 4 | the tree changed during the run | rerun once |
| 5 | approval is required but missing, or the stamp is invalid or malformed | ask the DRI or stop |

When several apply, precedence is 2 > 1 > 4 > 3 > 5 > 0. Exit 5 is reported last, so it means
"everything else is green; only the human is missing".

**Sections.**
- `approval`: from `spec_machine.approval_state`.
  - `approved` and `exempt` pass.
  - `missing` and `pending` pass only at `autonomy.level: auto_full`; at any other level they give 5.
  - `invalid`, `malformed` and `no_spec` always give 5.
- `gates`: run with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.
  - Source: `verification_plan.read_plan(...).primary_commands()`.
  - With no CI file, the source is `verification_cache.spec_plan` with the project's `.venv/bin/python`
    only.
  - `reviewers.mechanical_checks` are added.
  - If none can be derived, exit 3.
- `ac`: every AC that is neither superseded nor `type: judgment` needs `pending_test: false`, non-empty
  `test_ids`, and every listed test passing in one pytest run.
  - A `judgment` AC needs a current `pass` verdict instead: `find_unjudged` reports none for it.
  - A SPEC with `ac: []` fails.
- `review`: when a `REVIEW-<slug>-*.md` exists, no finding may lack a disposition. If none exists, the
  section is reported and does not gate.
- `security`: `secscan.secrets` runs over changed paths only, and `secscan.hook_injection` runs over
  changed hook files only (`.claude/settings.json`, `.codex/hooks.json`, `.cursor/hooks.json`).
  - Changed paths are `git diff HEAD`, staged, and untracked-unignored.
  - A finding in an untouched path is counted as `out_of_scope` and does not gate.
  - An import that resolves inside the project root never counts.
  - `prompt_injection`, `permissions` and `hallucination` do not run here; `hm cli security-scan`
    keeps them.
- `cve`: on by default, see IRR-004.
  - A CVE in a dependency the change added or re-pinned (the `uv.lock`/`pyproject.toml` diff against
    HEAD) gates.
  - A CVE in an untouched dependency is listed as `existing` and does not gate.
  - A failed lookup gives `cve: unavailable`, which warns and does not gate.
  - `--offline` skips the lookup and says so.
- `--red`:
  - Each testable AC needs at least one listed test that fails or errors for a real reason.
  - These do not count as RED: `SyntaxError` or `IndentationError` in the test file, a fixture not
    found, or a node id that does not exist. Any of them gives exit 1.
  - A test that passes before the code exists is listed under `green_before`.
  - An AC whose tests all pass gives 1, unless it was named with `--green-ok`. A waived AC is echoed.
- `--mutation`: `spec_mutation gate --tier <verification_tier>` over `paths_to_mutate`. If mutmut is
  absent, a skip notice is printed and the run passes, as at db19f023.
- `--harness`: the structural layer of `hm cli health`.

## AC-002 table (Cursor brownfield)

| Input (0.62 tree, then `make --update` at HEAD) | Expected |
|---|---|
| targets `[claude-code, cursor, codex]`, `.cursor/*` pristine | one `cursor target removed` warning; `.cursor/rules/harness.mdc`, `mcp.json` and `hooks.json` deleted; empty `.cursor/` removed; harness.yaml `targets: [claude-code, codex]` |
| as row 1, one byte of `harness.mdc` edited | that file is kept byte-identical with one KEPT warning; the other two are deleted |
| as row 1, `hooks.json` with a user entry folded in by an earlier merge (its hash is in the manifest) | kept byte-identical, with one KEPT warning |
| as row 1, `mcp.json` edited | kept |
| targets `[cursor]` | one warning; targets become `[claude-code]` |
| `agent_models.code-reviewer.cursor: <alias>` | one warning; the key is ignored and the render succeeds |
| `hm make --targets claude-code,cursor` | the same as row 1 for a fresh render |
| a fresh tree with no Cursor anywhere | no warning |

"Pristine" means two things: the on-disk sha256 equals the manifest's recorded hash, and, for
`hooks.json`, every entry is harness-managed. A harness-managed entry carries the `HM_HOOK_HOST=cursor`
prefix and a `<HM>:`-normalisable command.

## 🚫 Non-Goals
- Deleting Python modules, except the Cursor-only code AC-001 names. Phase 2 deletes unreachable CLI.
- A TASK file or any new state format. Progress stays in the existing `PLAN-<slug>.md`, which holds no
  ACs and points at the SPEC.
- Any change to `docs/reference/multi-session-worktree.md` or to the worktree CLI.
- Changing `machine.yaml` schema v3, the approval hash, or `spec_machine` semantics.
- Reclassifying `step_sensitivity` entries. AC-003 checks the ledger against the registry; it does not
  edit the registry.
- Tier-3 evaluation, and the Phase 2–4 deletions.
- Supporting Cursor. Cursor may still read `.claude/` natively, without any guarantee.

## ⚠️ Constraints
| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest`; tests under `tests/unit/test_overhaul_p1_*.py`, plus `tests/integration/` for AC-006 and AC-010 | repo standard |
| Split | **PR-C** (0.63.0): AC-001, 002, 008. **PR-S** (0.64.0): AC-003…010, re-checking 008. C ships first | PR-C is mechanical and has an exact differential oracle. Shipping it first removes the flat-schema and Cursor test rows that PR-S would otherwise rewrite and then delete |
| Version sync | PR-C makes it four files; each PR is one minor bump with a CHANGELOG `### Removed` | CLAUDE.md release policy |
| Retired hooks | append `telemetry`, `hooks.post_write_reminder` and `hooks.autopilot_autoarm` to `render._HARNESS_RETIRED_HOOK_INVOCATIONS`; their `python -m` entry points become exit-0 stubs for 2 minors; library functions stay | the append-only retire path; the stubs cover kept user copies |
| Kept hooks | `loop_gate`, `worktree span-end` and `sessionid_envfile` stay rendered | the multi-session doc must not change; `HM_SESSION_ID` and the stage spans feed task-preflight and the digest |
| Cursor sweep | add `.cursor/hooks.json` to `reconcile._SWEEP_NEVER_DELETE`, with a pristine-exact retire path like `cli._retire_stale_hooks_json`; `.cursor` stays in `_SWEEP_ROOTS` and in the backup | the manifest hash of a merged hooks file can include user entries |
| `hook_host` | keep `is_claude_copy_in_cursor` and `tests/unit/test_hook_host.py` until the stubs go | a kept `.cursor/hooks.json` still runs in Cursor, and Cursor imports `.claude/settings.json` too; without the back-off, `permission_gate` and `flush_session` fire twice. Once the file is gone, the Claude copy runs alone, so Cursor users keep `permission_gate` |
| Frozen template | `templates/hooks/hooks.json.j2` is unchanged | `_retire_stale_hooks_json` compares against it |
| User blocks | the new stage templates keep the block ids `@hm:user:extra-quality-checks` and `@hm:user:extensions` | MERGE_BLOCK carries user content across |
| Bench | keep accepting `--autoloop`, `--preset` and `--autonomy-level auto_full`; `.claude/commands/hm/spec.md` matches `uv run --with (\S+) hm `; the `/hm:spec ` prefix works | `scripts/bench_light_lane.py`; `runner_hash` changes |
| Config | `autonomy.autopilot_persistent` defaults to false; an explicit `true` gives one "autopilot retired" warning and is inert | DRI part 5 |
| Registry | the new headings are registered with their classes, carried from the ledger | `test_step_sensitivity_registry.py` keeps guarding |
| No writes | `hm check` writes nothing under the project root; it calls the `secscan` modules directly, not `security_scanner.scan_all`, which persists findings | the tree-change exit 4 must not fire on itself |
| CLI wiring | `check` is added to `hm._DISPATCHABLE` and `command_registry.MODULES` | the structural CLI tests |
| Environment | external calls (OSV) are mocked in unit tests and real only under `INTEGRATION=1` | CLAUDE.md test policy |

## 🔒 Irreversible Decisions
| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Drop the Cursor target. `targets: cursor` is ignored with a warning, `.cursor/` is no longer rendered, `.cursor-plugin/plugin.json` is deleted, version sync drops to four files, and the Cursor-only Python is deleted | public API/CLI contract | Users and the Cursor Marketplace lose a supported target. Restoring it means restoring the code and the listing |
| IRR-002 | `/hm:review`, `/hm:verify`, `/hm:configure` and `/hm:loop` stop rendering, as do Codex `$hm-review`, `$hm-verify` and `$hm-loop` | public API/CLI contract | Scripts and habits calling them break. Kept user-edited copies call CLI that Phase 2 may delete |
| IRR-003 | New `hm check` CLI: flags, JSON shape, and exit codes 0/1/2/3/4/5 with their precedence | public API/CLI contract | Stage prompts and users will script against it |
| IRR-004 | `hm check` security scope covers only touched paths, never counts self-imports, gates only on secrets and hook-injection, and checks CVEs by default with gating only on added or re-pinned dependencies | security/permission boundary | This decides what can ship. A finding in an untouched file or dependency is reported but never blocks |
| IRR-005 | Retire the `telemetry`, `post_write_reminder` and `autopilot_autoarm` hooks through the append-only retired set; stub their entry points; end autopilot auto-advance | public API/CLI contract | The retire set is append-only by test, and re-rendering strips these from every user's settings |

## ✅ Verification
| Scenario | Mode | Oracle |
|---|---|---|
| S1 | unit | differential against db19f023 (AC-001); golden tables (AC-004) |
| S2, S3 | unit | golden exit table and tree-bytes property (AC-005) |
| S2 | integration | golden: eval-3 section verdicts recorded 2026-10-15 (AC-006) |
| S4 | unit + integration | golden tables (AC-002, AC-007); property over hook commands (AC-008) |
| S5 | unit | differential against db19f023 modules via `git show` (AC-009) |
| S6 | unit | golden: the db19f023 registry (AC-003) |
| S7 | integration (eval) | golden thresholds from the DRI (AC-010) |

## Cut ledger (AC-003)

Every db19f023 registry heading not listed here is **KEPT** in its stage. Dispositions:
- **CUT-COMP** and **CUT-HOST** cite the class.
- **MOVED** keeps the function in a new owner.
- **VACUOUS** means a listed change removed the heading's input.
- **TUNE-M** is decided on a named measurement.
- **DRI** is a lock-in that overrides the class.

| Stage / heading | Class | Disposition |
|---|---|---|
| research Phase 0.75 | COMP | CUT-COMP |
| spec Step 0 (lane call only) | INV | VACUOUS: no review or verify stage is left to skip; the skip heuristic is kept |
| spec Step 4.6 | TUNE | DRI (card b): kept, one advisory pass |
| execute Step 0.1 | INV | VACUOUS: execute now requires a SPEC, so whether one is needed has a single answer |
| execute Step 0.2, Step 4.5, Step 5 | INV / INV / HOST | VACUOUS: they render only with `loop.enabled`, and `/hm:loop` is not rendered |
| execute Step 1.5 | HOST | CUT-HOST |
| execute Phase A.4, Phase B | INV | MOVED to `hm check --red` |
| execute Phase A.5 | TUNE | TUNE-M: merged into the one reviewer. Run 2 had 2/15 self-blocks on tasks plain passed; in eval 3, 31/36 runs skipped A.5 (light lane) and hm still solved 34/36 |
| execute Phase C.0, Phase D.5 | COMP | CUT-COMP |
| execute Phase D, Step 4.2, Checks 2/4/6 | INV | MOVED to `hm check` (gates, security and cve, ac) |
| review Phase 0 | INV | MOVED to `hm check` gates (`reviewers.mechanical_checks`) |
| review Step 0, 2, 3.3, 3.4, 4e, 5 | INV / TUNE (4e) | MOVED to execute's review step: `review_run` ids, drift against PLAN scope, intent drift, a disposition for every finding, the REVIEW record |
| review Step 1 | INV | VACUOUS: one reviewer, plus any second-opinion voters |
| review Step 3 | TUNE | TUNE-M: fan-out 1. Eval 3 showed no hidden-test or trap gain at tiers 1–2, judge scope 4.73 for plain against 4.00, and a cost of 26.4x |
| review Steps 3.5, 3.6, 4, 4a–4d | INV | MOVED to execute's review step, live when `second_opinion.models` is non-empty (heterogeneous voters, K=2) |
| review Steps C1–C3 | TUNE | TUNE-M: cut. The evidence is at stage level (the eval-3 result; review spends 4.4 VERIFY turns per PRODUCE turn, from RESEARCH-harness-diet); no per-step `measure_cmd` was run. The AC-010 re-run re-measures |
| verify Checks 1–4, 6 | INV | MOVED to `hm check`: review, gates, `--harness`, security, ac (stronger than spec_need) |
| verify Check 5, Step 0.5 | INV | VACUOUS: Check 5 is loop-only, and Step 0.5 has no verify stage left |
| wrapup Step 2, Step 3 | INV | MOVED to `hm check` |
| wrapup Step 3.5 | INV | MOVED to execute: `mark-tested` before `hm check` |
| wrapup Step 7.7 | HOST | DRI (23:10Z): kept with the worktree lifecycle |

**Items that are not headings** (one line each):
- `/hm:review` is CUT-HOST: the host ships `/code-review` and `/security-review`, and its INV steps
  moved as above.
- `/hm:verify` is MOVED to `hm check`.
- `/hm:configure` is MOVED into `/hm:make`, because re-running it reuses the answers.
- `/hm:loop` is CUT-HOST: the host ships `/loop`.
- Autopilot auto-advance is measured net-negative: in eval 2, 36/80 auto-advances were gate-blocked
  and 5/36 runs stalled after spec.
- `.claude/stages/*` has no reader (grep).
- `.claude/hm/*` is folded into the stages, and each line follows its heading's row.
- The `telemetry` hook is CUT-HOST: the host transcript records every tool call, and `economics`
  reads it.
- `post_write_reminder` is CUT-COMP.
- `refdocs-search` is CUT-HOST: the host Grep reaches any folder.
- `conditional-router` and `stuck` are VACUOUS (fan-out 1, A.5 merged).
- `autoloop-driver`, `executor` and `autoloop-coder` are VACUOUS (no loop).
- `security-auditor`, `security-scanner`, `verify-before-completion` and `targeted-test-selection` are
  MOVED to `hm check`.
- `judgment-reviewer` is KEPT: it is the independent oracle for judgment ACs that `hm check` relies on.
- The CVE scan is KEPT in `hm check`.
- The second opinion is KEPT as opt-in (INV, heterogeneous model).

## ❓ Open Questions
1. `/hm:research`: the approved part 5 removed it, but the 23:15Z rule keeps it, because the registry
   grades Phase 1–3 INV `**` and only 0.75 is COMP. This SPEC follows the later rule (D-7). Flipping it
   moves research to IRR-002 and changes only AC-004 rows and AC-003's research row.
2. Ordering is not enforced. Nothing proves RED ran before the code. The RED summary goes into the
   commit body, so the history carries it, but no receipt file is written. A receipt would be a new
   format (an IRR).
3. The `--green-ok` waiver is free text in the call. The reviewer reads it, and nothing else bounds it.
4. A kept `.cursor/hooks.json` whose `uv run --with <path>` names a pruned plugin cache fails before
   any module loads. AC-008 cannot cover this, and Cursor's handling of a non-2 failure is unverified.
5. The budgets are estimates from scratchpad drafts, not implementations: spec ~5.8k, execute ~4.4k,
   wrapup ~3.0–3.2k at default config. The DRI's targets were 6k, 7k and 3k. Wrapup cannot keep memory
   capture and judgment binding under 3k, so this SPEC sets 3,500. Spec is set at 6,500 to leave a
   margin.
6. In eval 3, all 36 hm runs left every AC unbound (`pending_test: true`), and t6-hm-2 had `ac: []`.
   Under the AC rule, `hm check` fails 36/36 of those trees. That failure is the SDD gap the rule
   targets.

## Refinement Decisions
- **Lane `full`** with five irreversible decisions.
- **DRI decisions, 2026-10-15:**
  - Q1: one reviewer by default.
  - Targets claude-code + codex, with Cursor removed (22:54Z; this replaces the Q3 card).
  - The worktree lifecycle and the full interview stay (23:10Z).
  - SDD and TDD stay, with a CLI RED gate and the AC→test rule (23:12Z).
  - Card a: wrapup keeps memory capture, and Second Brain is opt-in.
  - Card b: the spec-validator stays.
  - Card c: mutation is opt-in through `hm check --mutation`.
  - The 23:15Z cut rule, with CVE kept and the second opinion opt-in.
- **Default pending the DRI's card:** `/hm:metrics` stays as a slim command (D-6).
- **A.5 merges into the one reviewer.** Red-correctness becomes mechanical (`--red`). The reviewer sees
  tests and code together, so it can also catch a test weakened during implementation. The trade-off:
  a bad test found after GREEN costs one re-implementation.
- **Legitimate test-free AC type:** only `type: judgment`. It is bound by a current `pass` verdict
  instead, through `judgment-reviewer` → `mark-judged`. Superseded ACs are exempt.
- **CVE on by default.** 0.62's `security-scan` already queried OSV by default, so this adds no new
  egress. The model cannot know CVEs. Shipped products need the check for existing dependencies, so
  those are reported every run. Gating only on dependencies the change touched avoids eval 3's
  every-run failure. A lookup failure never reads as clean.
- **Not retired, against the draft:**
  - `loop_gate`: the multi-session doc is unchanged, and in-flight 0.62 loop markers still need it.
  - `worktree span-end`: the digest's stage and session rows come from spans.
  - `sessionid_envfile`: `HM_SESSION_ID` feeds task-preflight.
- **No TASK file.** `PLAN-<slug>.md` is the progress state. It points at the SPEC and holds no ACs.
- **The skill set stays** except where the ledger cuts it. The rubric and context-linter skills have no
  measured use, but no class justifies cutting them either.
- **The spec-validator** was not dispatched for this draft. The DRI's review replaces that pass.
