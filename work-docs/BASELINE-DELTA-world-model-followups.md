# BASELINE-DELTA — world-model-followups

Re-frozen inside this task (Phase 4 retire), not left as an in-flight allowance.

Direction: both aggregates **grew** by 67 chars (`aggregate_chars`).

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.help.chars` (`help`) | 2079 → 2146 | `/hm:help` settings table gained the world-model router row (SPEC-world-model-followups AC-015) |
| `surface.codex.hm-help.chars` (`hm-help`) | 1965 → 2032 | the same row on the Codex help skill (`$<handle>`) |
| `aggregate_chars.claude` | 358153 → 358220 | the `help` +67 |
| `aggregate_chars.codex` | 311672 → 311739 | the `hm-help` +67 |
| `payload_digest`, `render_sha` | mechanical | re-frozen from this worktree with the new render |

Golden re-capture (`autopilot_gate_golden.json`): only `help` moved, in all four arms; recorded
in the test module docstring.

Ownership (ADR-010): the baseline is re-frozen only by the phase that owns the retire step —
Phase 4 of PLAN-world-model-followups — never by whichever phase trips the ratchet
(`ratchet-rebaselined-by-its-own-subject`). The re-freeze happened after the change that moved it
was tested, in the same task, with this row-per-key attribution.
