---
type: plan
task_slug: review-effect-measurement
status: complete
created: 2026-10-17
spec: "[[SPEC-review-effect-measurement]]"
summary: One stdlib module review_effect (parse, ledger, escape, seed, score, report), a best-effort wrapup_land hook, a /hm:metrics step, a registry measure_cmd and a reference doc
---

# PLAN — review-effect-measurement

SPEC: `specs/SPEC-review-effect-measurement.md`. RESEARCH: `work-docs/RESEARCH-review-effect-measurement.md`.

## Phases

- **Phase 1 — `review_effect` core module.**
  - scope: new `src/harness_maker/review_effect.py`, containing `parse_review`, `clopper_pearson`, row
    builders, `record_review`, the `escape-candidates` / `escape` / `seed` / `score` / `report` verbs and
    `main`; register it in `command_registry.py` (ACs 001, 004–009).
  - exit: `uv run pytest tests/unit/test_review_effect.py tests/integration/test_review_effect_git.py`
  - risk: medium (git blame parsing, AST line selection)
  - rollback: delete the module and its registry line
- **Phase 2 — land hook.**
  - scope: `wrapup_land.run` calls `review_effect.record_review(worktree, base, slug)` after the commit
    exists and before the post-commit pop, inside `try/except Exception`, and stores the result in
    `receipt["steps"]["review_effect"]` (ACs 002, 003).
  - exit: `uv run pytest tests/integration/test_review_effect_land.py tests/unit/test_wrapup_land*.py`
  - risk: medium (land is a hot path, so the hook must never raise)
  - rollback: remove the call block
- **Phase 3 — surfaces.**
  - scope:
    - `/hm:metrics` gains one escape-attribution step (`templates/commands/hm/metrics.md.j2`);
    - the `step_sensitivity` execute Step 6 entry gets `measure_cmd` and `remeasure_on`;
    - new `docs/reference/review-effect.md`;
    - regenerate the snapshot digests, and update the surface baselines if `hm check` names them
      (ACs 010–012).
  - exit: `uv run pytest tests/unit/test_review_effect_surfaces.py tests/structural tests/snapshot`
  - risk: low to medium (snapshot and surface ratchets)
  - rollback: revert the template, registry and doc edits

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/stages/execute.md.j2`
- `src/harness_maker/templates/stages/wrapup.md.j2`
- `src/harness_maker/delivery_metrics.py`
- `src/harness_maker/codex_ledger.py`
- `src/harness_maker/economics.py`
- `src/harness_maker/ledger_exclusions.py`
- `.gitignore`

## ADRs

- **ADR-001: The ledger path resolves through `second_opinion_invoke.resolve_base_root(base)` and is written
  with `io_utils.append_atomic_line`.** This is the same resolver and helper `mutation_receipt` uses, so 10–20
  parallel sessions never lose a row and a nested repo never writes into an ancestor.
  **Decided by:** agent
- **ADR-002: The hook runs between the commit block and `_cli_post_commit_pop`.** Only there do both the
  first-run and the `already-present` resume path reach it with a commit that exists. Idempotency comes from
  the `(slug, commit)` key, read back from the ledger before appending. **Decided by:** agent (SPEC AC-002
  fixes the placement relative to the pop)
- **ADR-003: Clopper-Pearson by bisection on the exact binomial CDF**, using `math.comb` and summation in
  floats, 200 iterations, for n ≤ a few thousand. This is the stdlib-only constraint from the SPEC.
  **Decided by:** user (SPEC Constraints, folded from the spec-validator pass)
- **ADR-004: `escape-candidates` reuses `delivery_metrics._REMEDIATION_SUBJECT` by import.** Its git calls
  live in `review_effect`, through a local `_git` helper with a list argv and a 30 s timeout, so the frozen
  `delivery_metrics` stays untouched. **Decided by:** agent
- **ADR-005: The `report` verb takes `--root` and `--json`.** The registry `measure_cmd` is
  `harness-maker: hm review_effect report --root .`. **Decided by:** agent
- **ADR-006: re-freeze `surface_baseline.json` in this task, attributed in
  `work-docs/BASELINE-DELTA-review-effect-measurement.md`.** The +493-char `/hm:metrics` step is funded by
  the SPEC constraint "`/hm:metrics` gains at most one step". It was compacted under the 3 000 per-command
  budget first. A PLAN `surface_allowance` would expire at wrapup and leave main red
  (project-surface-allowance-expires-at-wrapup), so the fold happens here, from the worktree, after the last
  template edit. **Decided by:** agent (funded by the DRI-approved SPEC constraint)
