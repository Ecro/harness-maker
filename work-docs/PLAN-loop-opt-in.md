---
type: plan
task_slug: loop-opt-in
status: complete
created: 2026-09-27
tags: [harness-maker, plan, python, synthesize, conditional-render, migration]
spec: "[[SPEC-loop-opt-in]]"
research_doc: "[[RESEARCH-loop-opt-in]]"
interview_rounds: 0
adrs: 5
validator_outcome: NOT_RUN
summary: "LoopConfig + fresh-vs-existing resolution in cli; gate 4 loop files and 6 listing surfaces on loop.enabled"
intent: LOOP-OPT-IN
spec_need_verdict: add
spec_need_target: loop-opt-in
---

# PLAN — loop-opt-in

## 🎯 Executive Summary

Add a `loop.enabled` key that decides whether `/hm:loop` and `/hm:loop-p5-batch`
render, along with their Codex skill twins. When the loop is off, the listing
surfaces carry a one-line enable hint instead of advertising the loop. The value
is off only when no `harness.yaml` exists on disk. Every existing file keeps its
explicit bool, and falls back to `true` when the key is absent or the file is
unreadable. A present but malformed value fails the render. The irreversible
decisions (IRR-001/002) and the fresh-vs-existing rule belong to the DRI and come
from SPEC rounds 1–3. The reversible build choices are recorded below.

## 📚 Prior Work

- **Precedent for the fresh/existing split:** `instrumentation.stage_agent_ledger`.
  The model default is `False` (fresh); `_parse_instrumentation`
  (interview.py:1444) maps an absent block to `True`. The same shape is reused
  here, with two differences the SPEC requires. The CLI preserves the value on
  the `--reinterview` and malformed-fallback paths, which the precedent does not
  do. A malformed value fails loudly rather than being tolerated.
- **Precedent for a config-gated file:** `_schema_files(answers.second_opinion.enabled)` in synthesize.
- **Orphan sweep:** `reconcile._classify_orphan` / `sweep_orphans`. Unchanged; it is relied on for AC-007.
- **Memory:** [wiki:architecture] onboarding-disclosure-and-six-gates says one template
  edit trips six gates, so Phase 3 is sized for them. `[fail:design]
  fix-introduced-defect-passes-all-gates` (count:15) means D.5 runs on any repair.
  Global Learned Correction 2026-06-08 (absent-case) is covered by AC-005/010.
- **RESEARCH-loop-opt-in:** usage evidence (0 of 547 spans), the listing-surface
  inventory, and the fact that the metric moves only after release and re-render.

## 📐 Architecture Decision Records

- **ADR-001 — Model default `False`; the loader maps absent to `True`.** `LoopConfig.enabled: bool = False`
  (fresh). `_parse_loop(value)` in interview.py maps an absent value, or `{}`, to
  `True` and raises `LoopConfigError` on anything malformed. Alternative rejected:
  model default `True` with the fresh interview setting `False`. That inverts the
  instrumentation precedent, and it makes `HarnessConfig()` (the legacy
  no-answers path) disagree with a fresh install.
- **ADR-002 — The CLI is the single resolver of the existing-file value.**
  `cli._resolve_existing_loop(existing_yaml) -> bool | None` runs **before**
  answers are built. It returns `None` when no file exists, `True` when the file
  is unreadable or not a mapping, `_parse_loop(data.get("loop"))` otherwise, and
  it lets `LoopConfigError` escape as a non-zero exit before any write. After
  answers are resolved on any path, a non-`None` result overrides `answers.loop`.
  This closes the `--reinterview` and malformed-fallback hole (cli.py:356-366)
  without touching the other axes.
- **ADR-003 — A `None` config_dump means the full inventory.** `_loop_enabled(config_dump)` returns
  `True` when `config_dump is None` (the legacy no-answers skeletons `SIDE_FILES` /
  `PRODUCTION_FILES`, and direct test calls). The check runs before the
  `_strict_fallback_dump()` substitution.
