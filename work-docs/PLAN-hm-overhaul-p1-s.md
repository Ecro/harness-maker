---
type: plan
task_slug: hm-overhaul-p1-s
spec: specs/SPEC-hm-overhaul-p1.md
spec_hash: a2058086eb49
scope: PR-S (AC-003 … AC-011, re-checking AC-008; IRR-002 … IRR-006)
version: 0.64.0
status: planning
summary: "Overhaul phase 1 PR-S: four stages, one hm check gate, retired hooks, brownfield sweep"
surface_allowance:
  chars: 960
  reason: "Review round 1 (ADR-044..ADR-047): execute gains the one-RED-then-phases order, the irreversible-decision stop, the test-edit rule in the fix loop and the background-gate rule (+912 claude, +822 codex); wrapup gains the background-gate rule, answer-gated intent writes and the closing Understanding print, net of compression (+48 claude, +8 codex). Both stages stay inside their AC-004 budgets. No new round trips."
  delta_doc: BASELINE-DELTA-hm-overhaul-p1-s.md
  commands:
    execute: 653
    wrapup: 41
---

# PLAN: overhaul phase 1, PR-S (stage collapse)

The SPEC holds the ACs, the tables and the IRR list; this PLAN holds the order of work, the calls
the SPEC leaves to the implementer (ADRs below) and the AC→test map. PR-C (AC-001/002/008) landed
as #31/#32.

## Phases

Each phase ends at a commit with the local gate green for what it touched.

1. **`hm check` (AC-005).** New module `harness_maker/check.py`, wired into `hm._DISPATCHABLE` and
   `command_registry.MODULES`. Sections approval, gates, ac, review, security, cve, `--mutation`,
   `--harness`; modes plain and `--red`; the exit table and precedence; tree snapshot and
   `tree_changed`. Tests first (`tests/unit/test_overhaul_p1_hm_check.py`).
2. **Telemetry readers (AC-011).** `security_scanner` Gate 7 status, `readiness` n/a signals,
   `feedback.telemetry_grep`, the reader-list grep pin.
3. **Eval-3 replay (AC-006).** Commit `tests/fixtures/hm_check_eval3/<run>/{patch.diff,expected.json}`
   for the 36 hm runs; the integration test rebuilds each tree from db19f023 and runs `hm check`.
4. **Stage collapse (AC-003, AC-004, AC-007, AC-009, re-check AC-008).**
   - New self-contained `stages/{research,spec,execute,wrapup}.md.j2`; delete review, verify,
     `_partials/`, `hm/*` helpers, loop commands and configure from the render.
   - `synthesize`: four stages, conditional agents and skills (D-1…D-9), no `.claude/stages/`, no
     `.claude/hm/`.
   - Hooks: retire `telemetry`, `hooks.post_write_reminder`, `hooks.autopilot_autoarm` (append to
     `_HARNESS_RETIRED_HOOK_INVOCATIONS`), stub their `python -m` entry points.
   - `reviewers.fanout` (InterviewAnswers field, round trip, preset yaml).
   - `make` inert-key warnings (AC-007 table); the pristine-only sweep of retired files.
   - Registry: drop cut and moved headings, register the new ones.
   - Suite: delete tests whose subject is gone, move kept-behaviour tests to the new owner,
     re-capture goldens; AC-001 pinned to the PR-C merge commit.
5. **Ship (AC-010, 0.64.0).** The scorecard test, version sync (four files), CHANGELOG
   `### Removed`, CLAUDE.md and README, surface allowance + BASELINE-DELTA, `mark-tested`.

## ADRs

- **ADR-001: db19f023 and the PR-C merge commit are read with `git archive`.** As PR-C ADR-001: the
  SPEC's `git worktree add` names the source of truth (that commit's tree); `git archive <sha> src`
  gives the same bytes and writes nothing into `.git/`, so a killed xdist worker leaks no
  worktree entry. This covers the AC-006 harness render, the AC-007/009 references and the AC-001
  pin (`tests/fixtures/overhaul_p1/prc_merge_sha` = `24d12cc5`, the PR-C squash on main).
- **ADR-002: `hm check` takes its snapshot from git's own file list.** `tree_changed` compares
  sha256 over `git ls-files -z --cached --others --exclude-standard` (plus deletions) at start and
  end. That is exactly "every tracked or unignored path". Outside a git repo the list is a walk
  that skips `.git`.
