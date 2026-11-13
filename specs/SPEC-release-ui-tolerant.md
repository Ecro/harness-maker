---
type: spec
task_slug: release-ui-tolerant
status: approved
created: 2026-11-13
tags: [harness-maker, spec, release, ci]
test_framework: pytest
interview_rounds: 0
summary: "Let release.yml's github-release job update a GitHub Release that already exists, so a release can be cut from the GitHub web UI (phone) without a local git client."
---

# SPEC — release-ui-tolerant

## Intent

The DRI has no local PC, and this cloud session cannot push tags (git proxy 403). The only way left
to create the `v0.65.4` tag is the GitHub web UI's "Publish release", which creates the tag and the
Release together. The `push: tags` run then reaches `github-release`, whose `gh release create`
fails with "a release with the same tag name already exists" (the 0.15.3 incident), and
`release-identity` never runs.

## Outcomes

- O1. A release created in the web UI is followed by a fully green release.yml run: PyPI publish,
  then the existing Release gets the `dist/*` assets and CHANGELOG-derived notes, then
  `release-identity` and `boundary-advisory` run as before.
- O2. The normal tag-push path (no Release yet) still creates the Release exactly as before.

## In-Scope Scenarios

- **S1 (normal).** Given a pushed `v*` tag and no Release, When `github-release` runs, Then it creates
  the Release with `dist/*` and CHANGELOG notes (unchanged).
- **S2 (edge).** Given a Release already created in the web UI for the tag, When `github-release`
  runs, Then it uploads `dist/*` with `--clobber` and replaces title and notes; the job succeeds.

## Non-Goals

- No `workflow_dispatch` publish path (it would run on a branch ref, and the `pypi` environment and
  every `refs/tags/v` guard assume a tag ref).
- No change to job order or to the Trusted Publisher setup.

## Constraints

| Constraint | Value | Source |
|---|---|---|
| Test framework | pytest (mandatory) | CLAUDE.md |
| Job graph | `github-release` needs `publish-pypi`; `release-identity` needs `github-release` | `test_release_identity.py` |

## Irreversible Decisions

None. A workflow step change, reverted by one commit.

## Acceptance Criteria

### AC-001: github-release updates an existing Release instead of failing
The `Create GitHub Release` step of `github-release` checks `gh release view "$TAG"`; when it
succeeds the step runs `gh release upload "$TAG" dist/* --clobber` and
`gh release edit "$TAG" --title "$TAG" --notes-file "$NOTES_FILE"`, otherwise it runs
`gh release create` as before.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1, S2 | unit | `tests/unit/test_release_ui_tolerant.py` (AC-001) |
| S2 | manual | the v0.65.4 run after the DRI publishes the Release in the web UI |

## Open Questions

None.

## Refinement Decisions

- Skip check: one workflow file, acceptance obvious, no API or format change, reversible in
  minutes; one mechanical AC. The release notes the DRI types in the UI are overwritten by the
  CHANGELOG section, so the CHANGELOG stays the single source of release notes.
- CLAUDE.md and docs/release-checklist.md gain the phone route; the "never run `gh release create`
  after a tag push" rule stays (a CLI race is still a race).
