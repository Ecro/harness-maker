---
type: review
task_slug: hm-light-lane-s3c
status: APPROVED
created: 2026-10-15
reviewers_invoked: [code-reviewer, security-reviewer, test-reviewer]
consensus_method: cross-check
review_base: c3096d4c
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hm-light-lane-s3c
  computed_at: 2026-10-15T09:30:00Z
---

# REVIEW — hm-light-lane-s3c (stage 3c of HM-LIGHT-LANE)

The review ran on the PR branch, with no per-task worktree. Lane `full`, preset Production.
The diff under review is `c3096d4c..a8c34893`. Regenerated goldens, snapshots and the surface
baseline were left out of the reviewer diff.

**Procedure, stated so nobody infers a step that did not run:**
- Round 1 had two dispatches:
  - Core lenses, read-only, with no shell.
  - Security and tests plus behavioural checks, with a shell, run in `git archive` exports. These
    checks covered:
    - 5 render arms at both commits;
    - 18 `check --all` fixtures × 2 strictness levels;
    - the upgrade path through `make --update`;
    - 6 mutations.
- Pass 2 was the main loop deciding each finding, not another dispatch.
- There was one confirmation pass, read-only, over 9fece65b and 25727c61. The main loop then re-ran
  the s2, s3c, quiet-check and light-plan suites; all of them passed.
- The cross-model second opinion was skipped because the `codex` CLI is not installed. The rule is
  to warn and proceed.
- The round-1 amendment changed AC-006, AC-010 and AC-016, which invalidated the approval stamp.
  The DRI's re-approval is required before merge.

## Round 1

No P0 and no P1.

**What the checks showed:**
- **Full lane:** every instruction is kept once the pointers are expanded. This held on all
  5 render arms.
- **Codex:** unchanged apart from the named deltas.
- **Cursor:** `.cursor/` is unchanged, and Cursor still reaches the preamble.
- **`check --all`:** exit codes and verdicts are unchanged in every fixture case.
- **Oracles:** the a7403f2f oracles were captured before any implementation commit, and they
  reproduce byte-identically.

**Findings:**

| Sev | Summary | Disposition |
|---|---|---|
| P2 | Short-PLAN routing relied on the preamble's prose loop check, which now lives in a ref file. A missing file meant no check at all. | Fixed: with the loop rendered, Step 0 runs `hm worktree loop-mode-active` and routes on its exit code (SPEC amendment, S7/S13) |
| P2 | The light read-back dropped full-lane integrity guards: stop after a failed repair, never invent `none`, no absolute paths, `..` or globs, and `user` provenance only on an explicit call | Fixed: guards added. The execute C bound was amended from ≤ −2500 to ≤ −2150 (measured −2201) |
| P3 | The execute-plan pointer was not lane-conditional, so a light run could read 5.4k extra | Fixed: the pointer is read only when not writing the light PLAN |
| P3 | The Step 0.3 sentence had no read rule | Fixed: read from the project root, never a worktree; STOP if the file is missing |
| P3 | `_run_check_all` labelled a `validate()` exception as a load failure, overwrote cross errors, and dropped the OSError reason | Fixed: load and validate are split; `validate failed: <Type>`; the reason is kept |
| P3 | The quiet-check test collapsed errors to their AC id | Fixed: it compares the full set of distinct error strings |
| P3 | Codex Step 0.3 names a `.claude/` file; Step 1.5 wording names PLAN metadata; the scorer exception fails open | Residual. The SPEC pins the first, the second is a design limit, and the third predates this change and is kept by the SPEC |

## Confirmation pass

Every round-1 finding is fixed. `loop_routing_as_off()` edits only the Step 0 head and cannot hide
a loop byte outside a span. The `loop-mode-active` exit convention matches
`worktree._cli_loop_mode_active`: 1 means inactive, and 2 falls through to the full lane.

**Accepted P3 residuals:**
- The helper's line filter is a substring match.
- An unfilled `<PROJECT_ROOT>` reads as exit 1. Step 0.2 shares this, and in a loop the PLAN
  already exists.

## Grade

**A** after round 1 and one confirmation pass. Status APPROVED, pending the DRI's re-approval of
the amended SPEC.

**Measured against a7403f2f:**
- **Light run:** −9,962 chars.
- **Full run:** −7,608 chars.
- **Codex hm-execute:** +2,039, within its ≤ +2,500 bound.

Not measured here: B's per-run saving, and the smaller PLAN and machine.yaml.