- **ADR-003: gates run in a scrubbed environment.** Every gate subprocess gets
  `PYTHONDONTWRITEBYTECODE=1`; a pytest-kind command gets `-p no:cacheprovider` appended. The AC
  run writes its junit XML to a temp dir outside the project. Gates all run (no stop at the first
  failure), so the JSON names every failing gate.
- **ADR-004: one pytest run for `ac`, over the files of the listed ids.** The runner is the
  project's `.venv/bin/python -m pytest` when present, else the pytest prefix of the first CI test
  gate; with neither, `ac` cannot run and the result is exit 3 (degraded). Pytest is given the
  test *files* with `--continue-on-collection-errors`, because a node id inside a module that
  fails to import, or one that does not exist, makes pytest abort the whole run. Outcomes are read
  from the junit XML. Two outcomes junit cannot express are settled before or around it:
  - a listed id that names no test (statically, by `ast`) is `not collected` and never reaches
    pytest;
  - a statically present id missing from the XML is `deselected` (an `addopts -m` filter);
  - a non-strict XPASS is a plain pass in junit, so a 9-line plugin, put on `PYTHONPATH` from the
    run's temp dir, adds a `hm_check_outcome=xpassed` property to that test's junit entry. The
    outcome still comes from the XML.
- **ADR-005: the RED reason test.** A body failure or a setup error is a real reason, except a
  fixture-not-found setup error. A collection error counts only through the `red_by_import`
  guard (`ImportError`/`ModuleNotFoundError`, or `AttributeError: module 'x' has no attribute
  'y'`, first-party and absent at HEAD). "First-party" for a missing module means its top-level
  package exists under the root (`<root>/<pkg>` or `<root>/src/<pkg>`).
- **ADR-006: approval states outside the SPEC's list.** `legacy` (a pre-v3 SPEC with no stamp) is
  read like `missing`: it passes only at `auto_full`.
- **ADR-007: the `review` section reads a findings table.** The new execute review step writes
  `## Findings` as a table with a `disposition` column (accepted / rejected / duplicate /
  unresolved; `rejected` needs an `authority`). A REVIEW doc with findings but no such column
  fails the section; a `none` findings section passes.
- **ADR-008: CVE baseline.** Added or re-pinned = a `(name, version)` in the working `uv.lock`
  absent from `HEAD:uv.lock`. With no lock at HEAD, every locked package counts as added (the
  change pinned it). Without any lock, `pyproject.toml` dependency names are compared. The lookup
  raises on HTTP failure (the crawler swallows errors), so a failed lookup is `unavailable`,
  never clean.
- **ADR-009: `--harness` reports and does not gate.** It is the structural layer of `hm cli health`
  (`ai_readiness.run_structural`): score and failed signals. The AC-005 exit-1 list does not name
  it, so it never changes the exit code; an exception there is reported as `ok: false` with the
  reason and still does not gate.
- **ADR-010: `--red` runs approval and the RED check only.** RED runs before the change exists,
  so gates, review, security and cve are reported as `skipped: --red`, and `--mutation` and
  `--harness` are ignored there. Approval still gives 5, and a tree change still gives 4.
- **ADR-011: the plain `ac` run always re-derives `red_by_import`.** Every first-party import in an
  AC's test files that is absent at HEAD is listed with `implemented`; one not implemented fails
  its AC and sets `ac.reason: red_by_import not implemented`, whatever the test outcome says.
- **ADR-012: the security scan walks git's file list.** `secscan.secrets` gains `scan_files`, fed by
  the same `git ls-files` list the snapshot uses, so an ignored `.worktrees/` copy is never read.
  "An import that resolves inside the project root never counts" is vacuous here: it is about the
  hallucination gate, which `hm check` does not run.

- **ADR-013: readiness telemetry signals are n/a whether or not a file exists.** The AC-011 row
  names the no-file case; a leftover `metrics-*.jsonl` from before 0.64.0 is a stale record of a
  writer that no longer runs, so scoring it would make readiness depend on history. Both signals
  carry weight 0 and `not_applicable`, and the dimension score is rescaled over the applicable
  weights (dir + dashboard).
- **ADR-014: "has a telemetry source" means a `metrics-*.jsonl` or legacy `metrics.jsonl` exists**
  (`_metrics_io.has_telemetry_source`). Security reports `prod_name_guard: scanned` with a file and
  `no telemetry source` without one; `telemetry_grep` keeps `""` for a file with no stop event
  (a clean session, as before). The `telemetry` stub drains stdin; `telemetry.main()` stays a
  library function. The `test_hook_host` writing control moved to `flush_session`.

