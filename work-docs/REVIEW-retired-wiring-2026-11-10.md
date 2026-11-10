---
type: review
task_slug: retired-wiring
created: 2026-11-10
spec: "[[SPEC-retired-wiring]]"
plan: "[[PLAN-retired-wiring]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: 4 minor findings and 1 nit. Three accepted and fixed, two doc parts rejected for this slice and moved to the docs rewrite, the nit rejected. 16 test files that pinned the removed wiring moved with the SPEC."
---

# REVIEW — retired-wiring

One code-reviewer round found no critical or major defect. It checked that the retirement path
covers both files: Claude `settings.json` and Codex `.codex/hooks.json` both merge through
`render._merge_hooks_json`, which strips every `_HARNESS_RETIRED_HOOK_INVOCATIONS` entry whatever
the `--with` path. The spec-validator was skipped (exempt SPEC, no irreversible decision). No
`Do not change` path was crossed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| 1 | minor | tests/unit/test_retired_wiring.py (AC-001) | The re-render test seeded only `.claude/settings.json`; a 0.65 user also has the old Stop group in `.codex/hooks.json`. Fix: `test_ac_001_rerender_retires_the_old_codex_stop_group` seeds the old group, a flush_session group and a user hook, and asserts no loop_gate, one flush_session and the user hook kept. Bound to AC-001 | accepted | SPEC S2 |
| 2 | minor | synthesize.py (`_codex_files` docstring), settings/Side.json.j2 header | Comments still said `make` installs the profiles and that the Stop stage ships. Fix: both now say the wiring is retired | accepted | SPEC O1, O2 |
| 2a | minor | docs/reference/multi-session-worktree.md:55 | It still says the Stop-hook `loop_gate` blocks | rejected | Out of this slice, moved to item 5. `tests/unit/test_claude_md_relocation.py` pins that section verbatim as text relocated from CLAUDE.md, and the section describes the retired `/hm:loop` as a whole. It goes with the docs rewrite (item 5), which can retire the section and its pin together |
| 2b | minor | docs/HOW-IT-WORKS.md (1630, 2163, 2412, 2415, 3029) and HOW-IT-WORKS.ko.md (1767, 1999, 2002, 2564) | They still describe the profile install and `.claude-progress.json` resume | rejected | Out of this slice, moved to item 5. Item 5 of the agreed order rewrites HOW-IT-WORKS; editing a doc that is about to be replaced is wasted work. Recorded for that rewrite |
| 3 | minor | tests/unit/test_retired_wiring.py (AC-004) | The progress-file scan read only `.claude` and `.agents` Markdown. Fix: it also reads `AGENTS.md` and `.codex/**/*.toml` | accepted | SPEC AC-004 |
| 4 | nit | tests/unit/test_retired_wiring.py (AC-001 Claude re-render) | `src` is the repo root, not `HEAD_SRC` | rejected | The normaliser ignores the `--with` path, which is the property the retirement relies on; the new Codex case uses a fake `/old/cache` path to show it |

## Tests moved with this SPEC

Each pinned the wiring that this SPEC removes. None guarded behaviour that is still live.

| file | change |
|---|---|
| tests/unit/test_overhaul_p1_surface.py | the Claude and Codex hook-row sets drop the `loop_gate` Stop row; the "hot tier" row now requires `.claude-progress.json` to be absent |
| tests/unit/test_overhaul_p1_kept.py | `test_ac009_compaction_checkpoint_resume` keeps the hot-tier sentence verbatim except for the dropped pointer, and asserts the pointer is gone |
| tests/unit/test_render_settings_hooks.py | `STAGE2_MODULES` is empty; the Stop test became `test_settings_stop_hook_carries_span_end_only`; the stop-mode merge test uses span-end as the still-shipped command |
| tests/unit/test_hook_host.py | loop_gate must not be among the settings hook modules |
| tests/unit/test_codex_phase5.py | `test_codex_hooks_json_stop_has_no_loop_gate`: no loop_gate, flush_session kept |
| tests/integration/test_stage_spans_e2e.py | the span-end Stop group no longer carries loop_gate |
| tests/unit/test_synthesize_codex_reasoning_effort.py | the rendered config no longer points at `~/.codex/config.toml` |
| tests/render/test_render_sessionid_wiring.py | the autopilot_caps and picker guards read the deleted partials and were removed; the task-preflight guard is re-pointed at the live `stages/_hm.md.j2`; the negative `worktree create` guard is unchanged |
| tests/structural/test_step_manifest_injection.py | the partial-content test was removed; the two "nothing includes it" guards stay |
| tests/structural/test_autopilot_advance_render_gate.py | the two picker tests read the deleted step_manifest partial and were removed; the autopilot_guard guard stays |
| tests/unit/test_autopilot_template_render.py | deleted: both tests rendered the deleted partials, and no other test was in the file |
| tests/structural/test_comprehension_render_gate.py | the standalone render of the deleted partial was removed; `test_minimal_renders_nothing_and_costs_zero_bytes` still covers the zero-byte opt-out on the real render |
| tests/structural/test_comprehension_zero_cost_golden.py | the pre-change arm (ran only while the partial was absent) was removed; the two "partial exists" skip gates are gone, so the golden and lever checks now always run against the inline depth branch in `stages/spec.md.j2` |
| tests/snapshot/*.expected.yaml | regenerated |

## Verification

- `uv run pytest -q -n auto --dist loadfile`: exit 0 before the review fixes; the affected files
  (`test_retired_wiring.py`, snapshots, command-size budget, overhaul surface) pass after them.
- ruff check, ruff format and mypy --strict are clean.
