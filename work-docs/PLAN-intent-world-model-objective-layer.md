---
type: plan
task_slug: intent-world-model-objective-layer
status: complete
created: 2026-09-16
tags: [harness-maker, plan, python, jinja2, intent, objective, autopilot, review, skill]
spec: "[[SPEC-intent-world-model-objective-layer]]"
research_doc: "[[RESEARCH-cell-dev-future-and-intent-layer-fit]]"
interview_rounds: 3
adrs: 12
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "State-only intent layer: intent.py + world.py + objective_gate in autopilot_caps + three prompt edits + one skill; six phases, baseline first"
spec_need_verdict: add
spec_need_target: intent-world-model-objective-layer
surface_allowance:
  chars: 11300
  reason: "DECLARED at Phase 4 from the Phase 0 delta doc; re-measured after the edit. plan Step 0.5 (status load, one closed question, the rejected[] revisit loop), wrapup 5.7 (two answer-gated blocks), review Step 3.3 (objective drift, P2), help one skill row — each within the SPEC ceiling of 25/25/25/3 lines per variant. Round trips (exact, the live-render check is equality): plan +2 per variant (status, revisit), wrapup +2 (assume observe, objective close), review +1 (objective show), help 0."
  delta_doc: BASELINE-DELTA-intent-world-model-objective-layer.md
  commands:
    plan: 1800
    hm-plan: 1800
    wrapup: 1800
    hm-wrapup: 1800
    review: 1800
    hm-review: 1800
    help: 250
    hm-help: 250
  round_trips:
    plan: 2
    hm-plan: 2
    wrapup: 2
    hm-wrapup: 2
    review: 1
    hm-review: 1
---

# PLAN — Intent / Assumptions / Objective layer (state-only slice)

## 🎯 Executive Summary

**TL;DR.** Add three human-written state files under `.claude/` (`intent.yaml`,
`world/assumptions.yaml`, `world/objectives/<id>.yaml`, plus human-recorded
`world/outcomes.yaml`), one CLI module (`hm world {status|assume|outcome|objective}`), a fourth
autopilot gate (`objective_gate`, which only ever replaces an `advance`), three ≤25-line prompt
additions (`/hm:plan` Step 0 load + revisit loop, `/hm:wrapup` two answer-gated questions,
`/hm:review` one main-loop drift check), and one skill (`intent-layer`) so the operator never
has to remember a verb. Nothing is measured automatically; nothing is written without an
answer; approval validity and `needs_revalidation` are derived at read time and never stored.

**Why now.** The repo stores *how* (`harness.yaml`, `CLAUDE.md`) and *what happened*
(`memory/`, `observability/`) but not *why* or *what the human chose*; 58.5% of rendered bytes
shipped with zero invocations and nothing could say that contradicted any stated outcome.
[[RESEARCH-cell-dev-future-and-intent-layer-fit]] found that every lab and cell report converges
on a written intent layer, that nobody has closed the product-metric loop, and that 77% of this
repo's spend is outside any stage — so the layer is state, not machinery, and its surface is a
skill, not a command. SPEC revision 6 passed six cross-model reviews (28 → 5 findings, P1 0).

**Key decisions.**