- **ADR-015: a run's "staged diff" is its change against HEAD, staged or not.** In 21 of the 36
  trees part of the change was never staged (e.g. t1-hm-3's `tests/test_format.py`, all of
  t10-hm-2), and the 2026-10-15 probe ran on the working tree. `git diff --cached HEAD` alone would
  rebuild a tree the golden was not recorded on, so `patch.diff` is `git diff --binary HEAD` plus
  each untracked, unignored file. Tool caches are left out with `.venv` and `__pycache__`:
  `.mutmut-cache` (3 trees, a SQLite file) and `.pytest_cache`. **For the DRI:** the SPEC's wording
  ("its staged diff") and the machine note (`git diff --cached HEAD`) say staged-only.
- **ADR-016: the replay venv is `venv --system-site-packages --without-pip` plus one `.pth`.**
  `--system-site-packages` from a uv interpreter sees the base install, not the suite's venv where
  pytest lives; the `.pth` adds the running environment's site-packages. pip is never used.
- **ADR-017: "modulo provenance" masks the version stamps and the install ref.** The harness
  digest is `_overhaul_p1_ref.normalise` plus a literal replacement of the checkout path the
  render was installed from (read from the rendered `execute.md`). The 36 original harness
  commits are identical once masked, so `harness_manifest.json` holds one digest (71 files).
- **ADR-018: `expected.json` is written from the golden rows, not from `hm check`.** Approval
  state per run, `ac` failing everywhere (t6-hm-2 with its skip-path reason), security and gates
  ok, `tree_changed` empty, exit 1. Negative controls use t1-hm-1 (`timeparse/format.py`): the
  harness-file control commits the line on top of the harness commit, so it stays untouched.

Phase 4 (each is the simplest option where the SPEC is silent):

- **ADR-019: commands keep the `/hm:` prefix; Codex stage skills stay `hm-<stage>`.** Only the
  set shrinks (research, spec, execute, wrapup + utilities).
- **ADR-020: the two rubric skills stay** (`agent-quality-rubric`, `ai-readiness-rubric`): kept
  readers point at them, so `communication_audit.PINNED_SKILLS` is those two.
- **ADR-021: second opinion is one compact step in execute's review**, rendered only with
  `second_opinion.models`; its agents and skill render under the same condition.
- **ADR-022: skills are minimal.** Six retired skill directories and four retired agent templates
  are deleted from `templates/`, not left unrendered; `RETIRED_*` in `synthesize` names them for
  the sweep and the inert-key warnings.
- **ADR-023: `waiver-check` is warn-only and renders only at strictness `warn`.**
- **ADR-024: `AtomicStage` and the six-stage `AutonomyConfig().pipeline` default are kept.**
  Both are inert library surface used by autopilot and its tests; changing the default broke ~20
  of them. The documentation contract reads the rendered `synthesize._ATOMIC_STAGES` instead.
- **ADR-025: inventories are re-derived, not edited.** Doc contract blocks, the provides table and
  the redundancy matrix list what renders today; 15 retired matrix rows are removed.
- **ADR-026: AC-004 budgets are measured at the pinned install ref** (`$HOME/harness-maker`), so a
  checkout path's length is in no number.
- **ADR-027: delegation renders for `wrapup` only;** other listed stages are skipped with the
  `delegation.stages` inert warning.
- **ADR-028: the TUNE knobs keep their registry rows;** `reviewers.max_review_rounds` still sets
  the review cap (default 3); reclassifying registry entries is left to the SPEC's non-goal.
- **ADR-029: `reviewers.installed` round-trips unchanged;** lenses render only with
  `reviewers.fanout: true` plus installed lenses (D-9).
- **ADR-030: user-block markers are literal in the stage wrappers** (`atomic_command.md.j2`,
  `codex/stage_skill.md.j2`), so an edited stage block-merges on upgrade instead of freezing; the
  Codex agent TOMLs have no markers and keep their pre-existing KEEP behaviour.
- **ADR-031: the instruction-preservation gate is deleted with the bodies it pinned;** its
  subject (`.claude/stages/`) no longer renders.
- **ADR-032: presets are pruned to rendered names;** `focus=security` maps to
  `security-reviewer` (a lens, opt-in) instead of the retired `security-auditor`.
