---
type: review
task_slug: pipeline-env-fixes
created: 2026-11-10
spec: "[[SPEC-pipeline-env-fixes]]"
plan: "[[PLAN-pipeline-env-fixes]]"
rounds: 3
reviewers: [code-reviewer]
summary: "Three code-reviewer rounds: 9, 2 and 0 findings (1 major, 4 minor, 6 nit), all accepted and fixed. Three more rows record expectations the suite found pinned to behaviour this SPEC changes."
---

# REVIEW — pipeline-env-fixes

Three code-reviewer rounds (9, 2 and 0 findings); every finding was accepted and fixed, none is
unresolved. The cross-model second opinion is not configured for this harness. No `Do not change`
item was crossed: `second_opinion_oracle.py`, `hm.py`, `.claude/intent.yaml`,
`docs/evals/RESULTS.md`, `scripts/bench/tasks/` and `tests/fixtures/hm_cost_p4/` are untouched.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | major | src/harness_maker/check.py:1381 | `mutation_section` was the one `gate_env` caller without `root=root`, so a `mutmut` installed only in the project `.venv` was no longer found under `--no-project`. Fix: `gate_env(root=root)`; test `test_ac_010_mutation_gate_gets_the_project_path` | accepted | SPEC AC-010 |
| F2 | minor | src/harness_maker/check.py:649 | A failed `uv sync` (or uv missing) surfaced as a bare "no pytest runner" on the AC and RED paths, and as "has no pytest" when a stale `.venv` sat next to it. Fix: `no_runner_reason` reads `project_python` and returns its reason for a tracked lock; the AC-003 golden rows without a lock are unchanged; test `test_ac_004_failed_sync_is_the_reason_on_the_ac_path` | accepted | SPEC AC-003, AC-004 |
| F3 | minor | src/harness_maker/check.py:595 | `project_python` ran `uv sync` once per reader (two or three times per `hm check`, and on the reuse-decision path), so a failing sync was retried each time. Fix: one answer per project state (root, lock mtime, interpreter present, uv path) | accepted | PLAN ADR-002 |
| F4 | nit | src/harness_maker/check.py:615 | `_VALUE_OPTIONS` missed some value-taking uv options, so `uv run --no-install-package pytest pytest -q` was cut at the option value. Fix: `--upgrade-package`, `-P`, `--reinstall-package`, `--no-install-package`, `--refresh-package` added | accepted | PLAN ADR-003 |
| F5 | nit | src/harness_maker/check.py:198 | `gate_env` with an empty PATH produced a trailing empty entry, which means the current directory. Fix: only non-empty parts are joined | accepted | PLAN ADR-005 |
| F6 | nit | src/harness_maker/render.py:1087 | `_no_project_entry` rewrote only the first `uv run --with` of a command: a chained command kept its second harness call old, and a user's own leading `uv run --with` call was the one rewritten. Fix: every old prefix that starts a `python -m harness_maker.` call is rewritten and nothing else; test `test_ac_008_rewrites_only_harness_calls_in_a_chained_command` | accepted | SPEC AC-008, IRR-002 |
| F7 | minor | tests/unit/test_allow_literal_prune.py:279 | The near-miss list silently lost the case that is now pruned on purpose (the 0.65.3 spelling with a harness-maker path). Fix: the test asserts that prune explicitly and says where it stops | accepted | SPEC AC-008 |
| F8 | minor | tests/unit/test_hm_cost_p2_check.py:190 | `gates.reason` was ignored on both sides of the pre-change comparison, so any later regression in it would pass. Fix: it must be equal, or differ only in the last clause this SPEC reworded | accepted | SPEC-hm-cost-p2 AC-006 |
| F9 | nit | tests/unit/test_overhaul_p1_surface.py:303 | The size allowance was computed from the rendered file's own call count, so an added call raised its own budget. Fix: the count comes from the reference tree | accepted | PLAN ADR-009 |
| R2-1 | minor | src/harness_maker/render.py:1073 | The F6 regex allowed one token between the old prefix and `python -m harness_maker.`, so `uv run --with requests --with /p python -m harness_maker.x` kept the old prefix for good. Fix: further `--with <ref>` pairs are allowed; the chained-command test gained that case | accepted | SPEC AC-008 |
| R2-2 | nit | src/harness_maker/check.py:596 | The F3 memo key was taken before the sync, so the first sync that created `.venv` was followed by one more. Fix: the answer is also stored under the post-sync key | accepted | PLAN ADR-002 |
| G1 | — | tests/unit/test_bench_tier3.py:566 | Found by the suite, not a reviewer: `bench_hash` is pinned and the committed fixture lock moves it `569e17ef29ab` → `92672094f80e`. Both pins moved, with the reason in the test and in the SPEC's Refinement Decisions | accepted | PLAN ADR-008 |
| G2 | — | tests/unit/test_overhaul_p1_hm_check.py:569 | Found by the suite: the CVE exit-table rows track a stand-in lock uv cannot sync, so they degraded to exit 3. The rows hide `uv` (the stub interpreter is then used as it is); the uv path itself is covered by the AC-004 rows and the integration walk | accepted | SPEC AC-004 |
| G3 | — | tests/render/test_retired_text.py:228 | Found by the suite: a user-extended hook group was expected back byte for byte, but its harness command now gains `--no-project`. The expectation keeps everything else identical | accepted | SPEC AC-008 |

## Gate

`hm check --slug pipeline-env-fixes`: approval, ac, review, security and cve sections ok; `ruff
check`, `ruff format --check` and `mypy --strict src tests` exit 0. The pytest gate (`-x`) stops at
`tests/unit/test_land_hold.py::…[unreadable]`, which fails only as root in this container and
predates this change (NT-010). A full run without `-x` has that one failure and no other.
