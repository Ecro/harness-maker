---
type: plan
task_slug: hm-check-docs-only-reuse
status: complete
created: 2026-11-02
spec: "[[SPEC-hm-check-docs-only-reuse]]"
summary: check.reuse_inert config, a pure reuse decision module, an audit-hook read-set plugin and a gate-only verdict record
---

# PLAN — hm-check-docs-only-reuse

RESEARCH: `work-docs/RESEARCH-hm-check-docs-only-reuse.md`.

## Phases

1. **P1 config** — scope: `models.CheckConfig` + `HarnessConfig.check` + `InterviewAnswers.check` mirror, `interview.answers_from_harness_yaml` parse, `synthesize` pass-through, `templates/harness-yaml/{Side,Production}.yaml.j2` conditional emit (AC-006) · exit: `uv run pytest tests/unit/test_hm_check_inert_reuse.py -k ac_006` · risk: medium (schema, render byte-identity) · rollback: revert models/interview/synthesize/templates.
2. **P2 decision** — scope: new `src/harness_maker/check_reuse.py`: glob translator, never-inert rule, declaration parse, `decide()` (AC-002 rule table, AC-003) · exit: `uv run pytest tests/unit/test_hm_check_inert_reuse.py -k "ac_003"` · risk: low (pure) · rollback: delete the module.
3. **P3 run** — scope: `check.py` read-set plugin, gate injection and merge, record v2, `run()` split routed through `check_reuse.decide` (AC-001, AC-002, AC-004, AC-005) · exit: `uv run pytest tests/unit/test_hm_check_inert_reuse.py tests/unit/test_hm_cost_p3_reuse.py tests/unit/test_overhaul_p1_hm_check.py -n auto --dist loadfile` · risk: high (CLI contract, stale pass) · rollback: revert check.py.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/templates/stages/`
- `specs/SPEC-hm-cost-p3.md`
- `specs/SPEC-hm-cost-p3.machine.yaml`
- `tests/unit/test_hm_cost_p3_reuse.py`

## ADRs

ADR-001: The reuse decision is a pure function in a new module `check_reuse.py`, and `check.run` routes every reuse through it. AC-003's property therefore tests the function `run()` actually uses, and `check.py` (1351 lines) does not grow by the rule table. **Decided by:** agent

ADR-002: An identical hit (same key, same HEAD, empty delta, recorded exit-0 `line`) reprints the whole line as in 0.65.2. Every other hit reuses only `gates`. **Decided by:** user (execute 2026-11-02, AskUserQuestion)

ADR-003: On a gate-only hit, `mutation` and `harness` sections (when their options are set) are computed fresh. `--red` never reuses, because it runs no gate. **Decided by:** agent

ADR-004: The read-set plugin ships the same way as `_OUTCOME_PLUGIN`: a temp module on `PYTHONPATH` loaded with `-p`. Each pytest process writes `<dir>/<pid>.json` with its role. The controller records the xdist worker ids it saw go down (`pytest_testnodedown`, `optionalhook=True`). A worker id without a file, or a pytest gate with no file at all, gives `read_set: null`. The parent keeps only paths present in the snapshot, which drops `.venv` and ignored files. **Decided by:** agent

ADR-005: `harness.yaml` templates emit `check:` only when `reuse_inert` is non-empty. A default render stays byte-identical, and a ≤0.65.2 reader never sees the key unless a user declared it. **Decided by:** agent

ADR-006: A malformed `check` block in `answers_from_harness_yaml` raises, following the `loop`/`world_model` precedent. `/hm:make` never silently drops a declaration, and `hm check` (raw dict) treats the same value as `bad-declaration`. **Decided by:** agent

ADR-007: A v2 record that carries a non-zero `exit` field (written by hand, or by p3's test) reads as no record. **Decided by:** agent