- **ADR-004 — The listing-surface hint is a single line.** Loop-off variants use
  `{% if config.loop.enabled %}` branches in help en/ko, claude-md × 4, codex
  AGENTS.md and cursor harness.mdc. In the off branch the loop line or section is
  dropped, and exactly one line names `loop.enabled: true` and `/hm:make`. Any
  surviving chaining line keeps `<!-- @hm:axis-removed -->`, because it still
  says there is no fused workflow command.
- **ADR-005 — `schema_version` default goes 5 → 6** in both models (`HarnessConfig`,
  `InterviewAnswers`) and in the `_build_answers` default. The existing
  carry-through keeps a legacy file's own version on `--update`, and the migration
  never reads it (SPEC constraint).

## 🏗️ Technical Design

**Current state:**
- `_base_files()` (synthesize.py:689-690) always lists `loop.md` and `loop-p5-batch.md`.
- `_codex_target_files()` (synthesize.py:822-829) always renders `hm-loop` and `hm-loop-p5-batch`.
- There is no `loop` key anywhere.

**Data flow after the change:**

```
cli.make ─► _resolve_existing_loop(.claude/harness.yaml) ──(LoopConfigError → exit 1, nothing written)
        │
        ├─ reused = answers_from_harness_yaml()  (─► _parse_loop, same rules)
        └─ else interview()                      (─► LoopConfig() = False)
        ▼
   answers.loop overridden when the resolver returned non-None
        ▼
synthesize: HarnessConfig(loop=answers.loop) ─► config_dump["loop"]["enabled"]
        ├─ _base_files: drop the 2 command FileSpecs when off
        ├─ _codex_target_files: drop the 2 skill FileSpecs when off
        └─ templates: help / CLAUDE.md / AGENTS.md / harness.mdc branch on config.loop.enabled
harness-yaml/*.yaml.j2: renders `loop:\n  enabled: <bool>`
```

**Affected components:** `models.py`, `interview.py`, `cli.py`, `synthesize.py`,
templates (harness-yaml × 2, help × 2, claude-md × 4, codex/AGENTS.md,
cursor/rules/harness.mdc), plugin `commands/make.md` (the disclosure row), and
the test fixtures and baselines.

## 📝 Implementation Plan

