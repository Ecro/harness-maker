---
type: review
task_slug: harness-diet
status: APPROVED
created: 2026-08-05
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/templates/commands/hm/configure.md.j2
    - src/harness_maker/templates/cursor/rules/harness.mdc.j2
    - src/harness_maker/templates/memory/session-readme.md.j2
  scenario_misses: []
  task_slug: harness-diet
  computed_at: 2026-08-05T00:00:00Z
---

# REVIEW — harness-diet (Phase 1 only)

Scope under review: the **Phase 1** change on `hm/harness-diet` — removal of the
fused-workflow axis, the `/hm:loop` rewiring (ADR-014), and the test repair. Phases 2–6
of `PLAN-harness-diet.md` are not started and are out of scope here.

## 🎯 Round 1 Summary

**Grade: F** (3 consensus-passed P0/P1). Auto-fix ran; see Round 2.

Voter pool **N = 4** — `code-reviewer`, `security-reviewer`, `codex`, `antigravity`.
Threshold **K = 2**.

The core Python removal reviewed clean on both Claude passes. Every severe finding was in
the same place: **shipped prose that outlived its subject.** The change deleted the axis
from code and from Jinja *expressions*, but eleven files kept *describing* it — four stage
templates, three shipped skills, the Codex root instruction file, the Cursor always-on
rule, `/hm:configure`, and the plugin's own `commands/make.md`.

## 🔍 Drift Findings

Three files in the PLAN's Phase 1 scope were never touched and still referenced the
deleted axis: `configure.md.j2:17`, `cursor/rules/harness.mdc.j2:55`,
`memory/session-readme.md.j2:29`. All three are **shipped, rendered artifacts**.

Counter-check: `profile.py`, `rubric_loader.py`, `test_dep_map.py` were also in the PLAN's
scope list and were correctly left alone — they matched only on `.github/workflows`. The
PLAN's scope list was over-broad, not the execution.

## ✅ Consensus Findings

### P0

| # | Finding | Voices |
|---|---|---|
| C1 | `ruff format --check` fails on **7 files**; CI gates on it at `ci.yml:42`, `release.yml:50`, `nightly.yml:40`, before pytest runs. | code-reviewer + **oracle** (`ruff format --check` run directly) |

C1 was single-source by reviewer count, but it is a *mechanically decidable* fact, and the
oracle confirmed it — and found it broader than reported (7 files, not 1). Treated as
confirmed rather than `manual-only`: refusing to fix a reproduced CI break because only one
reviewer saw it would be a misuse of the consensus rule. Recorded here as the deviation it is.

Root cause, stated plainly: `/hm:execute` Phase D ran `ruff check` (lint) and never
`ruff format --check` (formatting). Different commands; only the first was run.

### P1

| # | Finding | Voices |
|---|---|---|
| C2 | `codex/AGENTS.md.j2:29-36` advertises four `@hm-exec-rev*` skills that no longer render. AGENTS.md is the Codex project-root instruction file, loaded every turn. | code-reviewer + security-reviewer |
| C3 | `loop.md.j2:52` — the `{% if is_codex %}` arm still parses `workflow: <name>`; only the Claude arm was rewritten. A Codex user has no way to reach `--per-iter-stages` at all. | code-reviewer + security-reviewer |

### P2

| # | Finding | Voices |
|---|---|---|
| C4 | `configure.md.j2:17` still lists `default_workflow` as a settable key. | code-reviewer + security-reviewer + codex + drift gate |
| C5 | `cursor/rules/harness.mdc.j2:55` (always-applied rule) still describes fused workflows. | code-reviewer + security-reviewer + drift gate |

## ⚠️ Weak Consensus

| # | Finding | Note |
|---|---|---|
| W1 | `review.md.j2:25` / `wrapup.md.j2:26` — "When invoked as part of a fused workflow … always run" is now permanently inert. | security-reviewer **P1**, code-reviewer **P2**. Surface matches; severity tiers differ, so per Step 4a they are not consensus candidates and are not bridged. Fixed anyway — the security reviewer's trace is the stronger one: a `/hm:loop` iteration with a single-file diff now meets the stage's own skip conditions with no override, which is the documented `loop-body-skipping-review-stage` incident (2026-05-22) that Gate 0 only catches *after* the fact. |

