# ADR-0011: Personalization rubric v0 (locked)

- **Status**: accepted (v0 locked; future amendments require a new ADR)
- **Date**: 2026-05-17 (extracted into `docs/adr/` from PLAN-personalization-depth-2026-05)
- **Source PLAN**: `work-docs/PLAN-personalization-depth-2026-05`

## Context

`/hm:personalization-audit` (now `/hm:health` Step 3) needs a stable
scoring rubric so that scores are comparable across runs and across
projects. An LLM-only judgement would be too noisy; a purely
deterministic rubric would miss the qualitative signal of "is the
harness actually shaped to this user's behaviour."

The v0 rubric is **locked** — implementations may not silently
change the layer weights, layer formulas, or composite tier
boundaries. Changes require a new ADR superseding this one.

## Decision

Personalization composite is a weighted sum of three layer scores
(each 0–100):

```
composite = 0.4 * L1_conversion + 0.3 * L2_stability + 0.3 * L3_cadence
```

| Layer | What it measures | Weight |
|-------|------------------|-------:|
| L1 conversion | Have user-recorded overrides (`harness_yaml_override` events in `.claude/observability/adaptive/overrides.jsonl`) actually been promoted into `harness.yaml`? Ratio of recorded → applied. | 0.4 |
| L2 stability  | How stable are user overrides across recent sessions? High churn = low score; sustained overrides = high score. | 0.3 |
| L3 cadence    | Is the user running `/hm:health` regularly enough that adaptive signals stay current? Counted against threshold (default 30 overrides since last audit, or N days since last run). | 0.3 |

Tier boundaries (locked):

| Composite | Tier |
|-----------|------|
| 80–100    | platinum |
| 60–79     | gold |
| 40–59     | silver |
| 0–39      | bronze |

Action items are emitted per layer with priority P0 (composite drop
of ≥ 20 points from prior run, or L1 conversion = 0) or P1 (any
single-layer score < 50).

## Consequences

- positive: stable scoring contract; users and CI can compare runs.
- positive: explicit priorities (P0 / P1) feed directly into the
  per-item structured-question loop (ADR-0001).
- negative: locking v0 means we accept its blind spots until v1.
  Known blind spots: rubric does not weight *quality* of overrides
  (a typo-fix override scores the same as a strategic re-targeting).

## References

- `src/harness_maker/personalization_audit.py`
- `.claude/observability/adaptive/overrides.jsonl`
- `src/harness_maker/telemetry.py` (`emit_override`, `compute_yaml_diff`)
