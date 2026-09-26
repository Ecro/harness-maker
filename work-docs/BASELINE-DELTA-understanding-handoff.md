# BASELINE-DELTA — understanding-handoff

SPEC-understanding-handoff (intent `UNDERSTANDING-HANDOFF`). Wrapup `Steps 6 → 7.6` gains the
paragraph and fenced example asking for the commit-body `Understanding:` block, and an
instruction to print that block immediately before the closing banner (review round 2 moved it
out of the `Done` line). Execute Step 0's ADR item requires a
`**Decided by:**` provenance line. No command, heading, shell call or dispatch was added, so
round trips are unchanged in every row.

## Final attributed re-freeze

ADR-010 assigns the final integration phase ownership of this re-freeze, to avoid
ratchet-rebaselined-by-its-own-subject: the classifier and the rendered prose have their own
tests (AC-001…AC-008); the baseline records cost, it does not prove correctness. No
`surface_allowance` was declared — an allowance expires when wrapup marks the PLAN complete and
would land main red by exactly this delta (PLAN ADR-005).

The aggregate grew (larger), an authorized feature cost rather than a saving: Claude
408964 → 410665 (+1701), Codex 362730 → 364431 (+1701). `render_sha` identifies the generator
checkout; `payload_digest` changes mechanically.

| Variant | Subject | Before chars | After chars | Before trips | After trips | Cause |
|---|---|---:|---:|---:|---:|---|
| `claude` | `execute` | 64071 | 64259 | 25 | 25 | ADR `**Decided by:**` provenance line |
| `claude` | `wrapup` | 53891 | 55404 | 33 | 33 | Step 6 `Understanding:` block paragraph + print-before-banner instruction (anchored source + warning branch) |
| `codex` | `hm-execute` | 65331 | 65519 | 26 | 26 | same as `execute` |
| `codex` | `hm-wrapup` | 54592 | 56105 | 33 | 33 | same as `wrapup` |

## Other size sites moved in the same change

| Site | Before | After | Note |
|---|---:|---:|---|
| `_ATOMIC_RATCHET["execute"]` | 62820 | 63008 | inside the 2 % band; re-based so the next task keeps its headroom |
| `_ATOMIC_RATCHET["wrapup"]` | 50649 | 52162 | re-based; the pre-review figure 51617 was 44 chars short of its ceiling |
| delegate-OFF wrapup lines (Side / Production) | 823 / 825 | 848 / 850 | +25 in both arms |
| `autopilot_gate_golden.json` | — | re-captured | only `execute` and `wrapup` moved, in all four arms; command sets unchanged |
