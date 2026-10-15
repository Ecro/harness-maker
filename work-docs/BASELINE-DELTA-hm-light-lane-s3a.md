# BASELINE-DELTA — hm-light-lane-s3a

Re-frozen inside this task: `test_aggregate_shipped_surface_does_not_grow` refuses any growth, and
the execute and spec commands grew.

Direction: the aggregate **rose** on both variants: `aggregate_chars.claude` by 858 chars
(265463 → 266321) and `aggregate_chars.codex` by 8601 chars (283848 → 292449). The Codex jump is
almost all execute. The Codex skill inlines the light check, because it has no `.claude/hm/`
reference file to point at. The Claude command carries a pointer, and the light check's body lives
in `.claude/hm/execute-light-check.md`, which this baseline does not measure.

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.execute.chars` (`execute`) | 44985 → 45421 | Step 4.2 "Light check": the entry condition (`lane` exactly `light`, every phase GREEN) and the pointer to `.claude/hm/execute-light-check.md` (SPEC-hm-light-lane-s3a AC-007). Round trips unchanged at 18: the light check's calls live in the reference file |
| `surface.codex.hm-execute.chars`, `.round_trips` (`hm-execute`) | 54887 → 63063, 20 → 26 | The same Step 4.2 with the light check inline: approval-status, verify's Check 2 (the verification_cache run and the degraded mark-pass), `security-scan --force` plus Check 4, Check 6 (op-check, waiver-check), review Step 2's drift rule, and the light-check record (AC-008/009/010) |
| `surface.claude.spec.chars`, `.round_trips` (`spec`) | 42511 → 42933, 9 → 10 | Step 5 stamps a `lane: light` SPEC with `irreversible_decisions: []` **exempt** with `approve --exempt` (AC-014, ADR-009) |
| `surface.codex.hm-spec.chars`, `.round_trips` (`hm-spec`) | 44558 → 44983, 10 → 11 | The same Step 5 exempt stamp in the Codex skill |
| `aggregate_chars.claude`, `.codex` (`aggregate_chars`) | 265463 → 266321, 283848 → 292449 | The four rows above |
| `payload_digest`, `render_sha` | mechanical | `render_sha` is the merge-base `e7dd6648` (= `origin/main`) |

The `test_roundtrip_budget._CLAUDE_ROUND_TRIPS` table counts each command together with the
`.claude/hm/` files it points at, so it moves differently from this baseline: execute 19 → 25
(the six light-check calls), spec 9 → 10, total 133 → 140.

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