| Decision | ADR |
|---|---|
| One CLI module: `hm world <verb>` | [ADR-001](#adr-001-one-cli-module-hm-world-verb) |
| Codex discoverability is mention-only (`@intent-layer`), no AGENTS.md block | [ADR-002](#adr-002-codex-skill-is-mention-only) |
| No Second Brain promotion in v1 | [ADR-003](#adr-003-no-second-brain-promotion-in-v1) |
| `scope_drift` is a main-loop review step, not an eighth lens | [ADR-004](#adr-004-scope_drift-is-a-main-loop-review-step) |
| `/hm:plan` writes the `objective:` frontmatter link from a closed question | [ADR-005](#adr-005-hmplan-writes-the-objective-link) |
| Two roots: versioned files in the current checkout, events at the base root | [ADR-006](#adr-006-two-root-resolver) |
| `objective_gate` sits after every existing check, before `advance_authorized` | [ADR-007](#adr-007-objective_gate-placement-and-event-shape) |
| Derived state is a pure function `derive(world, id)`; nothing stored | [ADR-008](#adr-008-derived-state-api) |
| Two-checkout fixture design (SPEC OQ3) | [ADR-009](#adr-009-two-checkout-fixture-design) |
| Surface: allowance for four commands after a BASELINE-DELTA doc; Codex arm on every new call site | [ADR-010](#adr-010-surface-allowance-and-codex-arm) |
| Dogfood `intent.yaml`: valid skeleton committed, measured outcomes draft presented for the user to paste | [ADR-011](#adr-011-dogfood-intentyaml-is-human-edited) |
| New state paths are deliverables via one constant that both `_DELIVERABLE_RE` and `wrapup_land` read; finalize stash-preserves them | [ADR-012](#adr-012-state-paths-are-deliverables-through-the-single-source) |

**Estimated impact.** Two new modules (~700 lines), one module edit in `autopilot_caps.py`
(~90 lines), one constant + regex alternation in `worktree.py`, one line in `wrapup_land.py`,
one allowlist entry in `hm.py`, one `make` hook in `cli.py`, three stage templates, one skill
template, one rubric, one help edit, three MATRIX rows, two `.gitignore` negations in this repo,
~19 test files. Rendered command growth ≤ 78 lines **per variant** (25 plan / 25 wrapup /
25 review / 3 help), measured separately for the claude and codex renders.

## 📚 Prior Work

- [[RESEARCH-intent-world-model-objective-layer]] — the proposal review (8 components → 3 new).
- [[RESEARCH-cell-dev-future-and-intent-layer-fit]] — outside evidence; "keep state, drop the
  machine"; 77% unattributed spend; skill over command.
- [[RESEARCH-harness-diet]] — cut behaviour scaffolding, keep state scaffolding. This layer is
  state by construction.
- `[wiki:architecture] codex-native-dispatch-vocabulary` — Codex has **no skill-running tool**;
  every new mandated call site needs `{% if is_codex %}Bash("…"){% else %}!…{% endif %}` or it
  renders as an inert `!` line. Drives ADR-002 and ADR-010.
- `[wiki:architecture] review-axis-seven-lenses-and-the-grade-fail-open` — "every defect lived in
  the seam between a tested library and the rendered prose that calls it"; regressions must
  drive the CLI over a temp path as the template prescribes. Drives the CLI-level predicates in
  AC-002/011/014 and the test strategy below.
- `wiki.md:29` — changing a rendered command moves **four** frozen numbers (`_ATOMIC_RATCHET`,
  `surface_baseline.json`, `_CLAUDE_ROUND_TRIPS`, wrapup line-count pin); the escape is
  `surface_allowance` created **after** a `BASELINE-DELTA-*.md`. Drives ADR-010 and P4 ordering.
- `.hm-autopilot` ADR-011 incident — an unregistered live file classifies as `user` and finalize
  stashes it. Drives the `_DELIVERABLE_RE` edit in P4 and AC-013.
- `codex_ledger` `Path.cwd()` row loss — drives ADR-006's split, not a single base-root rule.
- Global learned correction 2026-06-08 (absent-case = feature black hole) — drives the
  absent-vs-`link_invalid` contract in P3.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | CLI shape | Contract | `hm` dispatches `hm <module>`; how do the four verbs map? | A one module `hm world <verb>` / B `hm intent status` + `hm world …` / C four alias modules | **A** | SPEC prose `hm status` → `hm world status`; AC-014/019 wording corrected at wrapup | ADR-001 |
| 1 | Codex skill | Scope | Codex has no skill-running tool; how is the skill discoverable there? | A accept, `@intent-layer` in skill + help / B AGENTS.md block / C skip codex render | **A** | zero always-on bytes on codex | ADR-002 |
| 1 | Promotion | Architecture | Promote closed objectives to Second Brain `decision` notes? (SPEC OQ1) | A none in v1 / B on close / C on approve | **A** | one memory mechanism; revisit when `observed:` accumulates | ADR-003 |
| 1 | Dogfood | Scope | How does harness-maker's own `intent.yaml` get filled in this task? | A drafted from measurements, user edits before commit / B skeleton only / C user dictates now | **A** | commit gated on the user's edit | ADR-011 |
| 2 | Drift lens | Architecture | Where does the `scope_drift` judgment live in `/hm:review`? | A main-loop check step / B eighth lens / C fifth question in the merged core brief | **A** | lens axis, router, coverage, telemetry untouched | ADR-004 |
| 3 | P-03 stash | Contract | Finalize stash-preserves deliverables by design; AC-013's "absent from stash" clause is unreachable. | A rewrite AC-013 to "intact after stash pop" / B classify as harness artifact | **A** | dirt filters untouched; SPEC clause corrected in this stage | ADR-012 |
| 3 | P-04 voice | Architecture | A `source: main-loop` P1 has no voice → manual-only → `human_review_needed` = a gate. | A emit at P2 / B new Voice.kind + exemption / C keep P1, accept gate / D report-only | **A** | `review_consensus` untouched; SPEC severity corrected to P2 | ADR-004 |
| 3 | P-05 grade | Testing | New registry headings need MATRIX rows; `unsourced` would move the CLAUDE.md count. | A grade from a RESEARCH row / B allow the count line to move | **A** | class INV, source [[RESEARCH-cell-dev-future-and-intent-layer-fit]] | — |
| 3 | P-09 ignore | Scope | This repo's `.gitignore` ignores `.claude/*`; dogfood files uncommittable. | A add two negations / B do not commit dogfood | **A** | boundary reworded: nothing newly ignored, two re-includes | ADR-011 |

Validator critiques resolved by revision without a question (each had one defensible fix,
verified against source): P-01 allowance shape (ADR-010), P-02 staging via `wrapup_land`
(ADR-012), P-06 `display_ref` (ADR-007), P-07/P-10 SPEC string corrections done **now** (SPEC
rev 6.1), P-08 skeleton stays valid (ADR-011), P-11 `Step 0.5` (ADR-005), P-12 AC-001 split,
P-13 fixture test named, P-14 resolved slug + base root (ADR-007), P-15 re-render before
judgment (P5), P-16 P3 ∥ P4, P-17 real symbol names, P-18 per-variant budget.

Defaults taken without asking (trivial or single defensible answer): objective check placement
(ADR-007), derived-state API (ADR-008), two-checkout fixture (ADR-009, SPEC OQ3), surface
allowance ordering (ADR-010), `approved_by` from `git config user.name`, `autopilot_ledger`
reuse for events, `{% if is_codex %}` arm on every new call site, PLAN link written by
`/hm:plan` (ADR-005).

## 📐 Architecture Decision Records

### ADR-001: One CLI module, `hm world <verb>`
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** `hm` is an allowlisted `hm <module> …` dispatcher (`hm.py:_DISPATCHABLE`); the SPEC's
`hm status` would need a `status` module, and the four verbs share one data root.
**Decision:** one module `harness_maker.world` with subcommands `status`, `assume {observe,resolve}`,
`outcome record`, `objective {approve,activate,drop,reopen,close,revisit}`; `_DISPATCHABLE`
gains exactly `world`. `intent.py` is a pure loader/validator/skeleton with no CLI.
**Consequences:**
- ✅ One allowlist entry, one entrypoint whose import graph AC-014 walks.
- ⚠️ SPEC prose said `hm status` / `hm assume` / …; corrected to the `hm world` form **in this
  plan stage** (SPEC rev 6.1: AC-011 argv, AC-015 `cmd` tuple, AC-019 verb forms, Skill-contract
  and Rendered-surface rows, S13) so no P4 gate runs against stale strings (validator P-07).
**Rejected alternatives:**
- Four alias modules — allowlist +4, code outside the mutation set.
- `hm intent status` + `hm world …` — status reads world data; dependency would point backwards.
**Source:** Interview #1

### ADR-002: Codex skill is mention-only
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** Codex starts a skill only when a human mentions `@hm-<name>`; there is no model-side
selection (wiki, live-probed against Codex CLI 0.147.0).
**Decision:** render `.agents/skills/intent-layer/SKILL.md` as for every other skill; the skill's
own body and the `/hm:help` codex arm say "mention `@intent-layer`"; no AGENTS.md block.
**Consequences:**
- ✅ Zero always-on bytes on the codex target; AC-019's codex clause holds.
- ⚠️ On Codex the discoverability promise reduces to `/hm:help` + the mention form. SPEC already
  says selection is not promised.
**Rejected alternatives:**
- AGENTS.md verb block — always-on bytes on every Codex turn; widens the Non-Goals exception.
- No codex render — target asymmetry that the dual-render tests would have to special-case.
**Source:** Interview #2

### ADR-003: No Second Brain promotion in v1
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** SPEC OQ1 asked whether closed objectives become `decision` notes.
**Decision:** `world/objectives/<id>.yaml` is the single source; wrapup Step 5.6 is untouched.
**Consequences:**
- ✅ One memory mechanism; no link-back schema; Step 5.6's must-evaluate rule unchanged.
- ⚠️ Cross-project recall of objectives waits until `observed:` values exist to justify it.
**Rejected alternatives:**
- Promote on close — two representations of one record before any evidence of cross-project value.
- Promote on approve — decisions without outcomes in the vault.
**Source:** Interview #3

### ADR-004: `scope_drift` is a main-loop review step
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** The lens axis is fixed at seven and read by `conditional_router`, `lens_coverage`,
`review_telemetry` and the `step_sensitivity` registry; a Production lens is mandatory and can
block approval, which contradicts the SPEC's "finding, not gate".
**Decision:** `review.md.j2` gains **Step 3.3 — objective drift** (main loop), placed **before
Step 3.4** so the finding receives a `codex_adapter.finding_id` like every other: if the PLAN
frontmatter has `objective:`, load the record via `hm world objective show <id> --json`, judge
the PLAN's scope against `scope` / `non_scope` / `hypothesis`, and emit `scope_drift` findings
with `source: main-loop` at **severity P2** into the Step 4 filter. AC-017's subject is that
step's text in both rendered surfaces.
**Why P2 (interview #7, validator P-04).** `Voice.kind` is `lens | cross-model`
(`review_consensus.py:89`); a voice-less finding is tagged `manual-only`, and the rendered
review sets `unverified_severe` for any manual-only **P0/P1**, which sets `human_review_needed`
and stops the stage — a gate by construction. At P2 the finding is visible, tracked by id,
dispositioned in the ledger, and never stops anything. SPEC S10, the Scope-drift row and the
rubric's `finding_not_gate` item are corrected to P2 in rev 6.1.
**Consequences:**
- ✅ Four lens-axis modules and `review_consensus.py` untouched; no `KNOWN_LENSES` change.
- ⚠️ A drifted PLAN does not stop autopilot; it is reported and left to the operator — which is
  what "finding, not gate" meant.
- ⚠️ The new heading is registered in `step_sensitivity.py` (class INV, grade sourced from
  [[RESEARCH-cell-dev-future-and-intent-layer-fit]]) **and** its row is added to
  `work-docs/MATRIX-native-redundancy.md` (validator P-05); the CLAUDE.md `unsourced:` count does
  not move.
**Rejected alternatives:**
- Eighth lens — four modules, Production-mandatory, approval-blocking.
- Fifth question in the merged core brief — reviewer would need the objective file; `lens_coverage`
  could not see it; provenance blurred.
**Source:** Interview #5

### ADR-005: `/hm:plan` writes the objective link
**Status:** Accepted (2026-09-16, default — no viable alternative)
**Context:** SPEC S7 makes PLAN frontmatter `objective: <id>` the sole link source but does not
say who writes it. Without a writer the key never appears and the gate never fires.
**Decision:** `/hm:plan` gains **`### Step 0.5 — Objective context`** (a distinct ordinal —
`Step 0` already exists as the skip heuristic, validator P-11; ≤25 lines together with the
revisit loop). It runs `hm world status --json`; when the intent is `not_filled_in` or no
objective is `active`/`proposed` it prints one line and continues. Otherwise it loads
`intent.yaml` + `assumptions.yaml`, asks one closed question — "Which objective does this task
serve?" with the objective titles plus "none" — then runs the `For each matching objective:`
revisit loop against `rejected[]`. It runs in **every** standalone path including Case A (the
question is closed, not an interview round). Under **loop-mode** it is skipped: the per-iter PLAN
inherits `objective:` from the master PLAN's frontmatter. Step 5 writes the chosen id or omits
the key.
**Consequences:**
- ✅ Absent key = the operator chose none; the gate stays a no-op for such tasks.
- ⚠️ One more closed question in every standalone `/hm:plan` on a project with objectives; none
  on a project without, none in loop-mode.
**Rejected alternatives:**
- `task-preflight --objective` — SPEC forbids a second source.
**Source:** default (Step 1 draft)

### ADR-006: Two-root resolver
**Status:** Accepted (2026-09-16, via SPEC R11 + plan default)
**Context:** `resolve_base_root()` returns the **main** checkout from a linked worktree; PLAN and
world files live on the task branch; a single base-root rule made the gate read the wrong PLAN.
**Decision:** `world.py` exposes `checkout_root(cwd) -> Path` = `git rev-parse --show-toplevel`
(argv list, `shell=False`, timeout 10 s, `FileNotFoundError`/non-zero → `cwd` with a stderr
warning, never `Path.cwd()` silently) for every versioned read/write; events go through
`autopilot_ledger.append_event(base_root, …)` with `base_root` from the existing resolver.
**Consequences:**
- ✅ A task worktree's PLAN and world files are what the gate sees; events never land in a
  gitignored worktree path.
- ⚠️ World edits made in a worktree reach main only at `task-land` — deliverable lifecycle, by design.
**Rejected alternatives:**
- Single base root — the rev-5 P1.
**Source:** SPEC Refinement R11

### ADR-007: `objective_gate` placement and event shape
**Status:** Accepted (2026-09-16, default)
**Context:** `_cmd_boundary` checks, in order: kill switch → unknown stage → bad slug → caps →
judgment gate → pipeline complete → merge gate → `advance_authorized`.
**Decision:** insert the objective check **after** the merge-gate branch and **before**
`advance_authorized`. It keys on the **resolved** slug (`out["task_slug"]` after
`_resolve_task_slug`, which falls back to the marker-persisted slug — the shipped call site
`stage_end_summary.md.j2:79` passes no `--slug`, validator P-14) and reads
`work-docs/PLAN-<slug>.md` under `world.checkout_root(Path.cwd())`; absent key or absent file →
no-op; otherwise resolve and, on failure, set `proceed: false`, `halt_kind: "objective_gate"`,
`reason ∈ {link_invalid, missing, not_active, approval_invalid}`, message containing
`display_ref`, and append event `gate_blocked` with fields `{stage, display_ref, raw_link,
parse_error, reason}` (the field is named **`display_ref`** exactly, validator P-06) at the
**base root** — resolved inside `autopilot_caps` by the same light-weight strip rule
`worktree_gate` uses (`_strip_worktree`), guarded by `tests/structural/test_gate_base_root_parity.py`,
because `args.root` is `.` = the worktree on the real surface. `HaltKind` gains the one
literal. `_HUMAN_GATED_STAGES` / `_JUDGMENT_GATED_STAGES` unchanged.
**Consequences:**
- ✅ Only an `advance` can become `objective_gate`; every existing halt keeps precedence (AC-012).
- ✅ AC-012 gains a case: `--slug` absent, slug persisted in the marker → gate still evaluates.
- ⚠️ `raw_link` must be JSON-safe: non-JSON YAML scalars are encoded `{"yaml_type", "repr"}`.
- ⚠️ The SPEC Gate-precedence row's `objective_id (or the raw link value)` wording is superseded by
  `display_ref`; corrected in rev 6.1.
**Rejected alternatives:**
- Before the caps — would let an objective halt mask a cap halt and change baseline rows.
**Source:** default (SPEC gate-precedence row)

### ADR-008: Derived-state API
**Status:** Accepted (2026-09-16, default)
**Context:** SPEC R8 — `approval_valid` and `needs_revalidation` are never stored.
**Decision:** `world.derive(world: World, objective_id: str) -> Derived` returns a frozen dataclass
`(approval_valid: bool | None, needs_revalidation: bool)`; `None` for terminal objectives. It
recomputes the approval hash from the canonical payload and reads assumption statuses. `status`,
the boundary check and `revisit` all call it; no writer ever touches these values.
**Consequences:**
- ✅ Every mutation touches one file; terminal immutability and the flag rule cannot conflict.
- ⚠️ Every read recomputes SHA-256 over a small payload — negligible.
**Rejected alternatives:**
- Stored flags — rev-4 findings #3/#4/#5/#11.
**Source:** SPEC Refinement R8

### ADR-009: Two-checkout fixture design
**Status:** Accepted (2026-09-16, default — SPEC OQ3)
**Context:** Codex rev-6 #4: a PLAN-only current-checkout read with objectives from base would pass
AC-012's minimal fixture.
**Decision:** the `TWO_CHECKOUTS` fixture creates a real git repo with a linked worktree; the same
objective id is approved-valid on main and approval-invalid in the worktree (target edited
there); the test asserts `approval_invalid` from the worktree, baseline from main, and that the
`gate_blocked` event file exists only under the base root.
**Consequences:**
- ✅ Distinguishes "PLAN from current checkout" from "everything from current checkout".
- ⚠️ One integration-tier test that shells out to git (existing pattern in `tests/integration/`).
**Rejected alternatives:**
- Mocking the resolver — would not catch a resolver that reads the wrong root.
**Source:** default (codex rev-6 #4)

### ADR-010: Surface allowance and Codex arm
**Status:** Accepted (2026-09-16, default)
**Context:** Four frozen numbers move on any command edit; the allowance must follow a
`BASELINE-DELTA-*.md`; Codex renders unbranched `!` lines as inert prose.
**Decision:** P0 writes `work-docs/BASELINE-DELTA-intent-world-model-objective-layer.md` with the
**current** chars and `!`/`Bash(` call counts per command **per variant** (`plan`, `hm-plan`,
`wrapup`, `hm-wrapup`, `review`, `hm-review`, `help`, `hm-help`). P4's first task adds to this
PLAN's frontmatter the block `surface_allowance._parse` actually accepts (validator P-01, working
example `work-docs/PLAN-bench-study-adoption.md:11-19`):

```yaml
surface_allowance:
  chars: <total allowed increase, both variants>
  reason: "intent layer: plan Step 0.5, wrapup answer-gated blocks, review Step 3.3, help line"
  delta_doc: BASELINE-DELTA-intent-world-model-objective-layer.md
  commands: {plan: N, hm-plan: N, wrapup: N, hm-wrapup: N, review: N, hm-review: N, help: N, hm-help: N}
  round_trips: {plan: N, hm-plan: N, wrapup: N, hm-wrapup: N, review: N, hm-review: N, help: N, hm-help: N}
```

Values are **allowed increments**, not baselines. Then templates are edited. Every new mandated
call site uses `{% if is_codex %}Bash("…"){% else %}!…{% endif %}`. The skill body is not a
command and is outside the ratchet; its index line is the Non-Goals exception.
**Consequences:**
- ✅ Four gates pass in one sequence instead of red-by-red.
- ⚠️ `test_render_wrapup_delegation.py`'s line-count pin must be updated with the measured delta.
- ⚠️ AC-011's render predicate is corrected in rev 6.1 to accept the shipped forms (`!uv run …`,
  `Bash("uv run …`) — a bare `uv run` line is inert on both targets (validator P-10).
**Rejected alternatives:**
- Regenerating `surface_baseline.json` — destroys the ratchet.
**Source:** default (`wiki.md:29`)

### ADR-011: Dogfood `intent.yaml` is human-edited
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** SPEC R3 commits harness-maker's own `intent.yaml` as a living example; the ETH result
says generated context hurts.
**Decision:** the file on disk stays the **valid empty skeleton** that P1's `make` writes (a
drafted file with empty `mission` and filled `outcomes` is a validation error naming `mission`,
SPEC S1 — validator P-08). P5 presents the measured draft **separately**, as a YAML block in the
P5 section of this PLAN and in the stage summary: three outcomes (share of rendered command
bytes with zero recorded invocations; review $/task; share of spend outside any stage), each with
`target`, `higher_is_better` and `how_measured`, for the user to paste after writing `mission`.
The skeleton is committed by `wrapup_land` (P5 makes it stageable: this repo's `.gitignore` gains
`!.claude/intent.yaml` and `!.claude/world/`, interview #9); the withdrawal clock starts at the
first wrapup after the user fills it in.
**Consequences:**
- ✅ The living example is the user's, not the model's; nothing invalid is ever on disk.
- ⚠️ Until the user pastes the draft, `hm world status` on this repo prints `not_filled_in`.
**Rejected alternatives:**
- Draft written into the file — invalid by the SPEC's own skeleton rule.
- Skeleton only, no draft — the user has to re-derive the measurements.
**Source:** Interview #4, #9

### ADR-012: State paths are deliverables through the single source
**Status:** Accepted (2026-09-16, via /hm:plan interview — validator P-02/P-03)
**Context:** `_DELIVERABLE_RE` is derived from `DELIVERABLE_PREFIXES` (`worktree.py:181-199`),
which `wrapup_land.derive_deliverable_globs` also reads (`wrapup_land.py:255-258`), and
`tests/structural/test_deliverable_single_source.py` asserts they agree; the new paths are
`.claude/`-rooted and cannot be expressed as a `work-docs/<PREFIX>-*.md`. Wrapup staging is not
a `git add` line but `hm wrapup_land --required … --optional …` plus the derived globs. The
finalize dirt filter (`_is_harness_artifact`) never consults `_DELIVERABLE_RE`: deliverables are
user dirt at finalize and are **stash-preserved** on purpose.
**Decision:** add one constant `DELIVERABLE_STATE_PATHS = (".claude/intent.yaml",
".claude/world/assumptions.yaml", ".claude/world/outcomes.yaml", ".claude/world/objectives/")` in
`worktree.py`; `_DELIVERABLE_RE` gains a second alternation built from it (files exact,
`objectives/[^/]+\.yaml`); `derive_deliverable_globs` appends the same four as `--optional`
globs so `wrapup_land` stages them with **no prose change**; `test_deliverable_single_source.py`
is extended to assert the regex and the derived globs agree on the new constant too. AC-013's
finalize clause is corrected (rev 6.1) to "byte-identical after the finalize stash round trip"
— the files enter the stash and come back intact, like PLAN and SPEC do.
**Consequences:**
- ✅ One symbol to add a state path; wrapup stages it without touching the template.
- ✅ `_is_harness_artifact`, churn dirs/files/globs and the create guard are untouched.
- ⚠️ A finalize between edits still stashes the files; that is the existing deliverable contract.
**Rejected alternatives:**
- Classify as harness artifact (stash-excluded) — a user's edit would lose stash protection, the
  inverse of the `.hm-autopilot` incident.
- Add `--optional` paths to the two `wrapup_land` prose lines — bytes on both variants for
  something the derivation already owns.
**Source:** Interview #6

## 🏗️ Technical Design

### Current state
- `autopilot_caps._cmd_boundary` (lines 232–470): ordered checks ending in `advance_authorized`.
- `worktree._DELIVERABLE_RE` (line 198): `work-docs/{PLAN,…}-*.md | specs/SPEC-*.md`.
- `hm.py:_DISPATCHABLE`: explicit module allowlist; `tests/structural/test_hm_entrypoint.py`
  asserts it covers every rendered call.
- `synthesize._ALL_SKILLS` (line 275) enumerates skills for both `.claude/skills/` and
  `.agents/skills/`.
- `templates/stages/{plan,review,wrapup}.md.j2`; `templates/commands/hm/help.{en,ko}.md.j2`.
- `spec_machine` judgment machinery (`mark-judged`, `find-unjudged`) hashes
  `judgment_subject_paths`.
- `autopilot_ledger.append_event(root, event, fields)` writes JSON lines at the base root.

### Affected components
| Component | Change |
|---|---|
| `src/harness_maker/intent.py` (new) | schema constants, `validate_intent`, `load_intent`, `write_skeleton_if_absent`, `is_not_filled_in` |
| `src/harness_maker/world.py` (new) | envelopes/records, loaders with `schema_version` check, `observe`/`resolve`, `record_value`, objective transitions, canonical hashes, `derive`, `status_report`, `revisit`, `checkout_root`, argparse `main` |
| `src/harness_maker/autopilot_caps.py` | `HaltKind += "objective_gate"`, `_objective_check(root, cwd, slug)` called before `advance_authorized` |
| `src/harness_maker/worktree.py` | `DELIVERABLE_STATE_PATHS` constant; `_DELIVERABLE_RE` second alternation (ADR-012) |
| `src/harness_maker/wrapup_land.py` | `derive_deliverable_globs` appends the four state globs (ADR-012) |
| `src/harness_maker/hm.py` | `_DISPATCHABLE += "world"` |
| `src/harness_maker/cli.py` | `make` calls `intent.write_skeleton_if_absent` after render |
| `src/harness_maker/synthesize.py` | `_ALL_SKILLS += "intent-layer"` |
| `templates/stages/plan.md.j2` | `### Step 0.5 — Objective context`: status, load, closed question, `For each matching objective:` revisit loop; Step 5 writes `objective:` |
| `templates/stages/wrapup.md.j2` | two `@hm:answer-gated` blocks only (staging is `wrapup_land`, no prose change) |
| `templates/stages/review.md.j2` | `### Step 3.3 — Objective drift` (main loop, before 3.4, P2) |
| `templates/commands/hm/help.*.md.j2` | one line each: skill name + mention form on codex |
| `templates/skills/intent-layer/SKILL.md.j2` (new) | description with trigger phrases; four verb forms; ordered answer-gated rule |
| `templates/rubrics/objective_scope_drift.yaml.j2` | exists (SPEC stage); `finding_not_gate` says P2 (rev 6.1) |
| `src/harness_maker/step_sensitivity.py` + `work-docs/MATRIX-native-redundancy.md` | register `plan Step 0.5`, `review Step 3.3`, the wrapup block heading — class INV, grade from the RESEARCH row; three MATRIX rows |
| `.gitignore` (this repo only) | `!.claude/intent.yaml`, `!.claude/world/` re-includes (interview #9) |
| `worktree._HARNESS_GITIGNORE_PATTERNS` / `_HARNESS_CHURN_DIRS` / `_HARNESS_CHURN_FILES` / `_HARNESS_ARTIFACT_PREFIXES` / `_is_harness_artifact` | **unchanged** — nothing new is ignored in consuming projects |
| `src/harness_maker/review_consensus.py` | **unchanged** (ADR-004: P2 needs no new voice kind) |

### Data flow
```
operator ──(prose)──▶ skill intent-layer ──▶ hm world <verb> ──▶ .claude/{intent.yaml, world/*}
                                                                   ▲            │
/hm:plan Step 0.5 ── hm world status --json ───────────────────────┘            │ (git, task branch)
/hm:plan Step 5 ── writes PLAN frontmatter objective: <id>                       ▼
autopilot boundary ── checkout_root(cwd)/work-docs/PLAN-<resolved slug>.md ──▶ derive() ──▶ objective_gate?
                                                        └─▶ autopilot_ledger @ base root (event, display_ref)
/hm:review Step 3.3 ── objective show <id> --json + PLAN scope ──▶ scope_drift P2 (main loop, id at 3.4)
/hm:wrapup ── AskUserQuestion ──▶ (yes) hm world assume observe / objective close
/hm:wrapup ── hm wrapup_land ── derive_deliverable_globs() stages the four state paths
```

### API changes
- New CLI: `hm world status [--json]`, `hm world assume observe <id> --relation … --text … --observed-at …`,
  `hm world assume resolve <id> --status … --claim …`, `hm world outcome record <id> --value … --observed-at … --evidence …`,
  `hm world objective {approve|activate|drop|reopen} <id>`, `hm world objective close <id> --observed … --note …`,
  `hm world objective revisit <id> [--json]`, `hm world objective show <id> --json`.
- `autopilot_caps boundary` JSON gains `halt_kind: "objective_gate"` (only when a link exists and fails).
- PLAN frontmatter optional key `objective: <id>`.
- `intent.yaml`, `assumptions.yaml`, `outcomes.yaml`, objective files: schemas exactly as the SPEC
  Constraints rows; every file carries `schema_version: 1`.

### Design decisions
Every decision above references its ADR; the canonical hash payloads, the `revisit_when` grammar,
the gap rule and the timestamp normalisation are taken verbatim from the SPEC Constraints table
and are not re-decided here.

## 📝 Implementation Plan

### Phase 0 — Capture the pre-change baselines
- depends_on: []
- parallel_group: serial-0
- merge_hazards: none
- Scope in: `tests/fixtures/autopilot_caps_baseline.json` (boundary matrix over every stage ×
  every input the existing tests enumerate, captured from the current module),
  `tests/fixtures/rendered_command_names.json`, `tests/unit/test_baseline_fixtures_load.py`
  (loads both fixtures and asserts non-empty), `work-docs/BASELINE-DELTA-intent-world-model-objective-layer.md`
  (current chars and `!` / `Bash(` counts for the eight variant keys, from the current render).
  Scope out: any source change.
- Exit: `uv run pytest tests/unit/test_baseline_fixtures_load.py -q` passes and the delta doc
  lists the eight variant keys with current numbers.
- Risk: low
- Rollback: n/a (additive files)

### Phase 1 — `intent.py` and the skeleton
- depends_on: [0]
- parallel_group: serial-1
- merge_hazards: `src/harness_maker/cli.py` (make hook)
- Scope in: `src/harness_maker/intent.py`, `cli.py` make hook, `tests/unit/test_intent_validate.py`
  (AC-001 **intent half** — the six intent defect classes, property-based via hypothesis),
  `tests/unit/test_intent_skeleton.py` (AC-002 raw YAML types, strict-loader acceptance,
  HALF_FILLED error), `tests/unit/test_intent_update_invariance.py` (AC-003 bytes).
  Scope out: any `world` logic.
- Exit: `uv run pytest tests/unit/test_intent_*.py -q` green; `uv run mypy --strict src/harness_maker/intent.py`.
- Risk: low
- Rollback: Phase 0

### Phase 2 — `world.py`: records, transitions, derived state, status, revisit, CLI
- depends_on: [1]
- parallel_group: serial-2
- merge_hazards: `src/harness_maker/hm.py` (`_DISPATCHABLE`), `tests/structural/test_hm_entrypoint.py`
- Scope in: `src/harness_maker/world.py`, `hm.py` allowlist, tests for AC-001 **world half**
  (five objective defect classes, eight assumptions defect classes, envelope), AC-004/005/006
  (reload tuples), AC-007 (six defects + UTC normalisation, property), AC-008 (16-pair transition
  property), AC-009 (hash property against a test-side canonicaliser + git identity fixture),
  AC-010 (single-call cap), AC-011 (revisit results + CLI record), AC-014 (CLI stdout JSON on the
  authored fixture; import-graph walk over the four subcommand entrypoints; tree hash), AC-015
  (close persistence/immutability half), AC-016 (four kinds × three version defects), AC-018
  (latest-value property with four timestamp forms).
  Scope out: templates, autopilot.
- Exit: `uv run pytest tests/unit/test_world_*.py tests/structural/test_hm_entrypoint.py -q` green;
  `mypy --strict`; `hm world --help` lists the four subcommands.
- Risk: medium (largest module; hash canonicalisation must match the test's independent copy)
- Rollback: Phase 1

### Phase 3 — `objective_gate` in `autopilot_caps`
- depends_on: [2]
- parallel_group: serial-3
- merge_hazards: `src/harness_maker/autopilot_caps.py` (ordering of checks), `autopilot_ledger` event schema readers
- Scope in: `_objective_check` (resolved slug, base-root event), `HaltKind` literal, JSON-safe
  `raw_link` encoder, ten PLAN fixture projects + `TWO_CHECKOUTS` (ADR-009) + the
  marker-persisted-slug case, `tests/unit/test_autopilot_caps_objective_gate.py` (AC-012 full
  matrix against `autopilot_caps_baseline.json`; signature clause; `display_ref` read back from
  the event file's JSON), `tests/structural/test_gate_base_root_parity.py` extended to the new
  strip site. Scope out: templates.
- Exit: AC-012 test green; every pre-existing `autopilot_caps` test unchanged and green.
- Risk: high (a wrong ordering changes baseline rows silently — the differential fixture is the guard)
- Rollback: Phase 2
- parallel note: P3 and P4 are siblings off P2 (`parallel-A`); each rolls back to P2
  independently and neither touches the other's files.

### Phase 4 — Render: prompts, skill, help, deliverable paths, allowance
- depends_on: [2]
- parallel_group: parallel-A
- merge_hazards: `surface_baseline.json` ratchet (four gates, see ADR-010), `step_sensitivity.py`
  registry + `work-docs/MATRIX-native-redundancy.md`, `test_render_wrapup_delegation.py` line pin,
  `synthesize._ALL_SKILLS`, `worktree._DELIVERABLE_RE` + `wrapup_land.derive_deliverable_globs` +
  `tests/structural/test_deliverable_single_source.py`
- Scope in, in this order: (1) add the `surface_allowance` block of ADR-010 to this PLAN's
  frontmatter from the P0 delta doc; (2) `DELIVERABLE_STATE_PATHS` + `_DELIVERABLE_RE` +
  `derive_deliverable_globs` + single-source test (ADR-012); (3) edit `plan.md.j2` (Step 0.5 +
  Step 5 link), `wrapup.md.j2` (two answer-gated blocks), `review.md.j2` (Step 3.3, P2),
  `help.{en,ko}.md.j2`; new `skills/intent-layer/SKILL.md.j2`; `_ALL_SKILLS`; (4) registry
  entries + three MATRIX rows; (5) tests: AC-011 render clauses (shipped `!`/`Bash(` forms),
  AC-013 (integration: clean repo, two objective files, check-ignore, `_path_owner`, `make
  --update` bytes, finalize stash round trip byte-identical, `hm wrapup_land` executed on the
  fixture → index contains the five files), AC-015 render half, AC-019 (dual render,
  description length, verb forms, ordered phrases, help, baseline command names);
  `tests/structural/test_no_claude_tool_calls_in_codex_output.py` stays green.
  Scope out: rubric fixtures.
- Exit: `uv run pytest tests/structural tests/unit/test_render_* tests/integration/test_intent_layer_lifecycle.py -q`
  green including the four surface gates.
- Risk: medium (ratchet sequencing; a heading missing from the registry or MATRIX fails ARMS)
- Rollback: Phase 2 (templates are independent of Phase 3)

### Phase 5 — Judgment fixtures and dogfood
- depends_on: [3, 4]
- parallel_group: serial-5
- merge_hazards: this repo's `.gitignore` (two negations); the rendered surfaces
  `.claude/commands/hm/review.md` and `.agents/skills/hm-review/SKILL.md` are gitignored and
  absent in a fresh worktree until re-rendered (validator P-15)
- Scope in: (1) `/harness-maker:make --update` **in the worktree** so both rendered review
  surfaces exist for the judgment subject; (2) `tests/fixtures/objective_scope_drift/` four
  (PLAN, objective) input pairs; (3) `hm spec_machine mark-judged` for AC-017 via
  `judgment-reviewer` over both surfaces; (4) `mark-tested` write-back for AC-001…019
  `test_ids`; (5) `.gitignore` `!.claude/intent.yaml` + `!.claude/world/` (verify with
  `git check-ignore -v --no-index .claude/intent.yaml` printing nothing); (6) the measured
  outcomes draft below, presented — **not** written into the file. Scope out: any further behaviour.
- Exit: `hm spec_machine check --all` reports no unbound closed ACs and no unjudged judgment AC;
  `hm world status` on this repo prints `not_filled_in` (valid skeleton on disk) and the draft
  block below exists in this PLAN; `git check-ignore --no-index .claude/intent.yaml` prints nothing.
- Draft for the user to paste after writing `mission` (values re-measured at P5):

  ```yaml
  outcomes:
    - id: dead_rendered_bytes
      description: share of rendered command bytes with zero recorded invocations
      target: 10          # percent
      higher_is_better: false
      how_measured: "hm economics stages + metrics invocation counts, per rendered command"
    - id: review_usd_per_task
      description: hm:review spend per task
      target: 15          # USD
      higher_is_better: false
      how_measured: "hm economics stages: hm:review total_usd / tasks with a REVIEW doc"
    - id: unattributed_spend_share
      description: share of spend outside any /hm: stage
      target: 60          # percent
      higher_is_better: false
      how_measured: "hm economics stages: (unattributed) total_usd / sum"
  ```
- Risk: low
- Rollback: Phase 4

### Phase status (execute, 2026-09-16)

| Phase | Status | Notes |
|---|---|---|
| P0 | DONE | `autopilot_caps_baseline.json` (77 cells, shipped pipeline order), `rendered_command_names.json`, delta doc with the eight variant keys; first capture was all-`kill_switch` (marker written with a stale `created_at`) and was regenerated with a fresh timestamp before any source changed |
| P1 | DONE | A.5 round 1 FAIL (AC-003 domain excluded the zero-byte file) → round 2 PASS; 7 tests green; `mypy --strict` clean |
| P2 | DONE | A.5 round 1 FAIL (in-process `sys.modules` diff could not fail; reopen assertion vacuous; git identity leaked from the host) → round 2 PASS; 92 tests green; canonical hashes use the raw YAML number (`10`, not `10.0`) on both sides |
| P3 | DONE | A.5 (joint with P4) PASS; AC-012 660 cells green; the check reads the PLAN from `world.checkout_root(cwd)` and appends the event at the base root |
| P4 | DONE | AC-011/013/015/019 green; snapshots regenerated in the worktree (three-pin safe); round-trip table re-baselined plan 26→28, review 33→34, wrapup 26→28 with the calls named; wrapup line pins 684→702 / 717→735; `autopilot_gate_golden.json` re-captured with the four moved commands recorded; allowance `round_trips` are exact increments (the live check is equality) |
| P5 | DONE | rubric fixtures (4 input pairs) authored; `.gitignore` negations added and verified with `check-ignore --no-index`; the worktree re-rendered (`make --update`, guard bypassed) so both review surfaces exist; `mark-tested` recorded 18 ACs (run from the worktree's own env — the cached 0.56.0 plugin cannot import `world`); AC-017 judged **fail then pass**: round 1 found the lens never asked for the objective id in the finding message, the prose was fixed, the golden re-captured (review only moved), round 2 PASS on both targets; `mark-judged` recorded; `find-unjudged` / `find-unbound` clean. The valid skeleton `.claude/intent.yaml` is on disk; the measured outcomes draft stays in this PLAN for the user to paste after writing `mission` |

**Phase C.0 / D.5:** every phase is new-feature work, no defect repair — both steps are not
triggered (stated, not skipped silently).

**T1 mutation gate — NOT completed, recorded as a known gap.** `hm spec_mutation gate --tier 1`
returned "checked ZERO mutants — broken run" twice: once with the default whole-suite runner
(wall budget) and once `--sampled` with a targeted `--runner` (the wrapper's own budget still
expired before mutmut reported). A direct `mutmut run` on `intent.py` was killed by the shell
timeout after 500 s **and left a mutated `intent.py` on disk** (caught by the P1 tests, restored
from the authored source). Score therefore unknown; the wrapper's zero-mutant path and the
kill-leaves-mutant hazard are for `/hm:wrapup`'s failures memory and a follow-up task.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/autopilot_caps.py` — only the additive `_objective_check` and the one
  `HaltKind` literal; `_HUMAN_GATED_STAGES`, `_JUDGMENT_GATED_STAGES` and the existing check
  order are frozen (AC-012 differential)
- `src/harness_maker/conditional_router.py` — lens axis untouched (ADR-004)
- `src/harness_maker/lens_coverage.py` — no new lens
- `src/harness_maker/review_telemetry.py` — `KNOWN_LENSES` unchanged
- `src/harness_maker/review_consensus.py` — `Voice.kind` unchanged (ADR-004, P2)
- `src/harness_maker/second_opinion_invoke.py` — not edited
- `src/harness_maker/worktree.py` — only `DELIVERABLE_STATE_PATHS` and the `_DELIVERABLE_RE`
  alternation; `_HARNESS_CHURN_DIRS`, `_HARNESS_CHURN_FILES`, `_HARNESS_ARTIFACT_PREFIXES`,
  `_HARNESS_GITIGNORE_PATTERNS`, `_is_harness_artifact`, `_is_create_guard_harness_artifact` unchanged
- `src/harness_maker/wrapup_land.py` — only `derive_deliverable_globs`
- `tests/structural/surface_baseline.json` — never regenerated; growth goes through `surface_allowance`
- `CLAUDE.md` — no bytes added; the `unsourced:` count does not move because the new registry
  entries are graded from a RESEARCH row (interview #8)
- Advisory: nothing new is ignored in consuming projects; this repo's own `.gitignore` gains two
  re-include negations only
- Advisory: no LLM-authored text in `intent.yaml` at make time; the dogfood draft fills only
  `outcomes` from measurements

## 🧪 Testing Strategy

- **Unit (pytest, hypothesis for property ACs):** AC-001/003/007/008/009/016/018 as properties
  with test-side canonicalisers (hash, timestamp normalisation, argmax rule) so the oracle never
  reads the implementation; AC-004/005/006/010/015 on reloaded files.
- **CLI-level (the seam rule):** AC-002, AC-011, AC-014 run the shipped `hm world …` entrypoint
  via subprocess with `--json`, on fixtures under a temp checkout — never the module function.
- **Differential:** AC-012 against the Phase 0 boundary matrix; AC-013 against git's own
  `check-ignore` and index; AC-019 against the Phase 0 command-name list.
- **Integration (`INTEGRATION=1` not required — local git only):** `TWO_CHECKOUTS`, the lifecycle
  test with a linked worktree and a real finalize.
- **Judgment:** AC-017 via `judgment-reviewer` over both rendered review surfaces at P5;
  `find-unjudged` gate.
- **Mutation:** `paths_to_mutate` = `intent.py`, `world.py`, `autopilot_caps.py`, threshold 85
  (SPEC); run at wrapup, receipt to `mutation-receipts.jsonl`.
- **Manual:** run `hm world status` in this repo before and after editing the dogfood file;
  invoke `/hm:plan` on a throwaway slug and confirm the objective question appears only when
  objectives exist.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Objective check reorders or shadows an existing halt | medium | high | Phase 0 baseline matrix; AC-012 compares every row, not the new ones |
| Surface ratchet fails in sequence (four gates) | high | medium | ADR-010 order: delta doc → allowance → templates; measured numbers, not guesses |
| New stage headings missing from `step_sensitivity` registry | high | low | Registered in P4 with class INV; ARMS test is the gate |
| Codex arm renders inert `!` lines | medium | high | `{% if is_codex %}` on every new call site; `test_no_claude_tool_calls_in_codex_output` |
| Hash canonicalisation drifts between test and code | medium | high | Test carries its own canonicaliser from the SPEC row; AC-009 compares bytes |
| Worktree finalize stashes the new files | low | high | `_DELIVERABLE_RE` edit + AC-013 on a real finalize |
| Skill never selected on Claude Code | medium | low | Not promised (SPEC); `/hm:help` lists it; `hm world status` is the fallback |
| Dogfood file never edited by the user | medium | low | ADR-011: left uncommitted and reported, never auto-filled |

## ✅ Success Criteria

- [x] AC-001 intent half, AC-002, AC-003 — Phase 1 tests green
- [x] AC-001 world half, AC-004…AC-011, AC-014…AC-016, AC-018 — Phase 2 tests green, CLI-level where the SPEC says so
- [x] AC-012 — Phase 3 differential green, `TWO_CHECKOUTS` green
- [x] AC-013, AC-019, render halves of AC-011/AC-015 — Phase 4 green with all four surface gates
- [x] AC-017 — judged at Phase 5, verdict bound to both rendered review surfaces
- [x] `hm spec_machine check --all` — no unbound closed ACs, no unjudged judgment ACs
- [x] Mutation ≥ 85% over the three modules (known gap: `spec_mutation gate` collected zero mutants under mutmut 2.5.1 this run — see REVIEW open items; not independently re-verified at wrapup)
- [x] `ruff check`, `ruff format --check`, `mypy --strict` clean
- [x] No byte added to `CLAUDE.md`; nothing newly ignored in consuming projects; `surface_baseline.json` untouched

## 🔍 Plan Validation

**Pass 1 — `plan-validator` (run-id `iwmol-20260916-1`, terminal): MAJOR_REVISION**, 10 critical ·
6 warning · 2 suggestion. **Cross-model (codex, stage plan): invoked**, 10 findings (P1 6 · P2 4);
reconciliation: cx-1…cx-9 accepted, cx-10 rejected on source evidence (its headline "interim"
condition is permanent — carried at higher severity as P-03; its second half carried as P-16).

Per the maintainer's standing rule (plan-validator runs **once**; no pass 2, no Step 4.5 — the
loop does not converge and findings roll into `/hm:execute` A.5 and `/hm:review`), the 18
critiques were resolved by revision in Interview Round 3 and this document, and the outcome is
recorded as `MAJOR_REVISION_RESOLVED`. `plan_rounds` scheduled all 18 as pending; none skipped.

| Id | Sev | Resolution |
|---|---|---|
| P-01 | critical | ADR-010 rewritten to the parsed shape; eight per-variant keys; increments not baselines |
| P-02 | critical | ADR-012: staging via `derive_deliverable_globs`; no `git add` line; AC-013 runs `hm wrapup_land` |
| P-03 | critical | Interview #6 → A: AC-013 finalize clause corrected to round-trip byte identity (rev 6.1); ADR-012 |
| P-04 | critical | Interview #7 → A: `scope_drift` at P2, emitted before Step 3.4 for an id; SPEC + rubric corrected |
| P-05 | critical | Interview #8 → A: MATRIX rows added; grade from the RESEARCH row; CLAUDE.md count unchanged |
| P-06 | critical | ADR-007: field is `display_ref`; SPEC precedence row corrected |
| P-07 | critical | SPEC rev 6.1 verb-string corrections done in this stage, not P5 |
| P-08 | critical | ADR-011: valid skeleton on disk; draft presented in P5, not written |
| P-09 | critical | Interview #9 → A: two `.gitignore` negations in this repo (P5) |
| P-10 | critical | AC-011 predicate accepts `!uv run` / `Bash("uv run` forms (rev 6.1) |
| P-11 | warning | ADR-005: `Step 0.5`; Case A runs it; loop-mode skips and inherits |
| P-12 | warning | AC-001 split across P1 (intent) and P2 (world); Success Criteria split |
| P-13 | warning | P0 exit names `tests/unit/test_baseline_fixtures_load.py` |
| P-14 | warning | ADR-007: resolved slug; base root strip inside `autopilot_caps`; extra AC-012 case |
| P-15 | warning | P5 re-renders in the worktree before `mark-judged` |
| P-16 | warning | P3 ∥ P4 as `parallel-A`, both rolling back to P2 |
| P-17 | suggestion | Real symbol names in Affected components and Contract Boundaries |
| P-18 | suggestion | ≤ 78 lines **per variant** |

Findings that remain risks for `/hm:execute`: the ratchet sequence (P-01/P-10 class) and the
registry/MATRIX pairing (P-05) — both are exit-criterion gates in P4, not open questions.
