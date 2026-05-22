# ADR-0012: L2 stability is convergence-aware

- **Status**: accepted (2026-05-22)
- **Source PLAN**: `work-docs/PLAN-audit-convergence-2026-05`
- **Amends**: [ADR-0011](0011-personalization-rubric-locked-v0.md) — formula
  unchanged; input to the formula is now filtered.

## Context

The L2 stability layer (ADR-0011) was implemented as
`100 − min(100, N × penalty_factor)` where `N` is the count of
`harness_yaml_override` events captured in
`.claude/observability/adaptive/overrides.jsonl` within the last
30 days.

In practice this fires false positives whenever harness-maker itself
renames or restructures a config axis. Concrete dogfood example
(2026-05-22 `/hm:health` run on harness-maker repo):

- The `memory` axis template default migrated from
  `{enabled, failures, wiki, session_dir}` to `{enabled, dir, files}` in
  an earlier release.
- The user re-rendered, then hand-edited their `.claude/harness.yaml` on
  2026-05-19 to match the new shape (5 override events: `memory.dir`,
  `memory.files`, `memory.failures→None`, `memory.wiki→None`,
  `memory.session_dir→None`).
- Three days later, `/hm:health` flagged the `memory` axis as a P2
  `override_stability` action item and dropped L2 to 5/100, dragging the
  composite from gold to bronze territory — even though the user's edits
  were a **convergence onto** the new template default, not a divergence
  from it.

Every future schema rename in harness-maker would re-trigger this for
~30 days. The score and the action item both mis-fired.

## Decision

L2 stability counts only **divergent** overrides. An override is
divergent if its `after` value does not already match the current
preset's rendered template default at the same `axis_path`.

Three sub-decisions make this precise:

1. **Convergence baseline = preset YAML template.** The canonical default
   is the parsed result of rendering
   `templates/harness-yaml/<preset>.yaml.j2` with `InterviewAnswers()`
   defaults. Not `synthesize.py` preset constants (which encode coarse
   policy at a different granularity), not a hardcoded reference dict
   (which would rot independently of the template).
2. **`after=None` is a clearing event.** When an override sets a field to
   `null`, treat it as convergent regardless of the default's shape at
   that path:
   - If the default still defines a value at `axis_path` (or any subtree
     prefix), the next render overwrites the user's null — the override
     has no lasting effect.
   - If the default does not define `axis_path`, the override is a no-op.
   Either way, the user's intent is not "I want this axis different from
   the default"; it is "I want to clear this field." We do not use time-
   window correlation between clearing and re-add events — the rule is
   local to one event.
3. **Single divergent filter feeds both L2 score and frequent-axis
   actions.** `_action_for_frequent_axis` cannot earn a P1/P2 finding on
   an axis whose events the L2 score ignored — the layer score and the
   surfaced actions can never disagree.

The formula itself is unchanged: `100 − min(100, divergent_count × penalty_factor)`.
ADR-0011's `l2_stability` rubric block stays locked; only its input set
narrows.

## Consequences

- **Honest signal.** A score drop now means the user's `harness.yaml`
  actually diverges from what `/hm:make --update` would write, not just
  that the user did edit-work to converge onto a new default.
- **No-action-needed migrations stay clean.** Future schema renames in
  harness-maker do not pollute downstream projects' L2 scores during the
  rollout window.
- **API addition.** `compute_l2_stability` gains a list+defaults overload
  while keeping the `int` legacy path verbatim. Public callers do not
  break.
- **Audit cost.** `run_audit` now renders the preset's harness-yaml
  template once per run (via `synthesize.synthesize` + a focused
  Jinja2 render). Measured cost on the dogfood project: ~80 ms — well
  below the existing `load_or_run` profile-detection cost.

## Rejected alternatives

- **Time-window collapse** of clearing-then-re-add event pairs. Fragile
  (depends on event ordering and clock resolution) and hides user intent.
- **Strict equality only** — would leave the false-positive in place,
  which is the whole reason for this ADR.
- **Synthesize.py preset constants as baseline** — they are coarser than
  what the template renders, and would still false-positive on
  `memory.dir` since the constant is `{"per_repo": True}`.

## References

- PLAN: `work-docs/PLAN-audit-convergence-2026-05.md`
- Implementation: `src/harness_maker/personalization_audit.py`
  (`_load_preset_defaults`, `_walk_axis_path`, `_converged_on_default`).
- Tests: `tests/unit/test_personalization_audit_convergence.py`.
- Dogfood data: `.claude/observability/adaptive/overrides.jsonl` (the
  2026-05-17 / 2026-05-18 / 2026-05-19 `memory.*` events).
