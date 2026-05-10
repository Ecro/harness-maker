---
type: review
task_slug: codex-loop-execute-gaps
status: APPROVED
created: 2026-05-11
reviewers_invoked: [code-reviewer, code-reviewer, security-reviewer]
consensus_method: cross-check (2/3)
grade_threshold: A
final_grade: A
human_review_needed: false
---

# REVIEW — codex-loop-execute-gaps

## 🎯 Round 1 Summary

**Grade: B** (0 consensus-passed P0, 2 consensus-passed P1)

Two independent code-reviewer agents converged on the same root-cause finding: both
`_codex_stage_skills()` and `_codex_target_files()` in `synthesize.py` bake rendered
skill bodies using `HarnessConfig()` defaults rather than the real per-user config.
This means any harness with custom workflow names, work-docs dir, or spec dir will
receive stage skill bodies with wrong embedded values.

Status after Round 1: `CHANGES_REQUESTED`. Auto-fix loop entered.

---

## 🔍 Drift Findings

No scope drift detected. All changed files are within PLAN phases:
- `src/harness_maker/synthesize.py` (Phase 3–4 scope)
- `src/harness_maker/templates/skills/*/SKILL.md.j2` (Phase 5–6 scope)
- `src/harness_maker/templates/codex/` (Phase 3 scope)
- `src/harness_maker/workflow_fuse.py` (Phase 4 bug fix)
- `src/harness_maker/templates/stages/research.md.j2` (Phase 4 bug fix)
- `tests/unit/test_codex_phase7.py`, `tests/unit/test_codex_stage_procedures.py` (test updates)
- `tests/snapshot/` (regenerated)

No PLAN phases with zero changed files (all phases touched at least one file in scope).

---

## ✅ Consensus Findings (consensus-passed)

### [P1] `_codex_target_files()` bakes loop_body with HarnessConfig() defaults

| Field | Value |
|-------|-------|
| **File** | `src/harness_maker/synthesize.py` |
| **Line** | ~371 (`default_config = HarnessConfig().model_dump(mode="json")`) |
| **Tag** | `consensus-passed` [2/2 code-reviewers] |
| **Severity** | P1 |
| **Between** | code-reviewer-1, code-reviewer-2 |

**Evidence:**
```python
def _codex_target_files(fused_workflows):
    from harness_maker.models import HarnessConfig
    from harness_maker.render import _make_env
    env = _make_env()
    default_config = HarnessConfig().model_dump(mode="json")  # ← defaults only
    loop_body = env.get_template("commands/hm/loop.md.j2").render(
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        is_codex=True,
        config=default_config,  # ← user's workflow names not here
    )
```

**Failure mode:**
`loop.md.j2` renders `config.default_workflow` and iterates `config.workflows.keys()`
inside the `@hm-loop` skill body. If a user's `harness.yaml` defines custom workflow
names (e.g., `exec-rev`, `full`), the rendered loop skill body will still show the
factory defaults. The Codex agent would invoke wrong workflow names.

**OBSERVE → INFER → CONCLUDE:**
- OBSERVE: `_codex_target_files()` is called from `synthesize()` which has the real
  `config_dump` in scope, but the function constructs its own `HarnessConfig()`.
- INFER: The rendered `loop_body` is config-independent of the actual harness config
  being synthesized.
- CONCLUDE: Any harness with non-default workflow configuration gets incorrect Codex
  loop skill bodies — a silent functional regression for customized harnesses.

**Suggestion:**
Pass `config_dump: dict` as a parameter to `_codex_target_files()` and use it instead
of constructing `HarnessConfig()` locally. The caller `synthesize()` already has
`config_dump` in scope.

```python
def _codex_target_files(fused_workflows, *, config_dump: dict) -> list[FileSpec]:
    from harness_maker.render import _make_env
    env = _make_env()
    loop_body = env.get_template("commands/hm/loop.md.j2").render(
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        is_codex=True,
        config=config_dump,  # real user config
    )
    ...
```

---

### [P1] `_codex_stage_skills()` bakes stage bodies with HarnessConfig() defaults

| Field | Value |
|-------|-------|
| **File** | `src/harness_maker/synthesize.py` |
| **Line** | ~418 (`default_config = HarnessConfig().model_dump(mode="json")`) |
| **Tag** | `consensus-passed` [2/2 code-reviewers] |
| **Severity** | P1 |
| **Between** | code-reviewer-1, code-reviewer-2 |

