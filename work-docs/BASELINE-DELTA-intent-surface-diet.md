# BASELINE-DELTA — intent-surface-diet

Re-frozen inside this task (Phase 4 retire), not left as an in-flight allowance.

Direction: both aggregates **shrank** — `aggregate_chars.claude` by 8091 chars and
`aggregate_chars.codex` by 8153 chars (`aggregate_chars`).

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.research.chars` (`research`) | 24503 → 23748 | the `feedback-entry`/`feedback-close` partial blocks left every stage (SPEC-intent-surface-diet AC-001) |
| `surface.claude.verify.chars` (`verify`) | 27458 → 26703 | the same two partial blocks |
| `surface.claude.execute.chars` (`execute`) | 64095 → 63063 | the two partial blocks plus Step 0's PLAN Feedback-section instruction (AC-001) |
| `surface.claude.review.chars` (`review`) | 88622 → 87350 | the two partial blocks plus Step 3.3 compressed to ≤60% of its bytes (AC-005) |
| `surface.claude.spec.chars` (`spec`) | 49261 → 46032 | the two partial blocks; Step 0.5 lost the draft-consent question and the `rejected[]`/`revisits` check; Step 4.9 removed (AC-002) |
| `surface.claude.spec.round_trips` (`spec`) | 12 → 10 | Step 0.5's second `hm intent status` read and Step 4.9's `hm intent new --from-proposal` call went with them |
| `surface.claude.wrapup.chars` (`wrapup`) | 56324 → 55276 | the two partial blocks (wrapup's 5.7-cutoff close line) and Step 5.7 compressed around its guard phrases, with the evidence source and absent-table clause added (AC-003, AC-008); /hm:review round 2 restored the empty-list readback clause and added source-row marking (+181) |
| `surface.codex.hm-research.chars` (`hm-research`) | 24430 → 23675 | the same partial blocks on the Codex stage skill |
| `surface.codex.hm-verify.chars` (`hm-verify`) | 27094 → 26339 | the same partial blocks |
| `surface.codex.hm-execute.chars` (`hm-execute`) | 65305 → 64273 | partial blocks plus the PLAN Feedback-section instruction |
| `surface.codex.hm-review.chars` (`hm-review`) | 88152 → 86880 | partial blocks plus Step 3.3 compression |
| `surface.codex.hm-spec.chars` (`hm-spec`) | 48016 → 44773 | partial blocks, Step 0.5 trim and Step 4.9 removal |
| `surface.codex.hm-spec.round_trips` (`hm-spec`) | 13 → 11 | the same two calls as on Claude |
| `surface.codex.hm-wrapup.chars` (`hm-wrapup`) | 56780 → 55684 | partial blocks plus Step 5.7 compression; review round 2 additions (+125) |
| `aggregate_chars.claude` | 358461 → 350370 | the sum of the Claude rows above (−8091) |
| `aggregate_chars.codex` | 311807 → 303654 | the sum of the Codex rows above (−8153) |
| `payload_digest`, `render_sha` | mechanical | re-frozen from this worktree with the new render |

Golden re-capture (`autopilot_gate_golden.json`): `execute`, `research`, `review`, `spec`,
`verify` and `wrapup` moved, in all four arms; recorded in the test module docstring.
Snapshots (`tests/snapshot/*.expected.yaml`) regenerated from this worktree with `regenerate.py`.
`test_roundtrip_budget.py`: `spec` 12 → 10 (same two calls). `test_render_wrapup_delegation.py`:
default wrapup line count 829/831 → 817/819.
Step-sensitivity registry: the `spec` `Step 4.9` entry was removed with its heading. It was an
unsourced entry, so the registry's unsourced count went 33 → 32 (CLAUDE.md updated) and the
`unsourced_step_share` metric drops 45.2 → 44.4. That movement comes from deleting a step, not
from sourcing one.

Ownership (ADR-010): the baseline is re-frozen only by the phase that owns the retire step —
Phase 4 of PLAN-intent-surface-diet — never by whichever phase trips the ratchet
(`ratchet-rebaselined-by-its-own-subject`). The re-freeze happened after the change that moved it
was tested (Phase 3 green), in the same task, with this row-per-key attribution.
