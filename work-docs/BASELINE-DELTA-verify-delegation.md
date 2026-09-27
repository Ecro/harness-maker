---
type: baseline-delta
task_slug: verify-delegation
created: 2026-09-28
owns: [surface_baseline.json, autopilot_gate_golden.json]
summary: "Turning on verify delegation in this repo's harness.yaml grew the verify surface"
---

# Baseline delta — verify delegation opt-in

`3359096e` added `verify` to this repo's `harness.yaml` `delegation.stages`. The shipped-surface
baseline is rendered from that file, so the opt-in grew the aggregate. No template changed. The
change renders verify's existing Step 0.5 (`verify.md.j2`), which was dead code in this repo's
render while the list held only `wrapup`.

Why the change: `/hm:metrics` on 2026-09-27 measured `hm:verify` at 0.90 carry and 679k context
per turn. That is worse than the Phase 6 pre-registration baseline of 0.83 / 395k in
PLAN-economics-attribution-and-carry. Wrapup already runs delegated.

| key | before | after | delta |
|---|---:|---:|---:|
| `aggregate_chars.claude` | 410 826 | 413 896 | +3 070 |
| `aggregate_chars.codex` | 364 592 | 367 668 | +3 076 |
| claude `verify` chars | 24 943 | 28 013 | +3 070 |
| claude `verify` round trips | 12 | 14 | +2 |
| codex `hm-verify` chars | 24 661 | 27 737 | +3 076 |
| codex `hm-verify` round trips | 11 | 13 | +2 |

The aggregate grew, the wrong way for a surface ratchet. That is the expected cost of the
opt-in. The two added round trips are `hm wrapup_brief --stage verify` and `hm wrapup_receipt
--stage verify`. The inline checks stay as the degraded path, so nothing was removed. No other
command moved. `render_sha` and `payload_digest` move with any re-freeze.

**Ownership (ADR-010).** This is not ratchet-rebaselined-by-its-own-subject. The ratchet guards
template growth, and this growth comes from a config choice on a template that was not edited.
The autopilot golden re-capture for `verify` in `auto_safe@warn` and `auto_safe@block` is recorded in
`tests/structural/test_autopilot_gate_render.py`. Removing `verify` from `delegation.stages`
restores every value in the "before" column.