## 📝 Manual-Only Findings

| # | Sev | Finding | Source |
|---|---|---|---|
| M1 | P1 | `_RETIRED_TOP_LEVEL_KEYS` shipped with a test that asserts the **constant**, not the wiring; deleting the filter clause in `_preserve_yaml_user_keys` would leave it green. Its written rationale also describes a failure mode with no code path. | code-reviewer |
| M2 | P2 | `loop.md.j2:634` — the seven-stage allowlist the model is told to enforce is never enumerated for it; `<EXPECTED_STAGES>` also lands unquoted in a shell line. | security-reviewer |
| M3 | P2 | `.claude-verify.sh` — 4 sites reference `workflow_fuse`, including running a deleted test file. | code-reviewer |
| M4 | P2 | Dead `_parse_stage_numbers` + `_STAGES` + stale module docstring in `interview.py`. | code-reviewer |
| M5 | P2 | `test_command_size_budget.py` AC-006/AC-007 scaffolding: empty section banner, orphan comment, unused `stage_arg_values`, stale module docstring. | code-reviewer |
| M6 | P2 | Three shipped skills (`autoloop-driver`, `second-opinion-gate`, `targeted-test-selection`) justify themselves by naming fused commands. | own sweep, prompted by C2/C4 |
| M7 | P2 | `commands/make.md:105,288` — the plugin's own new-install entry point named `default_workflow` / `{workflow_names}`. Not a template, so no template sweep could see it. | code-reviewer |
| M8 | P2 | Interview prompt **sequence** changed (two prompts removed); any automation piping positional answers misaligns. | antigravity + confirmed during execute |
| M9 | P3 | `autoloop_driver.run()` lost its `workflow` kwarg. No Python caller passes it and it was unused (`ARG001`), so no in-repo break — CHANGELOG line only. | codex P1 + antigravity P2, **severity reduced by oracle** |
| M10 | P3 | `readiness.py:1306` — `c.stem not in meta_cmds` is unreachable (`atomic_stages ∩ meta_cmds = ∅`). | antigravity + code-reviewer |
| M11 | P2 | `readiness` workflow_clarity weights went 130 → 110. Both still cap at 100, so the dimension remains reachable, but the slack for one failing signal shrank from 30 to 10. | codex |

## 🤝 Disagreements

