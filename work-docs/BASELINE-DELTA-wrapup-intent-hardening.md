# BASELINE-DELTA — wrapup-intent-hardening

Re-frozen inside this task (Phase 3 retire), not left as an in-flight allowance.

Direction: both aggregates **grew**, `aggregate_chars.claude` by 1018 chars and
`aggregate_chars.codex` by 1017 chars (`aggregate_chars`). All of the growth is in wrapup.

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.wrapup.chars` (`wrapup`) | 55276 → 56294 | Step 5.7 step 5 gained the whole-value argument check (patterns, malformed line, name-not-value, failed→declined on re-offer), and the marking sentence now marks source rows in their own table (SPEC-wrapup-intent-hardening AC-001…AC-003). The close block gained the intent-id check and the `--observed` enum line (AC-004). /hm:review round 2 (+75) added the leading-alphanumeric id and locator patterns, the `<item>` kind definition, the re-offer pointer, and restored the close sentence's predicate |
| `surface.codex.hm-wrapup.chars` (`hm-wrapup`) | 55684 → 56701 | The same edits on the Codex stage skill. One char less than Claude because the edit source reads "in the reply" instead of "through Other". It carries the same round-2 additions |
| `aggregate_chars.claude` | 350370 → 351388 | The Claude row above (+1018) |
| `aggregate_chars.codex` | 303654 → 304671 | The Codex row above (+1017) |
| `payload_digest`, `render_sha` | mechanical | Re-frozen from this worktree with the new render |

Golden re-capture (`autopilot_gate_golden.json`): only `wrapup` moved, in all four arms. This is
recorded in the test module docstring. The snapshots (`tests/snapshot/*.expected.yaml`) were
regenerated from this worktree with `regenerate.py`. No hm call was added, so `round_trips` is
unchanged.

Ownership (ADR-010): the baseline is re-frozen only by the phase that owns the retire step, which
is Phase 3 of PLAN-wrapup-intent-hardening, never whichever phase trips the ratchet
(`ratchet-rebaselined-by-its-own-subject`). The re-freeze ran after Phase 2 was green, in the same
task, with one attribution row per key.
