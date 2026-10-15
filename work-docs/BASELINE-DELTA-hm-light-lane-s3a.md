# BASELINE-DELTA — hm-light-lane-s3a

Re-frozen inside this task: `test_aggregate_shipped_surface_does_not_grow` refuses any growth, and
the execute and spec commands grew.

Direction: the aggregate **rose** on both variants: `aggregate_chars.claude` by 1310 chars
(265463 → 266773) and `aggregate_chars.codex` by 8380 chars (283848 → 292228). The Codex jump is
almost all execute. The Codex skill inlines the light check, because it has no `.claude/hm/`
reference file to point at. The Claude command carries a pointer, and the light check's body lives
in `.claude/hm/execute-light-check.md`, which this baseline does not measure.

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.execute.chars` (`execute`) | 44985 → 45572 | Step 4.2 "Light check": the entry condition (`lane` exactly `light`, every phase GREEN, loop mode off) and the pointer to `.claude/hm/execute-light-check.md`, whose absence skips the check (SPEC-hm-light-lane-s3a AC-007); the stage-end banner names wrapup after a passing light check. Round trips unchanged at 18: the light check's calls live in the reference file |
| `surface.codex.hm-execute.chars`, `.round_trips` (`hm-execute`) | 54887 → 62541, 20 → 26 | The same Step 4.2 with the light check inline: approval-status; verify's Check 2 under `light_check` (the verification_cache run, no guessed-gates mark-pass) and the `key` read for the record; `security-scan --force` with its failure clause, plus Check 4 on this scan's rows; Check 6 under `light_check` (op-check, waiver-check, no stop box or 6a/6b prose); review Step 2's drift rule; and the light-check record (AC-008/009/010/016); the skip list gates on approval-status's `trusted_lane`, and Check 4 gates on the scan's own `Severity:` line |
| `surface.claude.spec.chars`, `.round_trips` (`spec`) | 42511 → 43234, 9 → 10 | Step 5 stamps a `lane: light` SPEC with `irreversible_decisions: []` **exempt** with `approve --exempt`, only when Step 4 passed, the SPEC has no open questions and the DRI was not asked (AC-014, ADR-009) |
| `surface.codex.hm-spec.chars`, `.round_trips` (`hm-spec`) | 44558 → 45284, 10 → 11 | The same Step 5 exempt stamp in the Codex skill |
| `aggregate_chars.claude`, `.codex` (`aggregate_chars`) | 265463 → 266773, 283848 → 292228 | The four rows above |
| `payload_digest`, `render_sha` | mechanical | `render_sha` is the merge-base `e7dd6648` (= `origin/main`) |

Re-frozen a second time the same day, after the review of 3a (items A–P). The Codex execute
skill fell 1024 chars from the first freeze (63063 → 62039), because the `light_check` flag drops
verify's guessed-gates path, Check 6's stop box and its 6a/6b prose. Part of that is spent again
on the scan's failure clause, Check 4's own-rows rule, the `key` read and the `computed_at` rule.
Claude execute rose 151 (the stub's loop-mode condition, the missing-file skip, the banner) and
spec 301 on both variants (the exempt branch's three conditions).

Re-frozen a third time the same day, after the confirmation pass. The Codex execute skill rose
502 chars (62039 → 62541). Step 4.2 now gates on approval-status's `trusted_lane`, the boundary's
own predicate. The light check's Check 4 now gates on the scan's `Severity:` line (`high` or
`P0` above 0, or a missing or unparseable line, is not a pass) and keeps the findings file for
detail. The Claude command did not move: both changes sit in `.claude/hm/execute-light-check.md`.

The `test_roundtrip_budget._CLAUDE_ROUND_TRIPS` table counts each command together with the
`.claude/hm/` files it points at, so it moves differently from this baseline: execute 19 → 25
(the six light-check calls; the review swapped the degraded mark-pass for the `key` read, so the
count held), spec 9 → 10, total 133 → 140.

Freeze path: `_surface_baseline.main()` refused because this checkout's local `main` ref is stale
(`d2c0ab0`, behind `origin/main`). That is the same cause as the known
`test_the_recorded_sha_is_base_reachable` environment failure. `e7dd6648` was checked to be on
`origin/main` (`git merge-base --is-ancestor`, and it is `origin/main` itself). The file was written
with the generator's own `build_baseline()` and its serialization (`indent=2, sort_keys=True`),
with `render_sha` set to that merge-base, so the content is what the generator produces at a
base-reachable SHA.

Ownership (ADR-010): re-frozen by the task that moved it, after its own tests were green
(`ratchet-rebaselined-by-its-own-subject`).

Other re-captures:
- `autopilot_gate_golden.json`: `execute` and `spec` in all four arms.
- The synthesize snapshots, via `tests/snapshot/regenerate.py`.
- `test_loop_opt_in._LOOP_ON_RECAPTURES`.

Each has a dated entry in its module.
