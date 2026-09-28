---
type: baseline-delta
task_slug: intent-file-inputs
created: 2026-09-28
owns: [surface_baseline.json, autopilot_gate_golden.json]
summary: "Taking intent free text off the command line grew spec and wrapup by ~150 chars each"
---

# Baseline delta — intent-file-inputs

`SPEC-intent-file-inputs` moves every free-text argument of the rendered `hm intent` write calls
from an inline quoted value to a `-file` path the agent writes with the Write tool. The shipped
surface grew because spec Step 4.9 and wrapup Step 5.7 each gained one instruction sentence
naming the Write tool and the `mktemp` path, and the `-file` flags are longer than the quoted
placeholders they replace. The `(no ' inside)` cues from sdlc-three-loops-gap were removed. Review round 1 added 5 more chars to wrapup:
the `add` preview prose named `--text` and now says "the why text".

Why the change: three review runs of `sdlc-three-loops-gap` each found a new quote-breakout site
at the same seam; the accepted residual P1 `58ef46c950a7b459` named file inputs as the
structural fix. A value in a file cannot end a shell word.

| key | before | after | delta |
|---|---:|---:|---:|
| `aggregate_chars.claude` | 413 896 | 414 198 | +302 |
| `aggregate_chars.codex` | 367 668 | 367 970 | +302 |
| claude `spec` chars | 49 251 | 49 400 | +149 |
| claude `wrapup` chars | 55 565 | 55 718 | +153 |
| codex `hm-spec` chars | 48 024 | 48 173 | +149 |
| codex `hm-wrapup` chars | 56 266 | 56 419 | +153 |

The aggregate grew, the wrong way for a surface ratchet; that is the price of one instruction
per surface. No round trip moved: the file is written with the Write tool, which is not a
`!`-counted call, and each `hm intent` call is still one call. No other command moved.
`render_sha` and `payload_digest` move with any re-freeze.

**Ownership (ADR-010).** This is not ratchet-rebaselined-by-its-own-subject: the ratchet guards
unintended template growth, and this growth is the approved content of the SPEC (IRR-001). The
autopilot golden re-capture for `spec` and `wrapup` in all four arms is recorded in
`tests/structural/test_autopilot_gate_render.py`. Reverting the three template edits restores
every value in the "before" column.
