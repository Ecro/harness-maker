# BASELINE-DELTA — world-model-name

Re-frozen inside this task (Phase 4 retire), not left as an in-flight allowance — an allowance
expires when wrapup marks the PLAN complete and would leave main red by this delta.

| Baseline | Before | After | Delta | Cause |
|---|---|---|---|---|
| `surface_baseline.json` aggregate `claude` | 357552 | 358153 | +601 | `/hm:configure`: §1 lists `world_model`, §2 "World model name" dimension, §4 forwards `--world-model-name` / `--world-model-handle` (SPEC-world-model-name AC-011) |
| `surface_baseline.json` aggregate `codex` | 311672 | 311672 | 0 | — |

Golden re-capture (`autopilot_gate_golden.json`): only `configure` moved, in all four arms;
arm and command sets unchanged. Recorded in the test module docstring.

Not measured by the surface baseline: the new router skill (`.claude/skills/<handle>/SKILL.md`,
`.agents/skills/<handle>/SKILL.md`) and the always-loaded `## World model` pointer
(≤ 200 chars per variant, asserted by `tests/render/test_render_world_model.py`).

Direction: the `claude` aggregate **grew** by 601 chars (`aggregate_chars`); `codex` unchanged.

| Key | Before → After | Attribution |
|---|---|---|
| `surface.claude.configure.chars` (`configure`) | 12072 → 12673 | the world-model dimension and its two dispatch flags (AC-011) |
| `aggregate_chars.claude` | 357552 → 358153 | the same +601, summed |
| `payload_digest`, `render_sha` | mechanical | re-frozen from this worktree with the new render |

Ownership (ADR-010): the baseline is re-frozen only by the phase that owns the retire step —
here Phase 4 of PLAN-world-model-name — never by whichever phase trips the ratchet
(`ratchet-rebaselined-by-its-own-subject`). The re-freeze happened after the change that
moved it was tested, in the same task, with this row-per-key attribution.