- **ADR-033: `make.md` documents `instrumentation.stage_agent_ledger` as inert** with one warning
  per `make`; the key and value are kept (IRR-006).
- **ADR-034: wrapup keeps the receipt reconcile and the promotion line in compressed form;**
  `<slug>` is the PLAN's `task_slug`.
- **ADR-035: tests whose subject is gone are deleted; their bound ids go to the known-dead
  `[pr-s-stage-collapse]` section** (92 ids, each resolving at `a3c2a5a8` and dead at HEAD).
  Several pinned behaviour that survives in compressed form (Understanding block, ADR "Decided
  by", receipt reconcile, intent file flags); rebinding them is a follow-up.
- **ADR-036: `modular_edit` passes the install ref** (`harness_maker_src_path`) so kept skills
  render through it.
- **ADR-037: AC-001 is pinned to the PR-C merge commit via `git archive`**
  (`tests/fixtures/overhaul_p1/prc_merge_sha`), not a `git worktree add`, matching ADR-001.
- **ADR-038: HOW-IT-WORKS gets a 0.64.0 banner and corrected inventories, not a rewrite.**
- **ADR-039: the sweep removes the directories it empties** — a swept skill's `skills/<name>/`
  including Codex's nested `agents/`, and the retired `.claude/stages/` and `.claude/hm/`. The
  AC-007 test found both left behind empty. `rmdir` refuses a non-empty directory, so a user file
  keeps its directory.
- **ADR-040: AC-007's "byte-identical" covers user records.** Under `specs/`, `work-docs/`,
  `.claude/memory/` and `.claude/observability/`, a file whose `content_hash` still matches its
  body is harness state and may re-render; memory seeds (no hash) may only change their
  `harness_maker_version` stamp; `orphans-*.jsonl` may only be appended to. Everything else must
  not move.
- **ADR-041: the surface baseline is re-frozen in the branch,** with `render_sha` = the merge-base
  `a3c2a5a8` (`BASELINE-DELTA-hm-overhaul-p1-s.md`). A shrink cannot be held as an allowance.
- **ADR-042: AC-010 stays `pending_test: true`.** Its test is committed and fails until the DRI's
  re-run rows exist; `mark-tested` waits for that.
- **ADR-043: a hash-matching file whose user blocks differ from the template's defaults
  block-merges.** A block-merged file records the hash of its merged body, so the next `make`
  read it as pristine and replaced it, dropping the user's block on the second upgrade. This was
  already true at `a3c2a5a8` (reproduced on an agent file) and surfaced as an alternating
  `test_dogfood_sandbox` failure. `reconcile._user_blocks_edited` compares the file's user
  blocks with the template's (and its literal includes'); an unreadable template counts as
  edited. Unedited files still REPLACE, so the render summary's merge count does not grow.

## Risks

- **Disk.** The AC-006 replay builds 36 trees plus venvs; each is created and deleted inside the
  test, never kept.
- **AC-010 cannot pass inside this PR.** It needs a published eval re-run on a harness SHA from
  this branch, which costs real model runs; the DRI runs it. Until then its test fails by design
  (the SPEC: "fails, never skips").
- **Surface ratchet.** The stage collapse removes commands, which the frozen baseline's shape
  check rejects. A shrink cannot be an allowance, so the baseline is re-frozen in the branch
  (ADR-041); the DRI re-freezes from main after the squash.

## AC→test map

| AC | Test id |
|---|---|
| AC-003 | `tests/unit/test_overhaul_p1_cut_ledger.py::test_ac003_ledger_covers_db19f023_registry`, `::test_ac003_no_inv_heading_is_cut` |
| AC-004 | `tests/unit/test_overhaul_p1_surface.py::test_ac004_file_set_per_target`, `::test_ac004_char_budgets`, `::test_ac004_hook_commands_per_file`, `::test_ac004_stage_content_substrings`, `::test_ac004_no_removed_command_named` |
| AC-005 | `tests/unit/test_overhaul_p1_hm_check.py::test_ac005_exit_table`, `::test_ac005_red_mode_table`, `::test_ac005_tree_bytes_unchanged`, `::test_ac005_gate_env_has_no_bytecode` |
| AC-006 | `tests/integration/test_overhaul_p1_eval3_replay.py::test_ac006_section_verdicts_match_golden`, `::test_ac006_negative_controls` |
| AC-007 | `tests/integration/test_overhaul_p1_brownfield.py::test_ac007_pristine_trees_sweep_to_the_ac004_set`, `::test_ac007_one_byte_edit_is_kept`, `::test_ac007_user_blocks_and_hooks_survive` |
| AC-008 | `tests/integration/test_overhaul_p1_hook_commands.py::test_ac008_every_shipped_hook_command_is_safe` |
| AC-009 | `tests/unit/test_overhaul_p1_kept.py::test_ac009_*` (six) |
| AC-010 | `tests/integration/test_overhaul_p1_ship_bar.py::test_ac010_scorecard_meets_bar` |
| AC-011 | `tests/unit/test_overhaul_p1_telemetry_readers.py::test_ac011_reader_table`, `::test_ac011_reader_list_matches_grep` |

