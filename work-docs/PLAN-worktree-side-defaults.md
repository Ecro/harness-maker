---
type: plan
task_slug: worktree-side-defaults
status: complete
created: 2026-08-06
tags: [harness-maker, plan, python, worktree, config-axis, preset, migration]
research_doc: "[[RESEARCH-worktree-side-defaults]]"
interview_rounds: 4
adrs: 7
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Collapse the worktree config axis to one live key worktree.enabled and expose it"
---

# PLAN — worktree axis collapse to `worktree.enabled`

## 🎯 Executive Summary

**TL;DR** — The `worktree:` block has four knobs and only one has runtime effect. Collapse
it to a single `worktree.enabled` boolean, render it from config (not from a template
literal), and expose it through the interview, `/hm:configure`, and a CLI flag.

**What** — Retire `scope`, `branch_prefix`, and the internal-sounding
`feature_branch_workflow`. The one surviving key is `worktree.enabled`: ON = every `/hm:`
stage runs in the persistent per-task worktree `.worktrees/<slug>/` on `hm/<slug>` and
`/hm:wrapup` squash-lands; OFF = no worktree is created anywhere and all work happens on
the current branch.

**Why** — Measured in RESEARCH V1–V8: Side answers `{'enabled': False}` yet renders
`scope: [execute]` and turns execute isolation **on**; `feature_branch_workflow` is never
emitted for Side so every Side project runs the legacy model behind a one-shot stderr
warning; a hand-edited `scope` is silently reverted on every re-render; and a
Production→Side preset flip drops the flag with zero output. Four user-visible symptoms,
one root cause: **the worktree block is written by the preset template, not by the config
object.**

