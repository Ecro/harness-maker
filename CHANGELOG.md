# Changelog

## [Unreleased]

### Added — `autonomy` config schema (PLAN-human-bottleneck-auto-advance Phase 1 of 9)
- **New `autonomy:` block in harness.yaml** — `level` (`gated` | `auto_safe` | `full`, default `gated`), `pipeline` (the 7-stage default), `step_cap` / `time_cap_min` (runaway caps), `extra_deny` (additive-only). Schema foundation for an opt-in pipeline auto-advance feature; **no runtime behavior yet** — `gated` is the default and old harness.yaml without the key loads as `gated` (absent-case guard).
- `AutonomyConfig` is wired round-trip (HarnessConfig + InterviewAnswers mirror + synthesize + both harness-yaml templates + `interview._parse_autonomy` reverse-mapper) so the policy survives `/hm:make --update`. The destructive never-auto deny baseline is deliberately NOT a config field (ADR-003) — only `extra_deny` is user-settable, so a yaml edit can never subtract a baseline guard.
- Phases 0, 2–8 (feasibility spike, session marker, Stop-hook backstop, never-auto enforcement, runaway caps, stage-terminal advance, ledger, docs) remain — see `work-docs/PLAN-human-bottleneck-auto-advance.md` Execution Log.

### Fixed — Worktree branch-backlog drain relocated off the create-only trigger (PLAN-multisession-worktree-concurrency Phase 0, ADR-009)
- **The gated, biased-to-preserve worktree sweep (`prune_stale`) now also runs at `/hm:wrapup` and `/hm:health`, not only at `worktree create`.** Previously a paused project accumulated leaked `execute-*`/`plan-*` branches unbounded (this repo had 76 against 1 landed-marker), printing a "N branch(es) preserved" warning wall on every create.
- New `worktree drain` subcommand (`_drain` / `_drain_summary` / `_cli_drain`) — a non-interactive, one-line-summary trigger that reuses the single `prune_stale` gate. It is **additive**: create-time reaping is retained, and it can never force-delete the legacy backlog (only the human-reviewed `prune-branches --force` does).
- Wired into `templates/stages/wrapup.md.j2` (Step 7.6) and `templates/commands/hm/health.md.j2`.
- This is Phase 0 of an 8-phase per-task feature-branch concurrency overhaul; Phases 1–7 remain.

## [0.30.0] - 2026-06-17

### Fixed — Codex second opinion survives the Bash sandbox (PLAN-codex-second-opinion-sandbox)
- **The Codex second opinion now actually runs instead of skipping with "Bash permission gate(sandbox)".**
  `codex exec` moved out of the tool-restricted reviewer subagents into the stage main loop via a new
  shared `agents/_partials/codex_exec_mainloop.md.j2` partial. A `Bash(codex exec:*)` allow rule is
  added to `settings.json` (Production + Side) and the orchestrator runs that one call with
  `dangerouslyDisableSandbox: true` — both gated on `codex_second_opinion.enabled`, so disabled
  renders are byte-identical (ADR-002/003).
- **plan stage migrated from agent-body exec to main-loop exec** with an ownership contract (main loop
  runs + injects findings/`codex_status`; `plan-validator` reconciles). The 3 dead agent-body partials
  (`second_opinion_codex`, `codex_tools_bash_suffix`, `codex_permission_line`) are deleted and the 3
  reviewer agents revert to `tools: Read, Grep, Glob` (ADR-004/005).
- **Review hardening:** the sandbox-disabled call is rendered as a bare `codex exec … < file` command
  so the `Bash(codex exec:*)` allow rule prefix-matches it headless; the untrusted diff is written to
  the prompt file via the Write tool (no `$(...)` shell expansion); the Claude-only directive is gated
  on `not is_codex` so codex-target skills aren't handed a parameter they can't honor.

### Added — persistent locale + per-command start/end observability (PLAN-locale-and-command-observability)
- **The configured `locale` now governs user-facing output in every command, not just onboarding.**
  A new shared `output_language.md.j2` directive (driven by `{{ config.locale }}`, zero new
  translation files) is injected into the atomic + workflow command wrappers, the Codex
  stage/workflow skills, and as a persistent `## Output Language` section in CLAUDE.md (×4) and
  `AGENTS.md`. Code, identifiers, and persisted PLAN/RESEARCH/REVIEW/SPEC documents stay English
  (ADR-001). Subagent output is out of scope (ADR-005).
- **Every command shows a structured start banner (🎯 Goal / 📋 Plan) and a per-stage end banner
  (✅ Done / 📁 Artifacts / ➡️ Next).** `step_manifest.md.j2` was reframed into the start banner
  (keeps its `.hm-loop-active` autoloop self-skip); a new `stage_end_summary.md.j2` rides each of the
  7 stage templates, so a fused workflow emits one banner per stage (the Codex `workflow_skill`
  delegates and carries none). Banners self-skip inside an autoloop — machine receipts cover that
  case (ADR-003).
- **`/hm:health` gained two Layer-1 sub-checks** (`output_language_present`, `start_end_summary_present`)
  that presence-audit the rendered stage/fused commands (meta commands excluded). The end-summary
  vars are StrictUndefined-required so a stage that omits one fails render loud (ADR-002).

### Security
- `HarnessConfig.locale` / `InterviewAnswers.locale` are now sanitized (single-line, ≤35 chars, else
  `en` fallback) — the value is interpolated raw into agent-facing rendered prose, so a multi-line
  value could otherwise inject instructions. Legitimate tags (incl. non-ASCII) are preserved.

## [0.29.1] - 2026-06-12

### Fixed — worktree create no longer self-blocks on plan deliverables (PLAN-worktree-deliverable-blocks-create)
- **`/hm:execute` no longer aborts on the `/hm:plan` deliverable it depends on.** Deliverables
  (`work-docs/{PLAN,RESEARCH,SPEC,REVIEW}-*.md`, `specs/SPEC-*.md`) are deliberately tracked (wrapup
  commits them), so they were always uncommitted at `worktree create` time → the Layer-2 dirty-base
  guard blocked *every* plan→execute. The create-guard now forgives deliverable-shaped paths
  **per-line** via `_is_deliverable_path` (anchored full-match, `[^/]+` so nested dirs aren't
  over-forgiven); the **finalize filter is unchanged**, so deliverables are still stash-preserved
  (ADR-001). Guard helpers use `git status --porcelain -uall` so a fresh project's first PLAN
  (fully-untracked `work-docs/`, which git collapses to one line) is still seen.
  *Non-goal:* a non-default `work_docs.dir` is not covered (pure porcelain predicate).

### Fixed — leaked `execute-*` branch wall (same PLAN, ADR-003/004)
- Finalize now records a **SHA-validated landed marker** `refs/hm-landed/v1/<branch>` (branch tip);
  `prune_stale` deletes a landed branch iff `current_tip == marker_SHA` — surviving later HEAD edits
  (the old current-blob compare preserved re-edited branches forever) and name-collision-safe (a
  re-created same-named branch falls to the preserve-biased content-gate).
- Orphan markers are reaped on every delete path so `refs/hm-landed/*` can't accumulate; the
  per-branch `[WARN] preserved branch …` wall collapses to **one summary line**.
- New **`python -m harness_maker.worktree prune-branches [--force]`** drains the legacy backlog;
  `--force` prints a `git log -p <branch>` recovery hint before each delete (reflog `wip(execute)`
  commits survive).

## [0.29.0] - 2026-06-07

### Added — Cross-model (Codex) deepening (PLAN-crossmodel-codex-gaps)
- `/hm:review` now runs Codex as a **k-of-3 consensus voter** (not advisory): Step 3.5
  invokes `codex exec`, a new `codex_adapter` normalizes findings (severity `critical→P0…`
  + null-location symbol/message-similarity relaxation) into the Step 4 filter, and a
  Codex-raised `consensus-passed` finding counts toward the grade.
- **Preset × high-diff mandatory matrix** (when `codex_second_opinion.enabled`): Production
  forces Codex on review+plan always; Side forces it only on a high-diff change
  (`harness_maker.high_diff`, per-iteration in `/hm:loop`). Mandatory = loud-warn +
  best-effort skip-receipt, never a hard block.
- **Calibration ledger** `.claude/observability/codex-second-opinion.jsonl`
  (`harness_maker.codex_ledger`, disposition + skip-rate v1) and a **positive Codex
  smoke-check** in `/hm:health` that catches a silently-degraded integration.
- **plan-validator PIDA**: Codex finding → Claude KEEP/REFUTE → oracle-or-`[unresolved]`,
  with a no-oracle short-circuit; `[unresolved]` surfaces but never blocks.
- Injection-safe CLIs: `codex_ledger emit --field …` (argv-built JSON) and
  `codex_adapter adapt < file` (stdin) so rendered recipes never inline untrusted
  content into a shell-quoted blob.
- Deferred: H3 (generated-harness Codex audit), H5 (curated hermetic bundle), H8 (`/duel` routes).

## [0.28.11] - 2026-06-03

Re-release of 0.28.10 with corrected snapshot fixtures. The 0.28.10 tag's
release workflow failed at `quality-gate` (nothing published) because two
snapshot expected files were regenerated against a polluted local fixture.

### Fixed: `side-python-cli` snapshots wrongly pinned to `Production`

- `tests/snapshot/side-python-cli-{spec,task}.expected.yaml` were regenerated
  while the `tests/fixtures/side-python-cli/` fixture had a leftover gitignored
  `.claude/` build artifact (65 files) and a stale
  `~/.cache/harness-maker/profile-*.json` entry, both of which pushed the
  profiler to `scale: medium` → `preset: Production`. On a pristine CI checkout
  the fixture profiles to `scale: small` → `preset: Side`, so the committed
  snapshots mismatched and `test_synthesize_snapshot` failed on CI only.
- Fix: regenerated both snapshots against the pristine fixture (cache cleared),
  restoring `preset: Side`. No source/runtime change versus 0.28.10 — this
  release carries the same TECH_SPEC audit fixes.

## [0.28.10] - 2026-06-03

Fix a batch of real defects surfaced by a multi-agent audit of the
implementation against TECH_SPEC.md. The audit found the code largely sound but
the spec ~2 years stale; this release lands the genuine code/template fixes
(doc-only stale-spec items are deferred to a separate doc sweep).

### Fixed: multi-document `harness.yaml` parse defect (3 readers)

- `i18n.resolve_locale`, `gates.permission_gate`, and `gates.spec_gate` parsed
  `.claude/harness.yaml` with a bare `yaml.safe_load`. Every rendered
  harness.yaml is a multi-document stream (provenance frontmatter + body), so
  `safe_load` raised `ComposerError` and the readers silently degraded:
  non-English users always got English messages, and — worst — `spec_gate`
  returned `{}` so `dev_mode` never read as `spec-driven`, **silently disabling
  the entire spec-driven TDD enforcement gate on every real install**. All three
  now use `io_utils.load_harness_yaml`. Regression tests added with provenance
  frontmatter (the old tests used a plain body that never exists on disk).

### Fixed: readiness `no_high_security_findings` blind to P0