## Progress

- [x] Phase 1 — `hm check`
- [x] Phase 2 — telemetry readers
- [x] Phase 3 — eval-3 replay
- [x] Phase 4 — stage collapse
- [x] Phase 5 — ship (0.64.0; AC-010 stays red until the DRI commits the eval re-run)

## Evidence

### Phase 1 (AC-005)

RED, 2026-10-16, against b5ff8af0 with `src/harness_maker/check.py` absent:

```
tests/unit/test_overhaul_p1_hm_check.py:25: in <module>
    from harness_maker import check, spec_machine
E   ImportError: cannot import name 'check' from 'harness_maker'
ERROR tests/unit/test_overhaul_p1_hm_check.py
```

A first-party name absent at HEAD, which is the SPEC's own `red_by_import` RED.

GREEN: `tests/unit/test_overhaul_p1_hm_check.py` 48 passed (25 exit rows, 16 RED rows, usage,
one-line output, tree bytes x2, gate env). `mark-tested --ac AC-005`: OK; `approval-status` still
`approved`.

### Phase 2 (AC-011)

RED, 2026-10-16, against 90573c8a:

```
>       findings, status = security_scanner.scan_all_with_status(empty, force=True)
E       AttributeError: module 'harness_maker.security_scanner' has no attribute 'scan_all_with_status'
FAILED tests/unit/test_overhaul_p1_telemetry_readers.py::test_ac011_reader_table
```

`test_ac011_reader_list_matches_grep` passed at RED: it is the pin (the four readers already are
the grep set), there to fail when a fifth reader appears.

GREEN: both AC-011 tests pass, including the Gate 7 differential against db19f023 on the same
file. Tests whose subject was the retired behaviour were rewritten (readiness rotation counting,
telemetry_grep empty-string, `scan_all` mocks → `scan_all_with_status`). `mark-tested --ac AC-011`:
OK; `approval-status` still `approved`.

### Phase 3 (AC-006)

RED, 2026-10-16: the replay helpers with `hm check` taken from b5ff8af0 (before Phase 1) on
t1-hm-1: `No module named harness_maker.check`.

GREEN: `tests/integration/test_overhaul_p1_eval3_replay.py` 38 passed in 43 s at `-n 4` (36 trees,
negative controls, fixture-set pin); every rebuilt harness commit matched the manifest. Fixtures:
830 KB of patches. `mark-tested --ac AC-006`: OK; `approval-status` still `approved`.

Phase 1 full-suite gate (run while Phase 2 edits landed): besides the five allowed failures it
found `test_autonomy_level_literals` (check.py restated `ask`/`auto_full`) and
`test_test_dep_map_config_class` (the two new suites unlisted); both fixed here.

### Phase 4 (AC-003, AC-004, AC-007, AC-009; AC-008 re-checked)

RED, 2026-10-16: the AC-007 brownfield suite run with the PR-C merge source (`24d12cc5`) fails all
four tests: no inert-key warnings, `post_write_reminder`/`autopilot_autoarm` still wired, the
lens/fanout values not round-tripped, `max_review_rounds` unread. At HEAD before ADR-039/043 it
also failed: `.claude/stages`, `.claude/hm` and `.agents/skills/autoloop-driver/agents` left
empty, and the reconcile unit test returned `REPLACE`/`hash-match-ours` for an edited block.

GREEN: brownfield 4 passed (8 db19f023 cells + 36 eval-3 trees; one mutation per retired path);
AC-004 surface and AC-009 kept suites pass; AC-008 passes. `mark-tested --ac AC-007`: OK;
`approval-status` still `approved`. Full suite: only the five allowed failures plus
`test_ac010_scorecard_meets_bar` (by design, ADR-042).