**Key decisions**
- [ADR-001](#adr-001-collapse-the-worktree-axis-to-a-single-boolean) — one boolean, three keys retired
- [ADR-002](#adr-002-side-defaults-to-isolation-off-and-both-presets-can-be-overridden) — Side defaults OFF, both presets overridable
- [ADR-003](#adr-003-refuse-a-productionside-downgrade-that-would-strand-live-state) — downgrade refused on a live-state probe
- [ADR-004](#adr-004-accept-the-uncommitted-base-tree-as-the-documented-cost-of-off) — dirty base is the documented cost of OFF
- [ADR-005](#adr-005-off-renders-no-worktree-surface-at-all) — OFF renders no worktree surface at all
- [ADR-006](#adr-006-migrate-an-existing-harness-by-asking-when-we-can-and-defaulting-to-off-when-we-cannot) — migration asks when interactive, defaults OFF otherwise
- [ADR-007](#adr-007-name-the-key-worktreeenabled) — the key is `worktree.enabled`

**Estimated impact** — 2 preset templates, 4 stage/command templates, 1 skill template,
`interview.py`, `cli.py`, `worktree.py`, 2 doc files, this repo's `CLAUDE.md`, and the
`tests/e2e/sandbox*` fixtures. No change to the 5-layer defense, the registry, or
`task-land`.

---

## 📚 Prior Work

- `[[RESEARCH-worktree-side-defaults]]` — findings F1–F7 and sandbox verifications V1–V8.
  Every claim in this PLAN's Technical Design traces to one of them.
- `[[PLAN-multisession-worktree-concurrency]]` — introduced `feature_branch_workflow`
  (ADR-008) as one axis among several. Its name made sense then; it does not now.
- `[[PLAN-worktree-cross-session-data-loss-defense]]` — the 5-layer defense the OFF path
  currently leans on. Untouched here, but Phase 4 must not render it away for ON harnesses.
- `[[PLAN-worktree-deliverable-blocks-create]]` — `_is_deliverable_path`; the reason a
  dirty base does not self-block. Directly relevant to ADR-004.
- `[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3) and
  `[wiki:pattern] squash-to-shared-base-must-scope-the-commit-to-its-own-paths` — why
  ADR-004 rejects per-stage auto-commit onto a shared base.
- Global CLAUDE.md, 2026-06-08: *"absent-case = feature black hole (count:8)"*. The
  absent `feature_branch_workflow` key is a textbook instance; ADR-006 closes it.

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Axis shape | Architecture | How should the worktree config axis be shaped, given 3 of 4 knobs are dead? | collapse-to-boolean / config-ify scope only / revive scope per-stage | **collapse to a single boolean** | Accepts the largest blast radius to make config match behavior | ADR-001 |
| 2 | Side default | Scope | What is Side's worktree default? (raised concern: OFF worsens the dirty base) | Side ON / Side OFF / Side OFF + selectable | **Side OFF, selectable via interview + configure** | User read the concern and kept OFF as the default while adding an escape hatch | ADR-002 |
| 3 | Downgrade | Risk | How to handle a Production→Side flip silently dropping the flag (V5)? | live-state probe refusal / preserve flag across flips / loud warn | **refuse via live-state probe** | Symmetric to the existing upgrade-side `enablement_preflight` | ADR-003 |
| 4 | Health signals | Observability | Add worktree signals to `/hm:health` (currently zero)? | axis coherence / absent-key / stale worktrees / none | **none — out of scope** | Deliberate scope boundary; recorded as a follow-up | — |
| 5 | Deliverables | Risk | With Side OFF, deliverables land in the base tree. How to treat the dirty base? | accept + document / per-stage auto-commit / gitignore + `add -f` | **accept + document** | Auto-commit onto a shared base is the count:3 footgun | ADR-004 |
| 6 | Existing harness | Phasing | What happens to an already-generated Side harness (key absent)? | silent `false` / ask on re-render / auto-ON when clean | **silent `false`** — *superseded by #8* | Chosen under an option description that turned out to be wrong; corrected in round 3 | — |
| 7 | Meaning of OFF | Architecture | With `scope` retired, what does OFF mean for execute isolation? | no worktree at all / keep legacy ephemeral execute worktree / 3-state enum | **no worktree at all** | Matches the intuitive meaning of "disable" | ADR-005 |
| 8 | Migration value | Risk | Correction: because of #7, migrating absent→`false` *removes* execute isolation from every existing Side project. Which value? | `false` + loud notice / `true` (preserve safety net) / ask on re-render | **ask on re-render; `false` when non-interactive** | Supersedes #6 | ADR-006 |
| 9 | Key name | Contract | With one knob left, `feature_branch_workflow` is an internal-implementation name. Rename? | `worktree.enabled` / `worktree.isolation` / `worktree.per_task_branch` / bare bool | **`worktree.enabled`** | User-initiated mid-stage; 1:1 with the interview question wording | ADR-007 |

**Round structure:** R1 = #1–4, R2 = #5–7, R3 = #8 (correction of #6), R4 = #9.

**No deferred decisions.** One item was explicitly scoped out (`/hm:health` signals, #4)
and one was ruled a separate concern (RESEARCH V8, un-`<WT>`-prefixed deliverable write
instructions — it affects Production, and the observed dirty base was Side). Both are
listed under Success Criteria as non-goals, not as open checkboxes.

---

## 📐 Architecture Decision Records

### ADR-001: Collapse the worktree axis to a single boolean
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** The `worktree:` block ships four keys. `enabled` is never rendered and never
read at runtime (its only consumer is a migration gate); `branch_prefix` is self-documented
as *"reserved for Phase 9 (currently informational)"* and does not even match the real
`hm/<slug>` naming; `scope`'s `plan` element has no call site — every `worktree create` in
every template passes the literal `execute`, and under the flag-on path `scope` is ignored
entirely. Only one key has effect, and `scope` and `branch_prefix` are template literals a
re-render silently reverts.
**Decision:** Retire `enabled`(old semantics), `branch_prefix`, and `scope` from the
rendered config. The block becomes exactly one key, rendered from `config.worktree`.
**Consequences:**
- ✅ The rendered config describes what the system actually does; a hand-edit round-trips.
- ✅ Removes the three-way incoherence a user cannot reason about.
- ⚠️ Largest blast radius of the options considered (2 preset + 4 stage/command + 1 skill
  template, plus docs and e2e fixtures).
- ⚠️ `_scope_includes` must survive as a legacy reader so an un-re-rendered harness keeps
  working. It is retained with a deprecation docstring and one caller (ADR-006's fallback).
**Rejected alternatives:**
- *Config-ify `scope` only* — Rejected: fixes the hand-edit reversion but leaves three inert
  keys, reproducing the exact confusion that prompted this work.
- *Revive `scope` as a real per-stage selector* — Rejected: resurrects dead code, costs the
  most to implement and test, and no evidence exists that anyone wanted per-stage control
  (it was never settable).
**Source:** Interview #1

### ADR-002: Side defaults to isolation OFF, and both presets can be overridden
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** Side's interview answer says isolation is off while the render turns it on.
The user wants Side to genuinely default off. The counter-evidence was surfaced before the
decision: RESEARCH V2 shows the dirty base is caused by six of seven stages *lacking*
isolation, so OFF widens it rather than fixing it.
**Decision:** Side defaults `worktree.enabled: false`, Production defaults `true`. Both are
overridable through a new interview question, a `/hm:configure` dimension, and
`--worktree` / `--no-worktree`.
**Consequences:**
- ✅ Side's config finally means what it says; the preset stays "lighter" in a real sense.
- ✅ A Side user who wants a clean base has one supported switch instead of a hand-edit.
- ⚠️ The dirty base is accepted for the OFF default — see ADR-004.
- ⚠️ Preset no longer fully determines the git model, so anything reading the preset to
  infer the model is wrong. Nothing does today; keep it that way.
**Rejected alternatives:**
- *Side ON* — Rejected by the user after reading the trade-off: it makes Side and
  Production behave identically on the axis that most distinguishes them operationally.
- *Side OFF, not overridable* — Rejected: the whole finding is that there is no supported
  way to change this.
**Source:** Interview #2

### ADR-003: Refuse *any* effective true→false transition that would strand live state
**Status:** Accepted (2026-08-06, via /hm:plan interview) — **scope widened 2026-08-06 by
unanimous cross-model second opinion** (codex `f05fbadd` P0, antigravity `78c0b80c` P0)
**Context:** V5 reproduced a `--preset Side` flip dropping the flag with zero output. The
upgrade direction is guarded by `enablement_preflight`'s clean-live-state probe; the
downgrade direction has no guard, so a project with live `hm/<slug>` worktrees is moved
back onto the legacy stash model without being told — the precondition class of the count:3
contamination failure.

The originally-drafted decision guarded only the **preset-flip** path. Both second-opinion
models independently rejected that as a P0: ADR-002 introduces four more ways to set the
value false (`--no-worktree`, the interview answer, the `/hm:configure` dimension) and
ADR-006 adds a fifth (migration), while ADR-005 removes the only rendered finalize/stash
recovery instructions. Guarding one of six producers leaves five paths that strand live
state.
**Decision:** One canonical `worktree.disable_preflight(base, sibling_bases)`, invoked at a
**single choke point** immediately before any config mutation that takes the *effective*
value from true to false — regardless of which input produced it (preset flip,
`--no-worktree`, interview answer, `/hm:configure`, migration). The transition is
**refused** (non-zero exit, no config mutation, no re-render) when the primary base or any
sibling has a live `hm/*` task worktree, a pending `.hm-finalize-stash-*`, a live
`.hm-loop-*` marker, or a live registry row. The message names the offending branches and
the remedy (`/hm:wrapup` or `worktree task-land`).

The choke point is a property of the *transition*, not of any caller: setters compute the
desired value and hand it to one function that owns the guard. A new setter added later
inherits the guard by construction.
**Consequences:**
- ✅ In-flight work cannot be orphaned by *any* disable path, not just a preset flip.
- ✅ Symmetric with the upgrade path, so one mental model covers both directions.
- ✅ Adding a sixth way to set the value false cannot regress the guard.
- ⚠️ A user with an abandoned worktree must clean up before disabling. Acceptable: the probe
  prints the exact commands.
- ⚠️ Refusal is a non-zero exit, so a scripted `--preset Side` or `--no-worktree` in CI can
  now fail. Intended, and loud rather than silent.
**Rejected alternatives:**
- *Guard only the preset flip* — Rejected on second-opinion evidence: five other producers.
- *Preserve the flag across preset flips* — Rejected: makes `--preset` mean different things
  for different keys, and a user who explicitly asks for Side and gets Production's git
  model is equally surprised. (Note: this is distinct from **not clobbering an explicit
  on-disk value with a preset default**, which Phase 1 *does* do — see R8.)
- *Warn and proceed* — Rejected: `--autoloop` and other non-tty paths bury warnings, which
  is how V5 stayed invisible.
**Source:** Interview #3; widened by codex `f05fbadd9329a579` + antigravity `78c0b80c1b0b44fa`

### ADR-004: Accept the uncommitted base tree as the documented cost of OFF
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** With isolation off, `RESEARCH-*.md` / `SPEC-*.md` / `PLAN-*.md` / `REVIEW-*.md`
are written to the base working tree and stay uncommitted until `/hm:wrapup`. Deliverables
are deliberately excluded from `_HARNESS_CHURN_PREFIXES` and gitignore because wrapup
commits them.
**Decision:** Accept it. No auto-commit, no gitignore change, no git mutation. State the
cost in the interview option text, in `/hm:configure`'s trade-off line, and in
`docs/HOW-IT-WORKS.md`, so a user choosing OFF knows what they are buying.
**Consequences:**
- ✅ Zero new git-mutation surface — the highest-risk category in this codebase.
- ✅ The uncommitted state remains recoverable and visible in `git status`.
- ⚠️ The user's original dirty-base complaint is *explained and made choosable*, not
  eliminated, for anyone who keeps OFF. Turning `worktree.enabled: true` on eliminates it.
**Rejected alternatives:**
- *Per-stage path-scoped auto-commit* — Rejected: committing onto a shared base is the exact
  shape of `[fail:design] task-land-squash-commits-whole-index-sweeps-concurrent-base-churn`,
  and it fragments one unit of work into four commits.
- *gitignore `work-docs/` + `git add -f` at wrapup* — Rejected: reverses
  PLAN-worktree-base-artifact-pollution's deliberate decision not to ignore deliverables, and
  makes them easy to lose.
**Source:** Interview #5

### ADR-005: OFF renders no worktree surface at all
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** With `scope` retired, the flag-off branch of `execute.md.j2` has nothing left
to gate on. Today Side renders a full `worktree create execute` + finalize + stash +
post-commit-pop surface despite answering "worktree off".
**Decision:** `worktree.enabled: false` means no stage creates a worktree. The flag-off
isolation block in `execute.md.j2`, the finalize/stash/post-commit-pop sections, the
`worktree create execute` calls in `loop.md.j2` and `loop-p5-batch.md.j2`, and the
`worktree-isolator` skill are all rendered only when the flag is ON.
**Consequences:**
- ✅ "Disable" means what a user expects; an OFF harness has zero worktree vocabulary.
- ✅ A large body of stash/finalize prose disappears from OFF harnesses' context budget.
- ⚠️ Highest-risk phase: a mis-placed `{% if %}` boundary can drop `finalize` from an ON
  harness, which is a data-loss-adjacent regression. Phase 4 gates on a render assertion for
  both states, not on reading the template.
- ⚠️ The legacy ephemeral `execute-<uuid>` worktree path becomes unreachable from new
  renders. Its Python implementation stays (un-re-rendered harnesses still call it).
**Rejected alternatives:**
- *Keep the legacy ephemeral execute worktree under OFF* — Rejected: reproduces today's
  "OFF but a worktree appears" contradiction, which is the reported bug.
- *Three-state enum `off | execute-only | full`* — Rejected: contradicts ADR-001 and re-adds
  a knob with no demonstrated demand.
**Source:** Interview #7

### ADR-006: Migrate an existing harness by asking when we can, and defaulting to OFF when we cannot
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** Every existing Side harness has `scope: [execute]` and no flag, so execute
isolation is **on** today. Under ADR-005, migrating the absent key to `false` removes that
isolation. The first answer to this question (#6) was given under an option description
that wrongly claimed zero behavior change; #8 corrects it.
**Decision (split by how much information the legacy block actually carries).** Both
second-opinion models rejected a blanket non-interactive `false` as a P0 (codex `26f76a6d`,
antigravity `810bad1d`): a legacy **Production** harness carries an explicit
`feature_branch_workflow: true`, and overwriting that with `false` on a scripted `--update`
silently disables a project that made the opposite decision on purpose. That case is not
ambiguous and must never be asked about or guessed at. Split accordingly:

- **Rung-2 present** — the block has an explicit boolean `feature_branch_workflow`. This is
  a prior explicit decision. **Preserve it exactly and silently** (`enabled: <same bool>`).
  No prompt, no notice beyond a one-line rename note. Lossless.
- **Rung-2 absent, rung-3 true** — the block has only the legacy `scope` containing
  `execute`. Genuinely lossy: the old axis could express *execute-only isolation*, and the
  new boolean cannot. `true` would expand one isolated stage to seven plus per-task branches
  plus squash-land; `false` would drop the one isolated stage.
  - **Interactive** (`--reinterview`, any tty interview path) → ask, presenting both losses.
  - **Non-interactive** (`--update`, `--autoloop`, non-tty) → write `false` plus one loud
    stderr notice naming the behavior change and the `--worktree` remedy.
- **`scope` present without `execute`** (`scope: []`, a hand-edited `scope: [plan]`) — a
  present key is a legacy *off* decision, not an absence. Write `false` with the rename
  note. Never fall through to the preset default: for Production those differ (`false` vs
  `true`), and `scope: []` is precisely the hand-edit a user makes trying to disable
  (RESEARCH V3 showed that edit was being reverted, so someone may well have one).
- **Nothing present** — write the preset default (ADR-002) with a one-line notice.

Every branch that yields `false` from a currently-effective `true` routes through ADR-003's
choke point, so a migration cannot strand live state either.
**Consequences:**
- ✅ A project that explicitly opted into the feature-branch model can never be silently
  opted out — the P0 both models found.
- ✅ Only the genuinely-unrepresentable case (`scope`-only) is ever asked about or defaulted.
- ✅ The absent-key black hole is closed — after one re-render every harness carries an
  explicit boolean.
- ⚠️ In the `scope`-only case the same project can still receive different values depending
  on how it was re-rendered. Mitigated by the loud non-interactive notice, by the value
  becoming explicit and visible in `harness.yaml` from then on, and by ADR-003's guard.
- ⚠️ Until a harness re-renders, the runtime must keep honoring the legacy keys — hence the
  Phase 2 fallback chain.
**Rejected alternatives:**
- *Blanket silent `false`* — Rejected in round 3, then rejected again as a P0 by both
  second-opinion models for the rung-2 case.
- *Blanket `true`* — Rejected: contradicts ADR-002 and would newly isolate six stages in
  `scope`-only projects that never asked for it.
- *Refuse to migrate when it cannot decide* (codex's suggestion) — Rejected: an un-migratable
  harness would fail every re-render, and the `scope`-only case has a safe loud default.
**Source:** Interview #6, superseded by Interview #8; split by codex `26f76a6dff8143f9` +
antigravity `810bad1dd48f0984`

### ADR-007: Name the key `worktree.enabled`
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** `feature_branch_workflow` was an apt name when it was one axis among four —
it named the *git model*, not the isolation feature. As the only knob it is an
internal-implementation term that does not answer the question a user is actually asking.
**Decision:** The key is `worktree.enabled`. The interview question, the `/hm:configure`
dimension ("Worktree isolation"), and the CLI flags (`--worktree` / `--no-worktree`) all use
the same vocabulary.

**Two under-specifications the second opinion caught, now pinned** (codex `e86c9abe` P1 +
`42ee827d` P1; antigravity `661d061f` P2):

- **A present-but-non-boolean value is a configuration error, not a miss.** It terminates
  the lookup, resolves fail-closed to `False`, and emits a loud error naming the file and
  the bad value. It must **never** fall through to a stale lower rung: under fall-through,
  `enabled: "false"` alongside a stale `feature_branch_workflow: true` would silently turn
  isolation *on* against the apparent opt-out. The same rule applies at rung 2, matching the
  existing `interview.py:877` bool-strictness.
- **A disagreeing mixed-generation block is surfaced, not silently resolved.** When
  `enabled` is present *and* a legacy key resolves to the opposite value, `enabled` wins
  (newest explicit decision) **and** a loud warning names both keys and both values. This
  converts the name-reuse hazard from a silent behavior flip into a visible one.
**Consequences:**
- ✅ One word across config, interview, configure, CLI, and docs.
- ✅ Malformed and mixed-generation shapes fail loudly instead of silently changing the git
  model in either direction.
- ⚠️ The name collides with the retired answers-side `enabled`. No harness this renderer
  produced contains `worktree.enabled` on disk, so there is no existing ambiguous value; the
  disagreement warning covers hand-crafted or copied files, which is the residual risk both
  models named.
- ⚠️ Two legacy names (`feature_branch_workflow`, `scope`) must be read for back-compat,
  making the reader a three-generation fallback chain (Phase 2).
**Rejected alternatives:**
- *`worktree.isolation`* — Rejected: `isolation: true` reads redundantly; its advantage
  (room to become an enum) is explicitly unwanted per ADR-001/005.
- *`worktree.per_task_branch`* — Rejected: leads with the implementation instead of the
  user-facing question.
- *Bare `worktree: true|false`* — Rejected: breaks every `config.worktree.get(...)` call
  site and forecloses any future sibling key.
**Source:** Interview #9

---

## 🏗️ Technical Design

### Current State

```
harness.yaml (Side, as shipped today)
  worktree:
    scope: [execute]        ← template literal, not config; hand-edit reverted (F1/V3)
    branch_prefix: hm-      ← dead in both directions (F1)
  # worktree.enabled        ← never rendered; runtime never reads it (F2)
  # feature_branch_workflow ← never emitted for Side → legacy model + stderr warning (F3)

runtime readers
  worktree._scope_includes(yaml, "execute")            → True   ← turns Side isolation ON
  worktree._feature_branch_workflow_enabled(base)      → False  ← legacy model
  cli.py:431  bool(a.worktree.get("enabled"))          → False  ← Side never migrates (F4)
```

### Affected Components

| Component | Change |
|---|---|
| `src/harness_maker/interview.py` | `_preset_extras` emits `{"worktree": {"enabled": bool}}`; `answers_from_harness_yaml` reads the new key with a legacy fallback; new interview question |
| `src/harness_maker/cli.py` | `--worktree/--no-worktree`; `_apply_dimension_overrides` handling; downgrade probe wiring; migration branch |
| `src/harness_maker/worktree.py` | `worktree_enabled()` three-generation reader; `disable_preflight()` + `apply_worktree_enabled()`; `_scope_includes` demoted to legacy |
| `templates/harness-yaml/{Side,Production}.yaml.j2` | Block becomes one config-driven key |
| `templates/stages/execute.md.j2` | Flag-off isolation + finalize/stash sections gated ON-only |
| `templates/commands/hm/{loop,loop-p5-batch,configure}.md.j2` | Gate `worktree create`; new configure dimension |
| `templates/skills/worktree-isolator/SKILL.md.j2` | Rewritten to `worktree.enabled`; rendered ON-only |
| `docs/HOW-IT-WORKS{,.ko}.md`, `CLAUDE.md` | `worktree.scope` references replaced |
| `tests/e2e/sandbox*/.claude/**` | Regenerated fixtures |

Six stage templates (`research`/`spec`/`plan`/`review`/`verify`/`wrapup`) already gate purely
on the flag via `config.worktree.get('feature_branch_workflow')` — they need only the key
rename, no structural change.

### Dependencies

No new third-party dependencies. No schema-version bump is required for `harness.yaml`
(the reader tolerates all three generations), but the migration is recorded in CHANGELOG.

### Target Architecture

```
harness.yaml
  worktree:
    enabled: true | false          ← the only key, rendered from config.worktree

five value producers                       ← preset flip · --worktree/--no-worktree
        │                                    · interview answer · /hm:configure · migration
        ▼
  desired_enabled: bool
        │
        ▼
  ┌────────────────────────────────────────────────────────────────┐
  │ apply_worktree_enabled(base, answers, desired) ← THE choke point │
  │   LAYER: operates on the resolved InterviewAnswers.worktree,     │
  │          immediately before synthesize(). Everything upstream    │
  │          (_preset_extras, answers_from_harness_yaml, CLI flags,  │
  │          the interview answer) produces a PROPOSAL, not a write. │
  │   effective = worktree_enabled(base)      # from disk, pre-write │
  │   if effective and not desired:                                  │
  │       disable_preflight(base, siblings)   → refuse on live state │
  │   answers.worktree["enabled"] = desired   # the one real write   │
  └────────────────────────────────────────────────────────────────┘
        (the on-disk write is synthesize.py:769 → Jinja, downstream of
         this and unconditional — it renders whatever survived the gate)
        │
        ▼
  InterviewAnswers.worktree = {"enabled": bool}
        │
        └─ synthesize → Blueprint.worktree → templates ({% if config.worktree.enabled %})

runtime  worktree.worktree_enabled(base):          ← THE single reader
           1. worktree.enabled          bool → return it (warn if a legacy key disagrees)
                                   non-bool → loud error, return False, STOP (no fallthrough)
           2. feature_branch_workflow   bool → return it
                                   non-bool → loud error, return False, STOP
           3. scope present (a list)         → "execute" in it ? True : False — TERMINATES
                                                 (a present key always wins; falling through
                                                  would contradict first-key-present-wins)
           4. none present                   → False + one-shot stderr warning
```

**Every** behavior-bearing consumer routes through `worktree_enabled` — not just the create
path. Codex `2f0bac2b` (P1) enumerated three that read the YAML directly today
(`_scope_includes` at `worktree.py:2304`, `_feature_branch_workflow_enabled` at `:3635`,
and `readiness.py:643`); a divergence between any two of them means `/hm:health` can report
a different mode than the one actually executing.

The three-generation chain is what makes ADR-006 honest: an un-re-rendered Side harness hits
rung 3 and keeps today's execute isolation until its owner re-renders and answers.

### Design Decisions

- The reader is a **fallback chain, not a merge** (ADR-006/007). The first key present wins,
  newest generation first, so an explicitly written `enabled: false` is never overridden by a
  stale `scope`.
- **A present-but-malformed value stops the chain** (ADR-007). It does *not* read as absent
  — falling through to a stale lower rung is how `enabled: "false"` would silently turn
  isolation on.
- **The guard belongs to the transition, not to any caller** (ADR-003). One
  `apply_worktree_enabled` choke point owns it, so a producer added later inherits it. A
  table-driven test enumerates every true→false producer and asserts each is refused with a
  byte-identical `harness.yaml` when live state exists.
- **One reader, no direct YAML interpretation elsewhere.** A structural test fails if any
  module outside the single legacy-compat function reads `worktree.enabled`,
  `feature_branch_workflow`, or `scope` from a harness YAML.
- `_scope_includes` is **retained, not deleted** (ADR-001), with exactly one caller (rung 3).
  Deleting it would strand every project that has not re-rendered.
- The disable probe **mutates nothing** (ADR-003), matching `enablement_preflight`'s
  config-only contract.
- **A preset default never clobbers an explicit on-disk value** (codex `5db98f7d` P2). The
  preset-extras rebuild in `_apply_dimension_overrides` — the mechanism behind V5 — must
  re-apply an explicit disk `worktree.enabled` unless `--worktree`/`--no-worktree` was given.
  Precedence is CLI flag > disk > preset default, and it is tested as a cross-product, not
  only on the `--update` path.

### Data Flow

`harness.yaml` → `answers_from_harness_yaml` → `InterviewAnswers.worktree` →
`_apply_dimension_overrides` (CLI flags) → migration/downgrade gates → `synthesize` →
`Blueprint.worktree` → Jinja `config.worktree.enabled` → rendered `harness.yaml` and the
flag-gated stage templates. Runtime reads the rendered `harness.yaml` back through
`worktree_enabled()`.

### API Changes

| Surface | Before | After |
|---|---|---|
| `harness.yaml` | `worktree: {scope, branch_prefix, feature_branch_workflow?}` | `worktree: {enabled}` |
| `worktree.py` | `_feature_branch_workflow_enabled(base)` | `worktree_enabled(base)` (old name kept as a thin alias for one release) |
| `worktree.py` | — | `disable_preflight(base, sibling_bases) -> (bool, str \| None)` and `apply_worktree_enabled(base, answers, desired)` |
| `cli make` | — | `--worktree` / `--no-worktree` |
| `/hm:configure` | 12 dimensions | +1 "Worktree isolation" |

---

## 📝 Implementation Plan

> **Execution status (`/hm:execute`, 2026-08-06) — all phases DONE.** Deviations are
> recorded here rather than folded silently; each changed what the PLAN said to do.
>
> | Phase | Status | Deviation |
> |---|---|---|
> | 1 | DONE | **Absorbed the gate rename in all seven stage templates** (PLAN put it in Phase 6). Forced: `synthesize` normalizes the block to `enabled`, so the moment the old key stops being emitted, `config.worktree.get('feature_branch_workflow')` is missing and every gated stage silently renders flag-OFF. Also added `synthesize._normalize_worktree` as THE normalization point so pre-collapse answers dicts (`{"feature_branch_workflow": True}`, bare `{}`) resolve instead of rendering `StrictUndefined`. |
> | 2 | DONE | **`_scope_includes` deleted, not retained** (ADR-001 said retain). With rung 3 inside `resolve_worktree_enabled` covering the un-re-rendered case, keeping it meant keeping a second path-based reader that nothing calls and carving it out of the singleton invariant — the invariant this phase exists to establish. Recorded in `test_worktree_reader_singleton.py`. Consumers redirected: `_cli_create` (:2529), the finalize dispatch (:2982), `readiness.py:643`, and `readiness.py:698/702`'s remediation string. |
> | 3 | DONE | Implemented together with 4 and 5 — all three land in the same `cli.py` region and the PLAN already forced them serial. `disable_preflight` + `_apply_worktree_enabled` (the choke point) + `_task_worktree_blockers`. |
> | 4 | DONE | `_ask_worktree`, `--worktree/--no-worktree`, the `/hm:configure` dimension. Added beyond the PLAN: the CLI flag explicitly **outranks** every migration branch (`flag_given`), or the flag would be inert on exactly the harnesses that need it. |
> | 5 | DONE | ADR-006's four-way split as written. |
> | 6 | DONE | Three scope additions the PLAN did not anticipate — see below. |
> | 7 | DONE | Docs, README, this repo's CLAUDE.md, CHANGELOG, `docs/assets/showcase-diff.md`, regenerated snapshots. `worktree.cleanup` recorded in CLAUDE.md as a phantom knob. |
>
> **Phase 6 — three findings beyond the stated scope:**
>
> 1. **`gate0_receipt.md.j2` used a literal `<WT>` root.** Under OFF that path can never
>    exist, so the receipt would silently never fire and the autoloop driver's Gate 0
>    would see every stage missing on every iteration. Same class as R11 and not in the
>    PLAN. Fixed with a `g0_root` that degrades to `.`.
> 2. **`<WT>` path roots leaked into `plan`/`review`/`verify`/`wrapup`** (`spec_need
>    --root`, `wrapup_land --worktree`). Under OFF these are literal bad paths, not just
>    prose. Fixed with a per-template `WTR` that degrades to `.`.
> 3. **Accepted limitation:** `loop.md`, `loop-p5-batch.md` and `health.md` still carry
>    worktree prose in an OFF render. `worktree create` is already a runtime no-op there
>    and the templates say so, so the OFF path is functionally correct; removing the
>    prose means rewriting `<WT>` threading through the entire iteration body, which
>    carries real autoloop regression risk and is left as separate work. The render test
>    exempts them by name with that reasoning inline.
>

> **Ordering rationale (revised on second-opinion evidence).** Both models flagged the
> original graph as unsafe (codex `ed830ea3` P1, antigravity `526e8570` P1): it created every
> way to set the value false (old Phase 3) and removed the finalize/stash recovery surface
> (old Phase 4) *before* building the guard (old Phase 5). A user toggling isolation between
> those phases would strand live worktrees, and a guard written after its callers tends to
> cover only the callers that existed when it was written. The graph below builds the
> **reader**, then the **guard choke point**, then the **setters**, and removes the recovery
> surface **last**. At no commit does a false-setting path exist without its guard.

### Phase 1 — `worktree.enabled` render contract

- **depends_on:** `[]`
- **parallel_group:** `serial-config`
- **merge_hazards:** `interview.py` (shared with Phases 4, 5); `cli.py` (Phases 3, 4, 5);
  both `harness-yaml/*.yaml.j2`
- **Scope — in:** `interview.py` (`_preset_extras`, `answers_from_harness_yaml`),
  `cli.py` (`_apply_dimension_overrides` preset-rebuild preservation),
  `templates/harness-yaml/{Side,Production}.yaml.j2`, **`worktree.py:2529`'s `_cli_create`
  gate**, **`templates/codex/AGENTS.md.j2:32`**
- **Scope — out:** every other stage/command template (Phase 6); the rest of `worktree.py`
  (Phase 2)
- **⚠️ Atomic — must not be split across commits.** The moment the preset templates stop
  rendering `scope`, two things break *at that same commit*: `_cli_create` (`worktree.py:2529`
  gates on `_scope_includes`) starts printing empty on a fresh **ON** harness, which every
  rendered command reads as *"no isolation"* (R11), and `AGENTS.md.j2:32`'s `is defined`
  fallback starts printing the literal `'execute'` on OFF harnesses (R12). Phase 2's full
  reader consolidation may follow later, but these two redirects ship **in this commit** —
  a `depends_on: [1]` phase lands *after* Phase 1, and Phase 1's own render/unit exits never
  call `worktree create`, so the intervening window would be green and broken.
- **Work:** `_preset_extras` returns `{"worktree": {"enabled": False}}` for Side and
  `{"worktree": {"enabled": True}}` for Production. Both preset templates render exactly
  `worktree:\n  enabled: {{ config.worktree['enabled'] | tojson }}` — no literals.
  `answers_from_harness_yaml` reads disk `worktree.enabled` bool-strictly and drops
  `scope`/`branch_prefix` from the merged dict. **Make the preset-extras rebuild preserve an
  explicit on-disk value** unless `--worktree`/`--no-worktree` was passed — this is the V5
  mechanism, and leaving it would let a `--preset` switch clobber the new key exactly as it
  clobbered the old one. (This rebuild writes `answers.worktree["enabled"]` directly because
  `apply_worktree_enabled` does not exist yet; **Phase 3 refactors it to route through the
  choke point** — see Phase 3's Work list.) Point `_cli_create` at an interim
  `worktree_enabled` and fix `AGENTS.md.j2:32` to read the new key, per the atomicity note
  above. Before touching the preset templates, run the **prose-inclusive** sweep
  `rg 'worktree\.scope|branch_prefix|feature_branch_workflow' src/harness_maker/templates/`
  — a `config.worktree.*` pattern finds Jinja expressions only and would miss the
  user-facing prose in `_partials/pf_intro.md.j2` and `execute.md.j2:403`.
- **Exit criterion:** `uv run pytest tests/unit -k "interview or render or preset" -q` green,
  including: (a) Side renders `enabled: false`, Production `enabled: true`; (b) the rendered
  block contains no `scope` or `branch_prefix`; (c) **V3 round-trip** — hand-edit `enabled`
  to the non-default value, re-render with `--update`, assert it survived; (d) a
  **cross-product** test over {interactive, `--reinterview`, `--update`, `--preset` switch} ×
  {explicit true, explicit false} asserting the explicit value survives unless a CLI flag
  overrides it (codex `5db98f7d`).
- **Risk:** medium
- **Rollback point:** pre-Phase-1 commit

### Phase 2 — One canonical reader, every consumer

- **depends_on:** `[1]`
- **parallel_group:** `serial-config`
- **merge_hazards:** `worktree.py` (Phases 3, 6)
- **Scope — in:** `src/harness_maker/worktree.py`, `src/harness_maker/readiness.py`
- **Scope — out:** `cli.py`; templates
- **Work:** Rename `_feature_branch_workflow_enabled` → `worktree_enabled`, keeping the old
  name as a deprecated alias. Implement the chain from Technical Design, including the
  **stop-on-malformed** rule, the **present-`scope`-terminates** rule, and the
  **disagreement warning**. Then **inventory and redirect every behavior-bearing consumer**
  (codex `2f0bac2b`), naming each:

  | Site | Today | After |
  |---|---|---|
  | `worktree.py:2529` `_cli_create` | `if not _scope_includes(yaml_path, stage): print(""); return 0` | `worktree_enabled(base)` |
  | `worktree.py:2304` `_scope_includes` | public-ish gate | rung 3's private helper, no other caller |
  | `worktree.py:3635` `_feature_branch_workflow_enabled` | second independent reader | deprecated alias |
  | `readiness.py:643` | direct `feature_branch_workflow` read | `worktree_enabled(base)` |
  | `readiness.py:698/702` | remediation text naming the retired key | names `worktree.enabled` |

  **`worktree.py:2529` is the load-bearing one, and its redirect already shipped in Phase 1**
  (see Phase 1's atomicity note). `_cli_create` is what decides whether a worktree is created
  at all; had it stayed here behind `depends_on: [1]`, the commit that stops rendering `scope`
  would have left `_scope_includes` returning False on a fresh **ON** harness, making
  `worktree create execute` print an empty line, which `execute.md`/`loop.md` explicitly read
  as *"no isolation; operate in cwd"* — a total, silent isolation loss on Production that
  every grep-based test in this PLAN would pass. This phase inherits it and folds it into the
  single reader. (Found by the validator; codex `2f0bac2b` gestured at the class but not this
  site.)

  **`_cli_create`'s `stage` argument** is retained and still consulted **for rung-3 harnesses
  only**, so an un-re-rendered `scope: [execute]` harness keeps returning empty for
  `create plan`. Once a harness reaches rung 1 the value is stage-blind by construction —
  ADR-001 retired per-stage scope — and that is an accepted, documented change, not a
  silent one.
- **Exit criterion:** (a) a parameterized unit test over **ten** fixture shapes — new-true,
  new-false, legacy-fbw-true, legacy-fbw-false, legacy-scope-execute, legacy-scope-empty,
  legacy-scope-plan-only, empty, malformed-`enabled`-string, disagreeing-mixed — asserting
  the exact boolean plus which diagnostic fired; (b) a **structural test** that fails if any
  module other than the single compat function reads `worktree.enabled` /
  `feature_branch_workflow` / `scope` from a harness YAML **or calls `_scope_includes`
  outside rung 3** (the original wording missed `_cli_create`, which reads no YAML itself —
  it calls a helper); (c) a **runtime** test, not a grep: in a tmp git repo rendered ON,
  `hm worktree create execute <base>` prints a real path and that directory exists; rendered
  OFF, it prints empty. Existing `tests/unit/test_worktree*.py` green.
- **Risk:** medium — a wrong precedence order silently changes the git model
- **Rollback point:** Phase 1

### Phase 3 — ADR-003: the disable choke point

- **depends_on:** `[2]`
- **parallel_group:** `serial-config`
- **merge_hazards:** `worktree.py` (Phases 2, 6), `cli.py` (Phases 1, 4, 5)
- **Scope — in:** `worktree.disable_preflight`, `worktree.apply_worktree_enabled`, and its
  wiring in `cli.py`
- **Scope — out:** `enablement_preflight` (unchanged); the setters themselves (Phase 4)
- **Work:** Mirror `enablement_preflight`'s structure — reuse `_load_sibling_dirs` so sibling
  discovery cannot drift — probing for live `hm/*` task worktrees, pending
  `.hm-finalize-stash-*`, live `.hm-loop-*` markers, and live registry rows across the
  primary base and every sibling. Wrap it in `apply_worktree_enabled(base, answers, desired)`, the
  single function permitted to write the value: it reads the effective value, and on
  `effective and not desired` refuses with a non-zero exit naming the branches and the
  remedy, mutating nothing. Route the one existing producer (the preset flip) through it,
  **and refactor Phase 1's direct preset-rebuild write** (`cli.py`, today
  `:391 a.worktree["feature_branch_workflow"] = _disk_flag`) to go through
  `apply_worktree_enabled` — Phase 1 had to write it directly because this function did not
  exist yet, and leaving it is what would make exit criterion (d) unsatisfiable.
- **Exit criterion:** integration tests — (a) tmp repo with a live task worktree + a
  true→false attempt → non-zero exit, message names the branch, `harness.yaml` **byte
  identical**; (b) clean repo → flips with a notice; (c) false→true is unaffected and still
  goes through `enablement_preflight`; (d) a structural test asserts **zero** direct assignments to
  `answers.worktree["enabled"]` in `cli.py` **and** `interview.py`, and **exactly one** in
  `worktree.apply_worktree_enabled`. ("Exactly one across `cli.py` and `interview.py`" was
  arithmetically wrong — once every producer is routed, the correct count in those two
  modules is zero, since the assignment lives in `worktree.py`.)
- **Risk:** medium
- **Rollback point:** Phase 2

### Phase 4 — Setters: interview question, CLI flags, `/hm:configure` dimension

- **depends_on:** `[3]`
- **parallel_group:** `serial-config`
- **merge_hazards:** `interview.py` (Phases 1, 5), `cli.py` (Phases 1, 3, 5)
- **Scope — in:** `interview.py` (new `_ask_worktree`), `cli.py`
  (`--worktree/--no-worktree`), `templates/commands/hm/configure.md.j2`
- **Scope — out:** migration (Phase 5)
- **Work:** Add the question after preset/dev_mode, defaulting from the preset and stating
  ADR-004's cost in the OFF option text. Add the flags. Add the configure dimension with
  benefit / trade-off / re-render impact / preservation lines matching the file's format.
  **Every one of these routes its desired value through `apply_worktree_enabled`** — none
  writes the key directly. Note that `/hm:configure` is a **markdown dispatcher**, not an
  independent producer: it collects intent and shells out to `hm make --update <flags>`, so
  its guard coverage is inherited from the `--no-worktree` row. Its row in the table-driven
  test asserts the *dispatched command string*, not a separate write path — do not try to
  build guard logic into prose.
- **Exit criterion:** `hm make <tmp> --autoloop --preset Side --worktree` renders
  `enabled: true`; `--preset Production --no-worktree` renders `enabled: false`; the rendered
  `configure.md` contains the new dimension. Plus the **table-driven guard test**: for each
  of the four producers (preset flip, CLI flag, interview answer, configure dispatch),
  attempting true→false with live state is refused (codex `f05fbadd`, antigravity `78c0b80c`).
- **Risk:** low
- **Rollback point:** Phase 3

### Phase 5 — ADR-006: existing-harness migration

- **depends_on:** `[4]`
- **parallel_group:** `serial-config`
- **merge_hazards:** `cli.py` (Phases 1, 3, 4), `interview.py` (Phases 1, 4)
- **Scope — in:** the migration branch in `cli.py` + the interactive prompt in `interview.py`
- **Scope — out:** the disable choke point itself (Phase 3) — migration is a *caller* of it
- **Work:** Implement ADR-006's three-way split: rung-2 present → preserve the bool exactly
  and silently; rung-2 absent with rung-3 true → ask when interactive, else `false` + one
  loud stderr notice naming the change and `--worktree`; nothing present → preset default.
  Route the value through `apply_worktree_enabled` so a migration cannot strand live state.
  Retire the now-unreachable `bool(a.worktree.get("enabled"))` gate that made
  `enablement_preflight` unreachable for Side (F4).
- **Exit criterion:** four integration tests over fixtures — legacy Production
  (`feature_branch_workflow: true`) + non-tty `--update` → **`enabled: true`, no prompt, no
  disable** (the regression test for both models' P0); legacy Side (`scope`-only) + non-tty →
  `enabled: false` **and** the notice on stderr; the same fixture with a tty-mocked ask →
  the answered value; a legacy Production fixture with a live worktree + a forced disable →
  refused.
- **Risk:** medium
- **Rollback point:** Phase 4

### Phase 6 — ADR-005: OFF renders no worktree surface

- **depends_on:** `[3, 5]`
- **parallel_group:** `serial-templates`
- **merge_hazards:** `execute.md.j2` and `loop.md.j2` are large and heavily cross-referenced;
  do not run concurrently with any other template work
- **Scope — in:** `templates/stages/execute.md.j2`,
  `templates/commands/hm/{loop,loop-p5-batch}.md.j2`,
  `templates/skills/worktree-isolator/SKILL.md.j2`,
  **`templates/agents/_partials/{pf_intro,worktree_preflight}.md.j2`**, and the key rename in
  the six already-gated stage templates. The two `_partials/` files carry **prose**, not Jinja
  expressions — `pf_intro.md.j2:6` renders the literal sentence *"`harness.yaml
  worktree.feature_branch_workflow` is **on**:"* into the preflight block of all seven ON
  stage commands, and `execute.md.j2:403` has the same class inside a file that is in scope
  but whose rename item only covers the expression. After the rename these would instruct the
  reader to check a key that no longer exists. `AGENTS.md.j2` moved to **Phase 1** (its
  breakage begins the moment `scope` stops rendering).
  `AGENTS.md.j2:32` renders `config.worktree.scope | join(', ') if … else 'execute'` — once
  Phase 1 drops `scope`, the `is defined` guard silently falls back to the literal
  `'execute'`, so every Codex-target `AGENTS.md` would assert *"Worktree isolation: execute"*
  including on OFF harnesses. No crash, no failing test, a false statement in the Codex
  entry-point instructions. Before Phase 1 lands, sweep for any other `config.worktree.*`
  template reference.
- **Scope — out:** `worktree.py` (the Python finalize/stash implementation is untouched)
- **Work:** Widen the existing `{% if %}` in `execute.md.j2` so the flag-off Step 0 block and
  the finalize/stash/post-commit-pop sections render only when ON. Gate the two loop
  templates' `worktree create execute`. Rewrite the skill to `worktree.enabled` and render it
  only when ON. Rename `config.worktree.get('feature_branch_workflow')` →
  `config.worktree.get('enabled')` in the six gated stage templates.
- **Why last:** this phase removes the only rendered recovery instructions for stranded
  state. It lands only after Phase 3's guard makes stranding unreachable and Phase 5's
  migration is guard-routed.
- **Exit criterion:** three assertions, not two —
  OFF → `rg -c 'worktree' <rendered>/commands/hm/execute.md` is 0 and no rendered command
  contains `worktree create` or `task-preflight`;
  ON → all seven stage commands contain exactly one `task-preflight` and `execute.md` still
  contains the finalize and post-commit-pop sections;
  **behavioral** → on a tmp repo rendered ON, run the rendered finalize + post-commit-pop
  command sequence against a real worktree carrying a deferred stash and assert the stash is
  **restored**. This is what actually distinguishes "Phase 6 gated correctly" from "Phase 6
  also deleted recovery from ON" — assertion 2 is still a grep, and codex `f040cd9b`'s point
  is that the grep assertions pass most cleanly exactly when recovery has just been deleted.
  A refusal test does **not** substitute here: it exercises Phase 3's guard, not this phase's
  `{% if %}` boundaries, and it already lives in Phase 4's table;
  **AGENTS.md** → the Codex-target render states isolation ON/OFF matching the flag.
- **Risk:** high
- **Rollback point:** Phase 5

### Phase 7 — Docs, fixtures, sweep

- **depends_on:** `[1, 2, 3, 4, 5, 6]`
- **parallel_group:** `serial-docs`
- **merge_hazards:** none (documentation and regenerated fixtures only)
- **Scope — in:** `docs/HOW-IT-WORKS.md`, `docs/HOW-IT-WORKS.ko.md`, this repo's `CLAUDE.md`
  (§Multi-session worktree, §사용자 하네스 구조), `CHANGELOG.md`, `tests/e2e/sandbox*`
- **Scope — out:** source code
- **Work:** Replace every `worktree.scope` instruction with `worktree.enabled`. Document
  ADR-004's cost where the option is described, and ADR-006's migration matrix. Regenerate
  the e2e fixtures.
- **Exit criterion:** the sweep is **split by ownership**, because a single tree-wide grep
  cannot both "fail on anything else" and respect this phase's `Scope — out: source code`:
  - **Here (docs only):** `rg 'worktree\.scope|branch_prefix|feature_branch_workflow' docs/ CLAUDE.md README.md`
    returns nothing but the CHANGELOG migration entry.
  - **Phase 2 owns `src/harness_maker/*.py`** (it already owns `worktree.py` +
    `readiness.py`): after it, the only surviving hits are the reader's own rungs
    (`worktree.py:3635`–`:3657`), `_scope_includes` + its docstring (`:2304`–`:2305`), the
    deprecated alias, the module docstring at `:13`, `enablement_preflight`'s docstring at
    `:988` (**not** the reader — the earlier label was wrong), the caller at `:2967`
    (**add this to Phase 2's consumer table** — it is behavior-bearing and was missing), and
    the deliberately-unrewritten historical notes in `economics.py:249` /
    `economics_source.py:94`. Comment-only text in `cli.py:400/1252/1266` and
    `interview.py:864/865/873` is updated in place as part of the same phase.
  - **Phase 6 owns `src/harness_maker/templates/`** via its prose-inclusive sweep.
  Full `uv run pytest` green.
- **Also sweep:** this repo's CLAUDE.md documents `harness.yaml.worktree.cleanup` (default
  `on_success`) — a **fifth** phantom knob no preset template has ever rendered. It is
  outside this PLAN's four-key framing and outside the grep pattern; record it as a known
  pre-existing doc error with a one-line note rather than silently leaving it to read as
  configurable.
- **Risk:** low
- **Rollback point:** Phase 6

---

## 🧪 Testing Strategy

**Unit**
- `_preset_extras` per preset (Phase 1).
- `answers_from_harness_yaml` over every harness generation, including bool-strictness on a
  `"false"` string (Phases 1, 2).
- `worktree_enabled` precedence over **ten** fixture shapes (new-true, new-false,
  legacy-fbw-true, legacy-fbw-false, legacy-scope-execute, legacy-scope-empty,
  legacy-scope-plan-only, empty, malformed-`enabled`-string, disagreeing-mixed), asserting
  the boolean *and* which diagnostic fired (Phase 2).
- Structural: no module outside the single compat function reads `worktree.enabled` /
  `feature_branch_workflow` / `scope` from a harness YAML, **and no caller of
  `_scope_includes` exists outside rung 3** (Phase 2).
- Structural: exactly one call site assigns `answers.worktree["enabled"]` on the path to
  `synthesize`, scanned across `cli.py` **and** `interview.py` (Phase 3).
- `disable_preflight` per live-state category, primary and sibling (Phase 3).
- Structural: `cli.py` writes `worktree.enabled` only via `apply_worktree_enabled` (Phase 3).

**Render / snapshot**
- Both presets' `harness.yaml` block is exactly one key (Phase 1).
- The V3 round-trip: hand-edit survives `--update` (Phase 1). This is the regression test for
  the original defect and must assert on the re-rendered file, not on the template.
- Precedence cross-product {interactive, `--reinterview`, `--update`, `--preset` switch} ×
  {explicit true, explicit false} (Phase 1).
- ADR-005 triple assertion (Phase 6): OFF has zero worktree surface; ON retains finalize and
  post-commit-pop; and the **behavioral** one — the rendered finalize + post-commit-pop
  sequence restores a real deferred stash. The refusal test is deliberately **not** here: it
  exercises Phase 3's guard, not Phase 6's `{% if %}` boundaries, and it lives in Phase 4's
  producer table. A reader who writes the refusal test instead of the stash-restoration test
  ships a green Phase 6 with recovery deleted from ON.
- Codex-target `AGENTS.md` states the isolation mode matching the flag, ON and OFF (Phase 1).

**Runtime** (`tmp` git repo — these exist because the corresponding grep tests are known to
pass while the behavior is broken)
- ON render → `hm worktree create execute <base>` prints a real path and the directory
  exists; OFF render → empty (Phase 2). This is the R11 regression.
- ON render → the rendered finalize + post-commit-pop sequence restores a real deferred
  stash (Phase 6). This is the R13 regression.

**Integration** (`tmp` git repo, real CLI)
- Flag precedence: `--worktree` beats `harness.yaml` beats preset default (Phase 4).
- **Table-driven guard**: every true→false producer (preset flip, CLI flag, interview answer,
  configure dispatch, migration) is refused with a byte-identical `harness.yaml` when live
  state exists (Phases 3–5). This table is the standing regression for both models' P0 — a
  new producer added later without a row is the failure mode it exists to catch.
- Migration matrix: legacy-Production non-tty preserves `true`; legacy-Side non-tty writes
  `false` + notice; tty ask-path honors the answer (Phase 5).

**Manual**
- Run `/hm:plan` in a freshly generated Side(OFF) project and confirm `git status` shows the
  deliverable as expected uncommitted dirt with no worktree created — the ADR-004 contract.
- Run the same in Side(ON) and confirm the base stays clean.

Per project policy, the full suite runs in the background (~6 min); do not poll for it.

---

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Phase 6's `{% if %}` widening drops `finalize`/`post-commit-pop` from an ON harness → uncommitted work lost on the legacy path | medium | high | Phase 6 asserts their **presence** in the ON render, not only their absence in OFF |
| R2 | A disable path added later bypasses the guard and strands live state | medium | high | ADR-003's single choke point + the table-driven producer test; `cli.py` may not write the key directly (structural test) |
| R3 | An existing Production harness is silently disabled by a scripted `--update` | medium | high | ADR-006 rung-2 exact preservation; Phase 5's first integration test is exactly this case |
| R4 | Reader precedence inverted, or a malformed value falls through to a stale rung → wrong git model | low | high | Phase 2's first-match-wins chain with stop-on-malformed and present-`scope`-terminates, over ten fixture shapes |
| R5 | A second reader diverges from `worktree_enabled` → `/hm:health` reports a different mode than the one executing | medium | medium | Phase 2 redirects `readiness.py:643` and `_scope_includes`; a structural test forbids new direct readers |
| R6 | Deleting `_scope_includes` strands un-re-rendered harnesses | low | high | ADR-001 explicitly retains it; Phase 7's sweep whitelists it |
| R7 | A preset switch clobbers an explicit `worktree.enabled` (the V5 mechanism, re-applied to the new key) | medium | medium | Phase 1's preset-rebuild preservation + the precedence cross-product test |
| R8 | `worktree.enabled` name collides with the retired answers-side key in a hand-crafted or copied file | low | medium | No renderer output ever contained it; ADR-007's disagreement warning makes the collision visible |
| R9 | Disable refusal breaks a scripted `--preset Side` / `--no-worktree` in someone's CI | low | low | Intended and loud; the message prints the exact unblocking commands |
| R10 | `cli.py` is touched by Phases 1, 3, 4, 5 → merge conflicts | high | low | All four are `serial-config`; no parallel execution |
| R11 | Dropping `scope` makes `_cli_create` (`worktree.py:2529`) return empty on a fresh **ON** harness → total silent isolation loss on Production, with every grep test passing | **was certain before the fix** | critical | The redirect ships **inside Phase 1's atomic commit** (a `depends_on: [1]` phase lands after, leaving a green-and-broken window) and is asserted at **runtime** — `create execute` returns a real path — not by grep |
| R12 | `templates/codex/AGENTS.md.j2:32`'s `is defined` fallback silently prints "Worktree isolation: execute" on OFF harnesses | high | medium | Moved into Phase 1's atomic commit (it breaks the moment `scope` stops rendering) with an ON/OFF render assertion |
| R14 | Prose mentions of the retired key survive the rename and instruct readers to check a nonexistent key | high | low | Phase 1's pre-change sweep and Phase 6's scope both use the **literal-name** pattern over `templates/`, not `config.worktree.*` — the latter finds Jinja expressions only and misses `_partials/pf_intro.md.j2:6` and `execute.md.j2:403` |
| R13 | A grep-only ON assertion in Phase 6 passes precisely when recovery has been deleted | medium | high | Phase 6's behavioral exit criterion runs the rendered finalize + post-commit-pop against a real deferred stash and asserts restoration |

---

## ✅ Success Criteria

- [x] A generated Side harness contains exactly `worktree:\n  enabled: false`; Production
      contains `enabled: true`. No `scope`, no `branch_prefix`, no `feature_branch_workflow`.
- [x] Hand-editing `worktree.enabled` survives `hm make --update` (the V3 regression).
- [x] `hm make --preset Side --worktree` and `--preset Production --no-worktree` both work,
      and the same choice is reachable from the interview and `/hm:configure`.
- [x] A Side(OFF) render contains no worktree vocabulary in any command; a Side(ON) render
      isolates all seven stages and retains finalize + post-commit-pop.
- [x] **Every** true→false producer (preset flip, `--no-worktree`, interview answer,
      `/hm:configure`, migration) is refused when live state exists, naming the branch and
      leaving `harness.yaml` byte-identical.
- [x] A legacy Production harness (`feature_branch_workflow: true`) re-rendered
      non-interactively keeps `enabled: true` — it is never silently disabled.
- [x] A legacy `scope`-only harness re-rendered non-interactively becomes `enabled: false`
      and emits the behavior-change notice; re-rendered interactively, it asks.
- [x] A malformed `enabled` value fails loudly and never falls through to a stale legacy key;
      a disagreeing mixed-generation block warns.
- [x] `/hm:health` and the execution path can never report different modes — one reader,
      enforced structurally.
- [x] An un-re-rendered legacy harness still resolves to its current behavior at runtime,
      with one recorded exception: `worktree create <non-execute-stage>` on a rung-3
      harness (nothing in the shipped templates calls it — RESEARCH F5 — and `_cli_create`
      keeps honoring `stage` for rung-3 shapes, so the exception is documented, not silent).
- [x] On a freshly-rendered **ON** harness, `hm worktree create execute` returns a real
      worktree path — asserted at runtime, not by grep. (The `scope` removal would otherwise
      make it return empty, which every rendered command reads as "no isolation".)
- [x] A Codex-target `AGENTS.md` states the isolation mode matching the flag, ON and OFF.
- [x] `rg 'worktree\.scope|branch_prefix|feature_branch_workflow' src/ docs/` returns only
      the legacy-reader sites and the CHANGELOG entry.
- [x] Full `uv run pytest` green; `ruff check`, `ruff format --check`, `mypy --strict` clean.

**Explicit non-goals** (decided, not deferred):
- `worktree.cleanup` — a fifth phantom knob documented in this repo's CLAUDE.md that no
  template has ever rendered. Recorded as a pre-existing doc error in Phase 7, not fixed.
- `/hm:health` worktree signals (Interview #4) — RESEARCH V6 remains open as a follow-up.
- `<WT>`-prefixing the deliverable write instructions (RESEARCH V8) — a Production-path
  concern; the reported dirty base was Side.
- Any change to the 5-layer defense, the session registry, `task-land`, or the finalize
  Python implementation.

---

## 🔍 Plan Validation

**Outcome: NEEDS_REVISION_RESOLVED** (validator pass 2 of 2 — the stage permits one re-run).

### Round 1 — `plan-validator`: MAJOR_REVISION (2 critical, 5 warning, 2 suggestion)

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | critical | `_cli_create` (`worktree.py:2529`) gates on `_scope_includes`; dropping `scope` makes `worktree create execute` print empty on a fresh **ON** harness, which every rendered command reads as "no isolation". Every grep test in the PLAN would pass. | Redirect moved **into Phase 1's atomic commit**; consumer table names the site; exit criterion is a **runtime** assertion; structural test widened to `_scope_includes` callers. R11. |
| 2 | critical | The `apply_worktree_enabled` choke point's layer was unspecified and its enforcement test scoped to `cli.py`, while `interview.py` also sets the key and the disk write is `synthesize.py:769` → Jinja. | Layer pinned to the resolved `InterviewAnswers.worktree` immediately before `synthesize`; upstream assembly declared a proposal; structural test scans `cli.py` + `interview.py` + `worktree.py`. |
| 3 | warning | Rung 3 had no False branch; `scope: []` / `scope: [plan]` unclassified in ADR-006. | Rung 3 terminates on a present `scope`; ADR-006 gains a fourth row (`false`). |
| 4 | warning | `templates/codex/AGENTS.md.j2:32` in no phase's scope. | Moved into Phase 1 (it breaks at the same commit). R12. |
| 5 | warning | Phase 7's grep criterion unsatisfiable; `readiness.py:698/702` names a retired key to the user. | Sweep split by ownership (Phase 2 = `src/*.py`, Phase 6 = templates, Phase 7 = docs); the remediation string moved into Phase 2's code scope. |
| 6 | warning | Phase 6's transition assertion duplicated Phase 4's refusal test; ON recovery still grep-only. | Replaced with a behavioral assertion — the rendered finalize + post-commit-pop restores a real deferred stash. R13. |
| 7 | warning | "Legacy harness keeps current behavior" falsifiable via `_cli_create`'s `stage` argument. | `stage` retained for rung-3 shapes; the criterion records the exception. |
| 8 | suggestion | `/hm:configure` is a CLI dispatcher, not an independent producer. | Stated in Phase 4; its guard coverage is inherited from `--no-worktree`. |
| 9 | suggestion | `worktree.cleanup` is a fifth phantom knob. | Recorded as an explicit non-goal + a Phase 7 doc note. |

### Round 2 — `plan-validator`: NEEDS_REVISION (0 critical, 5 warning, 1 suggestion)

All nine round-1 critiques verified **closed** (one partially — the `readiness.py` half closed,
the grep half re-filed as W2 below). New findings, all resolved in-place without a further
interview round: each is a self-consistency defect in the PLAN text with one defensible
correction, not an architectural choice.

| # | Finding | Resolution |
|---|---|---|
| W1 | `_partials/{pf_intro,worktree_preflight}.md.j2` carry the retired key as **prose**; the prescribed `config.worktree.*` sweep finds Jinja expressions only and structurally cannot see them. | Both files added to Phase 6; both sweeps switched to the literal-name pattern over `templates/`. R14. |
| W2 | Phase 7's whitelist under-enumerated against the real tree, and `worktree.py:988` mislabeled (it is `enablement_preflight`'s docstring). `worktree.py:2967` is a behavior-bearing caller missing from Phase 2's table. | Sweep split by ownership; label corrected; `:2967` added to Phase 2. |
| W3 | Phase 3 exit (d) was arithmetically self-contradictory — "exactly one assignment across `cli.py` and `interview.py`" when the assignment lives in `worktree.py`, so the correct count there is zero. | Restated as zero/zero/exactly-one, plus an explicit Phase 3 item to refactor Phase 1's necessarily-direct preset-rebuild write. |
| W4 | §Testing Strategy stale against the revised phases (duplicate refusal assertion, eight vs ten fixtures). | Re-synced; the behavioral assertion replaces the duplicate and says why. |
| W5 | Phase 2 claimed to "precede Phase 1's effect" while declaring `depends_on: [1]` — leaving a green-and-broken window between the two commits. | Phase 1 marked **atomic** and absorbs the two redirects that break at that commit; the rest of the consolidation stays in Phase 2. |
| S1 | `downgrade_preflight` vs `disable_preflight`; two signatures for the choke point. | One name (`disable_preflight`) and one signature (`apply_worktree_enabled(base, answers, desired)`) across all five places. |

### Cross-model second opinion (Step 4 pre — Production preset, both models mandatory)

```
second_opinion_results:
  - model: codex        status: invoked   findings: 9 (1 P0, 5 P1, 2 P2, 1 P3)
  - model: antigravity  status: invoked   findings: 4 (2 P0, 1 P1, 1 P2)
```

Both models independently produced the **same two P0s**, and both were real:

1. **ADR-003 was bound to the wrong transition boundary** (codex `f05fbadd`, antigravity
   `78c0b80c`) — the guard covered the preset flip only, while ADR-002 adds three more
   false-setting paths and ADR-006 a fifth, and ADR-005 deletes the recovery surface.
   → rewritten to one `apply_worktree_enabled` choke point owned by the *transition*.
2. **ADR-006's non-interactive `false` silently disabled legacy Production harnesses**
   (codex `26f76a6d`, antigravity `810bad1d`) — they carry an explicit
   `feature_branch_workflow: true` and my "no `enabled` key" condition swept them up.
   → split by rung; an explicit prior bool is now preserved exactly and silently.

Validator reconciliation of all 13 injected findings: 9 `addressed`, 4 `partially-addressed`
in round 1; every partial closed in round 2. Full dispositions are in the round-1 and round-2
validator returns.

**Two findings originated with the validator, not the models** — the `_cli_create` gate
(critical #1) and the choke-point layer (critical #2). The first is the single most severe
defect found anywhere in this planning cycle: it would have shipped Production with zero
isolation while every test the PLAN specified passed.
