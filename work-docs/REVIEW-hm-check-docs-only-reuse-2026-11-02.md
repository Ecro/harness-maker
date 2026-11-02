---
type: review
task_slug: hm-check-docs-only-reuse
created: 2026-11-02
spec: "[[SPEC-hm-check-docs-only-reuse]]"
plan: "[[PLAN-hm-check-docs-only-reuse]]"
rounds: 2
reviewers: [code-reviewer, codex (second opinion), code-verifier]
summary: 6 findings over 2 rounds; 5 accepted and fixed with regression tests, 1 rejected by SPEC authority; round 2 clean.
---

# REVIEW — hm-check-docs-only-reuse

Round 1: `code-reviewer` (4 findings) and one `codex` second-opinion call (3 findings). One finding
was raised by both (K=2 → accepted). The other five single-voter findings went to `code-verifier`:
4 accepted, 1 rejected. Round 2 (`code-reviewer` on the fixes) found none.

RED (Phase A): `hm check --red` exit 0. All 6 ACs failed for a real reason (`check_reuse` and
`CheckConfig` did not exist).

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1-F1 | major | src/harness_maker/cli.py:1644 | `make --update --preset X` rebuilt answers via `_build_answers` without `check`, so the DRI's `check.reuse_inert` reset on a preset switch (IRR-001, AC-006) | accepted | code-verifier; fixed + `test_ac_006_preset_switch_keeps_check` |
| R1-F2 | minor | src/harness_maker/check.py (run, record `line`) | a fresh `--reuse` miss stored its `reuse_miss` in `line`; a later identical reprint carried it next to `reused: true` (IRR-003) | accepted | code-verifier; fixed + `test_ac_005_identical_reprint_carries_no_reuse_miss` |
| R1-F3 | minor | src/harness_maker/check.py (`_READSET_PLUGIN._hook`) | `rel.startswith("..")` dropped in-repo names starting with `..` from the read-set (fail-open) | accepted | consensus (code-reviewer + codex); fixed + `test_ac_004_late_and_dotdot_reads_are_recorded[dotdot]` |
| R1-F4 | minor | src/harness_maker/check.py (`_READSET_PLUGIN._BUSY`) | a single global re-entrancy flag skipped other threads' `open` events | accepted | code-verifier; fixed (threading.local); no deterministic test |
| R1-C1 | major | src/harness_maker/check.py (`_READSET_PLUGIN` sessionfinish write) | reads after the plugin's `pytest_sessionfinish` (terminal summary, `pytest_unconfigure`, earlier-registered plugins) were missed but the set was treated as complete | accepted | code-verifier (narrowed from P1); fixed (outermost `pytest_unconfigure` wrapper rewrite) + `test_ac_004_late_and_dotdot_reads_are_recorded[unconfigure]` |
| R1-C3 | minor | src/harness_maker/check_reuse.py:115 | an identical hit with a malformed declaration reuses instead of reporting `bad-declaration` | rejected | SPEC Constraints "malformed declaration" (reads as no declaration) + "absent declaration" (identical reuse is today's rule); code-verifier |

## Notes

- Not filed: a non-blocking remark from round 2. `_hook` swallows path-decode exceptions. No
  realistic input reaches it, because `open` would fail first.
- Gate run 1 (before the fixes) stopped under `-x` at one failure:
  `test_test_dep_map_config_class` wanted the new suite classified. It is now in
  `TESTS_NOT_CONFIG_AFFECTING`.
- SPEC changes made during execute, with DRI approval (Refinement Decisions): an identical hit
  reprints the whole line (ADR-002); AC-001 row 4's declaration became
  `['work-docs/**', 'specs/**']`.