**Evidence:**
```python
def _codex_stage_skills() -> list[FileSpec]:
    from harness_maker.models import HarnessConfig
    from harness_maker.render import _make_env
    env = _make_env()
    default_config = HarnessConfig().model_dump(mode="json")  # ← defaults only
    out: list[FileSpec] = []
    for s in _ATOMIC_STAGES:
        tpl = env.get_template(f"stages/{s}.md.j2")
        body = tpl.render(
            ...,
            config=default_config,  # ← wrong for customized harnesses
            ...
        )
```

**Failure mode:**
Stage templates reference `config.work_docs.dir`, `config.spec.dir`,
`config.worktree.scope`, etc. A user who customizes e.g. `work_docs.dir: "tasks"` will
see `work-docs` hardcoded in their Codex stage skills. The `@hm-execute` skill would
tell the Codex agent to look for `PLAN-{slug}.md` in the wrong directory.

**OBSERVE → INFER → CONCLUDE:**
- OBSERVE: `_codex_stage_skills()` is a module-level helper with no access to the
  live `config_dump`. `synthesize()` calls it without passing config.
- INFER: All 7 Codex stage skills are rendered with factory-default config values,
  regardless of what the user configured in `harness.yaml`.
- CONCLUDE: Same class of bug as the loop_body issue — silent config isolation failure
  for any customized harness.

**Suggestion:**
Same fix pattern: add `config_dump: dict` parameter and thread it from `synthesize()`.

```python
def _codex_stage_skills(*, config_dump: dict) -> list[FileSpec]:
    from harness_maker.render import _make_env
    env = _make_env()
    out: list[FileSpec] = []
    for s in _ATOMIC_STAGES:
        tpl = env.get_template(f"stages/{s}.md.j2")
        body = tpl.render(
            ...,
            config=config_dump,  # real user config
            ...
        )
        ...
```

---

## ⚠️ Weak Consensus

None. All surface-match candidates reached strong reasoning alignment (or no surface
match at all).

---

## 📝 Manual-Only Findings

### [P1-MO-1] No regression guards for plan/spec/research/wrapup/verify with is_codex=False

| Field | Value |
|-------|-------|
| **File** | `tests/unit/` |
| **Tag** | `manual-only` (code-reviewer-1 only) |
| **Severity** | P1 |

The 5 non-execute stages (plan, spec, research, wrapup, verify) have `{% if is_codex %}`
blocks added in this iteration, but no test asserts that `is_codex=False` rendering
(the Claude Code path) still emits the original content. A future template edit could
accidentally gate Claude Code content behind `{% if is_codex %}` with no regression guard.

**Suggestion:** Add parameterized tests rendering each stage with `is_codex=False` and
asserting the key phrases that Claude Code relies on (e.g., `$ARGUMENTS`, `AskUserQuestion`).

---

### [P1-MO-2] No per-stage test that Codex renders omit AskUserQuestion for 5 stages

| Field | Value |
|-------|-------|
| **File** | `tests/unit/test_codex_stage_procedures.py` |
| **Tag** | `manual-only` (code-reviewer-1 only) |
| **Severity** | P1 |

`test_codex_stage_procedures.py` tests that Codex stage renders contain required
keywords, but does NOT assert that `AskUserQuestion` is absent (or wrapped) in the
5 non-execute stages. If a template adds an `AskUserQuestion` call outside an
`{% if not is_codex %}` guard, Codex agents would attempt an unsupported tool call.

**Suggestion:** For each stage rendered with `is_codex=True`, assert
`"AskUserQuestion" not in rendered` (or if present, wrapped in `{% if not is_codex %}`).

---

### [P1-MO-3] stage_body two-level render lacks contract test

| Field | Value |
|-------|-------|
| **File** | `src/harness_maker/synthesize.py`, `src/harness_maker/templates/codex/stage_skill.md.j2` |
| **Tag** | `manual-only` (security-reviewer only) |
| **Severity** | P1 |

The `stage_body` value (rendered HTML/MD from a stage template with `is_codex=True`) is
embedded into `codex/stage_skill.md.j2` as a Jinja2 variable. If `stage_body` contains
`{{` or `{%` sequences (e.g. from a Jinja2 example in the stage body), the outer render
could fail or produce unexpected output. No test currently exercises this edge.

**Suggestion:** Either mark `stage_body` as `Markup()` in the outer render call
(prevents double-rendering), or add a test that exercises a stage body containing Jinja2
syntax fragments.

---

### [P2-MO-4] `$(pwd)` unquoted in execute.md.j2 Codex Bash() block

| Field | Value |
|-------|-------|
| **File** | `src/harness_maker/templates/stages/execute.md.j2` |
| **Line** | ~75 (Codex `Bash()` example block) |
| **Tag** | `manual-only` (security-reviewer only) |
| **Severity** | P2 |

