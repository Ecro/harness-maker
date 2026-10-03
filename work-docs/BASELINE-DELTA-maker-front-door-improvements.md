# BASELINE-DELTA — maker-front-door-improvements

Re-frozen inside this task (Phase 4, rendered surfaces), not left as an in-flight allowance.

Direction: both aggregates **grew** — claude +241 chars, codex +68 chars (`aggregate_chars`).
`round_trips` did not move for any command.

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.research.chars` (`research`) | 24479 → 24503 | stage description gained the entrance gate `Only when typed, or via <Name>, autopilot or /hm:loop.` with a shortened summary (SPEC-maker-front-door-improvements AC-003, PLAN ADR-008) |
| `surface.claude.spec.chars` (`spec`) | 49233 → 49261 | same description gate |
| `surface.claude.execute.chars` (`execute`) | 64027 → 64095 | same description gate, plus the memory-retrieval note rewritten to the lexical-first / newest-dated-block behaviour (IRR-006; the old "regardless of vocabulary" / "tail-biased" claims became false in Phase 3) |
| `surface.claude.review.chars` (`review`) | 88574 → 88622 | same description gate |
| `surface.claude.verify.chars` (`verify`) | 27427 → 27458 | same description gate |
| `surface.claude.wrapup.chars` (`wrapup`) | 56288 → 56324 | same description gate |
| `surface.claude.help.chars` (`help`) | 2146 → 2152 | intent-layer / project-knowledge rows say `typed only` and name the Maker invocation (AC-004) |
| `surface.codex.hm-research.chars` (`hm-research`) | 24424 → 24430 | Codex stage skill description: summary + gate with `$hm-loop`, "Invoke when" dropped (AC-003) |
| `surface.codex.hm-spec.chars` (`hm-spec`) | 48006 → 48016 | same |
| `surface.codex.hm-execute.chars` (`hm-execute`) | 65287 → 65305 | same, plus the execute memory-retrieval note (as above) |
| `surface.codex.hm-review.chars` (`hm-review`) | 88140 → 88152 | same |
| `surface.codex.hm-verify.chars` (`hm-verify`) | 27085 → 27094 | same |
| `surface.codex.hm-wrapup.chars` (`hm-wrapup`) | 56765 → 56780 | same |
| `surface.codex.hm-help.chars` (`hm-help`) | 2032 → 2030 | the same help rows on the Codex help skill (`$<handle>`); shorter than the old "(mention `$x`)" wording |
| `aggregate_chars.claude` | 358220 → 358461 | the rows above (+241) |
| `aggregate_chars.codex` | 311739 → 311807 | the rows above (+68) |
| `payload_digest`, `render_sha` | mechanical | re-frozen from this worktree with the new render (`render_sha` c70f300a) |

Golden re-capture (`autopilot_gate_golden.json`): `execute`, `help`, `research`, `review`, `spec`,
`verify`, `wrapup` moved, in all four arms; recorded in the golden's `rebases` and the test module
docstring.

Ownership (ADR-010): re-frozen by the phase that changed the surfaces, after the change was
tested, in the same task, with this row-per-key attribution (`ratchet-rebaselined-by-its-own-subject`
does not apply — the ratchet is not this task's subject).