- **W1** — security-reviewer P1 vs code-reviewer P2 on the same line. Kept both, not bridged.
- **`render.py` retired-key handling** — antigravity called it **P0** ("will crash on
  application startup"); codex called the same code **P2** ("render-local, future callers
  still strict"). The oracle settles it toward codex: no production path validates a user's
  `harness.yaml` into `HarnessConfig`. Both Claude reviewers independently reached the same
  conclusion, one of them tracing all 26 `load_harness_yaml` call sites.

## 🧊 Cross-model findings (frozen @ round 1)

```yaml
second_opinion_results:
  - model: codex
    status: invoked
    findings: 4    # 1 P1, 3 P2 — all four accepted (one at reduced severity)
  - model: antigravity
    status: invoked
    findings: 8    # 1 P0, 3 P1, 3 P2, 1 P3 — 5 rejected
```

| id | model | claim | oracle | disposition |
|---|---|---|---|---|
| `1befad4f` | antigravity P0 | existing `harness.yaml` crashes on load | no production path validates it into `HarnessConfig`; `answers_from_harness_yaml` reads selected keys | **rejected** |
| `7c24a153` | codex P2 | retired-key filter is render-local only | same oracle; true as a *latent* statement | **accepted** → M1/M11 context |
| `b73e84d2` | antigravity P1 | `--per-iter-stages` path traversal, no allowlist | template `:634-639` has an explicit 7-stage allowlist + `wrapup` rejection + halt | **rejected** — its `evidence` quotes the prompt summary, not the file |
| `d99ba802` | antigravity P1 | `_build_answers` positional shift | `def _build_answers(*, …)` is keyword-only | **rejected** |
| `ac29377a` | antigravity P2 | stage templates still use `workflow_context` | zero occurrences | **rejected** |
| `6fba96db` | antigravity P2 | readiness can never reach a passing score | weights sum 110 ≥ cap 100 | **rejected** |
| `855f8197` | antigravity P1 | interview prompt sequence shifted | true — two test files were fixed for exactly this | **accepted** → M8 |
| `ff899f8a` | codex P1 | `autoloop_driver.run()` API break | no Python caller; param was unused | **accepted, severity reduced** → M9 |
| `f904352e` | antigravity P2 | same `autoloop_driver` claim | — | **duplicate** of `ff899f8a` |
| `9f1cc5af` | codex P2 | `configure.md.j2:17` names `default_workflow` | confirmed | **accepted** → C4 |
| `b837cf4f` | codex P2 | readiness scoring meaning changed | confirmed: 130 → 110, slack 30 → 10 | **accepted** → M11 |
| `e4ca1cd7` | antigravity P3 | `meta_cmds` condition redundant | sets are disjoint | **accepted** → M10 |

**Model quality note.** codex: 4/4 accepted. antigravity: 3/8 accepted, and its P0 plus one
P1 were constructed by paraphrasing the prompt's own summary rather than reading the code —
both asserted the absence of things that are present in the file. Recorded because the
ledger's accept-rate is what calibrates whether a voter earns its cost.

## Round 2 — Auto-Fix

### Iteration 2 (Grade: F → pending re-verification)

Fixes applied: **14**

| # | Sev | Summary | File | Status |
|---|-----|---------|------|--------|
| 1 | P0 | `ruff format` (7 files) | repo-wide | Applied |
| 2 | P1 | Delete `@hm-exec-rev*` skill table | `codex/AGENTS.md.j2` | Applied |
| 3 | P1 | Codex arm → `stages: <a,b,...>` | `loop.md.j2:52,106` | Applied |
| 4 | P1→W1 | Re-anchor always-run override on `/hm:loop` / autopilot | `review.md.j2:25`, `wrapup.md.j2:26` | Applied |
| 5 | P2 | Stage-terminal + recovery prose | `verify.md.j2:395,221`, `execute.md.j2:416` | Applied |
| 6 | P2 | Drop `default_workflow` | `configure.md.j2:17` | Applied |
| 7 | P2 | Drop fused sentence | `cursor/rules/harness.mdc.j2:55` | Applied |
| 8 | P2 | Drop fused mention | `memory/session-readme.md.j2:29` | Applied |
| 9 | P2 | Re-justify three shipped skills | `skills/{autoloop-driver,second-opinion-gate,targeted-test-selection}` | Applied |
| 10 | P2 | Plugin entry point | `commands/make.md:105,288` | Applied |
| 11 | P2 | Remove `workflow_fuse` sites | `.claude-verify.sh` ×4 | Applied |
| 12 | P2 | Delete dead helpers + docstring | `interview.py` | Applied |
| 13 | P1 | Replace constant-assertion with **behaviour** test; correct the false rationale | `test_no_fused_workflow_axis.py` | Applied |
| 14 | P1 | **Prose gate** — 2 new tests sweeping 119 templates + the plugin's own command surface | `test_no_fused_workflow_axis.py` | Applied |
| — | P1 | Re-point `test_codex_agents_md_mentions_workflow` at `@hm-loop` rather than deleting it | `test_codex_phase4.py` | Applied |

**Not fixed (deferred, recorded):** M2 (`<EXPECTED_STAGES>` quoting — the security reviewer's
own analysis concludes the value is self-directed, so it is a posture nit, not exposure),
M5 (test-file cosmetics), M9/M10/M11 (CHANGELOG line + two nits).

### The structural fix

Finding 14 is the one that matters beyond this round. The original gate checked Jinja
**expressions** (`workflow_context`, `config.default_workflow`) and therefore could not see
a template that merely *talked* about the deleted feature — which is precisely how eleven
shipped files survived. The new sweep is prose-level, covers the plugin's own
non-template command surface, and was checked for non-vacuity against the two real
violation strings.

## Round 3 — re-review of the fix delta, and the defects it found

`code-reviewer` was re-spawned on the fix delta only. `security-reviewer` was **not**
re-spawned: every round-2 fix in its scope was a prose deletion, and the one change to a
mechanism it flagged (`loop.md.j2:634`) *added* the allowlist enumeration it asked for.
`unreviewed_fix_count = 3` (the three security-scoped prose fixes) — recorded, not hidden.

### The question that mattered

`test_a_retired_key_is_not_re_injected_on_re_render` was traced end-to-end and is a **real
behaviour test**: `render.py:1326-1327 → 1398 → 1401-1418`. Remove the
`and k not in _RETIRED_TOP_LEVEL_KEYS` clause and both keys land in `user_only`, get
`yaml.safe_dump`-ed into the `@hm:user:extensions` appendix, and both assertions fail. It
also carries its own non-vacuity guards. Asking this explicitly mattered — round 1 of this
task had already shipped one vacuous assertion.

### Defects the round-2 fixes themselves introduced or left

| # | Sev | Finding | Fixed |
|---|-----|---------|-------|
| R1 | P2 | `help.ko.md.j2:37` kept a "legacy workflow" diagram branch that the **en** file had lost — the en/ko pair was half-updated. | ✅ |
| R2 | P2 | `render.py:1350`'s comment still carried the `extra="forbid"` rationale that the new test docstring had just refuted — a self-contradiction introduced in the same round. | ✅ |
| R3 | P2 | `loop.md.j2:617-648` still spoke Claude flag syntax (`--per-iter-stages`) to the Codex arm; the C3 fix reached line 52 only. | ✅ |
| R4 | P2 | Deleting the AGENTS.md table left three consecutive blank lines in a shipped artifact. | ✅ |
| R5 | P2 | **The round-2 prose gate was itself weak**: ban was English-only, allow was one exact English phrase. Hardened — ban now covers `융합 워크플로` / `fused-workflow`; allow is an explicit `<!-- @hm:axis-removed -->` marker that cannot be satisfied by accident; both sweeps gained non-vacuity guards. | ✅ |

R5 paid for itself on the first run: the Korean pattern immediately caught three lines
(`claude-md/{Production,Side}.ko`, `help.ko`) that the English-only ban had passed. The
non-vacuity guard caught a second error in the same edit — the sweep was pointed at
`skills/` and `agents/` paths that do not exist at the repo root.

### Deferred to Phase 6 (serial-close), not fixed here

| Sev | Finding |
|-----|---------|
| **P1** | `README.md:508-515` and `:140`, `README.ko.md:130,409` still advertise `/hm:exec-rev-wrap-ver` et al. as shipped commands. This is the primary user-facing doc of a published plugin — a **release blocker**. |
| P2 | `TECH_SPEC.md:124` and `CLAUDE.md:214` still describe the axis as live. |
| P2 | `scripts/measure_workflow_baseline.py` reads a file that can no longer be produced; reports `N/A` permanently. |
| P3 | Cosmetic stale wording: `loop.md.j2:4,9`, `codex/loop_skill.md.j2:3`, `review.md.j2:69`, `conditional-router` §, `context-linter` documents a `workflow` asset type no render can produce. |

`PLAN-harness-diet.md` Phase 6 already owns "README/docs references to fused workflows",
so this is scheduled work, not an unplanned gap. The prose gate deliberately does **not**
sweep README: a gate that fails on scheduled work teaches people to disable gates.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | F     | —             | 16        | —   |
| 2         | A     | 15            | 6 deferred | 5 (R1–R5) |
| 3         | A     | 5             | 8 deferred | 0 |

Final grade: **A**
Iterations used: 3 / 3
Exit reason: converged
Status: **APPROVED**
human_review_needed: **true**
Counters (see §5): unreviewed 3 · prior-fix 5 · unattributed 0

⚠️ **Grade A but 1 unverified severe finding present** (manual-only P1: the README
fused-command advertisement). The letter cleared because no `consensus-passed` P0/P1
remains, but that finding was single-source and never cross-verified. Per the grade gate's
interactive path: **STOP for human review before wrapup.**

### Verification at close

- `ruff check .` · `ruff format --check .` (535 files) · `mypy --strict src/` (127 files) — all pass.
- Full suite: `rc=0`, **0 failures**.
- Shipped surface: **641,452 chars** (from 1,173,667 — **−45.3%**), within the PLAN's
  per-target Phase 6 ceilings (claude 352,667 ≤ 375,000; codex 288,785 ≤ 300,000).

### Process note carried forward

The P0 (`ruff format --check` failing on 7 files, gated by CI in three workflows) existed
because `/hm:execute` Phase D ran `ruff check` and not `ruff format --check`. They are
different commands. Phase D's exit criterion should name both.