### Phase 1 — Schema, loader and CLI resolution
- depends_on: none
- parallel_group: A
- merge_hazards: shared model file `models.py`, consumed by every later phase
- scope in: `src/harness_maker/models.py`, `src/harness_maker/interview.py`, `src/harness_maker/cli.py`, `src/harness_maker/synthesize.py` (only the `loop=` pass-through in `HarnessConfig(...)`), `tests/unit/test_loop_opt_in.py`
- scope out: templates, fixtures
- exit criterion: `uv run pytest tests/unit/test_loop_opt_in.py -k "ac005 or ac008 or ac010 or ac011"` green
- risk: medium (migration of user state)
- rollback: revert the four source files; no on-disk format has shipped
- status: DONE (Phases 1 and 2 were implemented together, because AC-005/008/010 assert the rendered harness.yaml that Phase 2's template writes)

### Phase 2 — Render gating and listing surfaces
- depends_on: Phase 1
- parallel_group: B
- merge_hazards: templates feed the snapshots and baselines that Phase 3 regenerates
- scope in: `src/harness_maker/synthesize.py`; templates `harness-yaml/{Side,Production}.yaml.j2`, `commands/hm/help.{en,ko}.md.j2`, `claude-md/{Side,Production}.{en,ko}.md.j2`, `codex/AGENTS.md.j2`, `cursor/rules/harness.mdc.j2`; `commands/make.md` (disclosure row); `tests/unit/test_loop_opt_in.py`
- scope out: `loop.md.j2`, `loop-p5-batch.md.j2`, skill/agent/hook templates, `reconcile.py`
- exit criterion: `uv run pytest tests/unit/test_loop_opt_in.py` green (all 11 ACs)
- risk: medium
- rollback: revert the templates and the synthesize filter
- status: DONE. All 24 `test_loop_opt_in.py` cases are green, and ruff, format and mypy --strict are clean.
- **Deviation 1 (found while implementing).** `make --update` hard-failed with
  `VERIFY ERROR: … content_hash mismatch` right after the orphan sweep KEPT a
  user-edited file. `verify()` exempted only the reconcile KEEP set. This is a
  pre-existing defect that any retired template with an edited copy would hit;
  AC-007 exposed it. Fix: `cli.make` now adds `sweep_report.kept` (the `.claude/`
  members, made `.claude`-relative) to `skip_hash_paths`. `reconcile.py` is untouched.
- **Deviation 2.** In the Codex render `/hm:make` becomes `$hm-make` (AGENTS.md). The
  AC-004 hint check accepts either spelling for the host's re-render command. Codex's
  re-render skill really is `hm-make`, so this is the correct spelling, not a
  loosened assertion.
- **D.5 — the window newly reachable through Deviation 1.**
  (1) Window: every orphan the sweep keeps under `.claude/`
  (ours-modified, theirs, missing-in-manifest), which is now skipped by the
  content_hash check. Before the fix these files hit the check and failed `make`.
  They are no longer in the blueprint, so there is no declared body to verify.
  (2) Test: `tests/unit/test_loop_opt_in.py::test_ac007_disable_sweeps_pristine_keeps_edited`
  enters the window with an ours-modified kept file and asserts exit 0, preserved
  bytes, and the kept row. It is in this change.
  (3) Absent case: an empty `sweep_report.kept` gives an empty set, and verify
  behaves exactly as before. Every other `make` test covers that.
  A kept file outside `.claude/` is filtered out; `verify()` never scans outside
  `.claude/` anyway.

### Phase 3 — Coupled gates and fixtures
- depends_on: Phase 2
- parallel_group: C
- merge_hazards: snapshot and baseline files are shared regeneration targets; regenerate serially
- scope in: `tests/snapshot/*.expected.yaml`, `tests/structural/surface_baseline.json` plus its attribution doc, `tests/fixtures/rendered_command_names.json`, any existing test that pins the loop inventory or schema_version 5
- scope out: raising the frozen surface baseline
- exit criterion: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest` green
- risk: medium (six-gate coupling)
- rollback: `git checkout` the fixtures
- status: DONE. Full suite 9335 passed, 7 failed, all 7 environmental. `test_install_ref` ×6
  fail only under the `$HOME` basetemp and pass (32/32) under the default tmp.
  `test_second_opinion_invoke::test_temp_files_are_removed_on_every_branch` is
  xdist-flaky: it passes in isolation under both tmp roots and the module is untouched.
  The `$HOME` basetemp was needed because a stray empty `/tmp/.git` (dated
  2026-09-26 11:00, before this session, left in place) breaks every
  tmp_path-under-/tmp test that probes for a git root.
  ruff, format and mypy --strict are clean.
- Snapshot regen (4 fixtures) matched the expected delta exactly: −2 loop paths
  (60→58 files); hash changes only for `../CLAUDE.md`, `commands/hm/help.md` and
  `harness.yaml`.
- 22 existing test files were updated by rule. Tests that guard loop templates or the
  full inventory render with the loop ON (the templates still ship). The fresh-inventory
  pin (`test_dogfood_sandbox`) now expects loop absent. schema_version pins went 5→6.
  `loop` is classified in `_DISCLOSED_AXES`.
- Deviation 3. `tests/e2e/test_reconcile_orphan_sweep.py` accepted `rc in (0, 1)`
  because a sweep-kept orphan used to fail verify. It now requires `rc == 0`, which
  makes it a regression guard for Deviation 1. Its overrides.jsonl check is now
  prefix-preserved, because a completed make appends configure-exit records by design.
- Boundary check: 47 changed paths, 0 crossings of `### Do not change`.
- Verified by hand: in a loop-OFF Codex render (en/ko/ja × both presets), no hm-*
  skill's next-step line references a skill that is not rendered. The only `$hm-loop`
  mention in `hm-help` is the enable hint. The other skill-body mentions are the
  runtime-conditional prose the SPEC puts out of scope.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/commands/hm/loop.md.j2` — SPEC non-goal (no loop body edits)
- `src/harness_maker/templates/commands/hm/loop-p5-batch.md.j2` — SPEC non-goal
- `src/harness_maker/reconcile.py` — AC-007 relies on the existing sweep contract unchanged
- `src/harness_maker/templates/skills/` — skill mentions of /hm:loop are an accepted residue
- `src/harness_maker/templates/agents/` — autoloop-coder stays
- `src/harness_maker/templates/settings/` — loop_gate and sessionid_envfile hooks stay
- `src/harness_maker/templates/stages/` — runtime-conditional loop prose stays
- `src/harness_maker/worktree.py`
- Advisory: never raise the frozen surface baseline to absorb growth

## 🧪 Testing Strategy

- **Unit:** `tests/unit/test_loop_opt_in.py` holds one test per AC (AC-001…011).
  Renders go through `synthesize()` with fixture profiles. CLI paths go through
  the typer `CliRunner` against a `tmp_path` project.
- **AC-003:** read the reference snapshot blobs with
  `git show 055cce85:tests/snapshot/<f>` via subprocess (timeout set,
  `shell=False`), and compare paths and body hashes with harness.yaml excluded.
- **AC-008:** a Hypothesis property over `enabled ∈ {True, False}` × preset.
- **Full suite:** once at the Phase 3 exit, in the background.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A test path that builds answers without the CLI gets `False` and drops the loop files, making unrelated tests fail | high | low | ADR-003 (None ⇒ full); set `loop.enabled: true` explicitly in fixtures where the inventory is asserted |
| The surface-ratchet aggregate drops, and the attribution doc must match exactly | high | medium | Regenerate the baseline via its tool and add an attribution row; never hand-edit the aggregate |
| `LoopConfigError` raised deep in the loader turns `--update` into a traceback instead of a message | medium | medium | Resolve in the CLI before answers; `typer.echo(err=True)` + `Exit(1)` naming `loop` |
| The claude-md edit breaks `test_no_fused_workflow_axis` | medium | low | Keep the `<!-- @hm:axis-removed -->` marker on the rewritten chaining line |

## ✅ Success Criteria

- [x] AC-001 … AC-011 tests green (`tests/unit/test_loop_opt_in.py`)
- [x] ruff, format, mypy --strict and the full pytest suite green (7 environmental/flaky, explained above)
- [x] No diff to the Contract Boundaries paths
- [x] Post-release follow-up recorded (flip this repo, measure `dead_rendered_bytes`)

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| `hm intent status` 2026-09-27T02:11Z: dead_rendered_bytes 21.7 > target 10 | metric dead_rendered_bytes / intent LOOP-OPT-IN | recorded + readback (`.claude/intent/metrics.yaml`) | Approve, activate, and run this task | user | explicit conversation consent 2026-09-27 | This task |
| SPEC-loop-opt-in approved 2026-09-27T02:53Z (IRR-001/002) | intent LOOP-OPT-IN | unchanged | Implement; the metric is observable only after release plus re-render (`extra="forbid"`) | agent | approved SPEC scope | After release: set `loop.enabled: false` here, `/hm:make`, `hm intent metric measure --all`, then decide close met/missed |
| This task started 2026-09-27 as a real task after the trial activation (PLAN-world-intent-closed-loop-trial) | intent WORLD-INTENT-CLOSED-LOOP / trial membership | pending (this session is not the named collector) | Leave enrollment to the collector | collector session | trial PLAN collector rule | The collector reconciles this task on its next entry/resume |
| REVIEW-loop-opt-in-2026-09-27 (run de811b436e83): APPROVED, grade A, confirm-1 clean. SPEC AC-004/009 amended and re-approved 2026-09-27T04:30Z (Codex hm-help) | intent LOOP-OPT-IN | unchanged | Proceed to verify → wrapup. The metric is still unobservable until release + re-render | agent | approved SPEC scope + DRI re-approval | /hm:verify loop-opt-in |
| /hm:verify 2026-09-27: 6/6 PASS. On the first run Check 2 FAILED on `mypy --strict src tests` (12 test-typing errors: dict passed for LoopConfig, unused ignores); these were fixed and re-run. pytest used TMPDIR=/var/tmp because of the stray /tmp/.git; 9343 passed | intent LOOP-OPT-IN | unchanged | Proceed to wrapup | agent | approved SPEC scope | /hm:wrapup loop-opt-in |