The worktree create example emits:
```
uv run python -m harness_maker.worktree create execute "$(pwd)"
```
`$(pwd)` expands correctly but a path with spaces would still break (the outer double
quotes protect the subshell result but any spaces in the CWD expansion are word-split
by the receiving shell). Low practical risk in typical project paths; mention as P2.

---

### [P2-MO-5] Misleading comment at synthesize.py lines 534-535

| Field | Value |
|-------|-------|
| **File** | `src/harness_maker/synthesize.py` |
| **Line** | 534-535 |
| **Tag** | `manual-only` (code-reviewer-2 only) |
| **Severity** | P2 |

The comment reads:
```python
# is_codex gates Codex-specific template branches; ctx may override
# to True when rendering Codex skill bodies (see _codex_stage_skills).
```
Since `ctx.get("is_codex", False)` is evaluated here, and `_codex_stage_skills()` does
NOT inject `is_codex` into `ctx` (it renders locally and passes `stage_body` as context),
the "ctx may override to True" note is misleading — ctx never carries `is_codex=True`
in practice.

---

### [P2-MO-6] Stale lazy-import comments at synthesize.py lines 84, 365, 413

| Field | Value |
|-------|-------|
| **File** | `src/harness_maker/synthesize.py` |
| **Lines** | 84, 365, 413 |
| **Tag** | `manual-only` (code-reviewer-2 only) |
| **Severity** | P2 |

`# local import: avoid cycle` comments appear on multiple `from harness_maker.* import`
statements. The project conventions (CLAUDE.md) say to avoid comments unless WHY is
non-obvious. The cycle avoidance reason is non-obvious here, so these comments are
appropriate; however, the same comment style should be consistent across all three sites
(one currently says `# local import: avoid cycle`, another omits the comment entirely).
Trivial consistency issue.

---

### [P2-MO-7] is_codex bypass via ctx.get() (low practical risk)

| Field | Value |
|-------|-------|
| **File** | `src/harness_maker/synthesize.py` |
| **Line** | ~534 |
| **Tag** | `manual-only` (security-reviewer only) |
| **Severity** | P2 |

`"is_codex": ctx.get("is_codex", False)` means any caller that passes a FileSpec with
`{"is_codex": True}` in `ctx` would cause a non-Codex file to render with `is_codex=True`.
No current caller does this, but the design relies on convention rather than enforcement.
Low practical risk given controlled codebase. Acknowledge as accepted risk or add
assertion.

---

### [P2-MO-8] _HARNESS_MAKER_PKG_ROOT path disclosure (known/accepted)

| Field | Value |
|-------|-------|
| **File** | `src/harness_maker/synthesize.py` |
| **Tag** | `manual-only` (security-reviewer only) |
| **Severity** | P2 |

`_HARNESS_MAKER_PKG_ROOT` (developer's absolute path) is baked into rendered Codex
skill files. This is a known design decision — skill files need to call the Python
module via absolute path. Accepted as pre-existing architectural constraint (same
pattern applies to Claude Code target). No new risk introduced by this session.

---

## 🤝 Disagreements

No severity disagreements between reviewers on consensus-passed findings. Both P1
consensus findings had matching severity from both code-reviewers independently.

---

## Iteration 2 — Auto-fix (Grade: B → A)

**Fixes applied: 8**

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Thread `config_dump` to `_codex_target_files()` | `synthesize.py:362` | Applied |
| 2 | P1 | Thread `config_dump` to `_codex_stage_skills()` | `synthesize.py:412` | Applied |
| 3 | P1 | Move config construction before file_specs; pass to Codex helpers | `synthesize.py:synthesize()` | Applied |
| 4 | P1 | Add parametrized `AskUserQuestion` absent tests (all 7 stages) | `test_codex_stage_procedures.py` | Applied |
| 5 | P1 | Add `is_codex=False` non-empty regression guards (all 7 stages) | `test_codex_stage_procedures.py` | Applied |
| 6 | P1 | Add `stage_body` Jinja2 double-render safety test | `test_codex_stage_procedures.py` | Applied |
| 7 | P2 | Fix misleading `is_codex` comment; standardize lazy-import comments | `synthesize.py` | Applied |
| 8 | P2 | Quote `$(pwd)` in Codex Bash() block | `stages/execute.md.j2:75` | Applied |

**Build verification:** `uv run pytest` — 1402 passed (0 failed). `mypy --strict` — 69 files clean. `ruff check` — all passed.

**New issues introduced: 0**

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | **B** | —             | 2 consensus P1, 6 manual/P2 | — |
| 2 (fix)   | **A** | 8             | 0 | 0 |

**Final grade: A**
**Iterations used: 2 / 3**
**Status: APPROVED**
**human_review_needed: false**
