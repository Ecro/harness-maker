# BASELINE-DELTA — world-intent-closed-loop

Before implementation, the committed baseline aggregate_chars is:

{
  "claude": 402060,
  "codex": 340488
}

Allowance: up to 30000 aggregate characters for Codex stage continuation and short feedback pointers; up to 5000 per stage. Existing boundary authority contracts stay unchanged. Final measured deltas must be recorded before any baseline re-freeze. No baseline is reset during implementation.

Golden re-capture moved commands (arm and command sets unchanged):
```json
{
  "auto_safe@warn": [
    "execute",
    "research",
    "review",
    "spec",
    "verify",
    "wrapup"
  ],
  "auto_safe@block": [
    "execute",
    "research",
    "review",
    "spec",
    "verify",
    "wrapup"
  ],
  "ask@flag_on": [
    "execute",
    "research",
    "review",
    "spec",
    "verify",
    "wrapup"
  ],
  "ask@flag_off": [
    "execute",
    "research",
    "review",
    "spec",
    "verify",
    "wrapup"
  ]
}
```

## Measured implementation delta

The frozen baseline remains unchanged. The active PLAN allowance funds these
changes; this is measurement, not re-freezing. Stage increases come from
feedback/trial hooks and Codex continuation; details remain in the lazy-loaded
intent-layer reference. Arm and command sets are unchanged.

| Key | Before | After | Delta |
|---|---:|---:|---:|
| aggregate_chars.claude | 402060 | 408696 | +6636 |
| surface.claude.execute.chars | 62732 | 64026 | +1294 |
| surface.claude.research.chars | 23649 | 24666 | +1017 |
| surface.claude.review.chars | 87419 | 88436 | +1017 |
| surface.claude.spec.chars | 48189 | 49206 | +1017 |
| surface.claude.verify.chars | 23881 | 24898 | +1017 |
| surface.claude.wrapup.chars | 52572 | 53846 | +1274 |
| aggregate_chars.codex | 340488 | 362641 | +22153 |
| surface.codex.hm-execute.chars | 61657 | 65286 | +3629 |
| surface.codex.hm-execute.round_trips | 24 | 26 | +2 |
| surface.codex.hm-research.chars | 21256 | 24611 | +3355 |
| surface.codex.hm-research.round_trips | 7 | 9 | +2 |
| surface.codex.hm-review.chars | 83822 | 87909 | +4087 |
| surface.codex.hm-review.round_trips | 29 | 30 | +1 |
| surface.codex.hm-spec.chars | 43871 | 47889 | +4018 |
| surface.codex.hm-spec.round_trips | 12 | 13 | +1 |
| surface.codex.hm-verify.chars | 21243 | 24587 | +3344 |
| surface.codex.hm-verify.round_trips | 9 | 11 | +2 |
| surface.codex.hm-wrapup.chars | 50827 | 54547 | +3720 |
| surface.codex.hm-wrapup.round_trips | 31 | 33 | +2 |

Delegate-OFF wrapup: Side 800 → 823; Production 802 → 825. The +23
lines are shared feedback/trial hooks and measurement-before-closure integration.
The existing 120-line intent SKILL budget is preserved by the reference file.

## Final attributed re-freeze

ADR-010 assigns the final integration phase ownership of this re-freeze to avoid
ratchet-rebaselined-by-its-own-subject: trigger and authority behavior have
independent tests and native evidence; the baseline does not prove correctness.
The aggregate grew (larger) from Claude 402060 / Codex 340488 to
Claude 408966 / Codex 363091. This is an authorized feature cost, not a saving.
The temporary PLAN allowance is removed; no cumulative headroom is retained.
`render_sha` identifies the generator checkout; `payload_digest` changes mechanically.

| Variant | Subject | Before chars | After chars | Before trips | After trips | Cause |
|---|---|---:|---:|---:|---:|---|
| `claude` | `execute` | 62732 | 64071 | 25 | 25 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `claude` | `research` | 23649 | 24711 | 8 | 8 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `claude` | `review` | 87419 | 88481 | 34 | 34 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `claude` | `spec` | 48189 | 49251 | 12 | 12 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `claude` | `verify` | 23881 | 24943 | 12 | 12 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `claude` | `wrapup` | 52572 | 53891 | 33 | 33 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `codex` | `hm-execute` | 61657 | 65331 | 24 | 26 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `codex` | `hm-research` | 21256 | 24656 | 7 | 9 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `codex` | `hm-review` | 83822 | 88044 | 29 | 30 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `codex` | `hm-spec` | 43871 | 48024 | 12 | 13 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `codex` | `hm-verify` | 21243 | 24632 | 9 | 11 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |
| `codex` | `hm-wrapup` | 50827 | 54592 | 31 | 33 | Feedback entry/close links, execute record map or wrapup ordering; Codex adds native boundary dispatch |

## Atomic fixture budget re-freeze

The distinct models-enabled flag-on fixture also loses temporary headroom at
completion. Most protocol detail is lazy-loaded (99 reference lines); inline
growth consists of entry/close links, record pointers and measurement ordering.
This final integration re-freeze retains the same ceiling/floor ratios and
separates earlier drift since the frozen table from this task's actual increase.

| Stage | Prior frozen | HEAD before task | Final | Task delta |
|---|---:|---:|---:|---:|
| execute | 60725 | 61481 | 62820 | +1339 |
| research | 27248 | 24708 | 25770 | +1062 |
| review | 80586 | 81821 | 82883 | +1062 |
| spec | 45248 | 45559 | 46621 | +1062 |
| verify | 24935 | 24325 | 25387 | +1062 |
| wrapup | 48388 | 49330 | 50649 | +1319 |

## Concurrent base integration (2026-09-22)

Integrated `358ba635` (Codex callable skill guidance) before final acceptance.
ADR-010 attribution remains explicit: this is not a correctness proof or a
ratchet-rebaselined-by-its-own-subject workaround. Compared with the preceding
feature render, aggregate size is smaller: Claude 408966 → 408964; Codex
363091 → 362730. `render_sha` and `payload_digest` identify this combined render.
Atomic fixture budgets are unchanged. Golden arms and command sets are unchanged;
help/spec include the peer task changes and six stages retain this task feedback.

| Variant | Subject | Before chars | After chars | Before trips | After trips |
|---|---|---:|---:|---:|---:|
| `claude` | `help` | 2043 | 2041 | 0 | 0 |
| `codex` | `hm-help` | 2317 | 1927 | 0 | 0 |
| `codex` | `hm-verify` | 24632 | 24661 | 11 | 11 |
