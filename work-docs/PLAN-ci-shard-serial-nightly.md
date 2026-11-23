---
type: plan
task_slug: ci-shard-serial-nightly
status: complete
created: 2026-11-23
spec: "[[SPEC-ci-shard-serial-nightly]]"
summary: "Shard filter in tests/conftest.py, then ci.yml / release.yml shard matrices and a nightly with the serial run, 3.13 and an unchanged-SHA skip."
---

# PLAN — ci-shard-serial-nightly

- [x] Phase 1 — shard filter. scope: `tests/conftest.py` (`HM_TEST_SHARD` collection filter + env scrub). exit: `uv run pytest tests/unit/test_ci_shard_serial_nightly.py -k "ac_001 or ac_005 or ac_006"`. risk: an xdist worker collects a different set than the controller (collection mismatch error). rollback: revert the conftest hunk.
- [x] Phase 2 — workflows. scope: `.github/workflows/ci.yml`, `release.yml`, `nightly.yml`, CHANGELOG. exit: `uv run pytest tests/unit/test_ci_shard_serial_nightly.py tests/unit/test_verification_plan.py tests/unit/test_release_identity.py tests/unit/test_pr_boundary_gate.py tests/structural/test_autotag_workflow.py`. risk: a check name a ruleset requires disappears; the PR then shows the check as expected and missing. rollback: revert the workflow files.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/verification_plan.py
- src/harness_maker/check.py
- .github/workflows/autotag.yml

## ADRs

ADR-001: Shard by a stable hash of the test file's rootdir-relative path, in the root conftest, with no new dependency. **Decided by:** agent
ADR-002: Ruff, format and mypy run in every shard, not only shard 1, so the steps stay unconditional. **Decided by:** agent
ADR-003: A summary job with the display name `quality-gate` needs the matrix and fails unless it succeeded. **Decided by:** agent
ADR-004: Restructure as chosen on the 2026-11-23 card (shards on PR/push/release, serial run in nightly). **Decided by:** user (decision card, 2026-11-23 01:21Z)
