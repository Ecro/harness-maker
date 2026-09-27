---
type: spec
task_slug: loop-opt-in
status: approved
created: 2026-09-27
tier: 2
tags: [harness-maker, spec, python, synthesize, conditional-render, migration]
test_framework: pytest
interview_rounds: 3
intent: LOOP-OPT-IN
research_doc: "[[RESEARCH-loop-opt-in]]"
summary: "loop.enabled gates /hm:loop + /hm:loop-p5-batch renders; off only when no harness.yaml exists"
---

# SPEC — loop-opt-in

## 🎯 Intent

`/hm:loop` and `/hm:loop-p5-batch` render into every harness (56,526 B in this
repo) but have zero recorded invocations: 0 of 547 stage spans, and the last
`autoloop(` commit is from 2026-05-16. Intent LOOP-OPT-IN asks that they become
opt-in, so a project renders only what it uses. When this repo turns them off,
its `dead_rendered_bytes` should fall from 21.7 to about 9.2 (target ≤10).

## 🌅 Outcomes

- The `harness.yaml` key `loop.enabled` decides whether a rendered harness contains
  the loop commands. Claude Code and Codex outputs follow the same key.
- A project with no `harness.yaml` on disk gets no loop commands. Its command-list
  and stage-chaining surfaces (the AC-004 list) do not advertise them; they carry
  one line saying how to turn them on.
- Any project that already has a `harness.yaml` keeps its loop commands with no
  user action, whatever path the re-render takes (`--update`, `--reinterview`, or
  the malformed-file fallback).
- Turning the loop off removes the loop files that the render manifest proves
  pristine. User-edited files are kept, with the existing warning.
- A present but malformed `loop` value stops the render with an error. It never
  silently resolves to on or off.

## 📋 In-Scope Scenarios

Paths below are project-root-relative, after `reconcile._normalize_expected_path`
normalization. `.claude/`-bound FileSpec paths carry no prefix in the raw blueprint.

### AC-001: Disabled loop renders no Claude loop commands
**Given** answers with `loop.enabled: false`, and the same answers with `loop.enabled: true`
**When** `synthesize` builds both blueprints
**Then** `.claude/commands/hm/loop.md` and `.claude/commands/hm/loop-p5-batch.md` are absent from the disabled blueprint
**And** both are present in the enabled blueprint (positive control)

### AC-002: Disabled loop renders no Codex loop skills
**Given** answers with `codex` in `targets`, one with `loop.enabled: false` and one with `true`
**When** `synthesize` builds both blueprints
**Then** `.agents/skills/hm-loop/SKILL.md` and `.agents/skills/hm-loop-p5-batch/SKILL.md` are absent from the disabled blueprint
**And** both are present in the enabled blueprint

### AC-003: Enabled loop renders exactly what it renders today
**Given** each existing snapshot fixture rendered with `loop.enabled: true`
**When** its rendered paths and body hashes are compared with the snapshot blob
at base commit `055cce85` (read from git, not from the working tree)
**Then** they are equal, except for the `harness.yaml` body

### AC-004: Disabled loop leaves no advertisement on the listing surfaces
**Given** answers with `loop.enabled: false` and targets `claude-code`, `cursor`, `codex`, rendered once per locale `en` and `ko` and per preset
**When** the harness renders
**Then** each of these surfaces exists: `.claude/commands/hm/help.md`, `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/harness.mdc`, `.agents/skills/hm-help/SKILL.md` (the Codex rendering of help)
**And** in each of them, every line containing `hm:loop` or `hm-loop` (this covers `/hm:loop`, `/hm:loop-p5-batch`, `$hm-loop` and the ko sentence "stage 연결은 `/hm:loop` 또는 autopilot") also contains `loop.enabled`. The only mention left is the enable hint.
**And** each surface contains exactly one enable-hint line naming `loop.enabled: true` and `/hm:make`

### AC-005: An existing harness.yaml without the key keeps the loop
**Given** an existing `harness.yaml` with no `loop` key, in each of three variants
(no `schema_version`, `schema_version: 5`, `schema_version: 6`), plus a variant
with `loop: {}` (no `enabled`)
**When** `/hm:make --update` re-renders
**Then** `loop.enabled` resolves to `true`, and the rendered `harness.yaml` contains `loop.enabled: true` explicitly
**And** the loop command files are rendered

### AC-006: A project with no harness.yaml gets the loop off
**Given** a project with no `.claude/harness.yaml` on disk
**When** `/harness-maker:make` renders with default answers for each preset
**Then** the rendered `harness.yaml` contains `loop.enabled: false` and `schema_version: 6`
**And** the install summary's "Set for you" disclosure contains a row for `loop.enabled`