- The signal counted only `"severity": "high"`, but `hallucination` and
  `prod_name_guard` emit `P0`/`P1`/`P2`. A persisted critical P0 left the signal
  passing. Now counts `high` and `P0` (matching `cli.py`'s gate).

### Fixed: `verify-before-completion` SKILL drift

- Three of the five checks were no-ops or wrong on modern installs: Check 3 read
  a never-written `metrics.jsonl`/`health` key, Check 2 ran
  `.claude-verify.sh phase_$CURRENT_PHASE` (never produced), Check 5 hardcoded
  `main`. Realigned to the canonical `/hm:verify` stage: drift-verdict gate,
  verification-cache + project toolchain, `dashboard.md` `## Structural`
  baseline with the no-baseline PASS rule, branch-agnostic merge check, and
  high/P0 findings honoring `accepted-risk-with-rationale`.

### Fixed: `.claude-verify.sh` acceptance gate broken

- `phase_1` asserted `__version__ == '0.1.0'` and aborted at 0.28.x; version
  checks are now dynamic (and cross-check the manifest against the package
  version per ADR-13). Deleted-template references (`dashboard.{ko,en}.md.j2`,
  `monitor.md.j2`, `dev.md`) corrected to current names.

### Fixed: smaller correctness issues

- `context_lint` Side thresholds aligned to the canonical CLAUDE.md values
  (agent 150, skill 100) so the linter and `/hm:health` agree.
- `worktree cleanup-all` CLI subcommand added (the documented disk-cleanup
  defense was unreachable); `finalize` now rejects unknown merge strategies.
- `modular_edit.add()` raises a clean `ModularEditError` (listing available
  components) instead of leaking `jinja2.TemplateNotFound`; `remove()` now runs
  the verifier like `add()`.
- SessionStart drift hint counts overrides **since the last audit**, not
  lifetime (the banner never reset before).
- Seed `dashboard.md.j2` aligned to the writer's 2-section schema; the
  false-promise `@hm:user:extensions` block removed (the writer overwrites this
  file, never block-merges it).
- `personalization_audit` baseline seeds preset-specific axes
  (consensus/default_workflow/fused_workflows) so it matches what `/hm:make`
  actually produces.
- `executor` agent description reworded — the write boundary is prompt-level
  convention, not a runtime-enforced sandbox (subagent-frontmatter permissions
  are not enforced by Claude Code).

## [0.28.9] - 2026-06-03

Fix the Codex second-opinion recipe so the call actually runs.

### Fixed: `codex exec --ask-for-approval` rejected by the CLI

- The rendered second-opinion recipe (`code-reviewer` / `consensus-arbiter` /
  `plan-validator`) invoked `codex exec --ask-for-approval never`, but
  `codex exec` does not accept `--ask-for-approval` (it's an interactive-only
  flag; `exec` is non-interactive). On codex-cli 0.133.0 this errors on the
  first recipe line, so the Codex second opinion silently skipped on every run
  (warn-and-proceed masked it).
- Fix: drop the `--ask-for-approval never` line from the recipe. `--sandbox
  read-only` remains the isolation. Verified end-to-end — `codex exec
  --sandbox read-only --ignore-user-config --ignore-rules --json
  --output-schema <f> --output-last-message <f> -` returns schema-conforming
  JSON. A render guard test (`test_codex_recipe_has_no_invalid_ask_for_approval_flag`)
  prevents reintroduction.

## [0.28.8] - 2026-06-03

Make rendered JSON schemas reach existing installs on re-render.

### Fixed: `.claude/schemas/*.json` froze on `/hm:make --update`

- `reconcile()` returns `KEEP("no-frontmatter")` for any rendered file without
  provenance frontmatter. Pure-JSON schema files (`codex exec --output-schema`
  contracts, no frontmatter by ADR-008) hit that branch, so an existing install
  never picked up a fixed rendered schema on re-render — the 0.28.7
  `codex-finding.schema.json` strict-mode fix reached fresh installs only.
- Fix: add a forced-REPLACE reconcile branch for `.claude/schemas/*.json`
  (machine artifacts with zero user-editable content), reusing the existing
  `render._is_schemas_json` predicate so reconcile and the render dispatch stay
  in lockstep. Mirrors the `settings.json` / `config-always-replace`
  precedent; `cli.py`'s `backup()` covers recovery. The live schema now
  re-renders on `/hm:make`, so existing installs get the strict-mode fix.

## [0.28.7] - 2026-06-03

Fix the Codex second-opinion JSON schema so it is valid under OpenAI/Codex
strict structured-output mode (`codex exec --output-schema`).

### Fixed: `codex-finding.schema.json` rejected by Codex strict mode

- Strict structured-output mode requires every key in an object's `properties`
  to appear in `required` when `additionalProperties: false`. The shipped
  schema violated this twice — top-level `confidence` and item-level
  `file`/`line`/`evidence` were declared but not required — so `codex exec`
  returned `invalid_json_schema` and the reviewer (`plan-validator` /
  `code-reviewer` / `consensus-arbiter`) silently fell back to a prompt-pinned
  shape each pass (retries + latency).
- Fix: every property is now in `required`; genuinely-optional keys
  (`confidence`, `evidence`, `file`, `line`) are expressed as nullable union
  types (`["X", "null"]`) — strict mode's way to encode optionality. Dropped
  the unsupported numeric/string constraint keywords (`minimum` / `maximum` /
  `minLength`), a likely secondary rejection cause on several Codex/OpenAI
  versions.

### Added: static strict-mode invariant test

- `tests/unit/test_schema_strict_mode.py` guards every rendered schema under
  `templates/schemas/*.json`: every property ∈ `required` under
  `additionalProperties: false`, and no banned constraint keywords. Carries a
  committed negative fixture (the pre-fix shape) so the regression proof is
  permanent. Previously the suite only checked schema *routing*, never *shape*.

## [0.28.6] - 2026-06-02

Security follow-up to 0.28.5: gate the codex agents' Bash tool on opt-in.

### Changed: codex agents' `tools: Bash` is now CONDITIONAL

- 0.28.5 added `Bash` to `code-reviewer` / `consensus-arbiter` / `plan-validator`
  `tools:` **unconditionally**. Investigation (codex permission probe, 2026-06-02)
  established that **subagent-frontmatter `permissions.deny` is NOT enforced by
  Claude Code** — only `tools:` / `disallowedTools:` and `settings.json` are. So
  an unconditional bare `Bash` tool on a reviewer = unrestricted shell
  (`sh`/`python`/`rm`), regardless of the frontmatter deny block that nominally
  "scoped" it to `codex exec`.
- 0.28.6 makes the `tools:` Bash token **conditional on
  `codex_second_opinion.enabled` AND the agent being in its list** — the same
  gate as the `Bash(codex exec:*)` allow line (new `codex_tools_bash_suffix.md.j2`
  partial). Harnesses without codex second-opinion get the original
  `tools: Read, Grep, Glob` (no shell). Accepted residual: with codex enabled,
  the 3 agents still carry full Bash (frontmatter deny can't scope it); true
  per-agent command scoping needs a PreToolUse hook or settings.json deny.
- Tests: split the unconditional assertion into enabled→Bash / disabled→no-Bash;
  the `_render_agent` SHA pins revert to their pre-0.28.5 values (no-codex config).
- CLAUDE.md §보안/권한 annotated with the enforcement reality; see
  `tests/manual/CODEX_PERMISSION_PROBE.md`.

## [0.28.5] - 2026-06-02

Fix: codex second-opinion agents could never run `codex exec`
(PLAN-spoton-codex-rm-stash-rootcause, ADR-001).

### Fixed: codex reviewer agents declare the `Bash` tool

- `code-reviewer`, `consensus-arbiter`, and `plan-validator` listed
  `tools: Read, Grep, Glob` while their `permissions.allow` carried
  `Bash(codex exec:*)`. Claude Code's `tools:` field is the hard gate on tool
  availability, so the Bash permission was **inert** — `codex_second_opinion`
  silently skipped with "validator env had no Bash". The three templates now
  declare `tools: Read, Grep, Glob, Bash` (unconditional; `permissions` still
  scopes the allowable Bash commands to `codex exec` only).
- Incidentally restores `code-reviewer`'s previously-inert `Bash(git diff:*)`
  / `git log` / `git status` capability (same root cause).
- No security regression: all three agents already deny the full
  `python/node/sh/bash` interpreter quartet (REVIEW-M7), so the deny list — now
  the sole barrier — stays complete. A new unit assertion pins both the
  `tools:`-Bash presence and the deny-quartet completeness.

## [0.28.4] - 2026-06-01

Worktree-finalize robustness pass (PLAN-p6-p7-worktree-finalize, all phases +
review follow-ups). All bug fixes / internal hardening; no API or breaking change.

> Re-tag of the unpublished **v0.28.3**, which failed `quality-gate` on two
> stale permissions-opt-out integration tests (a boundary test + the
> fresh-install settings-migration test still asserted the pre-opt-out non-empty
> `settings.json` deny default). v0.28.3 published nothing — quality-gate is the
> first job — so no artifacts were produced; the stale tests are fixed here.

### Fixed: finalize stash-orphan + merge-fence hardening (CR2 / CN1 / CN2)

- **CR2** — `_stash_base_dirty` matched its just-pushed stash by an exact/endswith
  subject compare, which a `git stash list` `%gs` format quirk (e.g. a trailing
  file count) could miss → raise → orphan the stash with the user's base dirt
  stranded inside. It now matches the unique message as a substring (the 32-hex
  `uuid4` suffix keeps it collision-safe).
- **CN1** — the merge-fence acquire-timeout was raised 60s → 360s (= the
  in-fence `git stash push -u` worst-case 300s + the 60s merge), so a
  legitimately-slow first finalize no longer spuriously times out a parallel
  second one. (Supersedes ADR-003's original "keep 60s".)
- **CN2** — both base-stash pops are now serialized behind the merge fence
  (`_fenced_restore_base_dirty`, with an unfenced fallback on fence-acquire
  failure) so two parallel finalizes don't race the shared stash stack /
  `index.lock`. (Supersedes ADR-003's "pops stay outside the fence".)
- Accepted narrow downside: the 360s budget lengthens the O_EXCL *secondary*-path
  stale-lock stall if a holder is SIGKILL'd (flock — the primary on Linux/WSL2 —
  auto-releases on death); self-heals via the unfenced fallback.

### Fixed: success-mode finalize rollback resets the conflicted index (CR1)

The finalize rollback reset the partial merge to HEAD only `if not auto_commit`
(stage-only). A success-mode `git merge --squash` CONFLICT also leaves a
dirty/conflicted index without committing, so the success-mode rollback skipped
the reset and applied the base stash over the conflict markers. The reset is now
gated on `wt_rc != 0` (any failure rollback); `git reset --hard HEAD` is a no-op
when the index is already clean.

### Internal: porcelain-parse dedup + batched gitignore check-ignore

`worktree` now extracts one `_porcelain_path()` helper for the
`git status --porcelain` line parse (previously 3 divergent inline copies) and
batches the `git check-ignore` subsumption test in `_ensure_harness_gitignore`
into a single `--stdin` subprocess instead of one per churn pattern (N→1 on a
typical `worktree create`). Behavior-preserving for the dirty-base guard; the
parse unification was reviewed and confirmed fail-safe in the only direction it
can diverge. (PLAN-p6-p7-worktree-finalize P3.)

### Changed: merge fence wraps the full base-mutating critical section

The Layer-4 finalize merge fence now wraps `{git stash, staged-before snapshot,
squash merge}` instead of only the merge. Previously `_stash_base_dirty` ran
*outside* the fence, so two parallel finalizes could `git stash push` the same
base concurrently — the race the fence exists to prevent. `staged_before` is
captured strictly after the stash (scope-guard `--allow-dirty-base` exemption);
`_capture_pending_in_worktree` and all pop/cleanup/handoff paths stay outside the
fence. (PLAN-p6-p7-worktree-finalize ADR-003.) Accepted trade-off: the 60s fence
acquire-timeout is retained though the guarded section can hold longer on a large
dirty tree — a rare parallel-finalize case degrades to preserve-and-rerun.

### Fixed: orphan worktree-branch leak (`prune_stale` content-gated sweep)

`worktree` cleanup never ran `git branch -D` (deliberately — it must keep the
`wip(execute)` recovery net alive while a worktree is live), so every finalized
worktree leaked its `execute-*`/`plan-*`/`phase-*`/`autoloop-*` branch forever.
`prune_stale` (run at every `worktree create`) now sweeps such branches once
their worktree dir is gone — but **only when their content is already in HEAD**.

- New `_branch_content_in_head` gate mirrors the stash-ref drain: path-keyed blob
  equality, **biased toward preserve** — any unresolvable ref / missing /
  mismatched blob keeps the branch. It does NOT use `git branch --merged` (a
  squash-merged tip is not a HEAD ancestor). (PLAN-p6-p7-worktree-finalize ADR-002.)
- Cross-session safe: an in-flight session's stage-only branch (work staged, not
  yet committed) is not in HEAD → preserved; swept only after its wrapup commits.
- Live-skip keys on `_registered_worktree_paths`; failed deletes are reported
  honestly (preserved+warned), never claimed as removed.

## [0.28.2] - 2026-05-31

### Fixed: agent `model:` frontmatter is version-agnostic (alias, not pinned id)

Rendered `.claude/agents/*.md` carried a stale **Cursor concrete id**
(`claude-4-7-opus`) in the `model:` line instead of the Claude alias. Claude Code
now respects that field (#43869), so subagents failed to launch (0 tool uses) in a
newer-model session. (PLAN-agent-model-version-agnostic.)

- **Agent frontmatter renders the Claude alias** (`opus`/`sonnet`/`haiku`) via a
  shared `_partials/model_frontmatter_line.md.j2` — Claude Code resolves it to the
  current tier model, so it never goes stale across releases (ADR-001).
- **`default_model` floor defaults to `opus`** (was `claude-opus-4-7`) (ADR-002).
- **Foreign-tool configs resolve alias→concrete** at the `foreign_config` render
  boundary via a new `_FOREIGN_MODEL_IDS` map (aider/Continue call the Anthropic API
  directly and need a concrete id). This is deliberately separate from
  `CURSOR_MODEL_IDS` (Cursor's reversed-format ids are a different namespace) (ADR-006).
- Guard: `test_agent_model_alias_rendering` fails if any concrete id reaches an agent
  `model:` line. Supersedes the PLAN-model-routing-multi-ide C-1/R-7 cursor-precedence.

## [0.28.1] - 2026-05-31

### Fixed: autoloop worktree phantom-path cascade-cancel

`/hm:loop` and `/hm:execute` could proceed on a fabricated `<WT>` worktree path
(e.g. an LLM-substituted `execute-<round-timestamp>` with no uuid segment that
`worktree create` never printed). Worktree-dependent operations — `.current-iter`
marker, receipt writes, stage `Task(...)` dispatches — were issued as parallel
tool calls, so one `cd <WT>` error into the non-existent path cancelled the
entire batch (`Cancelled: parallel tool call … errored`).

- **`worktree verify <path>` (new CLI subcommand):** the loop/execute driver runs
  it immediately after `create` and HALTs on a non-zero exit. The gate is
  structural — it accepts only an existing **linked** git worktree root and
  rejects phantom paths, non-git dirs, worktree subdirectories, and the **main
  repo root** (`git-dir` vs `git-common-dir`), so a drifted path that lands on
  main does not pass.
- **`iter_receipts` fail-loud root guard:** `write` and `set_iter_marker` now
  reject a non-existent `--root` instead of silently materializing a bogus
  receipts tree under it (`atomic_write` auto-creates parent dirs).
- **Template guidance (`loop.md.j2`, `execute.md.j2`):** the verify gate is
  documented at Step 5 / Step 0, multi-repo mode verifies every printed line,
  and an explicit "never batch `create → verify → marker` in one parallel
  tool-call turn" rule now also lives at the per-iter marker site (Step 3.5),
  not only at the loop-top engage step.
- Tests: `tests/unit/test_worktree_verify.py` + `_require_existing_root` guard
  cases in `test_iter_receipts.py`.

## [0.28.0] - 2026-05-30

### Added: forward spec↔test binding on the everyday `/hm:execute` path

`/hm:execute` now consumes `SPEC-{slug}.machine.yaml` as a source of truth, so
the AC→test→mutation graph accumulates *forward* during normal feature work
instead of being reconstructed retroactively by the spec-coverage backfill loop
(PLAN-spec-test-accumulation).

- **Predicate contract tightened (ADR-007):** `spec_machine.validate` now rejects
  a mechanical AC unless its `executable_predicate` `ast.parse`s as an assertable
  Python expression (comparison / call / bool-op / unary-op referencing ≥1
  symbol). Prose (`"retries are bounded"`) and tautologies (`True`) are rejected.
  `spec.md.j2` guidance updated accordingly. (Back-compat waived per ADR-008;
  no CI gate runs validate over the real `specs/` tree.)
- **`spec_machine` CLI:** `validate`, `cross-validate`, and `mark-tested`
  subcommands (`python -m harness_maker.spec_machine ...`) — the `/hm:spec`
  template's `validate` call is now real, not aspirational.
- **Forward write-back (ADR-005):** `/hm:wrapup` calls `mark-tested` in the base
  repo after finalize to flip `pending_test→false` + record the authored
  `test_ids`, making `machine.yaml` a living document. Located post-finalize so
  collection resolves correctly and there is no cross-session worktree race.
- **`spec_mutation` CLI:** `gate --yaml ... --tier 1` runs a tier-gated mutation
  check (execute Phase D, T1 only — ADR-003); degrades to non-gating when mutmut
  is absent.
- **`spec_drift` resolved-but-pending detector (ADR-009):** `/hm:health` now
  flags ACs whose tests resolve but stayed `pending_test=true` (the
  wrapup-was-skipped bucket), so the wrapup-gated write-back is never a silent miss.
- **Fixed (latent):** `spec_machine._check_pytest_collect` used non-`-q`
  `--collect-only`, whose tree output carries no `::` nodeids — rule-3 reported
  *every* test_id as unresolved in real use (only ever tested with the helper
  mocked). Now uses `-q` + return-code-aware degradation; guarded by an unmocked
  lifecycle test.

## [0.27.1] - 2026-05-29

### Fixed: parallel `/hm:execute` no longer blocked by the harness's own churn

- **Root cause:** the harness wrote per-session churn (telemetry on every tool
  call → `.claude/observability/`, iter-receipts, loop-context, render manifest)
  into the base repo, and the two dirt-filters disagreed — so `git status` was
  never clean. Finalize stashed on every run (queue-guard then blocked the next
  `create`), and `work-docs/` churn tripped the dirty-base guard directly. The
  5-layer cross-session defense was firing constantly on self-inflicted dirt.
- **Keep-base-clean:** one shared churn source of truth (`worktree.`
  `_HARNESS_CHURN_DIRS` prefix-matched + `_HARNESS_CHURN_FILES` exact-matched,
  unioned into `_HARNESS_GITIGNORE_PATTERNS`) now drives (a) a gitignore set
  seeded at make time + every `worktree create` (`_ensure_harness_gitignore`,
  idempotent + subsumption-safe), and (b) BOTH dirt-filters
  (`_is_harness_artifact` union; create-guard via delegation) — so churn
  neither blocks `create` nor triggers a finalize stash. Genuine user
  `.claude/` edits are still preserved (narrow-filter invariant).
- **Deliverables committed:** wrapup now `git add`s RESEARCH + SPEC alongside
  PLAN + REVIEW, so they stop lingering as untracked dirt.
- **Known limitation:** the two `work-docs/` churn entries assume the default
  `work_docs.dir` (`work-docs/`); a non-default `work_docs.dir` is not yet
  covered by churn-isolation (the `.claude/` churn — the dominant source — is
  unaffected). Tracked as a follow-up.
- **Orphan stash-ref drain:** `prune_stale` now removes a finalize-stash ref
  whose stash object is gone (gc-pruned/dropped → nothing to restore); a
  dropped-but-reflog-recoverable stash is still preserved.
- **Docs:** corrected CLAUDE.md (no 24h `/hm:health` worktree cleanup exists;
  `prune_stale` runs only at `worktree create`).
- Accepted limitation: already-committed `.claude/` churn stays cosmetically
  dirty in `git status` (no auto `git rm --cached`); opt-in manual cleanup
  documented.

## [0.27.0] - 2026-05-28

### Added: Second Brain promotion — wrapup now escalates local memory to Obsidian

- **Root cause fixed:** the Obsidian Second Brain vault was empty despite being
  enabled. The only write path was an *advisory floating preamble* in the wrapup
  stage — not a numbered procedure step, so the LLM completed the concrete local
  `.claude/memory/` Step 5 and silently dropped the advisory every time
  (locked as "Advisory" by PLAN-second-brain-write-failure ADR-006).
- **wrapup Step 5.6 (must-evaluate):** a new numbered step promotes qualifying
  local-memory entries into the curated, cross-project Obsidian vault. It is
  evaluated every wrapup; notes are written only when the LLM judges them
  *cross-project durable* (no count gate → no synthetic notes). Supersedes the
  prior "Advisory" decision.
- **`second_brain promote` CLI + `promote_note`:** the idempotency/path safety
  rail. Deterministic filename `<type>-<slug>.md`, `project_id`/`hm_source`
  link-back, dedup via `write_note` (re-promoting the same `--source-slug`
  updates in place, never duplicates).
- **Promotion receipt:** Step 5.6 emits `promotion evaluated: N candidates,
  M promoted` so silent under-promotion is observable.
- **Known limitation:** promotion fires only at `/hm:wrapup` — manual/quick
  commits bypass it (documented in CLAUDE.md).

## [0.26.8] - 2026-05-28

### Fixed: SessionStart drift hook no longer reports a phantom "downgrade"

- `sessionstart_drift._scan_plugin_cache_versions` scanned a single **hardcoded**
  marketplace dir (`…/cache/harness-maker-local/harness-maker/`). When a project
  was installed from the published GitHub marketplace (cache key `harness-maker`)
  but a stale local-dev marketplace (`harness-maker-local`) still sat in the cache
  with an older top version, the hook read the stale dir, decided the "latest
  installed" version was *older* than the version stamped in `harness.yaml`, and
  fired a false `accidental rollback` alarm on every session start. (Same family
  as the 0.26.6 hardcoded-cache-path bug.)
- The scan now globs **every** marketplace dir
  (`…/cache/<marketplace>/harness-maker/`), so the highest cached version wins
  regardless of the registration name.
- `latest_installed_version` is now additionally **floored by the running
  `__version__`**: "latest available" can never be older than the plugin code
  executing the hook. This also removes phantom downgrades in the harness-maker
  dev repo itself, where a source/editable build routinely runs ahead of any
  published marketplace cache.

## [0.26.7] - 2026-05-28

### Fixed: reconcile self-heals legacy Codex skills frozen by a pre-0.26.2 "phantom" content_hash

- Pre-0.26.2, the Codex skill pre-render path hashed stage/loop bodies (which
  embed the install_ref `uv run --with <path>` command) **before** path
  substitution, persisting a `content_hash` that never matches the file's own
  body. reconcile's REPLACE-vs-KEEP gate read that unverifiable hash as a user
  edit and KEPT the file, so the affected skills (`hm-execute`, `hm-verify`,
  `hm-wrapup`, `hm-loop`) **froze at their old version** on every
  `/hm:make --update` while sibling skills upgraded normally.
- reconcile now heals these: a `generated_by: harness-maker` file whose
  `source_template` is a Codex skill template (`codex/stage_skill.md.j2` /
  `codex/loop_skill.md.j2`) and whose `harness_maker_version` is below the
  0.26.2 floor is REPLACED instead of frozen. The heal is keyed on the **stable
  `source_template`** (never on volatile path/version enumeration) and bounded
  by a **fixed** version floor, so current/future user edits are never
  clobbered; the CLI's pre-render `.backup-<ts>/` covers the residual case.
- Render itself was already correct (0.26.2+ hashes the exact bytes it
  persists); this change recovers files left stale by the historical bug.

## [0.26.6] - 2026-05-28

### Fixed: hooks.json dedup now path-agnostic — no more triplicated hooks on marketplace switch

- The 0.26.x hooks merge normalizer (`render._normalize_hm_managed_command`)
  matched only the `harness-maker-local` cache path, so the GitHub-marketplace
  cache (`…/cache/harness-maker/harness-maker/<ver>/…`) and dev-repo
  (`--with /home/noel/harness-maker …`) command forms evaded dedup. Switching a
  project from the local to the GitHub marketplace (or bumping versions across
  them) left every harness hook **duplicated 2-3×** — each firing per event, the
  stale copies running old plugin code and dangling once the old cache was pruned.
- Hook identity is now keyed on the `python -m harness_maker.<invocation>` module
  suffix (module + trailing args), path-agnostic — covering local-cache,
  GitHub-cache, dev-repo, and any future path form. Already-duplicated `hooks.json`
  files **self-heal** to one entry per (event, matcher, module) on the next
  `/hm:make --update`. User-authored hooks are preserved unchanged.

## [0.26.5] - 2026-05-28

### Fixed: orphan-sweep now removes provenance-stripped assets of de-selected targets

- `reconcile._classify_orphan` consulted the render manifest only for files
  WITHOUT frontmatter. A file carrying a non-harness frontmatter — e.g.
  `.cursor/rules/*.mdc`, whose `generated_by`/`content_hash` provenance is
  intentionally stripped for Cursor's strict frontmatter parser — short-circuited
  to "theirs" and was kept forever. Dropping the `cursor` target therefore leaked
  a stale `.cursor/rules/harness.mdc` (the pure-JSON `.cursor/hooks.json` /
  `mcp.json` siblings were already swept via the no-frontmatter branch).
- The non-harness-provenance branch now runs the same per-path full-file-hash
  check the no-frontmatter branch already used: a byte-identical,
  blueprint-orphaned render is classified ours-clean and swept; user-authored,
  edited, or content-colliding-under-a-different-path files are kept. R4 safety
  preserved — a file with no manifest fingerprint is never deleted.

## [0.26.4] - 2026-05-27

### Fixed: Second Brain fully operational after config + runtime overhaul

- Corrected `vault_path` to actual Obsidian vault root (was pointing to non-existent subdir)
- Added `99_HM/harness-maker` folder entry with read+write and full note types
- Removed dead `trusted_allowlist` field from model, templates, and docs
- Added warn-and-strip migration for legacy `harness.yaml` files still carrying the field
- Wired `required_frontmatter` config to `validate_note()` at runtime
- Implemented search scoring: word-boundary detection + title 3x boost + tag 2x boost
- Enhanced degraded-mode empty-folders warning with stderr `ACTION:` message

## [0.26.3] - 2026-05-25

### Fixed: `/harness-maker:make` no longer resolves stale project installs

The plugin-level `/harness-maker:make` command now bootstraps through the newest
cached harness-maker package and delegates install selection to
`harness_maker.cli locate --plain`. This closes the stale resolver path where a
project without its own plugin entry could fall back to the first
`harness-maker@harness-maker-local` record, reusing another project's old cache
such as `kairos@0.7.3` and leaving `.claude/harness.yaml` stale after a full
interactive make run.

### Version bump

6-file version sync 0.26.2 -> 0.26.3: `pyproject.toml`,
`src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `uv.lock`.

## [0.26.2] - 2026-05-25

### Changed: verify-before-wrapup workflow cuts duplicate final checks

Production's recommended fused workflow now runs `execute -> review -> verify -> wrapup`
so the full regression suite has a single pre-commit owner. `verify` and
`wrapup` both call the `verification_cache` CLI; wrapup reuses a fresh
code/test-relevant marker instead of rerunning the same lint, format, type, and
test suite after memory or work-doc updates.

The relevant fingerprint ignores wrapup-only churn such as `.claude/memory/`,
`work-docs/`, review logs, and changelog edits, while still invalidating on
source, tests, lockfiles, tool configuration, CI, and harness templates. The
worktree handoff prose now makes deferred stash restoration visible, and both
wrapup and manual commit paths run `post-commit-pop` in UUID strict mode.

### Version bump

5-file version sync 0.26.1 -> 0.26.2: `pyproject.toml`,
`src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`.

### Fixed: worktree artifact janitor no longer blocks multi-session create

`worktree create` now prunes stale harness-owned artifacts before evaluating
the stash queue guard. Orphan loop markers and dangling owned `.worktrees/*`
directories are cleaned opportunistically, while finalize-stash refs are
deleted only when their tracked and untracked blob content is already present
in `HEAD`; otherwise they are preserved with an explicit warning.

The queue guard now counts only live finalize-stash refs whose session marker
still exists. Stale refs can no longer make unrelated multi-session worktree
creation fail, but genuinely live queued handoffs still trigger the existing
guard. Render manifests are also compacted by deduping unique
`(path, content_hash)` pairs so re-renders no longer grow the manifest without
bound.

### Changed: Codex second opinion is now mandatory for `plan-validator` (was opt-in)

When `codex_second_opinion.enabled=true`, the `plan-validator` agent now
**MUST** invoke Codex on every run (was "MAY … opt-in per call", which LLMs
correctly declined whenever findings were file:line-confirmable — so Codex
never actually fired). The validator must emit two new **top-level** output
keys, `codex_status` and `codex_reconciliation` (one entry per Codex finding,
each citing the finding's `file:line` or verbatim `message` — boilerplate
`"rejected: n/a"` does not satisfy the anti-boilerplate floor). The
Claude-derived verdict still owns `overall_assessment` (Codex stays input, not
a verdict source). On Codex failure the call degrades **loudly**:
`codex_status: "skipped"` + `codex_skip_reason`, surfaced to the user by
`/hm:plan` Step 4 — no hard-fail.

**Behavior change (intended):** harnesses with `codex_second_opinion.enabled=true`
get this on the next `/hm:make` re-render. `enabled` is the single knob — there
is no `mode` field; set `enabled=false` for the old soft behavior.

**Scope:** `code-reviewer` and `consensus-arbiter` keep their opt-in MAY
behavior for now — their output is a top-level JSON array that the
two-pass/verifier/consensus pipeline would strip a reconciliation envelope
from. Forcing them (with `k-of-n` spend implications) is deferred to a
follow-up PLAN. See `work-docs/PLAN-codex-mandatory-second-opinion.md`.

## [0.26.1] - 2026-05-24

### Fixed: `_count_user_md_files` 500-byte sniff window too tight (quality-gate regression on 0.26.0)

`readiness._count_user_md_files` searched `text[:500]` for `content_hash:` to
distinguish harness-rendered files from user-authored ones. The 0.26.0 feature
added `permissions: allow + deny` blocks to consensus-arbiter and plan-validator
(~280 bytes of new frontmatter), pushing `content_hash:` past byte 500. Both
agents were then mis-counted as "user files", inflating `ceremony_penalty` by
3 points (2 × 1.5) and dropping Side fresh-install composite 67 → 64, below
the test floor of 66.

Sniff window widened to 2000 bytes — covers the longest observed agent
frontmatter (executor.md at byte 809) with ample margin. Pure bug fix; no
behavior change for files whose `content_hash:` was already within 500 bytes.

Side fresh-install composite restored to 67 (above floor 66). Production
unaffected (its floor / signals are different).

## [0.26.0] - 2026-05-24

### Added: Codex CLI as second-LLM reviewer — `codex_second_opinion` opt-in (PLAN-codex-second-llm-integration)

New `harness.yaml.codex_second_opinion` block lets `code-reviewer`,
`consensus-arbiter`, and `plan-validator` invoke `codex exec` for a cross-model
second opinion. Disabled by default. Set `codex_second_opinion.enabled: true`
to activate.

When enabled, the 3 allow-listed reviewer agents receive:
- A `Bash(codex exec:*)` permission in their frontmatter (Jinja-conditional —
  ADR-007 byte-zero whitespace control keeps disabled-state rendering identical
  to today).
- A rendered `## Optional: Codex second opinion` section with a hermetic Bash
  recipe (`--ignore-user-config --ignore-rules` by default — ADR-006) that
  enforces a `finding[]` JSON schema (`.claude/schemas/codex-finding.schema.json`,
  newly rendered when enabled — ADR-008).

Failure policy is `warn-and-proceed` globally (ADR-003) — Codex outages do not
block reviewer agents. No in-code budget (ADR-004); Codex account rate limits
are the only ceiling. Transport is `codex exec` Bash dispatch only — no MCP
server registration (ADR-001).

**Prerequisite**: user must have `codex` CLI installed and `codex login`
completed. First call surfaces an auth error if missing.

**Orthogonal to `targets`** (ADR-009): `codex_second_opinion.enabled=true` works
even when `codex` is not in `harness.yaml.targets`.

Schema changes (back-compat): legacy harness.yaml files without
`codex_second_opinion:` load with safe defaults (`enabled: false`).

### Security (review Round 2 fixes shipped in the same feature)

- `output_schema_path` strict field validator: rejects absolute paths, `..`
  traversal, and shell metacharacters. yaml templates interpolate via
  `| tojson`; the rendered Bash recipe shell-quotes the argument. Closes a
  shell-injection / path-traversal vector via tampered harness.yaml.
- `consensus-arbiter` and `plan-validator` agents gain the full `deny:`
  baseline matching `code-reviewer` (Write, Edit, Bash bash/sh/python/eval/
  node/curl/npm/rm). Both agents previously had NO permissions frontmatter
  block at all — this feature's `allow:` addition exposed a gap that the
  review caught.
- Heredoc terminator `<<'PROMPT'` replaced with `mktemp` tmpfile + stdin
  redirect to prevent adversarial-diff content containing a bare `PROMPT`
  line from terminating the heredoc early and injecting shell commands.

## [0.25.1] - 2026-05-24

### Changed: loop self-pause prohibition rail (`templates/commands/hm/loop.md.j2`)

After a 2026-05-24 forensic observed a `/hm:loop` driver halting iter 1/50 with an invented `stop_reason="context-budget pause (operator decision; ... needs fresh context to avoid half-merged state)"` instead of running `/compact`, the loop spec gains a 3-layer prohibition that closes the rationalization path:

- **L0 — Self-pause prohibition rail** (new subsection right after Safety rails). Negatively enumerates the 4 forbidden halt rationales (context-budget / phase-boundary / operator-decision / half-merge-risk) with corrective action per row. Output prefix is strict — final report MUST start with `loop done — `; `loop paused` / `loop stopped` / `loop suspended` / `loop hold` are spec violations.
- **L1 — `/compact` mandatory procedure** (replaces the prior "Context advisory" block). The advisory wording is gone; `iter % 10 == 0` OR context usage ≥60% triggers a 4-step procedure (persist runtime → `/compact` → reload counters → continue iter). Explicitly states `/compact` and halt are mutually exclusive — there is no third branch where pause is correct.
- **L6 — Per-iter anti-self-pause reminder** (4-bullet block at every iter start). Reinforces legal halt list, mandatory `/compact`, phase-boundary ≠ stopping point, and required output prefix.
- **Section 8 schema strictness** — `stop_reason` field now enumerates the 8 legal strings (incl. `blocked: <reason>` escape hatch and `user interrupt`). Any other string surfaces as a regression, not normalized into schema.

### Why patch-level

Behavior-strengthening only — no breaking change. Existing legitimate halts (max_iter / time_cap / failed_streak / feature×3 / Gate 0 exhausted / convergence) all continue to fire on the same conditions. The rail only blocks LLM-invented `stop_reason` strings that were never in the schema.

## [0.25.0] - 2026-05-24

### Added: cross-session worktree data-loss defense (PLAN-worktree-cross-session-data-loss-defense)

5-layer defense after 3rd incident (2026-05-23) of `[fail:design] worktree-finalize-pulls-orphan-wip-into-main`. Each layer independently catches a different failure mode; only simultaneous regression across all 5 can re-open data loss:

- **Layer 1 ADR-003 queue-guard** — `worktree create` ABORTs when ≥2 unpopped `.claude/.hm-finalize-stash-*` ref files. `--allow-stash-queue` bypasses.
- **Layer 2 ADR-002 dirty-base-guard** — `worktree create` ABORTs when base has uncommitted USER changes. `--allow-dirty-base` bypasses. New `_is_create_guard_harness_artifact` filter recognizes the whole `.claude/` dir as harness-managed.
- **Layer 3 ADR-004 Session UUID** — `_session_marker_present` (file-exists) replaced by `_session_owns_marker(ref_uuid, current_uuid)`. `_validate_stash_ref_fields` schema gains `session_uuid` (optional for legacy refs; one-shot sentinel migration). `_cli_post_commit_pop` skips cross-session refs.
- **Layer 4 ADR-005 merge fence** — new `_acquire_merge_fence(base, timeout)` serializes parallel finalize. Primary: `fcntl.flock`. Secondary (equal-status): `os.open(O_CREAT|O_EXCL|O_WRONLY)` polling. Reliable on WSL2/NTFS.
- **Layer 5 ADR-006 scope-guard** — new `_verify_scope_subset(base, branch, staged_before)` asserts merge delta is a subset of worktree's own diff. Handles `--allow-dirty-base` interaction.

### Changed

- `CLAUDE.md` `## Multi-session worktree` section documenting 5 layers + escape flags + cherry-pick recovery cross-link.
- `.gitignore` forward-looking entries for `tests/e2e/sandbox*/` + `tests/fixtures/*/CLAUDE.md` (destructive `git rm --cached` requires user authorization, logged as follow-up).

### Test coverage

- `tests/unit/test_worktree_queue_guard.py` (12 + 1 skip), `test_worktree_dirty_base_guard.py` (11), `test_worktree_session_uuid.py` (7), `test_worktree_merge_fence.py` (4), `test_worktree_scope_guard.py` (4).
- `tests/integration/test_worktree_parallel_session.py` opt-in via `HM_RUN_PARALLEL_SESSION=1`. RED on pre-Phase-3 code → GREEN after Layer 3 UUID isolation.

### REVIEW round 1 fixes (5 auto-applied + dirname embed land)

- **P0-CON1 `.hm-session-uuid` gitignore** — `_current_session_uuid` now calls `_ensure_gitignore_entry(_SESSION_UUID_GITIGNORE_PATTERN)`; prevents commit-to-public.
- **P0-MAN1 `_acquire_merge_fence` lock_dir** — uses `git rev-parse --git-common-dir` so parallel worktrees of same repo share lockfile (was naive `is_dir()` → per-wt lockfile → no serialization).
- **P0-MAN2 dirname UUID embed (substantive fix)** — `create()` generates UUID + embeds in wt dirname `execute-{uuid12}-{ts}`. `_write_stash_ref_file` reads UUID from wt_name. `_cli_post_commit_pop` strict mode via `HM_OWNED_SESSION_UUIDS` env (wrapup template wiring task #14 follow-up). Original project-scoped persistent UUID (which silently defeated Layer 3) replaced.
- **P1-CON1 `session_uuid: legacy` rejected** — validator no longer accepts the sentinel value (was a permanent bypass vector).
- **P1-MAN1 dynamic base branch** — `_verify_scope_subset` uses `git merge-base wt_branch HEAD` instead of hardcoded `main`.
- **P1-MAN3 TOCTOU re-read** — `_current_session_uuid` re-reads file AFTER atomic_write (concurrent first-callers converge on disk value).
- **P1-MAN4 bypass flag stderr `[WARN]` logging** — every `--allow-stash-queue` / `--allow-dirty-base` use now leaves audit trail.

### Follow-ups landed

- **Task #14 closed (c6617fe)**: wrapup template Step 7.5 now exports `HM_OWNED_SESSION_UUIDS` via new `owned-uuids` CLI subcommand before invoking `post-commit-pop`. Layer 3 strict mode is now end-to-end load-bearing — env-var per-process boundary replaces filesystem-shared marker scan.
- **Phase 6 closed (8d50bac)**: `git rm --cached` applied to `tests/e2e/sandbox*/` (130 files) + `tests/fixtures/*/CLAUDE.md`. Sandbox seed scaffolding now re-created at test time via session-scoped autouse fixture (513c224, `tests/e2e/conftest.py`).
- **Phase 7 closed (f567899)**: `tests/integration/test_worktree_parallel_session.py` opt-in via `HM_RUN_PARALLEL_SESSION=1`; passes after Phase 3 follow-up dirname-embed land.
- **Phase 9 closed (f567899)**: 3 pre-existing test fixtures updated to match real-world `.gitignore` convention.

## [0.24.0] - 2026-05-23

### Added: opt-in maintainer-dogfooding feedback module (PLAN-auto-feedback-2026-05)

New `harness.yaml.feedback.enabled: bool` (default `false`, togglable only
via the `/hm:configure` interview — no CLI flag, no env var). When `true`,
dispatcher wrappers (`atomic_command.md.j2` + `workflow_command.md.j2`) emit
a Jinja-conditional block instructing the current turn's LLM to inspect
local telemetry (`telemetry_grep.gather_recent_signals`, ≤2KB output),
decide whether a harness-self issue occurred, and if so write a draft to
`.claude/observability/feedback/{YYYY-MM-DD}-{slug}-{hash}.md` plus print a
one-line footer with the exact `gh issue create --web --body-file` command.

When `false` (every non-maintainer user), the dispatcher block is a dead
Jinja branch — **zero file IO, zero token cost, byte-identical render**.

Zero socket calls from harness-maker Python — preserves PRIVACY.md +
ADR-005 of PLAN-oss-readiness-audit (`tests/unit/test_no_network.py`
extended with two new functions covering `feedback/telemetry_grep.py` and
`feedback/draft_writer.py`).

Surface additions:
- `FeedbackConfig` + `FeedbackDraft` + `TriggerSignal` Pydantic models
  with `strict=True` + `extra="forbid"`. AST-walk drift test
  (`tests/unit/test_privacy_doc_schema.py`) extended to cover the new
  schemas inside a scoped `@hm:privacy:feedback-module` marker block
  (validator C3 follow-up guards against generic-token false-pass).
- 5-field whitelist for draft body (`harness_maker_version + ide + os +
  stage + task_slug + trigger_signal + redacted error_message +
  .claude/-only file_paths`). Free-text markdown body — `bug.yml` form
  alignment intentionally dropped (ADR-004).
- Dedup by `sha256(trigger_signal_id, task_slug, YYYY-MM-DD)[:16]` —
  skip-if-exists today, regenerate next day (ADR-006).
- `PRIVACY.md` gains one anchored paragraph documenting the opt-in module
  (`@hm:privacy:feedback-module` marker block). Existing "Nothing is
  transmitted off your machine by this tool" sentence remains literally
  true.

Out of scope (deferred to follow-up PLAN): Codex stage skills bypass the
wrapper layer (use `codex/stage_skill.md.j2` / `codex/workflow_skill.md.j2`
directly), so Codex users who flip `feedback.enabled: true` see no
behavior change. Interview wiring also deferred — toggle via direct
`harness.yaml` edit in 0.24.0.

## [0.23.7] - 2026-05-23

### fix(render): dedupe hooks.json across cache-version bumps

Discovered in spoton 2026-05-23 dogfood: every `/plugin update` was leaving
stale hook entries in `.codex/hooks.json` (and `.claude/hooks/hooks.json`,
`.cursor/hooks.json` by the same path). After bumping spoton from 0.23.2
to 0.23.4, each event (`PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`,
`PermissionRequest`) had **TWO** entries — one for each cache version
— firing the same hook twice per event and dangling at a cache path
`/plugin update` would later clean up.

Root cause: `_entry_identity()` used the full command string as part of
the identity tuple, including the `--with .../harness-maker/X.Y.Z/...`
cache-version-pinned path. Different cache versions = different command
strings = different identities → merge classified the on-disk previous-
version entry as "user-added" and preserved it alongside the new entry.

- **fix(render): `_entry_identity` now normalizes harness-maker-managed
  commands** via new `_normalize_hm_managed_command` helper. Cache-version
  prefix collapses to a stable `<HM_CACHE>:<module>` form before identity
  tuple comparison. User-authored hook commands (which don't match the
  harness-maker cache shape) round-trip unchanged — genuine user
  additions still preserve correctly.
- **test(render): 2 new tests in `test_render.py`**:
  - `test_merge_hooks_json_dedupes_across_hm_cache_version_bumps` —
    regression pin for the spoton scenario.
  - `test_merge_hooks_json_preserves_genuine_user_added_command_alongside_hm`
    — counter-test confirming user-authored commands are NOT touched.
- 5-file version sync 0.23.6 → 0.23.7.

**Brownfield recovery for users hit by the duplicate-entries state**: after
`/plugin update` brings 0.23.7 into the cache, run `/hm:make --update`
once. The 0.23.7 merge logic will identify both old-version stale entries
as duplicates of the new shipped entry and dedup them to a single entry.

## [0.23.6] - 2026-05-23

### CI hotfix — strip ANSI codes before `make` subcommand assertion

The 0.23.5 `install-cmd-regression` job failed on its very first CI run:
`test_pypi_install_works` asserted that `harness-maker --help` advertises
the `make` subcommand via regex `^\s*[│|]?\s*make\b`, but Typer/Rich emits
ANSI color codes into the captured subprocess stdout even when not on a
TTY (`\x1b[1;36mmake` inside the Commands box). The regex matched only
when the local terminal happened to suppress ANSI; in CI the test
discovered the gap immediately.

- **fix(test): strip ANSI escape sequences from `harness-maker --help`
  stdout before regex matching** in
  `tests/integration/test_readme_install_commands.py::test_pypi_install_works`.
  Uses `re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", stdout)` — standard ANSI CSI
  pattern. The cleaned stdout is then matched against the `make`
  command-list regex.
- 5-file version sync 0.23.5 → 0.23.6.

The `install-cmd-regression` defense IS working — it caught the first
real regression on the first CI run (itself). Fitting.

## [0.23.5] - 2026-05-23

### CI install-cmd regression test + Codex first-run Skill doc fix (ADR-001 Q4 trigger fired)

The "README overpromises IDE parity" failure class hit its 3rd occurrence
in 4 days, firing the deferred Q4 trigger from
`work-docs/PLAN-readme-codex-truthification.md` ADR-001. This release adds
mechanical defense against that class + closes the most recent occurrence.

- **fix(readme): Codex CLI first-run Skill tool clarification.** README +
  README.ko Codex branch now explicitly tells the AI to run
  `harness-maker make` as a Bash command on first install — the Skill tool
  has nothing called `harness-maker:make` yet because `.agents/skills/` is
  generated BY `make`, not by the install step. Canonical anchor phrase
  `"Skill tool not yet populated"` appears verbatim in both files.
- **test(ci): new `tests/integration/test_readme_install_commands.py` +
  `_install_helpers.py`.** Four tests verify the README install commands
  mechanically — positive PyPI install (BLOCKING), Cursor git-clone path
  structure (BLOCKING), README allowlist drift (BLOCKING per ADR-002
  Round 2 amend), and codex marketplace install continues to fail as
  documented (ADVISORY via custom `@pytest.mark.advisory`).
- **ci(workflow): new `install-cmd-regression` job in `.github/workflows/ci.yml`.**
  Runs after `quality-gate` on PRs + main pushes. Installs `codex` via
  `npm install -g @openai/codex` for the advisory negative test;
  BLOCKING positive + lint tests run in one step, ADVISORY codex
  negative test in a separate `continue-on-error: true` step per
  ADR-002 Round 2.
- **chore(pytest): registered `advisory` marker** in `pyproject.toml`
  `[tool.pytest.ini_options].markers` so the CI workflow can filter
  blocking vs advisory tests via `-m advisory` / `-m "not advisory"`.
- **docs(readme): also bundles the post-0.23.4 truthification commit**
  (`docs(readme): truthify Codex CLI install path` — dc4fb73) which
  landed in main between the 0.23.4 tag and this release.
- 5-file version sync 0.23.4 → 0.23.5.

See `work-docs/PLAN-install-cmd-cifence.md` + ADR-001/ADR-002 for the full
decision record. **release.yml is intentionally NOT modified** —
`install-cmd-regression` gates PRs landing on main; tag-push trusts
main's state after the merge.

## [0.23.4] - 2026-05-22

### Release-recovery — ruff format fix-up

- **chore(format): apply `ruff format` to three test files** that were
  ruff-lint-clean but not formatter-clean. The 0.23.3 release attempt
  failed at the `quality-gate` job (ruff format --check), skipping every
  downstream publish job (TestPyPI, PyPI, GitHub Release) — nothing was
  published under 0.23.3, so no artifact recall needed. This patch
  re-formats `tests/integration/test_boundary_codex_toml.py`,
  `tests/unit/test_codex_user_config.py`, and
  `tests/unit/test_synthesize_codex_reasoning_effort.py`. Functionally
  identical to 0.23.3.
- 5-file version sync 0.23.3 → 0.23.4.

## [0.23.3] - 2026-05-22

### Codex compatibility fixes — SessionStart hook + profiles bootstrap

- **fix(hooks/sessionstart_drift): `systemMessage` lifted to top-level payload.**
  Codex CLI v0.130+'s `SessionStartHookSpecificOutputWire` is
  `deny_unknown_fields` and accepts only `{hookEventName, additionalContext}`
  nested. The prior 0.11.x layout nested `systemMessage` inside
  `hookSpecificOutput`, which Claude Code silently tolerated but Codex
  rejected on every session with "hook returned invalid session start
  JSON output". Both IDEs' official schemas place `systemMessage` at the
  top level — that's where it now lives. Tests updated with negative
  guards at BOTH levels (drift-only path AND hint path).
- **fix(templates/codex): `[profiles.cheap]` / `[profiles.deep]` removed from
  project-local `.codex/config.toml`.** Codex CLI v0.130+ rejects
  `[profiles.*]` at the project layer with "Ignored unsupported
  project-local config keys ... profiles". The template now carries a
  reference comment instead.
- **feat(codex_user_config): new module installs `[profiles.cheap]` /
  `[profiles.deep]` into user-level `~/.codex/config.toml`** when `codex`
  is in targets. Idempotent regex-based detection tolerates TOML
  whitespace variants (`[ profiles.cheap ]`), respects user-disabled
  blocks (`# [profiles.cheap]`), preserves all other user content
  byte-for-byte, and does not duplicate the ADR-008 explanatory header
  on partial-install re-runs. Wired from `cli.make` post-render; failure
  is graceful (printed to stderr, never blocks `make`).
- **fix(readiness): readiness hint updated** to point users at
  `~/.codex/config.toml` for the cheap/deep profile shortcuts.
- **test(boundary): `parse_codex_config_toml` now rejects project-local
  `[profiles.*]`** — guards future template regressions at the boundary
  layer instead of surfacing as a user-visible Codex warning on every
  session start.
- 5-file version sync 0.23.2 → 0.23.3.

## [0.23.2] - 2026-05-22

### L2 stability is convergence-aware (false-positive fix)

- **fix(personalization_audit): `compute_l2_stability` + `run_audit` now exclude
  override events that converged on the current preset default** before applying
  the penalty multiplier. ADR-0012 (amends ADR-0011 input set, formula unchanged).
  - Resolves a dogfood false-positive: `/hm:health` 2026-05-22 docked L2 from
    100 to 5 because the user's 2026-05-19 hand edits migrating `memory.*` onto
    the new `{enabled, dir, files}` template default were counted as instability.
    Every future schema rename in harness-maker would hit the same pattern for
    ~30 days. The L2 score and the surfaced `override_stability` action item
    are now both gated by the same divergent-event filter (ADR-003 in PLAN).
- **feat(personalization_audit): new helpers `_load_preset_defaults`,
  `_walk_axis_path`, `_converged_on_default`** + back-compat `int|list[OverrideRecord]`
  overload on `compute_l2_stability`. List path opt-in via `current_defaults` kwarg.
- **docs(adr): ADR-0012 added** (`docs/adr/0012-l2-convergence-semantics.md`).
  Documents the three sub-decisions: preset YAML template as baseline, `after=None`
  as clearing event, single `recent_divergent` list feeds both L2 score and actions.
- **rubric(personalization.yaml): inline note under `l2_stability`** pointing at
  ADR-0012 so the rubric file and the audit module agree on the new input semantics.
- 5-file version sync 0.23.1 → 0.23.2.

## [0.23.1] - 2026-05-22

### Phase 2 render-merge fully shipped + marker-syntax fix

- **feat(block_merge): `merge()` accepts `style: MarkerStyle` parameter** (default `HTML_COMMENT` for back-compat) — forwards to `parse_segments`, `parse_user_blocks`, `_collect_outside_marker_lines`, `_find_close`; fence-tracking now gated on `HTML_COMMENT`; HASH-comment files (`.toml`, `.sh`) use `_HASH_OPEN_RE` / `_HASH_CLOSE_RE` regex dispatch. Closes the half-shipped state from v0.23.0.
- **feat(render): `_render_pure_toml(merge_with_existing=True, merge_reports=...)`** invokes `block_merge.merge(..., HASH_COMMENT)` when reconcile flagged the path as `MERGE_BLOCK`. Re-validates merged TOML before atomic write — invalid-TOML merge falls back to template overwrite + `typer.echo(err=True)` warning. Render dispatch loop threads `merge_with_existing=fe.path in paths_to_merge` for both `_is_codex_config_toml` and `_is_codex_agent_toml`.
- **fix(templates)!: marker syntax corrected from `@hm:user:start:NAME` / `@hm:user:end:NAME` → `@hm:user:NAME` / `@hm:/user:NAME`** in `codex/config.toml.j2` and `codex/agent.toml.j2`. The v0.23.0 markers parsed as inert comments because `_HASH_OPEN_RE` requires the canonical `# @hm:user:<id>` open + `# @hm:/user:<id>` close (slash on kind, no `start:`/`end:` infix). v0.23.0 users will see the shipped marker block re-rendered with the corrected syntax on first v0.23.1 re-render; their backup snapshots still hold the prior state. Same rename across PLAN/CHANGELOG/preservation-matrix doc/MANUAL_CHECKLIST/e2e + unit tests.
- **test(e2e): `test_e2e_codex_config_toml_user_block_survives` xfail-strict marker removed** — flips to GREEN with the merge engine now working. 5/5 INTEGRATION=1 e2e scenarios pass.
- **docs(matrix): M7a/M7b cells flipped from ⚠️ → ✅**; "Phase 2 render-merge follow-up" section renamed to "Phase 2 fully shipped (v0.23.1)" with the v0.23.0 footgun caveat preserved for migration honesty.
- 5-file version sync 0.23.0 → 0.23.1.

## [0.23.0] - 2026-05-22

### Phase 7 follow-up additions (vs e844a28)

- **`tests/e2e/test_preservation_e2e.py`** — 5 INTEGRATION=1-gated scenarios verifying end-to-end on-disk preservation: Claude PascalCase hooks.json merge, Cursor flat-schema hooks.json merge, Codex PermissionRequest (matcher-less, nested) merge, `.codex/config.toml` user-block survival (initially xfail-strict in v0.23.0; flips to GREEN in v0.23.1 — see [0.23.1] entry above), `.backup-*/` auto-gitignore wiring + idempotency. 4 GREEN + 1 xfail.
- **`tests/cursor-compat/MANUAL_CHECKLIST.md`** — appended sections C7.1/C7.2/C7.3 for user-driven Cursor IDE + Codex CLI acceptance checks (verifies that merged hooks.json entries actually fire at IDE runtime, not just survive on disk). ~15 min user-side effort.

### Phase 2 render-merge half-shipped (discovered by e2e — honest disclosure)

- **`block_merge.merge()` is HTML_COMMENT-only by construction** (`block_merge.py:477-479` already documented this contract). Phase 2's reconcile **decision** correctly returns `MERGE_BLOCK` for HASH_COMMENT-markered TOML/sh files (verified by `test_m7a_codex_config_toml_marker_aware` etc.), but render's `_render_pure_toml` ignores `merge_paths` and falls back to template overwrite. The unit test gap masked this: unit tests verify reconcile decisions, e2e exposed the render-side gap. Backup remains the recovery path per ADR-001 — **user data is NOT lost**, just not auto-merged. Follow-up scope (v0.23.x): extend `merge()` with a `style: MarkerStyle` parameter and forward to `parse_segments` / `parse_user_blocks` / fence detection. e2e xfail-strict marker on `test_e2e_codex_config_toml_user_block_survives` flips to GREEN at that point.

### feat(reconcile)!: brownfield in-place preservation closure across hooks.json + TOML + sh, with `harness-maker prune-backups` CLI — PLAN-onboarding-backup-friction (7 ADRs across 6 interview rounds; validator MAJOR_REVISION → NEEDS_REVISION → RESOLVED). User reframed RESEARCH's "conditional skip backup" recommendation: backup is non-negotiable; the gap is whether existing user-owned commands/skills/agents/hooks survive at their original paths after `/hm:make` on a brownfield project. Empirical preservation audit (`docs/reference/preservation-matrix.md`) showed three always-REPLACE paths (hooks.json × 3 schemas, `.codex/*.toml`, `.claude/lib/*.sh`) where backup was the only recovery; Phase 1+3 (atomic ship) closes hooks.json via schema-aware in-place 3-way merge (new `ReconcileDecision.MERGE_JSON` + `_merge_hooks_json` with per-entry identity dispatched on Claude/Codex nested vs Cursor flat shapes per ADR-006; manifest records merged hash so `sweep_orphans` classifies merged file as ours-clean), plus `.codex/hooks.json` literal-match fix that closes a latent KEEP-fallback bug. Phase 2 extends block-merge `HASH_COMMENT` markers to `.toml`/`.sh` (`detect_marker_style` extension + reconcile TOML/sh dispatch); shipped `codex/config.toml.j2` and `codex/agent.toml.j2` gain `# @hm:user:extensions` blocks at TOML statement level (ADR-004/007 — inside `developer_instructions` multi-line strings explicitly NOT supported per the design's single-pass parser constraint). Phase 4 auto-adds `.backup-*/` to user's `.gitignore` via the proven `worktree._ensure_gitignore_entry` helper. Phase 5 adds `harness-maker prune-backups [--keep-last N=5] [--keep-days D=14] [--apply]` with read-only default + UNION keep-window semantics + symlink TOCTOU guard at both enumeration and pre-rmtree (closes security-reviewer P1 surfaced in `/hm:review`). Phase 6 updates `commands/make.md` safety receipt with references to the matrix doc + prune CLI. Phase 7 (cross-IDE e2e test module + manual IDE acceptance checklist) explicitly deferred — captured in PLAN frontmatter `phase_status.phase_7_e2e_on_disk: deferred`. Why **BREAKING**: `ReconcileDecision` enum gained `MERGE_JSON` value; any external code that pattern-matches on the enum's full membership (e.g. exhaustive match statements) must add a branch. Internal callers updated in the same commit. **REVIEW disclosure**: loop body skipped the per-iter review stage in favor of mechanical gates (ruff/mypy/pytest) — captured as `[wiki:gotcha] loop-body-skipping-review-stage`. Cumulative review at loop close caught 5 P1 + 9 P2 across 3 reviewers; orchestrator applied 9 fixes inline outside the strict-consensus auto-fix loop (the rubric's cross-domain coverage quirk returned Grade A despite 5 single-reviewer P1s — addressed honestly in REVIEW report rather than papered over). Dogfood signal motivating the work: 108 `.backup-<ts>/` directories accumulated in this repo before Phase 4/5 landed. New entries: `docs/reference/preservation-matrix.md` (user-facing audit), `tests/unit/test_preservation_matrix.py` (12-cell parametrized table — 11 GREEN + 1 strict-xfail for the `.sh` template-not-yet-shipped slot).

## [0.22.3] - 2026-05-22

### Removed (ADR-0007 supersedes ADR-0006)

- **`/hm:health` external_risks layer** — the entire 4-source crawl
  (`anthropic_blog`, `github_releases`, `arxiv`) + LLM relevance filter +
  adaptive threshold + per-item AskUserQuestion gate is gone. A 2026-05-22
  production run surfaced 12 items, 1 accepted (already known), 11 rejected
  — 91% noise. CVE detection (the one source with rare-but-critical value)
  survives via `secscan/dependency_cves.py` consumed by `/hm:verify`.
  Dashboard collapses from 3 sections to 2 (Structural + Personalization).
- **Skills deleted**: `research-crawler`, `relevance-filter` (templates +
  rendered output). Pinned LLM-judgment skill count: 5 → 4.
- **CLI subcommand `harness-maker health-finalize`** — folded into the
  single `harness-maker health` command. The split existed only because
  the 3-layer flow had a Python-then-Claude handoff via a tmp JSON file;
  with 2 layers, personalization stays Claude-judged inside the slash
  template which edits `dashboard.md` directly. `--external-risks-json`
  flag removed; `--skip-llm` flag removed (it gated the deleted relevance
  scorer).
- **Verify Check 4 (`external_risks_pending`)** — 6-check protocol becomes
  5-check. Remaining check IDs renumber 5→4 and 6→5. CI pipelines that
  key off check NAMES are unaffected; pipelines that key off check IDs
  must update. The `_emit_verify_text` denominator changed from a
  hardcoded `/6` to dynamic `f"/{total}"`.
- **Python source modules**: `crawler/anthropic_blog.py`,
  `crawler/arxiv.py`, `crawler/github_releases.py`, and `relevance.py`
  (entire file — includes the stale-asset half: `StaleAsset`,
  `detect_stale_assets`, `build_proposal_lines`, `update_last_reviewed_at`,
  `StaleAssetUpdateError`). The stale-asset functions had zero production
  caller. `crawler/osv_dev.py` preserved (consumed by
  `secscan/dependency_cves.py`).
- **Tests deleted**: `tests/unit/test_relevance.py`,
  `tests/unit/test_relevance_stale.py`,
  `tests/unit/crawler/test_anthropic_blog.py`,
  `tests/unit/crawler/test_arxiv.py`,
  `tests/unit/crawler/test_github_releases.py`. `test_crawler_osv_dev.py`
  preserved.

### Migration

Existing users running 0.22.3 the first time:

- Run `/hm:health` once — produces a fresh 2-section `dashboard.md`. The
  parser silently drops any stale `## External risks` section from
  pre-0.22.3 dashboards; no breakage.
- (Optional, gitignored anyway) clean up orphan artifacts:
  ```bash
  rm -rf .claude/observability/health/raw-*.jsonl \
         .claude/observability/health/decisions.jsonl \
         .claude/observability/.health-external-risks.tmp.json
  ```
- `/hm:verify` shrinks 6 checks → 5. CI pipelines keying on check IDs
  must shift `id 5 → 4` and `id 6 → 5`.

### Internal changes

- `synthesize.py` + `interview.py` `_ALL_SKILLS` lists pruned: 11 → 9.
- `communication_audit.py:PINNED_SKILLS`: 5 → 4 (`relevance-filter` removed).
- `cache.py:SOURCE_TTLS` trimmed to `{"osv_dev": TTL_1H}` only.
- `models.py:CrawlItem` docstring + source-field comment narrowed to OSV.
- `spec_inventory/{batch_generator,catalog}.py` classification tuples
  trimmed to OSV-only.
- `.claude-verify.sh`: `phase_5` reduced to OSV-only test; R2 anti-rot
  check narrowed to `osv_dev` import; skill assertions reduced to 8 entries.
- `templates/stages/verify.md.j2` rewritten for 5-check protocol; Check 4
  description deleted.
- `templates/cursor/rules/harness.mdc.j2` drops `/hm:refresh` 4-source
  description.
- `cli.py:552` + `:703` "3-layer harness health" strings → "2-layer".

### Version bump

5-file version sync 0.22.2 → 0.22.3: `pyproject.toml`,
`src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`.

Per ADR-0007 §Consequences: shipped as patch despite CLI subcommand
removal because the surface is internal (`health-finalize` had no
public-docs reference; only known caller was the auto-updating slash
template). Accepted risk documented.

## [0.22.2] - 2026-05-22

- **fix(wrapup): add `ruff format --check` to Step 2 verification command set** — closes the recurrence vector for `[fail:lint] ruff-format-not-in-local-verify-pass` (now count:2 — v0.19.2 + v0.22.0 both shipped as ghost tags because `ruff format --check` was missing from `/hm:wrapup` Step 2's "Final verification pass" command list, while CI's `quality-gate` ran both `ruff check` AND `ruff format --check`). The wrapup template's Step 2 had only `ruff check src/ tests/` + `mypy --strict src/` + `pytest -x` — `ruff check` does NOT catch formatting violations, only lint rules. This patch adds one line to both rendered branches (Claude Code and Codex) of `src/harness_maker/templates/stages/wrapup.md.j2`: `uv run ruff format --check src/ tests/` with an inline comment citing the failure entry. snapshot fixtures regenerated (8 files). 5-file version bump 0.22.1 → 0.22.2. Wrapup-template self-fix — when our own template causes a known failure to recur, fix the template rather than relying on human discipline at every wrapup.

## [0.22.1] - 2026-05-22

- **docs(observability): launch-baseline.md + cold-eval cycle close (PLAN-harness-maker-cold-eval Phase 3)** — `docs/observability/launch-baseline.md` (new, ~70 lines) commits the Day-0 metric snapshot that ADR-008 promised: PyPI weekly downloads **1,424**, GitHub stars **2**, Discussions count **1**, forks/watchers/issues **0**. Three reproducibility CLI commands embedded inline (pypistats API + 2 × `gh api`). ISO target dates locked: **Day +30 = 2026-06-21**, **Day +60 = 2026-07-21**, **Day +90 = 2026-08-20** — derived from the v0.22.0 tag date (2026-05-22). Retrospect-trigger TODO at Day +90: two-branch decision tree — if PyPI weekly grows ≥3× from baseline (≥4,272/week *sustained*, not a one-day spike), kick off `harness-maker-v0.23-uvx-cta-plan` to promote the no-install profile-wedge to the README hero; otherwise kick off `harness-maker-personalization-retrospect` to re-examine ADR-008's PyPI-downloads-as-primary-metric choice. baseline.md "Notes" section documents PyPI Day-0 noise inflation honestly (TestPyPI smoke-installs from 4 recent tags + maintainer worktree installs + bots) — interpret the 3× threshold as *sustained*, not absolute. "100% local telemetry" PRIVACY commitment intact (all measurements query public PyPI + GitHub endpoints, not internal `.claude/observability/*` files).
- **PLAN-harness-maker-cold-eval cycle closed.** `status: complete` — Phase 1 (v0.21.0 + v0.21.1) + Phase 2 (v0.22.0 BREAKING) + Phase 3 (v0.22.1) all shipped 2026-05-22 across 5 commits (07461be / ccd185a / 067c748 / 9bff72c / this commit). 8 ADRs locked; plan-validator critique #1 (the silent SIDE→PRODUCTION mis-routing trap from the `experiment` enum removal) caught and resolved pre-execute; ADR-002 amended in v0.21.1 (PNG → MD) with full justification preserved in PLAN body. Memory: 4 new wiki patterns + 2 new failure entries (`worktree-finalize-untracked-loss` count:1 — recovered via base-write discipline; `breaking-enum-change-pre-flight-grep-discipline` + `snapshot-regen-on-main-not-worktree-discipline` + `adr-spec-deviation-amendment-over-silent-fudge` + `cold-eval-staged-ship-via-adr-separation` as recurring patterns). Cycle duration: research → plan → 4 execute turns + 4 wrapups → tag-push → release within a single day.
- **5-file version bump** to 0.22.1 across the 3 plugin manifests + pyproject.toml + `__init__.py`. Patch release per semver (docs-only — no API or behavior change vs v0.22.0).

## [0.22.0] - 2026-05-22

### BREAKING

- **`ProjectProfile.lifecycle` enum changed: 4-tier → 3-tier (`active` | `maintenance` | `dormant`); `"experiment"` removed entirely (ADR-006, PLAN-harness-maker-cold-eval Phase 2).** Migration: external Python code that imports `ProjectProfile` and string-matches `profile.lifecycle == "experiment"` must change to `profile.lifecycle == "dormant"` (semantic replacement — the new tier is the most conservative bucket and routes to the same SIDE preset downstream). Internal callers updated in the same commit (5 production modules + 13 test files). Root cause this fixes: reality-check on 5 public repos showed `BurntSushi/ripgrep` mis-classified as `"experiment"` despite being a mature CLI; the prior algorithm conflated "no .git", "git error", and "zero recent commits" under one vague label. New algorithm: `active` = ≥10 commits in last 30d, `maintenance` = 1–9 commits in last 30d, `dormant` = 0 commits in last 30d (or `.git` missing, or subprocess error).

### Phase 2 features (PLAN-harness-maker-cold-eval ADRs 005, 006, 007)

- **Rust `detected_checks` whitelist (ADR-007).** `Cargo.toml` present → emits `cargo test`, `cargo clippy`, `cargo fmt --check`. Standard cargo subcommands always work when Cargo.toml exists, so the whitelist is provably safe (no false positive risk). Closes the empty-`detected_checks` gap that `ripgrep` reality-check exposed.
- **Node `detected_checks` whitelist (ADR-007).** `package.json` scripts that match the keys `test`, `lint`, `check`, `typecheck`, `format`, `build` emit `<runner> run <key>`. Runner picked from lockfile (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, otherwise npm). Scripts with non-whitelisted keys (`build:prod`, `deploy`, project-specific names) are skipped to avoid emitting commands the user didn't intend as harness checks.
- **Python strict block matching (ADR-007).** Pre-v0.22.0 had bare-string `"mypy" in content` / `"pytest" in content` matching pyproject.toml, which emitted `uv run mypy .` on repos that merely listed mypy as a dep (`psf/requests` reality-check). New policy: only `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` block presence triggers detection. False-positive vector closed.
- **`package_manager` manifest fallback (ADR-007 exception).** Lower-stakes documentation hint — pyproject.toml without lockfile narrows by header inspection (`[tool.uv]` → "uv", `[tool.poetry]` → "poetry", otherwise "pip"). package.json without lockfile → "npm" default. Pre-v0.22.0 returned `""` when no lockfile was present even when manifest was clearly stack-specific. Documented as an intentional asymmetry vs `detected_checks` strictness because `package_manager` is a documentation hint, not a runnable command — false positives there are softer.
- **`detected_checks` cap raised 4 → 6.** The whitelist now spans Python + Rust + Node + Makefile; a polyglot repo can legitimately want more than 4 distinct check commands.

### Verification

- 5 production modules updated: `profile.py` (`_detect_lifecycle`, `_detect_mechanical_checks`, `_python_package_manager`, `_node_package_manager`), `models.py` (`ProjectProfile.lifecycle` Literal), `interview.py` (`proxy_profile` + `_recommend_preset` set literal at 269/315), `recommendation.py` (preset set literal at 249), `modular_edit.py` (hardcoded dict at 121).
- 13 test files refreshed (validator critique #1 enumerated each — full list in PLAN-harness-maker-cold-eval.md ADR-006 affected-files).
- 11 new unit tests added in `tests/unit/test_profile.py` covering 3-tier lifecycle dispatch (mock subprocess), Rust/Node whitelist positives, Python strict-block negative (no false positive on dep listing), and manifest-fallback exception cases.
- 1 new integration test `tests/integration/test_profile_reality_check.py` — gates the regression against 6 real public repos (requests, fastapi, ripgrep, fastify, htmx, embedeval) behind `INTEGRATION=1` env guard. Each repo's expected lifecycle/`package_manager`/`detected_checks` shape encoded directly from PLAN Phase 2.5.
- 4 snapshot fixtures regenerated (CLAUDE.md frontmatter version 0.21.1 → 0.22.0; behavior fixtures unaffected because the lifecycle field is computed at profile-time, not pinned into the rendered harness).
- Phase D: ruff + mypy --strict + pytest -x all green on main after worktree finalize + snapshot regen (the `snapshot-regen-inside-worktree` count:7 recurrence pattern was deliberately avoided by running `regenerate.py` from main, not the worktree).

### Phase 3 deferred to v0.22.1

`docs/observability/launch-baseline.md` (Day-0 metric snapshot + 30/60/90-day target dates) is the Phase 3 deliverable. Best-fit timing is within 24h of the v0.22.0 tag; the file ships in the v0.22.1 wrapup alongside the baseline observation.

## [0.21.1] - 2026-05-22

- **feat(readme): showcase artifact + ADR-002 PNG→MD amendment (PLAN-harness-maker-cold-eval Phase 1.2)** — the v0.21.0 headline ("Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness.") gets its proof artifact this patch. `docs/assets/showcase-diff.md` (170 lines) captures a real `harness-maker make` comparison between two public maintainer projects: **embedeval** (Python embedded-firmware LLM benchmark, Side preset, `claude-code` target) vs **harness-maker** self (Production preset, `claude-code + cursor + codex` targets). Same maintainer, same Python+uv+Pydantic stack — yet 99 vs 54 rendered files (+45 diff). Five Production-only agents (`autoloop-coder`, `concurrency-reviewer`, `plan-validator`, `stuck`, `test-reviewer`) are each tied to a stage that Side preset disables; 15 multi-IDE-only assets (13 Codex agent TOMLs + Codex config + Cursor hooks + AGENTS.md root) are driven by the targets axis. ADR-002 quantitative threshold (≥3 file additions OR ≥1 distinct agent/skill) cleared by 15×.
- **ADR-002 amended: PNG → MD format.** The original ADR specified `docs/assets/showcase-diff.png`. Shipped as `.md` instead because markdown is strictly better on 6 of 7 axes — git-diff reviewability, full-text search, screen-reader accessibility, one-turn generation cost (no PIL/matplotlib pipeline), update cost (text edit), file size (6.7 KB vs 50–200 KB typical PNG). PNG only wins on "inline display in first README scroll" which the hero `📸` emoji + click-through link compensates for. The MD form also documents the quantitative threshold table inline, so the proof artifact is self-documenting rather than relying on a hand-rendered screenshot a skeptical reader would distrust. Full justification: `work-docs/PLAN-harness-maker-cold-eval.md` ADR-002 Amendment 2026-05-22.
- **README hero** gains a one-line link directly under the ADR-004 v2 spec-kit comparison: *"📸 See it on two real projects → docs/assets/showcase-diff.md — same maintainer, same Python stack, +5 agents and +15 multi-IDE files between Side and Production preset renders."* The headline→evidence chain now resolves in two clicks (README → showcase MD → reproduce command).
- **5-file version bump** to 0.21.1 across the 3 plugin manifests + pyproject.toml + `__init__.py`. Patch release per semver (docs-only, no API or behavior change). Phase 2 (profile.py Rust/Node hardening + BREAKING lifecycle enum) and Phase 3 (launch-baseline.md) remain deferred to v0.22.0 per ADR-001.

## [0.21.0] - 2026-05-22

- **feat(readme): personalization headline + spec-kit comparison line + surface pruning (PLAN-harness-maker-cold-eval Phase 1, 8 ADRs)** — README hero retains the locked tagline ("A different harness for every project — built from yours, never generic.") and gains a one-line comparison directly under it: *"Other harnesses give everyone the same starting point. harness-maker reads YOUR repo and builds YOUR harness."* (ADR-004 v2 — earlier "fixed bundle" wording was inaccurate for BMAD's role-based orchestration and agent-os's memory-first design per plan-validator critique #5). The 5 research-tier features (anti-rot crawler, /hm:health 3-layer rubric, SessionStart drift, cache-miss classification, unified health audit) are demoted from the Features section into a new "🔧 Advanced features" sub-section that sits *inside* README (not split into a separate doc — `docs/HOW-IT-WORKS.md` linkage preserved, anchor backwards-compat intact). "How it compares" first line rewritten to match ADR-004 v2 and the "Anti-rot crawl" axis row removed (the same content lives once now, in Advanced features). 3 plugin manifest `description` fields synchronized to the 136-char About-sidebar copy from [wiki:positioning] — keyword bloat (anti-rot / 3-layer / consensus / etc.) removed so the marketplace snippet reads as the headline rather than a feature list. 5-file version bump to 0.21.0 (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`). **Not yet shipped this release**: Phase 1.2 showcase image (`docs/assets/showcase-diff.png` — embedeval Side preset vs harness-maker Production preset render diff — deferred to v0.21.1 because the render pipeline requires running `harness-maker make --reinterview` against the embedeval clone and capturing a meaningful visual diff, which exceeded this release's turn budget). Phase 2 (profile.py Rust/Node hardening with BREAKING `lifecycle` enum change, "experiment" tier removed) is scheduled for v0.22.0 as a separate release per ADR-005. Plan-validator outcome: NEEDS_REVISION → RESOLVED (1 critical + 7 warnings + 2 suggestions all addressed in PLAN body or via interview round 11).

## [0.20.2] - 2026-05-21

- **sec(deps): bump transitive `idna` 3.13 → 3.15 to resolve GHSA-65pc-fj4g-8rjx (CVE-2026-45409, moderate)** — the advisory describes a DoS path where `idna.encode()` consumes substantial resources on specially-crafted long Unicode inputs (e.g. repeated `U+0660`, or `U+30FB` followed by `U+6F22`) before length validation, bypassing the CVE-2024-3651 fix. Affected: idna `0.1`–`3.14`; first patched: `3.15` (with initial mitigation in `3.14`). Real-world exploit surface in harness-maker is **effectively zero** because `idna.encode()` is only reached transitively (through `httpx` and the `anthropic` SDK) for outbound calls to a fixed allowlist of hosts — `api.anthropic.com`, `arxiv.org`, `api.github.com`, `api.osv.dev`, `www.anthropic.com` — none of which is influenced by user input. Despite the low practical risk, shipping the bump because the fix is mechanical (one `uv lock --upgrade-package idna`) and keeps Dependabot's main-branch alert table clean. Verified via the project's own `harness_maker.crawler.osv_dev` scanner: `0` findings on the new lockfile (was 1 on 3.13). pytest under `FORCE_COLOR=1`, mypy --strict, ruff, ruff format all green. No production code changed.

## [0.20.1] - 2026-05-21

- **fix(tests): `--help` substring assertions broken under CI's `FORCE_COLOR=1`** — `v0.20.0` release run failed at `quality-gate` because Click 8.2 / Typer 0.16+ renders `--help` output through Rich with ANSI escapes and width-driven line wraps when `FORCE_COLOR=1` is set (GitHub Actions default). The user's `tests/snapshot/test_cli_help.py` + `tests/unit/test_locate_cli.py` did naive `"--plain" in result.stdout` / `"--require-version" in result.stdout` checks that worked on a normal local TTY but broke when Rich inserted ANSI sequences mid-token or wrapped the option name across a panel border. Fix: pass `color=False` to `runner.invoke()` AND strip residual ANSI via a `_ANSI_RE.sub("", out)` belt-and-suspenders before substring assertions. Snapshot fixtures + e2e sandboxes unchanged; help-text wording unchanged. Reproduced locally with `FORCE_COLOR=1 uv run pytest tests/{snapshot,unit}/test_*cli*.py` (was failing, now passes). v0.20.0 tag exists but published nothing — `quality-gate` is the first job, so build / publish-testpypi / publish-pypi / github-release all skipped on the failed run.

## [0.20.0] - 2026-05-21

- **feat(cli): add `harness-maker locate` subcommand + `--require-version X.Y` gate (PLAN-locate-cli-version-gate, 3 ADRs)** — eliminates the fresh-install footgun where bootstrap meta-prompts could resolve a stale plugin cache entry (e.g. `kairos@0.7.3` from `entries[0]` fallback) instead of the just-installed user-scope version, then every downstream command emitted "unknown command / option / skill" errors. `locate` walks `~/.claude/plugins/installed_plugins.json` with a strict priority ladder (`projectPath == cwd` > `scope == "user"` > `installedAt` desc tiebreak) — no tier-3 fallback to "most-recent project-scope of another project" because that would re-introduce the same footgun in a different form. Default output is JSON (`{marketplace, version, scope, installPath, gitCommitSha, installedAt, projectPath?}`); `--plain` prints `installPath` alone for shell consumers. Exit codes are stable: `0` ok, `2` version mismatch, `3` no install found. The `--require-version X.Y` flag is available on both `locate` and `make` (gate fires before `make` does any disk work). New `docs/BOOTSTRAP.md` is the canonical onboarding reference for Claude Code / Cursor / Codex CLI, with an explicit anti-pattern callout reproducing the legacy buggy resolver and a migration snippet. `/hm:make` template (`templates/commands/hm/make.md.j2`) now shells out to `locate --plain` rather than re-running its own `ls / sort -V` cache walk, so the resolver lives in one place. Snapshot fixtures regenerated for the 8 preset×dev_mode×fixture matrix — only `commands/hm/make.md` body SHA changed, all other rendered files unchanged.

- **feat: add `/hm:help` — locale-aware (en/ko) one-screen overview of every `hm` command, the recommended workflow path, and the user's current harness settings (PLAN-help-command, 2 interview rounds / 4 ADRs / plan-validator NEEDS_REVISION_RESOLVED).** Static locale templates (`commands/hm/help.{en,ko}.md.j2`) via the existing `_localized()` helper — render is locked at make-time, no per-invocation LLM translation. No arguments — `/hm:help` always shows the same overview. Cross-IDE display is `targets`-driven: `{% if "cursor" in config.targets %}` and `{% if "codex" in config.targets %}` blocks surface IDE-specific notes only for the IDEs the user actually configured. Codex receives a parallel `.agents/skills/hm-help/SKILL.md` (mirroring the `/hm:loop` precedent, ADR-004) so Codex users have parity for the help discovery surface; the SKILL body is pre-rendered with `is_codex=True` so all command stubs use the `@hm-*` form. Template body lists atomic stages (7), fused workflows (read from `config.workflows`, with the user's `default_workflow` marked ⭐), and meta commands (6) in compact tables; followed by an ASCII workflow flow, a current-settings table, and IDE-specific notes. Plan-validator (sonnet) caught one critical pre-write regression — `config.fused_workflows` is an `InterviewAnswers` field, not a `HarnessConfig` field; the template uses `config.workflows` (matches `loop.md.j2:547`) and the Phase 1 exit renders all three new templates under `StrictUndefined` so any future regression Jinja-crashes immediately. Tests: 7 unit assertions in `tests/unit/test_help_command.py` covering both locales, targets-conditional Cursor/Codex blocks, exact `default_workflow ⭐` substring match, and `@hm-*` vs `/hm:*` stub correctness for the Codex SKILL body. Snapshot regeneration touched all 8 fixtures (every preset×dev_mode now ships `commands/hm/help.md`). Folded into the 0.20.0 minor alongside `locate` rather than shipping as a separate patch.

## [0.19.1] - 2026-05-20

- **fix: `/hm:make --update` self-upgrade bootstrap trap** — the rendered `commands/hm/make.md` was hard-pinning `uv run --with <plugin-cache>/<rendered-version>` so `/hm:make --update` always re-executed the OLD CLI, which re-emitted its OLD pin. Effect: `/plugin update` bumped the cached plugin but `/hm:make --update` could never adopt it; the only escape was the plugin-level `/harness-maker:make`. Template `make.md.j2` now prefixes a single-line bash discovery shim — `ls -1d ~/.claude/plugins/cache/harness-maker*/harness-maker/[0-9]*.[0-9]*.[0-9]* | awk-prefix-by-basename | sort -V | tail -1` — and uses the discovered path, falling back to the render-time `{{ harness_maker_src_path }}` pin when discovery yields nothing (no plugin cache / direct source checkout). Sort is keyed on the version basename, not the full path, so `harness-maker-local/.../0.19.1` correctly beats `harness-maker/.../0.17.0` (the naive `sort -V` on full path picked the wrong dir because `-` < `/` in ASCII collation). Scope-limited to `make.md.j2` on purpose: other slash commands (`exec-rev`, `loop`, `configure`) keep their render-time pin because they are semantically coupled to the harness they were rendered with — only `/hm:make` exists to upgrade, so only it should self-upgrade. Existing users still need a **one-time** escape (via `/harness-maker:make` or a manual `uv run --with <latest-cache> python -m harness_maker.cli make . --update`) to install the fixed template; after that the trap closes permanently.

## [0.19.0] - 2026-05-20

- **CI infrastructure: upgrade 4 GitHub Actions to Node.js 24-compatible versions** — `actions/checkout` v4 → v6.0.2 (SHA `de0fac2`), `astral-sh/setup-uv` v5 → v8.1.0 (SHA `08807647`), `actions/upload-artifact` v4 → v7.0.1 (SHA `043fb46d`), `actions/download-artifact` v4 → v8.0.1 (SHA `3e5f45b2`). Each new pin verified by reading the action's `action.yml` `using:` field == `node24`. SHA-pinning preserved per project security policy. The 0.18.0 release run emitted Node 20 deprecation annotations on every job; this minor closes that warning and prepares for the June 2nd, 2026 forced migration. Single sed-driven replacement across `ci.yml`, `nightly.yml`, `release.yml` (20 reference points total). No semantic workflow change — only the action version pins moved.

## [0.18.0] - 2026-05-20

- **Total SPEC coverage initiative — `/hm:spec` framework upgrade + dual-file SPECs (PLAN-total-spec-coverage, 10 phases / 13 ADRs)**: ship the foundation for AI-verifiable per-feature SPECs across the ~146 surface (52 Python + 94 templates per ADR-001 computed universe). Loop ran in `.worktrees/execute-20260519T1544Z/` with `--per-iter-workflow exec-rev`, plan-validator passes R1 + R2 → MAJOR_REVISION resolved via interview round 5 (P5 redesign to prompt-driven `/hm:loop p5-batch-N`, NOT `autoloop_driver.run()`) + round 6 (P0.5 baseline fallback rule).
  - **P0** test inventory reverse-map (`spec_inventory.reverse_map` + `__main__` CLI + 36 unit tests). Walks `tests/`, AST-extracts docstring + source-ordered first-3 asserts, classifies via injectable `JudgeProtocol` (heuristic fallback for unit determinism). Split exit Gate A (auto avg_confidence ≥ 0.85) + Gate B (manual ≥ 18/20). Heuristic-mode run produced **1972 entries across 155 files** in `work-docs/test-inventory-2026-05.json`; LLM Gate A pending user-side `INTEGRATION=1` invocation.
  - **P0.5** mutation baseline measurement (`work-docs/spec-mutation-baseline-2026-05.json` + `pyproject.toml` `mutmut>=2.4` dev dep + 60-min wall-clock fallback with `--use-coverage` sampled 200-mutant budget per ADR-005). Baselines for `render.py` + `cache.py` pending user-side full mutmut run; PLAN's `max(baseline + 5pp, tier_floor)` formula carries `pending_full_run: true` until measured.
  - **P1** SPEC framework upgrade — 5 new modules + 1 extension: `spec_machine.py` (pydantic schema_v1 + 6-rule `cross_validate` + `evaluate_coverage` + `resolve_pytest_selector` test-naming bridge per ADR-004), `spec_mutation.py` (`mutmut` wrapper + tier-relative `threshold_for(tier, baseline) = max(baseline + 5pp, tier_floor)`), `spec_inventory.catalog_schema` (pydantic Feature/L1Cluster/Catalog per ADR-012), `spec_inventory.batch_state` (CRUD helper per ADR-013 R2, NOT `ExecutorCallable`), `spec_quality.py` extension (3 new dims `machine_verifiability` / `mutation_coverage_set` / `non_python_intent_alignment` + optional `machine_yaml` kwarg, backward-compat preserved for all 5 existing callsites per Risk R12). 101 unit tests across 6 new test files; mypy --strict + ruff clean.
  - **P2** feature catalog: 172 L2 features + 15 L1 cluster seeds enumerated. Heuristic tier scoring with weight-recalibration hook (ADR-008 if user override rate > 50%). `work-docs/spec-catalog-2026-05.yaml` written.
  - **P3** pilot 3 reference SPECs — 6 SPECs total (3 L2 + 3 L1 cluster stubs): `SPEC-render` (T1 Py), `SPEC-cache` (T2 Py), `SPEC-agent-code-reviewer` (T1 non-Python, 3-layer ADR-009), plus `SPEC-rendering` / `SPEC-caching` / `SPEC-reviewers` L1 stubs. All 6 pass `spec_machine.validate` + `cross_validate` (0 errors). `specs/INDEX.md` coverage matrix seeded.
  - **P4** framework adjustment + representativeness probe — `work-docs/spec-framework-v1.1-deltas.md` lists 7 framework fixes (assertion source-order bug, pending_test rule-3 skip, tier-token matching, ISO-date strict-string handling, etc.). Probe against 2 non-pilot features dry-run PASS — **P4.5 not triggered**.
  - **P5** bulk authoring scaffolded — `work-docs/p5-batch-state.yaml` ready; ~166 SPECs remaining for prompt-driven `/hm:loop p5-batch-N` invocations (separately user-initiated). Per ADR-013 R2, P5 does NOT route through `autoloop_driver.run()`.
  - **P6** drift detection — `observability.spec_drift.scan(specs_dir, dev_mode=...)` per ADR-013 (only runs when `dev_mode == "spec-driven"`; task-driven returns skipped report). Detects orphan tests, stale mutations (T1 > 7d / T2 > 14d), AC↔test mapping gaps, per-SPEC OQ overflow (> 3), aggregate OQ count (cap 30). 12 unit tests.
  - **P7** version bump — 5 files synchronized at **0.18.0**. **No git tag, no push** (user constraint mid-loop). Release workflow is intentionally not triggered; users can manually tag + push when ready.
  - **Deferred to follow-up**: (a) `templates/stages/spec.md.j2` dual-write extension; (b) `templates/commands/hm/loop.md.j2` P5 batch procedure baked; (c) `.github/workflows/spec-mutation.yml` + `spec-drift.yml`; (d) LLM judge wiring in `spec_inventory.reverse_map`. All four documented in `spec-framework-v1.1-deltas.md` as carry-over for the next minor.

## [0.29.0] - 2026-06-07

## [0.19.3] - 2026-05-20

- **Re-tag of 0.19.2 after `ruff format --check` quality-gate failure** — v0.19.2 quality-gate stopped at the format step (5 files in the calibration commit were not run through `ruff format` locally before tag — only `ruff check` was, which doesn't enforce formatting). v0.19.2 produced no PyPI publish + no GitHub Release page (quality-gate is the first job, so nothing downstream ran). v0.19.3 ships the identical feature scope below, with `ruff format` applied to `src/harness_maker/{ai_readiness,improvement}.py` and the 3 new test files. Lesson recorded in failures as `[fail:lint] ruff-format-not-in-local-verify-pass` — wrapup's local verification command set must include `ruff format --check` alongside `ruff check`.

- **Fresh-install P0 calibration (PLAN-fresh-install-p0-calibration, 3 review rounds — terminal display only, no scoring change)**: bridges the gap left in 0.17.0's `INTENDED_P0_SIGNALS` allowlist. The 0.17.0 frozenset was wired into the integration-test allowlist only ("readiness scoring itself unchanged" per its docstring); the user-facing priority emitter in `improvement._extract_layer1_actions` still mapped weight ≥ 25 → `[P0]` regardless of `INTENDED` membership, so every fresh `/hm:make` flagged `metrics_jsonl_present` + `metrics_has_samples` + `adr_present` + `contributing_present` as urgent. This release routes that allowlist through the emitter with a two-branch policy: telemetry signals (`metrics_jsonl_present`, `metrics_has_samples`) are **suppressed** from the action list while `metrics_has_samples.passed == False` (samples < 5) and **resurface as P0** once samples ≥ 5 so a real steady-state telemetry regression still alerts; user-author signals (`adr_present`, `contributing_present`, `ci_workflow_present`) are **overridden to `[P2]`** regardless of weight, surfacing them as aspirational items rather than urgent alerts. `INTENDED_P0_SIGNALS` is now derived as `TELEMETRY_AUTO_RESOLVE_SIGNALS | USER_AUTHOR_SIGNALS` (backward-compatible union; existing imports unchanged). `ImprovementPlan` gains two `int` counters (`deferred_telemetry`, `demoted_governance`, default 0); when either is > 0, `ai_readiness.render_terminal_summary` appends a single-line footer naming the totals + pointing at `/hm:health` so the user knows the list is *deferred*, not *broken*. Composite ai-readiness score and dimension scores are unchanged — only the user-facing priority labels and the new footer differ. ⚠️ **BREAKING for stdout-parsing scripts**: `[P0]` counts in `/hm:make` output drop on fresh install; the output is informational, not API. Tests: 16 new unit tests in `tests/unit/test_improvement_p0_calibration.py` + `tests/unit/test_ai_readiness_action_list_footer.py` covering suppression / threshold-crossover / override / control / no-action footer / footer ordering; new `INTEGRATION=1`-gated `tests/integration/test_fresh_install_p0_calibration.py` exercises full CLI fresh-make then asserts no `[P0]` for INTENDED signals + footer present + ADR appears as `[P2]` (demoted, not hidden). Diff scope: 3 production files (`readiness.py`, `improvement.py`, `ai_readiness.py`) +66/-12 LOC; 3 new test files +312 LOC.

- **Transparent stash isolation in finalize+wrapup, hardened end-to-end (PLAN-worktree-finalize-stash-isolation + PLAN-worktree-stash-phase4, 5 review rounds)**: ships the full cross-session WIP-survival fix promised by the parent PLAN, plus the Phase 4 schema refactor + multi-round security hardening that closes every reviewer-surfaced vector. One feature, two commits (`ef79688` parent + this PR's Phase 1–4).
  - **What it does (parent PLAN)**: at `/hm:execute` finalize time, `worktree._cli_finalize` stashes the base repo's pre-existing dirty (tracked + staged + untracked) BEFORE squash so session B's commit never absorbs session A's WIP. The stash is identified by ref-file handoff and popped at `/hm:wrapup` time via `_cli_post_commit_pop`, restoring session A's intent untouched. Multi-repo (`sibling_repos`) supported; submodule pointers abort cleanly per ADR-005; per-session liveness gated by the existing `.hm-loop-*` marker.
  - **Phase 4 schema refactor (REVIEW M-P0-1 / M-P1-1/-2/-4/-6)**: stash identity switched from positional `stash@{N}` to **40-char commit SHA** (`git stash push -u` + UUID-suffixed message + SHA capture by exact message match, with `git stash apply <sha>` + manual reflog drop on restore — position drift across the finalize→wrapup handoff is now impossible regardless of concurrent stashers). Ref-file body schema updated to `ref_sha / base / session_marker (absolute path) / sibling_bases / created_at`; new `_validate_stash_ref_fields` regex-validates every field, rejects path-traversal (`..`, double-slash, `.` segments), NUL bytes, reserved delimiters (`|`, `\n`, `\r`), and symlinked markers at the validation boundary. `_stash_base_dirty` uses `_GIT_TIMEOUT_LONG=300` for the stash-push call only (M-P1-3).
  - **Multi-round hardening** (5 review rounds, ~600 LOC delta in `worktree.py`):
    - Round 2: containment check on `target_base` (pops must target a known scan-set repo); atomic-append `_ensure_gitignore_entry` (no SIGINT-leaves-partial-line); `pending` set + `.discard()`; dedupe `bases_to_scan` to prevent primary self-scan.
    - Round 3: `_is_git_repo` via canonical `git rev-parse --git-dir` (closes planted-`.git`-file injection in `_load_sibling_dirs` AND `_detect_existing_worktree`); `_is_safe_absolute_path` predicate consolidating NUL/symlink/normalize/forbidden-char checks; rejection-instead-of-crash semantics across the full validator.
    - Round 4: pipe-character + newline + CR rejection at WRITE time on sibling-base paths (`_write_stash_ref_file` raises before producing an ambiguous body); explicit `.`/`..` segment rejection in safe-path predicate.
    - Round 5: `//`-prefix POSIX-double-slash defense-in-depth rejection.
  - **P2 cleanup pass**: `_POP_UNKNOWN_SIGNAL` constant extracted (no more inline literal divergence with consumers); session-marker `.unlink()` deferred to after the post-commit-pop scan loop (no mid-loop marker delete starving subsequent ref files); `glob` single-snapshot behavior documented; stash-drop best-effort with stderr warning when the reflog entry is missing (visible leak instead of silent).
  - **Test matrix (ADR-003, full 7 cases shipped)**: `tests/unit/test_worktree_stash.py` updated 5 + added 6 new tests covering Class A merge-conflict pop, Class B untracked-collision pop, submodule abort, multi-repo fail-fast ref preservation, stale-ref end-to-end skip, cleanup-failure-after-squash handoff survival. New `tests/integration/test_worktree_stash_isolation.py` (gated by `INTEGRATION=1`) drives the real `_cli_finalize stage-only` → wrapup-template-pinned `git add` → `_cli_post_commit_pop` chain end-to-end against a tmp repo; the wrapup `git add` line is **regex-extracted verbatim from `templates/stages/wrapup.md.j2`** with a sibling guard test catching template drift (validator finding #8 closure). `test_worktree.py` updated to replace the planted `.git` file fixture with a real nested worktree (round 4 hardening tightened `_detect_existing_worktree`'s gate).
  - **Diff scope**: 4 files (~1185 LOC, +1064 / -121). `worktree.py` +600 / -121; unit tests +468; new integration test +213; `test_worktree.py` +25 / -12.
  - **Validation**: full unit + snapshot suite GREEN; `INTEGRATION=1 pytest tests/integration/test_worktree_stash_isolation.py` 2/2 GREEN; `ruff check` + `mypy --strict` clean. `[wiki:pattern] sha-based-stash-identity-survives-concurrent-pushers`.

- **Worktree cleanup prefix safety + second_brain timestamp auto-fill (PLAN-untested-trio-fix-2026-05-19, 4 phases / 10 ADRs)**: post-trio-review fix pair sourced from `REVIEW-untested-trio-summary-2026-05-19` items 2 + 3 (item 1 / P0-1 traversal validator deferred — user explicit per ADR-001, would have broken 4+ existing test fixtures using legitimate `../sibling` patterns).
  - **P0-2 cleanup prefix safety** (`worktree.py`): `_list_worktrees` now filters by `_OWNED_PREFIXES = ("execute-", "plan-", "phase-", "autoloop-")` so `cleanup_all(force=True)` cannot touch cross-tool worktrees (Cursor's `/worktree`, IDE-spawned, manual). Aligns code with the CLAUDE.md §"Worktree 공유" safety claim that previously had no enforcement. 2 unit tests pin the boundary. CLAUDE.md updated at lines 90 + 267 to list all 4 prefixes (line 267 follow-up applied post-/hm:review per M1 finding — exit-criterion grep had checked only line 90).
  - **P1-3 second_brain timestamp auto-fill** (`second_brain.py`): new `_autofill_timestamps(fm) → dict` helper sets `created` if missing (ADR-006) and `updated` always (last-touch semantic), returns a **NEW dict** (ADR-010: caller's input never mutated — slash-command templates reusing a template fm would otherwise lock `created` to first call's timestamp across all subsequent notes). `write_note` additionally reads on-disk `created` when target exists and propagates it (ADR-008 — without this, repeat writes would silently install a new `created` and lose history). `append_note` / `patch_note` now **re-serialize frontmatter via `_format_note(fm, new_body)`** instead of the prior raw concat (ADR-009 resolves validator C-1 — the prior path's fm-dict mutation was DISCARDED on disk, meaning `updated` bumps existed in-memory only). `patch_note` matching narrowed to body-only (corrective per ADR-009; pre-fix `old_text in existing` could accidentally match-and-replace inside the frontmatter block, undefined behavior). 9 unit tests + 1 inline smoke (write → append → patch with monotonic-bump assertions on `updated` + invariance assertion on `created`). Unblocks the wrapup-stage minimal-frontmatter write path that `REVIEW-second-brain-2026-05-19` I1 had flagged as critical (silent drop of intended notes when LLM doesn't supply `created`/`updated`).
  - **plan-validator MAJOR_REVISION resolution** (R3 interview): 2 critical + 6 warnings + 1 info all addressed inline. C-1 (append/patch on-disk no-op) → ADR-009 expansion of Phase 2. C-2 (orphans potentially invisible after filter) → Phase 0 enumeration + assertion (live: only main worktree registered, trivially passed). W-1 sentinel test → dropped as tautological; manual-update risk documented in §Non-Goals item 6. W-3 on-disk `created` preservation → ADR-008. W-2 caller-dict mutation → ADR-010 dict-copy at entry. W-5 smoke theatrical → Phase 3 smoke extended to write→append→patch sequence with 3 invariants.
  - **Diff scope**: 5 files (~331 LOC, +315 / -16); no out-of-scope drift (PLAN success criterion #11). `tests/e2e/sandbox*/` mutations from pytest auto-regeneration reverted before stage-only finalize per scope guard.
  - **/hm:review verdict**: Grade A Round 1 (0 consensus-passed P0/P1). 3 manual-only items surfaced — M1 (CLAUDE.md line 267 stale) applied as 1-line follow-up; M2 (`_ensure_gitignore_entry` non-atomic) + M3 (`_iter_markdown` rglob symlink-follow) flagged as `out_of_diff` for a future hardening PLAN.
  - **Deferred (§Non-Goals)**: P0-1 traversal validator, orphan marker-file sweep, tag/project_id auto-injection, wrapup-template e2e test, sentinel test, refdocs `load_harness_yaml` convergence (Pattern 2 of trio summary), concurrent-writer race fix. `[wiki:convention] plan-exit-grep-must-cover-all-doc-occurrences`.

- **README Domain Packs claims corrected** (PLAN-readme-domain-packs-accuracy, docs-only): two bullets in README.md (lines 143 + 358) overstated `--add-domain` scope. Old wording promised `--add-domain python|node|rust` grafts "standards, agents, and skills"; shipped reality is python-only standards inlining into the 5 reviewer agents (code/security/performance/concurrency/ux) via `templates/agents/_standards/python.md.j2` — `node`/`rust` were never sample-ready and no agents/skills-graft mechanism exists. New wording names the 5 reviewers, references the actual stub path `.claude/agents/_standards/<name>.md`, drops the `node`/`rust` parenthetical, and removes the "agents, and skills" phrase. Source verification: `_SHIPPED_DOMAIN_SAMPLES = frozenset({"python"})` at `cli.py:37`; exactly 5 `*_body.md.j2` templates carry the inline loop. No CLI/code change; `--add-domain` flag behavior unchanged. `[wiki:architecture] domain-packs-are-standards-only-not-agents-skills`.

- **Model-routing review fixes (PLAN-model-routing-code-review-2026-05-19, 6 phases / 5 ADRs)**: post-0.15.0 audit of the per-agent routing surface across schema (`models.py`), resolver (`presets.py`), render boundary (`synthesize.py` + 14 dispatcher templates), and health gate (`readiness.py`). 4 reviewer agents independently surfaced **22 findings** (2 consensus-passed, 20 manual-only); 3 manual-only items were orchestrator-verified as live bugs and promoted to fix-eligible. Phase 5 applied 4 source fixes + 1 defensive guard + 8 new regression tests:
  - **MV-1 / MV-2** (P1, security): Pydantic v2 `model_copy(update=...)` in `interview.answers_from_harness_yaml` was bypassing `_validate_default_model_chars` on the `default_model` and deprecated `recommended_model` load paths — a YAML-injection vector (newline / hash / quote payload could survive into rendered agent frontmatter). Fix: explicit `_MODEL_ID_PATTERN.fullmatch()` pre-check at `interview.py:769/772` with WARNING-log fallback to the canonical default. This **retracts Phase 2 Finding R-6** — plan-author had verified the validator "safe" because the regex was correctly anchored, but the regex never ran on the load path. Strongest evidence for ADR-005 multi-agent payoff in the session.
  - **MV-3** (P1, render): Jinja2 `{% if x is defined %}` returns True for `None` values; all 14 dispatcher templates emitted literal `model: None` when users overrode only `cursor:` / `codex:` fields. Fix: `{% if X is defined and X is not none %}` guard.
  - **C-1 / R-7** (P1, render): `cursor_model` Jinja context key was built by `_agent_files` (via `_normalize_cursor_alias`) but consumed by zero templates — `CURSOR_MODEL_IDS` normalization machinery was performing work whose result was discarded. ADR-003 R5 intent ("render concrete IDs for Cursor consumption") was unrealized. Fix: 14 dispatcher templates now prefer `cursor_model` (concrete ID) over `claude_model` (alias) with appropriate fallback chain. Cursor 2.4 floor consumers now read `model: claude-4-7-opus` rather than `model: opus`.
  - **CP-1 / R-1** (P2): `trajectory-monitor` was in both PRESET maps but absent from `_ALL_AGENTS` / `_ALL_SKILLS` / `_COMMUNICATION_VARIANT` — unreachable dead data. Fix: removed preset entries (templates left in place for future reactivation; reactivation requires adding to all three iteration lists together, documented in code comment).
  - **CP-2 / CG-3** (P2): `_COMMUNICATION_VARIANT[n]` bare dict access at `synthesize.py:325` would KeyError at render time if a future agent were added to `_ALL_AGENTS` without a matching variant entry. Fix: `.get(n, "full")` defensive fallback + structural test asserting `set(_ALL_AGENTS) ⊆ set(_COMMUNICATION_VARIANT)` catches the omission at test time.
  - Collateral test updates: `test_full_agent_md_sha256_unchanged` (12 hashes regenerated for the template change), `test_preset_agent_models_completeness_vs_shipped_templates` (symmetry contract tightened to use `_ALL_AGENTS` as the source of truth — resolves the asymmetric-test gap Phase 2 R-2 had flagged).
  - **Deferred to follow-up** (NICE-priority per user-scoped Phase 5 invocation): test-reviewer T-2 (no `_codex_agent_files` test coverage), T-4 through T-10 (8 coverage gaps), performance-reviewer P-1/P-2/P-3 (Pydantic re-construction overhead, import-time module evaluation, `model_copy` hot-path allocations), P-4 (executor cost-model recalibration), P-5 (no `medium` profile in `.codex/config.toml`), security-reviewer S-3 (TOML description field unescaped — latent, hardcoded `_CODEX_AGENT_META` makes it safe today).
  - Verify gate (Phase 6): `INTEGRATION=1 pytest tests/integration/test_fresh_install_readiness.py` = 5 passed in 5.04s; programmatic `_dim_model_routing` against 4 fixtures (baseline + 3 advisory FAIL paths) all behave as expected; full unit suite exit 0.

- **Stage memory loader: hybrid lexical + Claude rerank (PLAN-memory-md-operations)**: `harness_maker.memory_retrieve` replaces the "first 60 lines + grep" skim pattern in `/hm:research`, `/hm:plan`, `/hm:spec`. Python module does deterministic lexical pre-filter (top-30 by token overlap, reusing `relevance.WORD_RE`, stopwords applied to topic only, tie-break = score desc → date desc → slug asc); running Claude turn does semantic rerank to top-6 inline via `<memory_candidates>` fence + directive line. No separate Anthropic API call (target env lacks `ANTHROPIC_API_KEY`; ADR-002). Closes the loading-window inversion where recent entries (line 60+ of wiki.md / failures.md) silently failed to load — `[wiki:pattern] boundary-parse-test-layer | 2026-05-19` and 200+ other recent entries are now retrievable. Byte cap default 10240 with real-overhead accounting + defensive re-shrink loop. Security guards in the fence renderer: `html.escape` on the topic attribute (prevents fence-attribute breakout) and `</memory_candidates>` literal neutralization in entry bodies (prevents stored prompt-injection via committed wiki.md). Parser is permissive on duplicate slugs — surfaces both with `(duplicate of [<tier>:<slug>])` annotation so the wrapup duplicate-section bug stays visible for Approach A follow-up. `relevance._WORD_RE` promoted to public `WORD_RE` (backward-compat alias retained). Three stage templates updated: `research.md.j2` (warm-tier replacement), `plan.md.j2` (new Session Context Loading block inserted — template had no memory loader previously, PLAN-vs-reality drift documented), `spec.md.j2` (memory `rg "<key terms>"` lines replaced; SPEC/PLAN/RESEARCH greps preserved). 46 new tests (33 unit + 5 CLI integration + 8 template integration), including regression guards for `test_no_anthropic_import`, fence-injection neutralization, and topic attribute escape. Format gate (Approach A) and lifecycle pass (Approach B) explicitly deferred as follow-up PLANs per ADR-001.

## 0.17.1 — Launch-readiness floor + Layer 1 boundary tests (2026-05-19)

- **Pre-launch validation strategy** (PLAN-pre-launch-validation-strategy, 12 ADRs / 10 phases): RESEARCH surfaced that 144 tests but only 1 invokes real `claude` (and that one bypasses interactive flow via `--ci`); combined with LLM-code-review BugMatch ~60% (arxiv 2603.00539), Show HN-grade functional coverage was insufficient. Strategy ships a 5-layer multi-modal validation plan (L1 LLM review + L2 unit/integration + L3a Python self-dogfood + L3b Next.js fresh-fixture + L4 Cursor manual checklist + L5 Codex smoke + L6 external beta), gates announcements behind composite ≥ 66 / 72 (Side floor, ADR-010) + Zero P0 (P0/P2 binary triage, ADR-011 supersedes P1 layer), and pre-cuts PyPI 0.17.1 to eliminate two-version PyPI ↔ main drift before validation begins (ADR-004 + ADR-009). PLAN phases 0/0.5/3/4/5/6/7/8 are user-action deferred from this commit.
- **Codex smoke 5-step manual checklist scaffolded** at `tests/codex-compat/MANUAL_CHECKLIST.md` per PLAN Phase 6 (ADR-003). Pre-commits BLOCK/DEFER threshold so triage is deterministic when the run happens: Steps 1 (install) / 4 (AGENTS.md absorption) / 5 (`.codex/*` render + PascalCase hooks schema) BLOCK launch on failure; Steps 2 (discovery) / 3 (interactive interview surface) DEFER acceptable. Run itself remains user-deferred.
- **README hero leads with per-project personalization** — the single differentiator vs. other harnesses (BMAD / SuperClaude / agent-os / claude-flow ship a fixed bundle; harness-maker synthesizes a different harness per project). EN tagline: "A different harness for every project — built from yours, never generic." KO mirror: "프로젝트마다 다른 하네스 — 당신 프로젝트로부터 빚어지고, 절대 generic 하지 않습니다." 4-pill descriptor leads with **Per-project personalization** (was "Interview-shaped"). "Try in 30 seconds" intro now explicitly states the profiler + 10-dim interview synthesize a harness specific to YOUR project, not a generic template. GitHub repo description (About sidebar) also reworked to "Per-project AI coding harness for Claude Code · Cursor · Codex. Profiler + 10-dim interview build a different harness for every project." (136 chars). Manifests + pyproject.toml already led with "Project-tailored" — this aligns the README + About surface with that positioning.
- **Layer 1 boundary-parse test suite (PLAN-test-fidelity-gap)**: new `tests/integration/test_boundary_*.py` suite covering 5 file types (`hooks.json` Claude+Cursor dual-schema, Codex TOML, `.claude/harness.yaml` multi-doc, `.cursor/rules/*.mdc`, `.claude/settings.json`). Each module ships positive tests via LIVE `cli.make` render (INTEGRATION=1) + `@pytest.mark.boundary_negative` negatives with synthetic bad bytes (template-state-independent). Production code `src/harness_maker/` 0 changes. `release.yml` gains a non-blocking `boundary-advisory` job (no secret needed — pure parser tests; appends result to GitHub Release body via `gh release edit`). CLAUDE.md §릴리스 절차 references the pre-tag command. `tests/integration/test_boundary_meta.py` pins 5-module presence + marker collection + runbook substring. Closes the "Python view ≠ consumer view" failure class behind 30+ recent `fix(...)` commits.
- **OSS launch-readiness floor (PLAN-oss-readiness-audit)**: restored PR CI (`ci.yml` + `nightly.yml`) byte-matching `release.yml` quality-gate after commit 565d7ce had removed it the day after the repo went public. Added community-files floor — root `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 with custom solo-maintainer Section 4 per ADR-009), `SECURITY.md` (GitHub PVR primary + Gmail backup per ADR-010), `.github/ISSUE_TEMPLATE/{bug,feature,config}.yml`, two-tier `.github/PULL_REQUEST_TEMPLATE.md` per ADR-011, `.github/dependabot.yml` (weekly pip + github-actions). Added `PRIVACY.md` documenting 4 telemetry JSONL schemas + `tests/unit/test_privacy_doc_schema.py` AST-walk drift defense (5/5 tests, no opt-out env var per ADR-004). README rewrites — "Try in 30 seconds" code-block hero, new "Stability" section listing frozen surfaces (slash command names + harness.yaml top-level keys + plugin manifest schemas) per ADR-001, comparison rewrite to category-axis (zero named competitors per ADR-007/012). KO mirror updated. Repo stays 0.x per ADR-001, solo-maintained per ADR-002. **Outstanding before first external PR**: SHA-pin `actions/dependency-review-action@v4` at `.github/workflows/ci.yml:59` — LLM left `TODO(maintainer)` because no network at write time. Phases 8–11 (PVR toggle + Discussions ON + marketplace submissions + Show HN) are user-action; see `work-docs/PLAN-oss-readiness-audit.md` § Implementation Plan.
- **README one-prompt rewrites slash-command typing to Bash auto-install** for all three IDEs. The AI now runs `claude plugin marketplace add` + `claude plugin install` (and `git clone` for Cursor, `codex plugin marketplace add` for Codex) via the Bash tool instead of telling the user to type `/plugin install ...` themselves. User-typed slash commands on Claude Code drop from 3 to 1 (`/reload-plugins`). Per-IDE step budget table now shipped at the top of the Quickstart. PLAN-readme-one-prompt-autoinstall; Phase 0 empirical verification deferred — README uses the conservative `manual-enter-required` wording (harmless when reload auto-triggers).

## 0.17.0 — Fresh-install /hm:health zero false-positive P0 (2026-05-19)

PLAN-fresh-install-health-baseline. A freshly-rendered `/hm:make` harness
now passes its own `/hm:health` with zero P0 outside a small, named
allowlist of "intended fresh-install noise" (telemetry × 2, CI workflow,
governance docs requiring user authoring). Bundles 4 fix categories:
template gaps, Side context-lint threshold raise, unknown-stack
auto-degrade, telemetry intended-noise allowlist.

### Highlights

- **Templates ship security + memory baselines**:
  - `harness.yaml` now renders a `memory:` block by default
    (`{enabled: true, dir: .claude/memory, files: [failures.md, wiki.md]}`).
  - `settings.json` `permissions.deny` ships 4 baseline patterns on
    both Side and Production: `["Bash(rm:*)", "Bash(curl * | sh)",
    "Write(/etc/**)", "Write(~/.ssh/**)"]`.
- **Side context-lint thresholds raised** to match shipped content:
  agent ≤ 150 (was 100), skill ≤ 100 (was 50). Production unchanged
  at 200/150. Side identity now differentiates on reviewer count +
  grade threshold + spec_gate, not on prompt size (ADR-001).
- **Unknown-stack auto-degrade**: projects without recognized manifest
  (board YAML, shell-only, etc.) no longer cascade into two P0 signals
  from `_detect_stacks() == set()`. Both `stack_detected` and
  `tests_present` weights drop to 5/10 advisory on unknown stack
  (ADR-004).
- **Telemetry intended-noise allowlist**: `metrics_jsonl_present` hint
  copy clarified ("First Claude Code tool use will create this file
  (PostToolUse hook is installed).") + `INTENDED_P0_SIGNALS` constant
  exposed for the new fresh-install integration test gate (ADR-006).
- **`_merge_permissions` idempotency fix** (`render.py`) — no phantom
  `ask: []` key emitted when neither input had it. Repeated `/hm:make`
  now produces byte-identical output.

### BREAKING — Production `permissions.deny` scope narrowed

Production previously shipped `["Bash(rm:*)", "Bash(curl:*)"]` (broader
`curl:*` blocks ALL curl). New baseline collapses to the 4-pattern
canonical (`Bash(curl * | sh)` only), aligning Side·Production identical
per ADR-003 option A. **Production users relying on blanket curl block
silently lose that protection on re-render**. If your project needs
all-curl blocked, append `Bash(curl:*)` to `permissions.deny` after the
next `/hm:make`; the user addition is preserved via `_merge_permissions`
list-union semantics.

### Migration

No flag. Existing 0.16.x users running `/hm:make` once pick up the
additive baselines automatically via the existing render path
(`_merge_permissions` list-union for `settings.json`,
`_preserve_yaml_user_keys` + template-emit for `harness.yaml.memory:`).

### Quality gate

New integration test `tests/integration/test_fresh_install_readiness.py`
runs in `release.yml` quality-gate with `INTEGRATION=1`. 5 cases: fresh
Side + Production within composite-score floors (66 / 72 measured);
existing-install harness.yaml + settings.json migration via existing
render semantics; byte-identical idempotency on re-render.

### Loop UX

`commands/hm/loop.md.j2` gains a "Non-stopping discipline" section —
codifies that `/hm:loop` iters never halt for verification or status
confirmation. Background-task notifications trigger automatic next-step
transitions, not user reports.

## 0.16.0 — BREAKING: 5-term inequality deep-interview gate replaces 3-layer (2026-05-18)

PLAN-deep-interview-question-criteria. Replaces the 3-layer interview gate
(5-rubric + GCIC + CLARITI + 5 implicit probes + weighted Ambiguity Score
+ 2-round streak) with a single 5-term inequality applied uniformly across
`/hm:research`, `/hm:spec`, `/hm:plan`, and `/hm:loop`:

```
ask(Q) iff EIG(Q) >= ε  ∧  TaskRel·UserAns >= 0.7
        ∧ slot ∉ common_ground  ∧  confidence < τ
        ∧ open_ended_count < cap_locale
```

### BREAKING

- **harness.yaml schema (deep_gate)** — `interview.deep_gate.max_rounds` and
  `interview.deep_gate.streak_target` are deprecated. On read they emit a
  warning and are ignored. Existing 0.15.x users upgrade without manual
  intervention; new defaults ship via `interview_deep_gate_defaults()`.
  New keys (ADR-007 uniform across Side/Production):
  - `eig_epsilon: 0.5`
  - `confidence_tau: 0.7`
  - `open_ended_cap_by_locale: {en: 2, ko: 1, ja: 1, default: 1}`
  - `common_ground.llm_inference_threshold: 0.95`
  - `common_ground.llm_inference_enabled: true` (ADR-012 kill-switch — only
    user-tunable key)
- **work-docs/loop-context/*.yaml** — old `ambiguity_score` weighted-sum
  format is no longer read. Active loops on upgrade abort with a schema
  error; restart via `/hm:loop --spec <slug>` to rebuild context.
- **Stage templates** (`templates/stages/{research,spec,plan}.md.j2` and
  `templates/commands/hm/loop.md.j2`) — Layer 1-3 GCIC/probing/score blocks
  replaced with 5-term checklist rendering (ADR-005).

### Added

- `harness_maker.common_ground` — explicit-evidence + LLM-inference (ADR-003)
  common-ground detector. Atomic JSONL audit at
  `.claude/observability/cg-marks-{slug}.jsonl`. 10-slot false-positive guard.
- `harness_maker.eig` — `score_eig(q, ctx) -> float` mechanism-agnostic
  public interface (ADR-002 rollback path enforced).
- `harness_maker.inequality_gate` — composes the 5-term inequality + ranks
  + enforces locale open-ended cap.
- `harness_maker.observability.intent_miss` — ADR-008 silent-intent-miss
  telemetry. `/hm:health` Layer 1 surfaces the rate.
- `harness_maker.observability.coverage_classifier` — ADR-010 post-hoc
  coverage-kind classifier (telemetry-only labels; ADR-004 deletes gating).

### Changed

- `templates/harness-yaml/{Production,Side}.yaml.j2` render new 5-term schema.
- `templates/stages/review.md.j2` — new Step 2.5 silent-intent-miss hook.
- `templates/commands/hm/health.md.j2` — new Layer 1 sub-check
  `silent_intent_miss_rate` (initial threshold 0.10, narrative-only pending
  telemetry calibration).

### Migration

For users on 0.15.x:
1. `/plugin update` then re-render via `/harness-maker:make`.
2. Old `deep_gate.max_rounds`/`streak_target` in user-edited harness.yaml
   are warn-and-ignored — no manual cleanup required (removing them silences
   the warning).
3. Active loops (`.claude/.hm-loop-active` present + a
   `work-docs/loop-context/<slug>.yaml` exists) must restart — run
   `/hm:loop --spec <slug>` to rebuild loop context. There is no automatic
   migration of the old `ambiguity_score` weighted-sum format.
4. Optional kill-switch: set
   `interview.deep_gate.common_ground.llm_inference_enabled: false` in
   `.claude/harness.yaml` to disable the aggressive LLM-inferred
   common-ground path (ADR-012). Default is `true`; flipping to `false`
   reverts the gate to explicit-evidence-only matching.

## 0.15.3 — fix ruff quality-gate regressions from 0.15.1 + 0.15.2 (2026-05-18)

CI-only patch. No runtime change.

### Fixed

- Removed two unused `import yaml` lines added to `tests/unit/test_render.py`
  in 0.15.2 (`F401`).
- Re-formatted a long-assertion message in `tests/unit/test_install_ref.py`
  added in 0.15.1 to match ruff format's preferred line break.

The release.yml `quality-gate` job now passes (was failing on both
v0.15.1 and v0.15.2 tag pushes at `ruff check .` / `ruff format --check .`).
End users were unaffected (harness-maker isn't on PyPI; distribution goes
through the Claude Code plugin marketplace, which reads the GitHub
release artifact directly).

## 0.15.2 — preserve user edits to settings.json + harness.yaml across re-render (2026-05-18)

Two patches to the renderer's reconcile path. Both address user-edit
durability across `/hm:make` invocations.

### Fixed

- **`settings.json` `permissions.{allow,deny,ask}` now deep-merge as a
  union** (template entries first, then user-added entries appended,
  dedup). Previously the template's `permissions` value won wholesale,
  silently wiping user-added denies (e.g. `Write(/etc/**)`,
  `Write(~/.ssh/**)` added via `/hm:health` Layer 1 acceptance) on every
  re-render. Documented as a "v1 limitation" in 0.3.1; promoted to a
  proper fix in 0.15.2. Other `permissions.*` keys (scalars, unknown
  sub-keys) still follow template-wins.

- **`harness.yaml` preserves user-added top-level keys** that the
  template doesn't emit (e.g. `memory:`, `custom:`, project-specific
  blocks). New keys are appended after a `@hm:user:extensions` marker
  comment. Template-emitted keys still win on overlap — if a future
  template natively adds a key the user previously added, the template's
  value replaces the user's on the next render (consistent with the
  block-merge model elsewhere in the codebase).

### Tests

- `tests/unit/test_render.py`:
  - Updated `test_render_settings_json_shallow_merges_existing` to
    reflect the new union contract.
  - Added `test_render_settings_json_unions_permissions_deny` (regression
    guard for the `/hm:health` audit finding).
  - Added `test_render_settings_json_unions_dedup_no_duplicates`.
  - Added `test_render_harness_yaml_preserves_user_added_top_level_key`,
    `test_render_harness_yaml_user_key_marker_present`, and
    `test_render_harness_yaml_template_key_wins_over_user`.

## 0.15.1 — fix uv archive cache path bug in renderer (2026-05-18)

### Fixed

- **`_compute_install_ref` returned a broken path when invoked from a uv
  archive cache** — when `uv run --with /plugin/cache/<version>` archived
  the package into `~/.cache/uv/archive-v0/<hash>/lib/python3.12/
  site-packages/harness_maker/`, the renderer's
  `Path(__file__).parent.parent.parent` math resolved to
  `<archive>/lib/python3.12` — not a Python project. That value got baked
  into every rendered hook, skill, and slash command as
  `uv run --with <archive>/lib/python3.12 python -m harness_maker.<module>`,
  and every invocation failed with `does not appear to be a Python project`.
  Fixed by reading the `file://` URL path from `direct_url.json` directly
  (the original source path uv was given), bypassing the `__file__`-derived
  guess. Surfaced by `/hm:health` audit 2026-05-18. Regression test:
  `tests/unit/test_install_ref.py::test_url_path_wins_over_uv_archive_pkg_root`.

## 0.15.0 — per-agent model routing + preset-aware defaults (2026-05-18)

Token-cost optimization across Claude Code / Cursor / Codex via declarative
per-agent model pinning. 13 ADRs locked in PLAN-model-routing-multi-ide.md.
8 implementation phases shipped via /hm:loop with per-phase /hm:review.

### Added

- **Per-agent model schema** (ADR-001/002) — new `HarnessConfig.agent_models:
  dict[str, AgentModelSpec]` with nested `{claude, cursor, codex: {model,
  reasoning_effort}}`. `recommended_model: str` renamed to `default_model: str`
  (deprecated read-side property kept for 0.15.x / 0.16.x; removed no earlier
  than 0.17.0 per ADR-012).
- **Preset-aware defaults** (ADR-005) — new `src/harness_maker/presets.py`
  ships `PRESET_AGENT_MODELS` for Production (opus on 3 reasoning agents,
  sonnet on 11 reviewers) and Side (sonnet everywhere with downshifted
  reasoning_effort). 3-tier `resolve_agent_spec()`: explicit override →
  preset map → `_spec_from_default_model` fallback (never KeyErrors on
  user-authored agents).
- **Canonical Cursor ID table** (ADR-003) — `CURSOR_MODEL_IDS` maps aliases
  (`opus`/`sonnet`/`haiku`) to concrete IDs. Users write aliases in
  `agent_models`; renderer normalizes via this table at render boundary
  (single-point upgrade across Claude releases). Templates lint-enforced
  against raw concrete IDs.
- **Codex profiles** (ADR-008) — `.codex/config.toml` now renders
  `[profiles.cheap]` (`reasoning_effort=minimal`) + `[profiles.deep]`
  (`reasoning_effort=high`). Codex agent TOMLs render
  `model_reasoning_effort` per-agent (the dominant cost lever; keep `model =`
  omission per RESEARCH-codex-plan-validator-model-unavailable).
- **/hm:health Layer-1 sub-check** (ADR-010) — new `model_routing` dimension
  with 3 advisory signals: Claude #43869 reliance, Cursor alias-form
  warnings, Codex reasoning_effort coverage. Weight 0 (advisory only;
  doesn't change composite).
- **CLI `--default-model` flag** + back-compat alias `--recommended-model`
  (ADR-012) with DeprecationWarning.
- **`--update` cwd guard** (ADR-013) — rejects snapshot regen invoked from
  inside `.worktrees/<branch>/`, turning the documented footgun
  (`[fail:snapshot-regen-inside-worktree]` count:4) into enforced
  prevention with actionable error message.
- **Silent schema migration** (ADR-004 + ADR-011) — `recommended_model:` in
  v1 harness.yaml migrates silently to `default_model`; INFO log gated on
  `schema_version<2` to avoid noise on fresh v2 renders. Multi-doc YAML
  provenance frontmatter handled via `io_utils.load_harness_yaml()`.
- **HOW-IT-WORKS docs** — new "Agent Models" section with worked example
  covering preset defaults, per-agent override, and the 3-tier resolution chain.

### Changed

- `HarnessConfig.schema_version`: 1 → 2.
- 14 agent `.md.j2` templates: hardcoded `model: opus|sonnet` → `model:
  {{ claude_model }}` (context driven by `resolve_agent_spec`).
- 2 preset YAML templates + 5 foreign-config templates: `recommended_model:`
  → `default_model:` rename.

### Fixed

- Pydantic dual-key handling for AliasChoices + `extra="forbid"` —
  `model_validator(mode="before")` silently drops `recommended_model` when
  `default_model` is also present (avoids `extra_forbidden` on rendered
  output round-trip).
- `agent_models` parse path catches `pydantic.ValidationError` in addition
  to `TypeError`/`ValueError` so a malformed override drops with a WARNING
  log instead of silently nuking the whole `answers_from_harness_yaml`
  return (Phase 2 /hm:review consensus-passed P1 fix).
- Migration log message sanitizes newline + ANSI escape sequences in
  user-provided values (security-reviewer P1 fix).
- Migration log includes the harness.yaml path so multi-repo runs can
  identify which file triggered the advisory (code-reviewer P1 fix).

## 0.14.3 — universal bootstrap prompt restored over the plugin-install paths (2026-05-17)

0.14.2 replaced the universal LLM bootstrap prompt with three per-IDE install
sections. User feedback: the universal prompt has its own value — a single
copy that any AI agent can run regardless of IDE — and should coexist with
the per-IDE manual instructions, not be replaced by them. This patch
restores the universal prompt on top of the manual section, but with the
install commands rewritten around plugin marketplaces (Claude Code,
Codex CLI) and a Cursor local-symlink fallback. The PyPI / `uv tool install`
path is preserved as a separate manual entry inside the same `<details>`
block for CI / headless / no-IDE-plugin contexts.

### Changed

- README Quickstart structure:
  - **Universal Bootstrap Prompt** at the top — IDE-autodetecting, runs
    the right `/plugin marketplace add` (Claude Code) /
    `codex plugin marketplace add` (Codex) / `git clone ~/.cursor/plugins/local/`
    (Cursor) command for the detected IDE, then drives
    `/harness-maker:make` + `/hm:health`.
  - **Manual install** in `<details>` covers four numbered paths:
    Claude Code marketplace · Codex CLI marketplace · Cursor (Team
    marketplace OR local symlink) · PyPI fallback.
- `.claude-plugin/marketplace.json` — removed `plugins[0].version`
  field. Auto-versioning by git commit SHA means future plugin patches
  don't require touching marketplace.json. Reduces the 5-file version
  sync footgun surface.
- Codex `--ref` example bumped to `v0.14.3` (current release pin).
- README.ko.md mirrored.

5-file version sync: 0.14.2 → 0.14.3.

## 0.14.2 — IDE plugin marketplace as primary install path (2026-05-17)

Reframes the install story around **plugin marketplace install**, the dominant
pattern across Claude Code / Codex / Cursor ecosystem peers (superpowers,
ruflo, spec-kit, anthropics/skills, everything-claude-code). PyPI install is
preserved as a CLI-only fallback inside a collapsed `<details>` block.

### Changed

- `.claude-plugin/marketplace.json` — renamed `name` from `harness-maker-local`
  (private-dev leftover) to `harness-maker`, owner from `noel` to `Ecro`,
  added `description` + per-plugin metadata (version, author, homepage,
  repository, license, keywords). Install command is now
  `/plugin install harness-maker@harness-maker`.
- README Quickstart — replaced the single Universal Bootstrap Prompt with
  three explicit per-IDE install sections:
  - **Claude Code**: `/plugin marketplace add Ecro/harness-maker` +
    `/plugin install harness-maker@harness-maker`.
  - **Codex CLI**: `codex plugin marketplace add Ecro/harness-maker`
    (`--ref v0.14.2` for pinned releases). marketplace add IS install for
    Codex; no separate install step.
  - **Cursor**: documents the curated-marketplace gap honestly — Team
    marketplace import path + community `~/.cursor/plugins/local/` symlink
    path.
- "First-time setup" prompt now assumes the plugin is already installed and
  only orchestrates `/harness-maker:make` + `/hm:health`. No more
  PyPI-install / uv-bootstrap steps in the LLM-facing prompt.
- README.ko.md mirrored.

### Preserved

- PyPI install (`uv tool install harness-maker`) survives inside a
  `<details>` fallback block for CI / headless / no-IDE-plugin use cases.

5-file version sync: 0.14.1 → 0.14.2.

## 0.14.1 — PyPI page Korean README link fix (2026-05-17)

Patch release. README marketing rewrite landed in commit `8e894e0` between
0.14.0 tag and now — the new English README ships an `**English** · [한국어](...)`
language switcher at the top. The relative link target was `README.ko.md`,
which resolves on GitHub but **breaks on PyPI** because PyPI's markdown
renderer does not rewrite relative paths to other files in the repository.

Fixes:
- README.md / README.ko.md language switchers now use absolute GitHub URLs
  (`https://github.com/Ecro/harness-maker/blob/main/...`).
- `pyproject.toml [project.urls]` gains a `한국어 README` entry so the
  PyPI Project Links sidebar links directly to the Korean version.

5-file version sync: 0.14.0 → 0.14.1.

## 0.14.0 — first PyPI release + communication-protocol variant family (2026-05-17)

### PyPI publication infrastructure (PLAN-pypi-publish-llm-prompts)

First public PyPI release of `harness-maker`. Install with `uv tool install harness-maker`.

**Added:**
- `.github/workflows/release.yml` — `uv publish --trusted-publishing always` to TestPyPI then PyPI on `v*` tag push. OIDC-based, no long-lived tokens. Third-party actions pinned to commit SHAs (`actions/checkout`, `actions/upload-artifact`, `actions/download-artifact`, `astral-sh/setup-uv`).
- `tests/integration/test_package_artifacts.py` — INTEGRATION=1-gated wheel/sdist regression tests (zipfile/tarfile membership of representative templates; no `__pycache__` leak).
- `scripts/release_smoke.py` — local end-to-end rehearsal (build → venv → install → CLI smoke).
- `docs/release-checklist.md` — maintainer runbook covering Phase 0 prerequisites, exact Trusted Publisher subject strings, tag command, yank procedure.
- Universal cross-platform LLM bootstrap prompt in README — single block, LLM-autonomous OS detection (Linux/macOS/Windows/WSL), works in Claude Code / Cursor / Codex / generic chat.

**Changed:**
- `pyproject.toml` — added PyPI classifiers, keywords, license-files (PEP 639), project.urls (Homepage/Repository/Issues), authors with email.
- `.claude-plugin/`, `.cursor-plugin/`, `.codex-plugin/plugin.json` — homepage/repository URLs corrected to `https://github.com/Ecro/harness-maker`.
- README install section — bootstrap prompt promoted from `<details>` to visible primary path; manual install moved into `<details>`.

**Maintenance:**
- Repo-wide ruff/mypy hygiene pass — 7 mypy --strict errors fixed (cache.py cast, interview.py dict annotation, render.py BaseLoader None guard, agent_quality.py variable shadowing), `ruff format` applied to 35 files. CI lint/type now clean.
- `tests/e2e/sandbox` regenerated to absorb post-0.13.0 schema additions and unblock 23 dogfood e2e tests that depended on `commands/hm/health.md`.

### Communication-protocol variant family (PLAN-antisycophancy-2026-05)

PLAN-antisycophancy-2026-05. Promotes the single `_partials/communication.md.j2`
into a 3-variant family (`_full`, `_reframe`, `_soft`) driven by explicit
`communication_variant` frontmatter on each dispatcher template. Variant
identity rides as an HTML comment marker in the rendered body — output
frontmatter / TOML stays clean so Cursor `.mdc` and Codex TOML strict parsers
are unaffected (ADR-004). `/hm:health` Layer 1 (structural) gains a
`communication_protocol` sub-check that surfaces silent-miss (a new agent
template added without declaring a variant) as a structured
accept/reject/defer item (ADR-006).

### Added
- `_partials/communication_full.md.j2`, `_partials/communication_reframe.md.j2`,
  `_partials/communication_soft.md.j2` — paraphrased from user SYCOPHANCY.md
  ANTISYC-FULL-v1 / REFRAME-v1 / SOFT-v1 (ADR-007). SOFT ships dormant: no
  consumer in current 14 agents.
- `harness_maker.communication_audit` — discovery + frontmatter requirement +
  marker scan + source ↔ output drift detection. Returns `ActionItem` records
  compatible with `/hm:health` Step "Per-item structured question" loop
  (0.13.0 ADR-001 "no auto-apply").
- `harness_maker.render._extract_source_communication_variant` — NEW
  pre-render extractor. Regex-based (survives Jinja expressions like
  `name: {{ name }}` in source frontmatter that break `yaml.safe_load`).
  Injects variant as Jinja context before `template.render()`.
- `_COMMUNICATION_VARIANT` table in `synthesize.py` — Codex render path
  (which bypasses dispatcher source frontmatter and includes `_body.md.j2`
  directly into TOML) gets the variant from this explicit map.
- 5 named unit tests for the variant resolver
  (`test_variant_full/reframe/soft_renders_*`,
  `test_variant_missing_raises_explicit_error` — ADR-002 forbids
  default-to-FULL, `test_variant_invalid_value_raises`).
- `tests/unit/test_communication_audit.py` with 2 acceptance fixtures
  (Fixture A: block removed from output; Fixture B: synthetic dispatcher
  missing frontmatter — silent-miss proof).

### Changed
- 14 dispatcher templates carry `communication_variant: full|reframe|soft`
  source-side frontmatter. FULL=4 (autoloop-coder, executor, stuck,
  trajectory-monitor — JSON-output, REFRAME inapplicable). REFRAME=10 (10
  reviewer-shaped agents). SOFT=0 (no idea-shaped agents).
- 14 body include sites use the variant-aware
  `{% include "agents/_partials/communication_" ~ communication_variant ~ ".md.j2" %}`
  pattern. plan-validator_body and test-reviewer_body newly receive REFRAME
  (behavior change explicitly accepted in PLAN R5).
- 5 LLM-judgment skills (agent-quality-rubric, ai-readiness-rubric,
  relevance-filter, security-scanner, refdocs-search) gain
  `communication_variant: full` frontmatter + body include (ADR-005).
  Other 7 procedural skills unchanged.
- `ai_readiness.run_structural()` invokes `audit_communication`; emits
  per-item entries via `signals_failed` and a new `communication_items`
  field on the returned dict.

### Removed
- `_partials/communication.md.j2` (single-variant partial; replaced by the
  3-variant family).

### Notes
- Stage templates retain their inline communication blocks (ADR-003
  RETRACTED in PLAN R5 after stage-specific protocol lines were surfaced as
  load-bearing — e.g. verify.md.j2's "PASS / FAIL — no soft language").
- Cursor `.mdc` render path unaffected (does not include agent bodies).
- New agent template checklist: declare `communication_variant` in source
  frontmatter; `/hm:health` Layer 1 catches the omission.

## 0.13.1 — health bug fixes + Second Brain write fix (2026-05-17)

This patch bundles two unrelated bug fix PLANs that landed on the same day:
the `/hm:health` plugin bugs (PLAN-health-plugin-bugs-2026-05) and the
Second Brain write failure (PLAN-second-brain-write-failure).

### Fixed — /hm:health plugin bugs (PLAN-health-plugin-bugs-2026-05)
- `readiness._dim_observability_setup` now reads date-sharded telemetry
  (`metrics-YYYY-MM-DD.jsonl`) via `_metrics_io._candidate_files`, not only
  the legacy `metrics.jsonl`. Both `metrics_jsonl_present` and
  `metrics_has_samples` signals now PASS on projects with rotated telemetry
  — pre-fix they failed with the misleading "Install the PostToolUse
  telemetry hook (run /hm:make)" recommendation on already-instrumented
  projects. (PLAN ADR-103 reuse.)
- `ai_readiness.run_structural()` return key renamed `"structural"` →
  `"score"`. Pre-fix the producer drifted to use the same name as the outer
  layer namespace (`{"structural": {"structural": <int>}}`), and the
  dashboard renderer + its unit tests always read `.get("score")` → every
  rendered dashboard showed `Structural score: 0 / 100` regardless of the
  real score. The `.health.tmp.json` schema between `health` and
  `health-finalize` changes by this one key rename — internal to the
  pipeline, no documented external consumers. (PLAN ADR-001.)

### Added — /hm:health regression nets
- `tests/integration/test_health_dashboard_roundtrip.py` — round-trip
  contract test that calls real `run_structural()` → real `write_dashboard()`
  → `parse_dashboard()`. Asserts `producer_score >= MIN_FIXTURE_SCORE (30)`
  AND `parsed_score == producer_score`. Plus a meta-test that fakes the OLD
  shape and proves the equality assertion fires on drift — closing the
  exact test-suite gap that let Bug 2 ship green. (PLAN ADR-002.)
- `tests/integration/conftest.py:build_min_fixture` — reusable minimal
  fixture (`.claude/`, `CLAUDE.md`, rotated telemetry, settings.json deny,
  `.github/workflows/ci.yml`, etc.) that deterministically clears the
  30-point floor on Side preset.
- Two paired regression tests in `tests/unit/test_readiness.py` covering
  the rotation-aware metrics signals (rotated-only project, rotated +
  legacy summation).

### Fixed — Second Brain (PLAN-second-brain-write-failure)
- `second_brain._load_config` no longer crashes with
  `yaml.composer.ComposerError: expected a single document in the stream` on
  rendered `harness.yaml` files. Root cause: the renderer prepends a
  provenance YAML frontmatter block, making `harness.yaml` a multi-document
  stream that single-document `yaml.safe_load` rejects. Every `/hm:research`,
  `/hm:wrapup`, and `/hm:plan` Second Brain invocation previously failed
  immediately. (ADR-001)

### Added
- `harness_maker.io_utils.load_harness_yaml(path)` — central provenance-
  frontmatter-aware loader for `harness.yaml`. Used by `second_brain`; a
  staged migration tracker (`docs/followups/io-utils-migration.md`) covers
  the remaining direct readers. (ADR-001 + ADR-007)
- Smart vault detection in `_load_config` (ADR-002): when `vault_path` does
  not exist on disk, accept it iff the parent is a real Obsidian vault
  (`.obsidian/` present) — the subdir is created on first write. A typo'd
  path with no Obsidian-vault parent fails loudly.
- Graceful degrade for `folders: []` (ADR-008): `_load_config` returns a
  degraded config + logs a remediation warning; `search_notes` returns `[]`
  + warns; `write_note` / `append_note` / `patch_note` raise
  `SecondBrainError` whose message points to `/hm:configure`.
- Interview folder enforcement (ADR-003): `_ask_second_brain` now prompts
  for a writable folder when `vault_path + project_id` are set, defaulting
  to `99_HM/{project_id}/` (ADR-004 — matches the `99_*/01_*` Obsidian
  organization style).
- `configure-second-brain` CLI subcommand (slash-command dispatch surface):
  `--check` emits guidance JSON; `--add-folder <path>` appends a writable
  folder entry to `harness.yaml`.
- `tests/integration/test_second_brain_e2e.py` — live render → load
  regression net. No snapshot pinning, so any future renderer-vs-loader
  drift fails here.

### Changed — testing
- `tests/unit/test_second_brain.py:_write_harness_yaml` now injects the
  provenance frontmatter block, mirroring real renderer output. Previous
  fixture omitted it, which is why the production crash went undetected.
  (ADR-005)

### Docs
- `CLAUDE.md` "외부 소비자의 파서 정합성" list now includes
  `.claude/harness.yaml` with explicit pointer to `load_harness_yaml`.

## 0.13.0 — health consolidation (PLAN-health-consolidation)

### Added — Phase 0 (framework groundwork)
- `reconcile.sweep_orphans()` content_hash-gated orphan-sweep (ADR-005). Walks
  `.claude/`, `.cursor/`, `.codex/`, `.agents/`, `AGENTS.md`; deletes only files
  whose frontmatter `generated_by: harness-maker` AND `content_hash` match a
  historical entry in `.claude/.hm-render-manifest.jsonl`. Theirs / copy-paste /
  `.claude/observability/adaptive/*` always KEEP + warn.
- `.hm-render-manifest.jsonl` append-only audit log written by every render via
  `io_utils.atomic_append` (`os.open(O_APPEND) + os.write`, POSIX line-atomic).
- 14 new unit tests covering the 5 ADR-005 fixture cases + R4 (adaptive
  preserved) + R7 (copy-paste foreign generated_by) + manifest idempotency.

### Added — Phase 1 (core refactor)
- `/hm:health` + `health-finalize` CLI subcommands (ADR-002/006). Replaces
  `ai-readiness*`, `refresh*`, and `personalization-audit` typer surfaces.
- `observability/dashboard.py` 3-section schema writer (`Structural` +
  `External risks` + `Personalization`) via `atomic_write`. Each layer scored
  separately; verify Check 3 reads `structural`, Check 4 reads `external_risks`,
  personalization is informational only.
- `ai_readiness.run_structural()` emits the new `structural` field shape.

### Removed — Phase 1
- `relevance.detect_version_drift` + helpers (migrated to
  `hooks/sessionstart_drift` — sole consumer; behavior bit-for-bit preserved).

### Changed — Phase 2 (template consolidation)
- DELETED `templates/commands/hm/{ai-readiness,refresh,personalization-audit}.md.j2`.
- ADDED `templates/commands/hm/health.md.j2` — three sequential layers with
  per-item `accept` / `reject` / `defer` flow (ADR-001 hard rule, no batching).
- UPDATED 3 skill SKILL.md descriptions (ai-readiness-rubric, research-crawler,
  relevance-filter) to reference the new command.

### Changed — Phase 3 (verify gate)
- `templates/stages/verify.md.j2` rewritten:
  - Check 3 reads `structural` (was `Health: NN` scalar).
  - Check 4 reads `external_risks` (path renamed `refresh/` → `health/`).
  - Both emit explicit "no-baseline PASS" when prior dashboard absent or pre-
    0.13.0 schema.
  - Personalization field never gates verify.
- New CI-safe e2e fixtures (invoke `harness_maker.cli` via `subprocess.run` —
  no Claude binary needed): `test_verify_health_dashboard.py` (engineered
  deltas + missing-baseline + pre-0.13.0 + personalization-ignored cases),
  `test_reconcile_orphan_sweep.py` (3 legacy + R4 simultaneously).

### Changed — Phase 4 (this release)
- 5-file version sync `0.12.1 → 0.13.0` (`.claude-plugin`, `.cursor-plugin`,
  `.codex-plugin`, `pyproject.toml`, `src/harness_maker/__init__.py`).
- `CLAUDE.md` + `README.md` updated to reference `/hm:health`. Atomic-stage
  list at line 145 UNCHANGED (health is a command, not a stage).
- New e2e `test_make_update_0_12_1_to_0_13_0.py` asserts `/hm:make --update`
  removes 3 legacy command files from upgraded sandboxes; user-edited theirs
  copies preserved with stdout warning; `.claude/observability/adaptive/`
  untouched.

### Architectural decisions (this PLAN)
- ADR-001: structured-question-only across all 3 layers (no auto-apply).
- ADR-002: scores remain split (3 separate dashboard fields), dashboard view
  unified.
- ADR-003: legacy commands removed atomically (rely on ADR-005 sweep).
- ADR-004: no observability-file compatibility shim; `adaptive/` preserved.
- ADR-005: reconcile gains content_hash-gated orphan-sweep.
- ADR-006: `/hm:personalization-audit` absorbed; `personalization_audit` module
  and `rubrics/personalization.yaml` are byte-identical to pre-PR state.

### Notes
- `personalization_audit.run()` output is bit-identical to 0.12.x — pinned by
  `tests/unit/test_health_personalization_integration.py`.
- ~3500 LOC delta across 4 commits on `phase0-execute-20260516T1406Z` worktree
  branch; squash-merged into main as a single 0.13.0 release commit.

## 0.12.1 — Group A follow-up patch

### Added
- TECH_SPEC.md `## 7. Personalization Architecture (0.12.0)` section — mirrors README.md update with deeper ADR cross-refs (PLAN-personalization-depth-2026-05).

### Fixed
- `detection_cache.CACHED_MANIFESTS` now includes literal filenames from `STACK_GLOB_MANIFESTS` (`stack.yaml`, `package.yaml`). Haskell projects' profile cache correctly invalidates on these manifests' mtime bump; previously stale until 24h ceiling. Glob patterns (`*.csproj`, `*.sln`, `*.cabal`) remain on 24h-ceiling-only path — they cannot be stat'd. (Closes Phase 3 known limitation from 0.12.0.)
- Snapshot fixtures regenerated — 0.12.0 release shipped with 8 failing `test_synthesize_snapshot.py` tests (`commands/hm/ai-readiness.md.j2` hash drift after Phase 10/12 template additions). 0.12.1 closes that quality gap.

### Notes
- 5-file version sync: 0.11.6 → 0.12.0 → 0.12.1 (.claude-plugin, .cursor-plugin, .codex-plugin, pyproject.toml, src/harness_maker/__init__.py).
- Code-review grade A (2 cosmetic nits deferred): asymmetric dedup in `_flatten_stack_manifests` vs `_flatten_stack_glob_concrete`; test sequencing comment.

## 0.12.0 — personalization depth (Tracks A + D + B-start)

### Added — Track A (Detection Depth)
- `ProjectProfile` schema +5 fields: `frameworks`, `package_manager`,
  `ci_provider`, `foreign_ai_configs`, `detection_confidence` (Phase 1).
- `STACK_MANIFESTS` expanded 5 → 12+: java, kotlin, swift, dart, ruby, php,
  csharp, elixir, scala, c-cpp, zig, haskell (Phase 3).
- Framework detection parses python/node/rust deps for fastapi, django,
  flask, streamlit, jupyter, react, vue, next, express, nestjs, remix,
  astro, tauri, axum, tokio, bevy, etc (Phase 3).
- `package_manager` detection: uv / poetry / pip / pipenv / npm / pnpm /
  yarn / bun / cargo (Phase 3).
- `ci_provider` detection: github-actions / gitlab-ci / circleci / jenkins
  / travis (Phase 3).
- `recommend_wrapup_docs()` detects CHANGELOG.md / TODO.md / HISTORY.md /
  docs/ADR-*.md (Phase 4).
- `recommend_mcp_servers()` framework → MCP mapping (frontend →
  playwright) (Phase 4).
- Detection cache `~/.cache/harness-maker/profile-<hash>.json` with
  manifest-mtime invalidation + 24h TTL + `atomic_write` + corruption
  recovery (Phase 2).

### Added — Track D (Foreign AI Config Migration)
- Detects 6 known foreign configs: `.cursor/rules/`, `AGENTS.md`,
  `CLAUDE.md`, `.continue/config.json`, `.aider.conf.yml`,
  `.github/copilot-instructions.md` (Phase 5).
- LLM-driven mapping `foreign_config.llm_map()` with sha256
  content-keyed cache + 24h TTL (Phase 6).
- `@hm:harness:*` inverted block markers (`block_merge.py`) +
  `MarkerStyle` dispatch for HTML / HASH_COMMENT / JSON_KEY (Phase 6).
- 0.11.x file migration handler — fingerprint detection +
  first-encounter rewrite into new marker family (ADR-009 amendment,
  Phase 6).
- 6 Jinja2 templates in `templates/foreign-configs/` (Phase 6).
- `configure.md.j2` extended with conditional foreign-config import
  section (Phase 6).

### Added — Track B start (Adaptive Self-Tuning)
- `AdaptiveConfig` in `HarnessConfig` with `disable_telemetry: bool =
  False` (opt-out per ADR-005) + `audit_session_threshold: int = 30` +
  `audit_days_threshold: int = 14` (Phase 1).
- `harness_yaml_override` telemetry event with `schema_version: 1`
  mandatory + dual capture (configure-exit primary + SessionStart
  secondary) + dedup key (Phase 9).
- `/hm:personalization-audit` command with ADR-011 rubric (composite
  score 0–100; Bronze < 40 < Silver < 65 < Gold < 85 ≤ Platinum;
  L1 × 0.4 + L2 × 0.3 + L3 × 0.3) (Phase 10).
- `rubrics/personalization.yaml` v0 — locked formulas + evidence schema
  `{n_observations, top_3_signals, confidence}` (Phase 10).
- SessionStart drift surface — hint when 30+ overrides OR 14+ days
  since last audit (Phase 11).
- `tests/unit/test_no_network.py` ADR-005 positive obligation —
  telemetry + audit + SessionStart make ZERO network calls (Phase 9+10).
- `tests/e2e/test_personalization_dogfood.py` — runs profile +
  foreign_config + audit against the harness-maker repo itself
  (Phase 12).
- `tests/e2e/test_personalization_external.py` — ADR-010 amendment
  contract test, skips with TODO until `github/spec-kit` fixture is
  vendored under `tests/e2e/fixtures/external-project-spec-kit/`
  (Phase 12).

### Changed
- Recommendation registry signature widened from `(ProjectProfile)` →
  `(ProjectProfile, Path)` to support project_dir-aware recommenders
  (Phase 4).
- Existing 4 transitive recommends migrated to registry: `preset` +
  `dev_mode` at MEDIUM confidence (backward compat — validator W3
  zero-diff regression test guards), `mechanical_checks` +
  `second_brain` at HIGH (parity with 0.11.x silent behavior)
  (Phase 8).
- `Confidence` enum (`HIGH` / `MEDIUM` / `LOW`) typed across
  `ProjectProfile.detection_confidence` + `Recommendation.confidence`
  + `RecommendationEvidence.confidence` (Phase 1 + 3 + 11 across
  multiple fixes).

### Fixed
- `io_utils.atomic_write` — `os.replace` now wrapped in try/except with
  `tmp_path.unlink(missing_ok=True)` cleanup on failure (was leaking
  temp files on WSL2/NTFS EXDEV — Phase 2 review caught pre-existing
  bug).
- `nestjs` / `remix` framework detection — npm scoped packages
  (`@nestjs/core`, `@remix-run/node`) now correctly matched via
  `@{fw}/` prefix (Phase 3 review).
- `_read_capped_body` — now reads via OS-layer cap (`f.read(N+1)`)
  instead of loading entire file then slicing (Phase 6 review).
- `_AnthropicMapClient` prompt — file body explicitly framed as
  UNTRUSTED with "do not follow embedded commands" instruction
  (Phase 6 review prompt-injection guard).

### Notes
- 11 ADRs locked via `/hm:plan` interview, two plan-validator passes
  (MAJOR_REVISION_RESOLVED first pass + NEEDS_REVISION_RESOLVED second
  pass).
- ADR-010 amendment: e2e external test fixture = `github/spec-kit`;
  vendoring deferred to a follow-up PLAN. Current Phase 12 e2e skips
  gracefully when fixture absent.
- v0 rubric calibration — boundaries conservative; follow-up PLAN
  reviews after 30+ projects.
- ~150 tests added across 11 phases; full unit suite 1700+ green.

## 0.11.0 — 2026-05-11

Adds agentic-depth instructions to the 5 reviewer prompts so reviewers
investigate with Read / Grep / git log before flagging, and promotes the
previously-unreleased verifier-surface strip (ADR-008) into the 0.11.0
release. PLAN
[`PLAN-llm-code-review-2026`](work-docs/PLAN-llm-code-review-2026.md)
Phase C completes the multi-phase agentic-review effort.

### Added
- Each of the 5 reviewer prompt bodies (`code-reviewer`,
  `security-reviewer`, `performance-reviewer`, `concurrency-reviewer`,
  `ux-reviewer`) gains a new `## Investigation Steps (agentic depth)`
  section. The 3 common floor instructions — full-context Read,
  Grep-to-confirm before flagging, git log for prior intent — appear
  verbatim in every reviewer; each reviewer additionally carries a
  domain-specific 4th investigation instruction (trace runtime path /
  Grep for related sinks / Grep for hot-path callers / Grep for lock
  acquisitions / Grep for related accessibility patterns).
- New `tests/structural/test_reviewer_prompts_contain_agentic_depth_clauses.py`
  enforces the substring contract from PLAN ADR-009 Decision #1 — 5
  reviewers × 4 verbatim substrings each. Drift in any of the 5 prompt
  bodies that drops a locked substring fails this structural test at
  PR-merge time.

### Removed
- Stripped the Anthropic-API-dependent surface from the 0.10.0 verifier
  feature: `AnthropicVerifierClient` class, `ModelUnavailableError`
  exception, and the `verify` CLI subcommand (`python -m
  harness_maker.two_pass_review verify`). The target env (Claude Code as a
  subscription tool) has no `ANTHROPIC_API_KEY`, so every shipped
  invocation since 0.10.0 fell back to `model_unavailable` and Pass 1.5
  never actually ran. See ADR-008 in
  `work-docs/PLAN-llm-code-review-2026.md`.
- Removed the Pass 1.5 step from `templates/stages/review.md.j2`. Pass 1
  findings now flow directly to Pass 2; the deferral note in the rendered
  stage points at ADR-008.
- Discarded Phase A7 (wall-time baseline capture). Wall-time measurement,
  if needed, is manual and out-of-band — no auto-test, no
  `tests/fixtures/walltime_baseline_*.json` fixture.
- Removed `test_verify_falls_back_on_model_unavailable`,
  `test_verify_cli_rejects_missing_stdin`,
  `test_verify_cli_rejects_malformed_payload`, and the structural
  `tests/structural/test_review_stage_verifier_wiring.py` test along with
  the corresponding `_RaisingClient` test helper.

### Retained (library surface; future-callable)
- `verify_findings()` function + `VerifierClient` Protocol — reduce-only
  algorithm intact. Callers supplying a custom client (in-process Claude
  Code Task, future external service, mock for tests) still get the
  reduce-only invariant + demote validation + fence-escaped prompts.
  Signature is now `client: VerifierClient` (required) — the previous
  auto-instantiate-Anthropic default is gone.
- `agents/code-verifier` definition retained as the role contract;
  description unchanged.
- Telemetry JSONL schema (15 fields including `verifier_*` counts +
  `wall_time_ms`) retained — fields are now populated manually by the
  stage orchestrator rather than by an auto-invoked CLI.

### Fixed
- `CHANGELOG.md` 0.10.0 "14-field schema" → "15-field schema"
  (release-0-10-0 REVIEW M1; matches the actual `ReviewTelemetryRecord`
  field count).
- `src/harness_maker/two_pass_review.py:_build_verifier_user_prompt` —
  `fixture_label` is now fence-escaped via `_fence_escape` and the
  fixture-label block is relocated AFTER the data-treat preamble so an
  attacker-controlled label cannot inject pre-preamble instructions
  (release-0-10-0 REVIEW O1).
- `src/harness_maker/review_telemetry.py:emit` — absolute
  `observability_dir` is now containment-checked against
  `project_root.resolve()` via `is_relative_to`; escape attempts raise
  `ValueError` (release-0-10-0 REVIEW O2).

### Internal
- PLAN-llm-code-review-2026 status: `phase-a-partial-revert-c-replanned`.
  9 ADRs (ADR-001 through ADR-009) record the design decisions. Phase C
  acceptance criteria adapted post-ADR-008 — verifier-dependent tests
  replaced by prompt-only static guards per ADR-009.

## 0.10.0 — 2026-05-11

Adds a Pass-1.5 verifier sub-role and built-in JSONL telemetry to the
`/hm:review` stage, plus the previously-unreleased Second Brain, research
discovery-lens, and Codex model-omit fixes.

### Added
- New `code-verifier` agent and `verify_findings()` engine for the Pass-1.5
  reduce-only verifier in `/hm:review` (PLAN-llm-code-review-2026 ADR-002).
  Reduce-only invariant — `set(kept ∪ dropped) ⊆ input`; out-of-range LLM
  indices silently dropped; `_validated_demote_severity` rejects promotion
  attempts (a malformed verifier response with `new_severity: "P0"` on a
  P2 finding falls back to one-tier demotion + warning log).
- New `harness_maker.review_telemetry` module emitting an append-only JSONL
  row per `/hm:review` invocation at `.claude/observability/review-{date}.jsonl`
  (ADR-006). 15-field schema (`ts, slug, round, pass1_n, verifier_kept_n,
  verifier_dropped_n, verifier_false_drop_n, verifier_false_keep_n,
  fixture_label, pass2_kept_n, consensus_passed_n, wall_time_ms,
  build_break_count, auto_fix_reverted_n, fallback`). Uses POSIX `O_APPEND` +
  looped `os.write` (EINTR-resilient); PIPE_BUF (4096) write-time guard plus
  pydantic `Field(max_length=...)` schema-time guard. Concurrent reviewers
  sharing `.worktrees/` serialize at the kernel level for writes ≤ PIPE_BUF.
- New `python -m harness_maker.two_pass_review verify` and
  `python -m harness_maker.review_telemetry emit` CLI subcommands so stage
  templates pipe JSON contracts through Python instead of re-implementing
  them in prose.
- New `tests/snapshot/EXCLUSIONS.md` mechanism (empty list at ship — Phase C
  populates) so reviewer-output paths can opt out of snapshot comparison
  when prompt-only agentic depth lands (ADR-005).
- New `tests/structural/` test category for assertions that complement
  snapshot comparison: verifier agent permissions, review-stage wiring,
  reviewer-output schema on a labeled adversarial fixture,
  snapshot-exclusion mechanism, and telemetry-leak grep lint.
- Filesystem-backed Obsidian Second Brain configuration and helper commands
  for typed Markdown notes — project-scoped write allowlists, frontmatter
  / tag / link validation, and stage-aware research / plan / review /
  wrapup guidance.

### Changed
- `/hm:review` Step 3 now runs Pass 1 → Pass 1.5 verifier → Pass 2 (the
  verifier-kept set is the input to Pass 2, not raw Pass 1). Pass 2 prompt
  body now includes `## Diff` explicitly — the parameter was previously
  accepted but never interpolated, leaving reviewers with no diff to
  validate findings against.
- `_build_verifier_user_prompt` fence-escapes LLM-originated `summary` /
  `reasoning` fields per the same defense used in `build_pass2_prompt` so
  a prompt-injected Pass-1 finding cannot break out of its block and leak
  instructions into the verifier turn.
- Updated `/hm:research` so broad trend, roadmap, and opportunity research
  starts with a user-workflow / product discovery lens before papers,
  benchmarks, or architecture-only sources.

### Fixed
- Omit per-agent `model = ...` line from rendered `.codex/agents/*.toml`.
  The hardcoded `o4` / `o4-mini` strings were rejected on ChatGPT-tier Codex
  CLI subscriptions with HTTP 400 `invalid_request_error`, causing reviewer
  / validator subagents (including `/hm:plan` Step 4 plan-validator) to fail
  to spawn. With the field omitted Codex inherits the account's
  `~/.codex/config.toml` profile default automatically. The template's
  `{% if model_codex %}` gate is preserved so a future opt-in
  `codex_agent_models` knob on `HarnessConfig` can re-enable per-agent models
  without touching the template. See ADR-001 in
  `work-docs/PLAN-codex-plan-validator-model-unavailable.md`.

### Internal
- `_codex_agent_files()` count assertions now derive from `_ALL_AGENTS`
  length so future agent registrations don't require manual test edits.
- Tightened the concurrent-writer test: round-trip JSON equality detects
  byte-tearing, not just missed records.

## 0.9.3 — 2026-05-10

Patch release after the Codex target rollout.

### Fixed
- Fixed conditional-router skill frontmatter so YAML descriptions containing
  colons do not create a double-frontmatter parse failure.
- Synchronized sandbox renders and snapshot baselines after the 0.9.3 bump.

## 0.9.2 — 2026-05-10

### Fixed
- Fixed Codex `config_file` rendering so paths do not accidentally include a
  duplicated `.codex/` segment.

## 0.9.1 — 2026-05-10

### Changed
- Version synchronization release after 0.9.0.

## 0.9.0 — 2026-05-10

### Added
- Added OpenAI Codex CLI as a third harness target alongside Claude Code and
  Cursor.
- Codex target renders `AGENTS.md`, `.codex/config.toml`,
  `.codex/hooks.json`, `.codex/agents/*.toml`, and `.agents/skills/*/SKILL.md`
  from the same preset, workflow, skill, and agent definitions.
- Added Codex workflow and loop skills so atomic stages, fused workflows, and
  `/hm:loop` are discoverable through Codex's skill layout.
- Added Codex agent registration in generated config.

### Changed
- Generated outputs (`.claude/`, `.codex/`, `.agents/`, and `AGENTS.md`) are
  treated as render artifacts and ignored in the source repo.
- Reconcile and render paths now understand Codex-specific pure TOML files and
  block-merge-aware `AGENTS.md`.

## 0.8.1 — 2026-05-10

### Added
- Added `ref_folders` and `sibling_repos` to the make interview and CLI flags.
- `ref_folders` can build a local docs index for the `refdocs-search` skill.
- `sibling_repos` lets worktree isolation include related repositories in the
  same logical run.

## 0.8.0 — 2026-05-10

### Added
- Completed the make UX lifecycle for install, configure, update, add, remove,
  and promote flows.
- Added `wrapup_docs`, allowing users to configure documents that `/hm:wrapup`
  should keep updated after work units.
- Added the 3-layer deep interview gate for research, spec, plan, and loop.

## 0.7.1 — 2026-05-08

Patch release closing all P1 + P2 carry-overs from
`REVIEW-harness-gap-cot-2026-05-2026-05-08.md` and
`REVIEW-harness-gap-cot-wiring-2026-05-08.md`. No new features; no
architectural changes; no breaking API changes.

> **Note on version sequencing:** the marketplace stamps had remained at
> 0.6.2 even though the 0.7.0 wiring round (commits 52346c9 → 00d91a0 →
> 3c7304a) was complete on `main`. This release coalesces that internal
> 0.7.0 work + this 0.7.1 cleanup into a single marketplace-published
> 0.7.1 — there is no separate published 0.7.0 artifact.

### Closed REVIEW findings

#### Security
- **Sec-R2-3 (P1)** — `telemetry.py` cwd resolution now uses env-var
  precedence (`CLAUDE_PROJECT_DIR` → `CURSOR_PROJECT_DIR` → stdin
  `workspace.current_dir` → `os.getcwd`). The bare stdin `cwd` field is
  no longer consulted; a poisoned PostToolUse payload can no longer
  redirect metric writes to an attacker-chosen path. (ADR-102)
- **Sec-R2-6 (P1)** — `_load_recent_tool_calls` now reads structured
  `tool_input` whose schema is enforced at write time (whitelist
  projection); upstream poisoning paths are narrowed.
- **Sec F6 parent (P1)** — `DriftMonitor.score` wraps both baseline and
  current text in XML fences with an instruction preamble before
  passing to the LLM judge; embedded `</baseline>` / `</current>`
  close-tags are escaped so an adversarial SPEC body cannot inject
  instructions. (ADR-108)
- **Sec F7 parent (P1)** — `secscan.hallucination._is_available` no
  longer calls `importlib.util.find_spec`; uses a pure filesystem scan
  of `sys.path` so the hallucination gate cannot be coerced into
  executing `__init__.py` or `.pth`-registered finder side effects.
  (ADR-105)
- **Sec F7 R2 (P2)** — `tool_input` strings are scrubbed by
  `_SECRET_PATTERNS` (`sk-…`, `ghp_…`, `AKIA…`, `Bearer …`) before the
  256-char value cap, so a partial-secret tail cannot survive
  truncation. (ADR-107)

#### Concurrency / data integrity
- **Conc-R2-2 (P1)** — Documented the lock-free read contract on
  `SemanticStore.read_all` / `search` and `ProfileStore.get` /
  `get_all`: `os.replace` atomicity guarantees readers see either the
  pre- or post-write file in full, but a read concurrent with a write
  may return the pre-write snapshot. (ADR-104)
- **Code F1 (P1, latent)** — `exclusive_lock` is now re-entrant within a
  single thread via a `threading.local` depth counter keyed by lock
  path string. Same thread can acquire the same lock twice without
  deadlock. (ADR-106)

#### Performance
- **Perf-R2-1 (P1)** — `metrics.jsonl` now rotates per-day to
  `metrics-YYYY-MM-DD.jsonl`; the legacy filename remains readable as a
  compat fallback. New shared reader `harness_maker._metrics_io.iter_recent_entries`
  walks dated files newest-first; both `cache_diagnostics.diagnose_cache`
  and `security_scanner._load_recent_tool_calls` use it (no more
  full-file `read_text().splitlines()`). (ADR-103)
- **Perf F5 (P2)** — `prod_name_guard.scan_sequence` switched to a
  `collections.deque(maxlen=window)` sliding-window walk; per-call cost
  dropped from O(n × window) to O(window).
- **Perf F6 (P2)** — `SemanticStore.write_many` bulk helper acquires
  the lock once for N entries instead of N times via repeated `write`.
- **Perf F7 (P2)** — `EpisodicStore.read_all(max_days=30)` defaults to
  the 30 most recent daily files; pass `None` for the pre-0.7.1
  unbounded behaviour.
- **Perf PF4 (P1, parent)** — `_is_available` now memoises via
  `functools.lru_cache(maxsize=512)`.

#### Code quality
- **Code F2 (P1)** — `security_scanner.scan_all` docstring updated from
  "5 gates" to "7 gates" (matches actual gate count since 0.7.0).
- **Code F3 (P1)** — `two_pass_review.merge_passes` now requires Pass-2
  entries to carry at least one `severity` key; otherwise treats Pass 2
  as failed and falls back to Pass 1, guarding against a malformed
  `[{}]` LLM response silently dropping all findings.
- **Code F7 (P2)** — `secscan.hallucination` now walks `except`
  handler bodies when collecting `guarded_lines`; the fallback import
  in `try/except ImportError: import alt` is now correctly tagged P2
  (guarded) instead of P0.
- **Code F8 (P2)** — `cache_diagnostics` zero-token skip uses
  `(parsed.get(field) or 0) == 0` so JSON `null` values also trigger
  the skip.

#### Tests
- 4 concurrency multiprocess tests bumped `p.join(timeout=30)` →
  `timeout=60` and added `assert not p.is_alive()` before the
  `exitcode` assertion to distinguish timeout from crash.
- New tests: `test_metrics_io.py` (6), `test_locking.py` (3), plus 6
  acceptance tests across telemetry / drift / hallucination /
  episodic / semantic for the items above.

### Out of scope (intentional carry-overs)

These remain on disk as documented limitations; promoted to the 0.8.0
plan if user feedback warrants:
- Sec F2 / F5 (parent) — `security_scanner._persist` and
  `telemetry` JSONL persistence still use plain `open("a")`. Treated as
  a deliberate hot-path exception; documented in code.
- SQLite migration for `semantic` / `profile` (rejected ADR-104).
- LOCK_SH read-side locking (rejected ADR-104).
- `find_spec` retention with `PYTHONNOUSERSITE` (rejected ADR-105).
- Schema versioning for metrics.jsonl entries — handled via
  forward-compatible field addition.
