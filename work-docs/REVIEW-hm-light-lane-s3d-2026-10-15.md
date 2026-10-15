---
type: review
task_slug: hm-light-lane-s3d
status: APPROVED
created: 2026-10-15
reviewers_invoked: [code-reviewer, security-reviewer, test-reviewer]
consensus_method: cross-check
review_base: d385e192
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hm-light-lane-s3d
  computed_at: 2026-10-15T18:40:00Z
---

# REVIEW — hm-light-lane-s3d (stage 3d of HM-LIGHT-LANE)

**Scope.** Lane `full`, preset Production. The review ran on the PR branch with no per-task worktree.
The diff reviewed is `d385e192..HEAD`. Regenerated snapshots, the surface baseline and the captured
reference JSON were left out of the reviewer diff; the tests pin them.

**Procedure:**
- Round 1 ran three read-only lenses: code, security and tests.
- The main loop decided each finding.
- One read-only confirmation pass followed.
- The main loop then fixed two residual P2s itself and re-ran the gate.
- The cross-model second opinion was skipped because the `codex` CLI is not installed. The rule is to
  warn and proceed.
- CI was not used, per the DRI's 2026-10-15 instruction. The gate was local.
- AC-007 (`INTEGRATION=1 tests/integration/test_light_lane_s3d_timeparse.py`) passed locally after main
  was merged.

**AC-006 reference.** It reads df070f6c, which is main with stage 3c, rather than the SPEC's 4bd3d3d8.
Stage 3c changed those renders after the SPEC was written. The intent is unchanged: 3d adds no render
bytes outside the light check. The DRI was told in the thread when the SPEC was approved.

## Round 1

No P0, no P1.

| Sev | Summary | Disposition |
|---|---|---|
| P2 (sec) | Any file at `.venv/bin/python` was accepted as the interpreter | Fixed: `.venv/bin/python` and `.venv/pyvenv.cfg` must both be files, else exit 3 |
| P2 (sec) | Deleting a workflow or a `[tool.*]` table turned a gated repo into a pytest-only one | Fixed: exit 3 when HEAD tracks a workflow yml the tree lacks, or HEAD's pyproject has `tool.ruff`/`tool.mypy` the tree lacks |
| P2 (sec) | Non-pyproject ruff/mypy configs were silently ungated | Fixed: `ruff.toml`, `.ruff.toml`, `mypy.ini` and `.mypy.ini` give exit 3 (unsupported) |
| P2 | mypy got a `.` target despite `packages`/`modules` | Fixed: no target when `files`, `modules` or `packages` is set |
| P2 | Long docstrings | Fixed |
| P2 (tests) | The CI-absent case "workflows dir without a yml" had no flag-on oracle | Fixed: rows for that dir (exit 0) and for one `.yaml` (exit 3) |
| P3 | `_spec_test_framework` relied on its caller for slug validation | Fixed: own `_is_plain_slug` guard |
| P3 | The record line and the Check 2 intro did not name the SPEC source | Fixed |
| P3 (tests) | Full executed argv; ruff+mypy row; masked-key check; timeout race; null/true framework; slug not echoed on exit 1/4; HOME pinned in renders; dev-group unit test; a wrong comment | Fixed |
| P3 | Bench fixture `pytest` unpinned | Fixed: `pytest>=8` |
| P3 (sec) | `check` honours a SPEC-path marker, so verify-before-completion could skip its lint run | Declined: the SPEC makes marker changes a non-goal. Follow-up |
| P3 | A cached pass survives `.venv` content changes | Declined: same as the CI path's PATH tools |
| P3 | Per-task worktree: `uv run` syncs `<WT>/.venv`; an extras-only pytest gives exit 1 ("a gate failed") | Follow-up. It fails closed, and the bench runs without per-task worktrees |

## Confirmation pass

Every round-1 fix is confirmed. No new exit 3 reaches the CI-present or flag-off paths, so AC-001
holds.

The new git calls are `ls-tree` and `show`. They do not refresh the index, so they add no
`core.fsmonitor`-style exposure.

The main loop fixed these residuals:
- `git show HEAD:pyproject.toml` is now `HEAD:./pyproject.toml`, so it resolves against cwd when
  `--root` is a subdirectory.
- `_git_out` now catches `ValueError`, so a non-UTF-8 HEAD file gives exit 3 rather than a
  traceback. A new row covers this, and it failed without the fix.
- A new row covers an unborn HEAD (exit 3).

Accepted:
- No subdirectory-`--root` row. Callers always pass the project root.
- The SPEC `.md` prose does not mention `pyvenv.cfg`, the HEAD-drift exit 3, the other-config exit 3
  or `modules`/`packages`. It also says `dev = ["pytest"]`, while the fixture pins `pytest>=8`. These
  are stricter readings of "fail closed" and were left as is, to keep the stamped SPEC untouched.

## Grade

**A** after round 1 and one confirmation pass. Status APPROVED.

**Measured:**
- Codex `hm-execute`: +212 chars over df070f6c.
- Claude renders: unchanged except `hm/execute-light-check.md`.
- Not yet measured: whether light runs now skip review and verify. That waits for the eval re-run.
