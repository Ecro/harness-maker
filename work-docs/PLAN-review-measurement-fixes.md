---
type: plan
task_slug: review-measurement-fixes
status: complete
created: 2026-11-21
spec: "[[SPEC-review-measurement-fixes]]"
summary: Severity normalisation in review_effect, pre-existing disposition in hm check, three execute rules, retire two_pass_review.
---

# PLAN — review-measurement-fixes

- [x] Phase 1 — measurement and gate code. scope: `review_effect.py` severity map (AC-001), `check.py` `_DISPOSITIONS` + `pre-existing` (AC-006). exit: `uv run pytest tests/unit/test_ac_review_measurement_fixes.py -k "ac_001 or ac_006" -q`. risk: low — additive parse paths. rollback: revert the two files.
- [x] Phase 2 — templates. scope: `templates/stages/execute.md.j2` (AC-002..005), `templates/agents/code-reviewer_body.md.j2` (AC-007); regenerate deliberate snapshots/goldens that pin these bytes. exit: `uv run pytest tests/render tests/structural -q -x`. risk: medium — byte goldens and budget ratchets pin rendered text. rollback: revert templates and snapshots.
- [x] Phase 3 — retire two_pass_review. scope: delete `src/harness_maker/two_pass_review.py`, its `hm.py`/`command_registry.py` entries, tests that only test it, the skill mention; CHANGELOG line (AC-008). exit: `uv run pytest tests/unit -q -x && uv run mypy --strict src/`. risk: low — no rendered consumer. rollback: `git revert`.

## 🚧 Contract Boundaries

### Do not change
- src/harness_maker/step_sensitivity.py
- src/harness_maker/second_opinion_invoke.py
- src/harness_maker/codex_ledger.py
- tests/structural/test_step_sensitivity_registry.py

## ADRs

ADR-001: Pre-existing is a new disposition accepted by hm check without an authority (SPEC IRR-001). **Decided by:** user (spec round 1)
ADR-002: Remove two_pass_review entirely rather than deprecate (SPEC IRR-002). **Decided by:** user (spec round 1)
ADR-003: The hm check retry cap is a literal 3 in the template, not `max_review_rounds`. **Decided by:** agent
ADR-004: No rendered heading changes, so the step-sensitivity registry needs no edit. **Decided by:** agent
