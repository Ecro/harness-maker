---
type: plan
task_slug: hm-overhaul-p1-s
spec: specs/SPEC-hm-overhaul-p1.md
spec_hash: a2058086eb49
scope: PR-S (AC-003 … AC-011, re-checking AC-008; IRR-002 … IRR-006)
version: 0.64.0
status: planning
summary: "Overhaul phase 1 PR-S: four stages, one hm check gate, retired hooks, brownfield sweep"
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
- **ADR-004: one pytest run for `ac`.** The runner is the project's `.venv/bin/python -m pytest`
  when present, else the pytest prefix of the first CI test gate; with neither, `ac` cannot run
  and the result is exit 3 (degraded). A listed id missing from the junit XML is classified by a
  `--collect-only -o addopts=` probe: collected means `deselected`, otherwise `not collected`.
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
- **ADR-010: `hm check --red` with `--mutation` or `--harness`.** The RED run is the AC run only;
  approval, review, security and cve are reported but cannot turn a RED pass into exit 1, because
  RED runs before the change exists. Gates do not run in `--red` (the code is absent by design).

(Phase 4 ADRs are added when that phase starts.)

## Risks

- **Disk.** The AC-006 replay builds 36 trees plus venvs; each is created and deleted inside the
  test, never kept.
- **AC-010 cannot pass inside this PR.** It needs a published eval re-run on a harness SHA from
  this branch, which costs real model runs; the DRI runs it. Until then its test fails by design
  (the SPEC: "fails, never skips").
- **Surface ratchet.** The stage collapse removes commands, which the frozen baseline's shape
  check rejects. Held as this PLAN's allowance with a BASELINE-DELTA doc, folded from main after
  merge, as PR-C did.

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

- [ ] Phase 1 — `hm check`
- [ ] Phase 2 — telemetry readers
- [ ] Phase 3 — eval-3 replay
- [ ] Phase 4 — stage collapse
- [ ] Phase 5 — ship
