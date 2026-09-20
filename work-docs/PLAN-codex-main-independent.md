---
type: plan
task_slug: codex-main-independent
status: complete
spec: "[[SPEC-codex-main-independent]]"
research_doc: "[[RESEARCH-codex-main-runtime]]"
validator_outcome: NOT_RUN
spec_need_verdict: add
spec_need_target: codex-main-independent
---
## Scope
Agent-authored execution notes for the authorized independent slice; no hm-plan stage.
## Implementation
Phase 1: pure bootstrap identity/state and strict Claude response parsing. depends_on: []; parallel_group: serial-foundations; merge_hazards: none. Scope: two new source modules and their tests only. Exit: targeted pytest, ruff and mypy. Risk: medium. Rollback: remove these unconnected files.
## 🚧 Contract Boundaries
### Do not change
- `src/harness_maker/models.py`
- `src/harness_maker/interview.py`
- `src/harness_maker/synthesize.py`
- `src/harness_maker/templates/`
- `src/harness_maker/second_opinion_invoke.py`
- `src/harness_maker/codex_ledger.py`
- Advisory: do not modify the other worktree or user plugin configuration.
## Validation
Tests first; independent test review; no product integration or landing claimed.

## Execution evidence
- Test review pass 1: FAIL, repaired engine-only mismatch coverage and UTF-8 byte discrimination. Pass 2: PASS.
- RED: two collection errors for absent intended modules. GREEN: 33 tests passed.
- Ruff and strict mypy passed for both new modules.
- No product integration, authenticated provider invocation, mutation run, commit or landing performed.
- Neighbor regressions included: 128 tests passed across new modules, existing second-opinion invoker and install-ref suites. Test typing corrected after extending mypy to all four changed Python files.

## Authorized verification repair
The DRI authorized repairing the inherited full-suite collection blocker on 2026-09-20. Scope additionally includes `tests/unit/test_land_hold.py`: align AC-008/009 table references and the directory input key with the existing accepted SPEC, align AC-010/011 names, and retain explicit subject-cap boundary and negative cases without requiring a nonexistent golden table. No product code or accepted SPEC is changed for this repair. Focused suite: 36 passed; independent test review: PASS.

## Final validation
Full CI gates passed: lint, format, strict typing, and 9065 tests passed, 100 skipped,
3 xfailed. Wrapup reused the fresh verification marker; all six mechanical ACs are
forward-bound, and both binding gates pass. Earlier execution counts above describe
the intermediate runs. This completes the independent implementation slice only;
SPEC approval, commit and landing remain separate, and broader integration is open.
