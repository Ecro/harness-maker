# BASELINE-DELTA — hm-autopilot-spec-advance

Re-frozen inside this task: `test_aggregate_shipped_surface_does_not_grow` refuses any growth, and
the spec command grew.

Direction: `aggregate_chars.claude` and `aggregate_chars.codex` each **rose** by 179 chars
(265284 → 265463; 283669 → 283848). Round trips did not move.

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.spec.chars` (`spec`) | 42332 → 42511 | Step 5's "autopilot stops at this stage" became a sentence true at every level: a missing approval does not end the stage, other levels stop at the gate, at `auto_full` the boundary's `proceed: true` advances without an approval, `/hm:wrapup` asks again before landing (SPEC-hm-autopilot-spec-advance) |
| `surface.codex.hm-spec.chars` (`hm-spec`) | 44379 → 44558 | The same sentence; the Codex skill renders the same Step 5 |
| `aggregate_chars.claude`, `.codex` (`aggregate_chars`) | 265284 → 265463, 283669 → 283848 | The two rows above |
| `payload_digest`, `render_sha` | mechanical | `render_sha` is the merge-base `d48bdc0` (= `origin/main`) |

Freeze path: `_surface_baseline.main()` refused because this checkout's local `main` ref is stale
(`d2c0ab0`, behind `origin/main`), the same cause as the known
`test_the_recorded_sha_is_base_reachable` environment failure. `d48bdc0` was checked to be
`origin/main` itself, and the file was written from the generator's own `build_baseline()` with
its serialization (`indent=2, sort_keys=True`), so the content is what the generator produces.

The values are after the light review, which tied the `auto_full` clause to the boundary's
`proceed: true` (+35 chars per variant over the first draft).

Ownership (ADR-010): re-frozen by the task that moved it, after its own tests were green
(`ratchet-rebaselined-by-its-own-subject`).

Other re-captures: `autopilot_gate_golden.json` (`spec` in all four arms), the synthesize
snapshots (`tests/snapshot/regenerate.py`) and `test_loop_opt_in._LOOP_ON_RECAPTURES`
(`commands/hm/spec.md`, `stages/spec.md`), each with a dated entry in its module.