### AC-007: Turning the loop off sweeps manifest-proven pristine files and keeps edited ones
**Given** a project rendered with `loop.enabled: true` and `codex` in targets, with a render manifest.
In it, `.claude/commands/hm/loop.md` and `.agents/skills/hm-loop/SKILL.md` are unmodified,
and `.claude/commands/hm/loop-p5-batch.md` and `.agents/skills/hm-loop-p5-batch/SKILL.md` were edited by the user.
**When** the user sets `loop.enabled: false` and re-renders
**Then** the two unmodified files are deleted
**And** the two edited files still exist with bytes identical to their pre-disable content
**And** render output contains the ours-modified keep warning for each edited file

### AC-008: An explicit value survives re-render
**Given** a `harness.yaml` with `loop.enabled` set explicitly to `true` or `false`
**When** `/hm:make --update` re-renders
**Then** the value in the rendered `harness.yaml` is unchanged

### AC-009: Disabling removes only the loop files
**Given** the same answers rendered with `loop.enabled: true` and with `false` (all three targets)
**When** the two blueprints are compared
**Then** the enabled path set minus the disabled path set is exactly the four loop paths from AC-001 and AC-002, and the disabled set has no path the enabled set lacks
**And** body differences are confined to `.claude/harness.yaml`, `.claude/commands/hm/help.md`, `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/harness.mdc`, `.agents/skills/hm-help/SKILL.md`, and every other agent, skill and hook entry is byte-identical (compared on post-render body hashes)

### AC-010: An existing harness.yaml keeps the loop on every re-render path
**Given** an existing `harness.yaml` with no `loop` key
**When** the project is re-rendered with `--reinterview`, or the file fails to load as answers (the malformed-file fallback to `interview()`)
**Then** the rendered `harness.yaml` contains `loop.enabled: true`, and the loop command files are rendered
**And** given an existing file with an explicit `loop.enabled: false`, `--reinterview` keeps `false`

### AC-011: A malformed loop value fails the render
**Given** an existing `harness.yaml` whose `loop` value is `null`, `loop.enabled` is `null` or the string `"false"`, or `loop` carries an unknown nested key
**When** `/hm:make --update` runs
**Then** it exits non-zero with an error naming `loop`
**And** no rendered file is written or deleted

## 🚫 Non-Goals

- Deleting or shrinking the loop body (`loop.md.j2`, `loop-p5-batch.md.j2`).
- Gating other zero-invocation commands (`configure`, `health`, `help`, `make`, `uninstall`).
- Gating the `autoloop-driver` skill, the `autoloop-coder` agent or the `loop_gate` / `sessionid_envfile` hooks. `sessionid_envfile` serves every stage's `HM_SESSION_ID`.
- Rewording `/hm:loop` mentions in skill or agent bodies and descriptions (`autoloop-driver`, `worktree-isolator`, `verify-before-completion`, `second-opinion-gate`, `autoloop-coder`). The no-advertisement guarantee covers the AC-004 surfaces only, and a skill description that names `/hm:loop` is an accepted residue.
- Removing runtime-conditional `/hm:loop` prose inside stage templates ("When dispatched by `/hm:loop` or by autopilot", `execute.md` Step 5). It is guarded by runtime marker checks.
- A `/hm:configure` entry, a new `/harness-maker:make` CLI flag, or an interview question for the key.
- Flipping this repo's own `harness.yaml` and measuring `dead_rendered_bytes`. This is a post-release follow-up, because `HarnessConfig` is `extra="forbid"` and the released 0.60.2 plugin would reject a `loop:` key.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Schema | New `loop: LoopConfig` sub-model (`strict=True, extra="forbid"`, `enabled: bool`) on `HarnessConfig` | Matches every other config block, and gives AC-011 its failure for free |
| Fresh vs existing | "Fresh" means no `.claude/harness.yaml` on disk, decided before any code path is chosen. When a file exists, its readable `loop.enabled` bool is carried; if it is absent or the file is unreadable, the value is `true` | Round 3 decision; closes the `--reinterview` / malformed-fallback hole (cli.py:356-366) |
| Absent-case | Absent `loop` key or `loop: {}` ⇒ `true`, keyed on presence, not on `schema_version` | Global rule 2026-06-08; precedent `io_utils.strip_retired_keys` is presence-keyed |
| schema_version | Fresh renders write 6. `--update` keeps the existing carry-through of the file's own version (interview.py:913-947); the migration never reads it | Version only records when a file was written |
| Compatibility | Existing harnesses render byte-identically except `harness.yaml` | Scope: 기존 하네스 보존 |
| Surface gates | Surface ratchet, BASELINE-DELTA attribution, command-name registry, snapshots, round-trip budget and render fixtures are updated in the same change. The frozen baseline is never raised. AC-003 reads its reference from git so this regeneration cannot make it circular | [wiki:architecture] onboarding-disclosure-and-six-gates |
| Performance | No measurable render-time change | A list filter only |
| Security | None | No permission, network or secret surface |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add top-level `loop.enabled: bool` to `harness.yaml`; fresh renders write `schema_version: 6` | schema/file format/storage layout | Once shipped, user files carry the key. Renaming it needs a migration, and older plugins reject it (`extra="forbid"`) |
| IRR-002 | Off only when no `harness.yaml` exists on disk. Every existing file keeps its explicit bool, or `true` when the key is absent or the file is unreadable, on every re-render path | data migration | Decides what every existing harness becomes on its next render. A wrong default silently removes a command users may rely on |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| AC-001 | unit | `tests/unit/test_loop_opt_in.py::test_ac001_disabled_renders_no_claude_loop_commands` |
| AC-002 | unit | `tests/unit/test_loop_opt_in.py::test_ac002_disabled_renders_no_codex_loop_skills` |
| AC-003 | unit (snapshot vs git blob) | `tests/unit/test_loop_opt_in.py::test_ac003_enabled_matches_pre_change_snapshots` |
| AC-004 | unit (render) | `tests/unit/test_loop_opt_in.py::test_ac004_disabled_leaves_no_loop_advertisement` |
| AC-005 | unit | `tests/unit/test_loop_opt_in.py::test_ac005_existing_absent_key_keeps_loop` |
| AC-006 | unit | `tests/unit/test_loop_opt_in.py::test_ac006_no_harness_yaml_writes_loop_off` |
| AC-007 | integration (tmp project) | `tests/unit/test_loop_opt_in.py::test_ac007_disable_sweeps_pristine_keeps_edited` |
| AC-008 | unit (property) | `tests/unit/test_loop_opt_in.py::test_ac008_explicit_value_round_trips` |
| AC-009 | unit (differential) | `tests/unit/test_loop_opt_in.py::test_ac009_disable_removes_only_loop_files` |
| AC-010 | integration (CLI) | `tests/unit/test_loop_opt_in.py::test_ac010_existing_yaml_keeps_loop_on_every_path` |
| AC-011 | unit | `tests/unit/test_loop_opt_in.py::test_ac011_malformed_loop_value_fails_render` |
| Follow-up (not an AC) | manual, post-release | Set `loop.enabled: false` in this repo, `/hm:make`, then `hm intent metric measure --all` and read `dead_rendered_bytes` |

