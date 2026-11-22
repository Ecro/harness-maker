---
type: spec
task_slug: pr-boundary-gate
status: approved
created: 2026-11-22
tags: [harness-maker, spec, ci, release, dri-bottleneck]
test_framework: pytest
interview_rounds: 0
summary: "Run the boundary suite on every PR before merge (merge now publishes via autotag), and put a five-line phone-readable block at the top of the PR template."
---

# SPEC — pr-boundary-gate

## Intent

Since 0.65.7 `autotag.yml` turns a version-changing push to main into a tag and a release, so a
merge is a publish. The boundary suite (`tests/integration/test_boundary_*.py`), the only tests
that check what the host actually parses and loads, runs only in `release.yml:boundary-advisory`,
after the Release exists. Its two real-host failure classes so far (rendered hooks the host never
read, Maker failing in the default permission mode, HR-022) both shipped with green unit tests.
The suite takes 16 s locally (39 passed, 2026-11-22), so running it before merge costs almost
nothing.

The DRI often reviews and merges from a phone. The PR template opens with a comment block and a
checklist of local lint commands; the facts the DRI decides on (what behaviour changed, whether the
host check passed, whether a decision is needed, whether the merge ships a release) are not at the
top. Plan items Q1 and U3 of the 2026-11-22 improvement plan (DRI said to apply them).

## Outcomes

- O1. Every PR and every push to main runs the boundary suite in CI as a blocking job.
- O2. A PR body written from the template answers the DRI's merge questions in its first five lines.
- O3. CLAUDE.md describes the new gate instead of "advisory, recommended locally".

## In-Scope Scenarios

- S1 (normal). A PR changes a template; CI runs `boundary` with `INTEGRATION=1`; a parser
  regression fails the job and the PR shows red before merge.
- S2 (edge). CI has no signed-in `claude`; the live Maker test skips by its own guard and the rest
  of the suite still runs. The session that opens a PR touching templates or settings rendering
  runs the suite locally, where `claude` is signed in, and reports the result in the Host check line.
- S3 (failure). A boundary test fails on a PR; the job is red (no `continue-on-error`), so the
  failure is visible before the merge that would publish.

## Non-Goals

- Removing or changing `release.yml:boundary-advisory` (it still records results on the Release).
- Making the live Maker test run in CI (needs a signed-in CLI and a secret; not worth it now).
- Branch-protection settings (repository setting, DRI's call; the job is visible either way).
- Rewriting the rest of the PR template.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| CI action pins | reuse the SHAs already in ci.yml |
| checkout depth | `fetch-depth: 0` (same checkout as release.yml boundary-advisory) |
| CLAUDE.md budget | stay under the Production 40,000-character limit |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: ci.yml runs the boundary suite as a blocking job on PRs and pushes
`.github/workflows/ci.yml` has a job `boundary` whose steps check out with `fetch-depth: 0` and run
`uv run pytest tests/integration/test_boundary_*.py` with `INTEGRATION: "1"`; neither the job nor
that step sets `continue-on-error`. The workflow is triggered by `pull_request` and by `push` to main.

### AC-002: the PR template opens with a five-line DRI block
In `.github/PULL_REQUEST_TEMPLATE.md` the first `## ` heading is `## For the DRI`, it comes before
`## Summary`, and its body holds exactly five list items starting with, in order:
`Behaviour change:`, `Host check:`, `Your decision:`, `Ships a release on merge:`,
`Understanding delta:`.

### AC-003: CLAUDE.md describes the gate
CLAUDE.md no longer contains `advisory 로 실행 권장`, names the CI `boundary` job, and says the live
Maker test must be run locally before merging a PR that touches templates or settings rendering.

## Verification

| scenario | mode | test |
|---|---|---|
| S1, S3 | unit (workflow parse) | tests/unit/test_pr_boundary_gate.py::test_ac_001_ci_runs_boundary_blocking |
| S2 | unit (template / doc text) | test_ac_002_pr_template_dri_block, test_ac_003_claude_md_describes_gate |
| S1 | manual | the PR that ships this change shows the `boundary` job green |

## Open Questions

none

## Refinement Decisions

- Approval: the DRI asked on 2026-11-22 to apply the plan's items ("다른것들은 반영안해?"); this
  SPEC is exactly plan items Q1 + U3, so it is stamped approved without a further card (ask-less
  rule). Cost to undo: revert one PR.
- Blocking, not advisory: a parser regression is exactly what must stop a publish; the suite is
  deterministic apart from the live test, which skips in CI. Undo: add `continue-on-error`.
- Separate job, no `needs: quality-gate`: it runs in parallel and finishes in about a minute, so the
  DRI sees it early. Undo: one line.
- Template block in English (repository docs are English); five fixed labels so a reviewer and a
  later check can find them. Undo: edit the template.
- Intent: none (`[intent] none`; HM-LIGHT-LANE is about cost, not this).
- spec-validator skipped (3 ACs, default skip at <= 8).
