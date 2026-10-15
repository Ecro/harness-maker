# BASELINE-DELTA — hm-light-lane-s3d

Re-frozen inside this task, after its own tests were green (ADR-010,
`ratchet-rebaselined-by-its-own-subject`): `test_aggregate_shipped_surface_does_not_grow` refuses
any growth, and the Codex execute skill grew. Measured on this repo's own `harness.yaml` render
(`_surface_baseline.measure_surface()`).

Direction: `aggregate_chars.codex` **rose** by 134 chars (295314 → 295448). `aggregate_chars.claude`
did not move (240359): the Claude execute command carries only the pointer, and the light check's
body lives in `.claude/hm/execute-light-check.md`, which this baseline does not measure (that file
grew by the same two additions; `test_render_light_lane_s3c.py::test_surface_meets_bounds` applies
its a7403f2f size bound with exactly those bytes undone).

| Key | Before → After | Attribution |
|---|---|---|
| `surface.codex.hm-execute.chars` (`hm-execute`) | 64580 → 64714 | Step 4.2's Check 2 (verify_check_2.md.j2 under `light_check`): the `run` command gains `--spec-slug <slug>`, and its exit-3 bullet says neither readable CI nor a usable SPEC plan was found (SPEC-hm-light-lane-s3d AC-005); the light-check record's body line names the gate source after `"gate_source": "spec"` (`regression: pytest from SPEC (no CI file)`). Round trips unchanged at 27 |
| `aggregate_chars.codex` (`aggregate_chars`) | 295314 → 295448 | The row above |
| `payload_digest`, `render_sha` | mechanical | `render_sha` is the merge-base `df070f6c` (= `origin/main`) |

Verify, review, wrapup, the loop and the Claude execute command render byte-identical to
`df070f6c` (AC-006, `tests/render/test_render_light_lane_s3d.py::test_typed_stages_match_4bd3d3d8`),
so no other row moved.

Freeze path: `_surface_baseline.main()` refuses because this checkout's local `main` ref is stale
(`d2c0ab0`, behind `origin/main`), the same cause as the known
`test_the_recorded_sha_is_base_reachable` environment failure. `df070f6c` was checked to be on
`origin/main` (`git merge-base --is-ancestor`). The file was written with the generator's own
`build_baseline()` and serialization (`indent=2, sort_keys=True`) and `render_sha` set to that
merge-base, as for s3a and s3c.

Other re-captures:
- The synthesize snapshots, via `tests/snapshot/regenerate.py` (only `hm/execute-light-check.md`'s
  body hash moved, in all four profiles).
- No golden was re-captured for the older light-lane suites: s3a's kept-gates check, s3c's named
  deltas and surface bound, and phase3's frozen light-check Check 2 undo exactly 3d's bytes
  (`tests/unit/light_lane_s3d_fixture.py::without_s3d`) and compare with their existing goldens.