## ❓ Open Questions

(none: design decisions for `/hm:execute` Step 0 follow)

## 🔎 Spec Validation

spec-validator pass 1: `MAJOR_REVISION` (2 critical, 7 warning). Codex second opinion: invoked, 8 findings, 7 accepted and 1 rejected.

| Finding | Disposition |
|---|---|
| Absence predicates could pass on un-normalized paths (critical) | Positive controls added to AC-001/002; normalized paths stated |
| `--reinterview` / malformed fallback silently turns loop off (critical) | DRI Round 3 decision: fresh = no file on disk; AC-010 added; IRR-002 reworded |
| AC-004 missed `$hm-loop`, the ko sentence and undefined surfaces | Surface list and token rule enumerated in AC-004 |
| Outcome vs autoloop-driver description contradiction | DRI Round 3: Outcome narrowed; skill/agent mentions moved to Non-Goals |
| AC-003 reference circular under same-change snapshot regen | Reference pinned to git blobs at `055cce85` |
| No bound on what disable removes | AC-009 added (differential enabled-vs-disabled) |
| AC-005/006 predicates weaker than prose; schema_version on update undefined | Predicates extended; schema_version constraint row added |
| Malformed loop value undefined | DRI Round 3: fail loudly; AC-011 added |
| AC-007 lacked bytes, warning and Codex twins; wrong oracle label; Outcome overclaimed | AC-007 extended; oracle relabeled `golden`; Outcome narrowed to manifest-proven files |
| Codex: deletion policy as an IRR | Rejected by validator: regenerable, reversible by re-enabling, fits no IRR category |

## 🔍 Refinement Decisions

- Round 1: new installs default off, and legacy harnesses are preserved on. The loop is re-enabled by hand-editing `harness.yaml` and running `/hm:make`, with no configure entry or flag. Codex `hm-loop*` skills are gated by the same key.
- Round 2: IRR-001/002 accepted. The absent key is presence-keyed (on). The repo flip and measurement become a post-release follow-up (`extra="forbid"`).
- Review amendment (2026-09-27, DRI-approved): AC-004 surfaces and AC-009 allowed diffs gained `.agents/skills/hm-help/SKILL.md`. It is the Codex rendering of help, surfaced once AC-009 compared real rendered bodies (review finding cd14c78815a4027d).
- Round 3 (after spec-validator): "fresh" means no `harness.yaml` on disk, covering `--reinterview` and the malformed fallback. The no-advertisement guarantee is narrowed to the listing surfaces. A malformed `loop` value fails the render.
