---
type: research
task_slug: worktree-side-defaults
status: complete
created: 2026-08-05
tags: [harness-maker, research, python, worktree, preset, config-axis, side-preset]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[PLAN-worktree-cross-session-data-loss-defense]]", "[[PLAN-multisession-worktree-concurrency]]", "[[PLAN-worktree-deliverable-blocks-create]]", "[[PLAN-worktree-base-artifact-pollution]]"]
summary: "worktree axis is 3/4 dead; Side's enabled:false is inert; +3 new defects found by sandbox test"
---

# RESEARCH — worktree config axis, Side defaults, and base-dirty deliverables

## 🎯 Recommended Direction

**Collapse the worktree config axis to one live, config-driven boolean and expose it.**
Today the axis has four knobs (`enabled`, `scope`, `branch_prefix`,
`feature_branch_workflow`) of which **exactly one** (`feature_branch_workflow`, plus the
single literal `execute` inside `scope`) has runtime effect. `enabled` is never rendered
and never read; `branch_prefix` is documented dead; `scope`'s `plan` element has no call
site. Meanwhile `scope` and `branch_prefix` are **hardcoded literals** in both preset
templates, so a user hand-edit is silently reverted on every `/harness-maker:make`.

All three of the user's observations are the same root defect — **the worktree block is
written by the preset template, not by the config object** — plus one intrinsic
consequence:

| Observation | Verdict |
|---|---|
| "is there a default-disable for worktree?" | **No.** No interview question, no CLI flag, no `/hm:configure` dimension. The one answer that exists (`worktree.enabled`) is inert. |
| "Side defaults to `scope: [execute]`" | **Confirmed, and it contradicts Side's own answer** (`enabled: False`). Side gets execute isolation ON. |
| "plan docs keep making main dirty" | **Real, but not Side-specific** — it is `feature_branch_workflow`-off-specific. Production defaults the flag ON so it never shows there. |
| "generated project has no feature-branch setting at all" | **Confirmed by committed artifact + sandbox render.** Side never emits the key, and never auto-migrates. |

Sandbox testing of both presets (V1–V8 below) reproduced all four and surfaced three
more the user did not ask about: a **silent Production→Side downgrade** off the
feature-branch model (V5), **zero worktree signals in `/hm:health`** (V6), and
**un-`<WT>`-prefixed deliverable write instructions that dirty the base in Production
too** (V8).

---

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary) — the question is
about this repo's own render pipeline and config round-trip, so codebase evidence is
authoritative. Secondary lens: **Risk** (the axis governs git-mutation safety). No
user-workflow or academic lens: the topic is not trend/roadmap-shaped, and no external
source can answer "what does this template emit".

`--deep` not set → Phase 0/0.5 interview skipped.

---

## 🛠️ Approaches Found

### Findings first (evidence for all three approaches)

**F1 — `scope` / `branch_prefix` are template literals, not config.**
`templates/harness-yaml/Side.yaml.j2:76-81` and `Production.yaml.j2:76-81`:

```jinja
worktree:
  scope: [execute]            # Production: [execute, plan]
  branch_prefix: hm-
{%- if 'feature_branch_workflow' in config.worktree %}
  feature_branch_workflow: {{ config.worktree['feature_branch_workflow'] | tojson }}
{%- endif %}
```

Only `feature_branch_workflow` reads `config`. Combined with
`reconcile.py:161-165` — *harness.yaml is **always** REPLACE* — a hand-edited
`scope: []` is overwritten back to `[execute]` on the next re-render. This is a
checklist-#1 violation (user-state preservation contract) and a checklist-#6 violation
(the round-trip mapper `answers_from_harness_yaml` cannot preserve a key the template
never sources from `config`).

**F2 — `worktree.enabled` is 100% inert.**
`interview.py:1323` gives Side `{"enabled": False}`; `interview.py:1343` gives Production
`{"enabled": True, "feature_branch_workflow": True}` (verified live:
`_build_answers(preset=SIDE).worktree == {'enabled': False}`). But no template emits
`enabled`, and no runtime reader looks for it — `grep` over `worktree.py` /
`readiness.py` for `.get("enabled")` on a worktree dict returns nothing. Its **only**
consumer is `cli.py:431` (`bool(a.worktree.get("enabled"))`), the migration gate. So:

- Side answers "worktree off" → the rendered harness still says `scope: [execute]`
- `worktree._scope_includes(harness.yaml, "execute")` reads that from disk → **True**
- `/hm:execute` Step 0 fires `worktree create execute` → **isolation is ON in Side**

**F3 — Side can structurally never emit `feature_branch_workflow`.**
Side's preset extras have no such key → the `{%- if 'feature_branch_workflow' in
config.worktree %}` guard is False → the key is absent from disk →
`worktree._feature_branch_workflow_enabled()` (`worktree.py:3635-3664`) hits its
conservative absent-key branch, returns `False`, and prints the one-shot stderr warning
*"…absent or non-boolean → defaulting to the old (non-feature-branch) model."*

Committed proof, not inference — `tests/e2e/sandbox/.claude/harness.yaml:93` and
`tests/e2e/sandbox-plugin-test/.claude/harness.yaml:93` are both `preset: Side` and both
contain exactly:

```yaml
worktree:
  scope: [execute]
  branch_prefix: hm-
```

This is verbatim what the user reported seeing in their generated project.

**F4 — and Side can never auto-migrate out of it.**
`cli.py:427-445` gates the make-time enablement preflight on
`bool(a.worktree.get("enabled"))`. Side is `False`, so the flip is skipped
unconditionally — even on a pristine clean-live-state repo. The stated reason
(`interview.py:1339-1342`) is that the flag "is inert without worktree isolation", which
is only true if `enabled` meant anything — and per F2 it does not. The comment and the
rendered reality disagree.

**F5 — `scope`'s `plan` element is dead config.**
Every `worktree create` call site in `templates/` passes the literal stage `execute`
(`stages/execute.md.j2`, `commands/hm/loop.md.j2`, `commands/hm/loop-p5-batch.md.j2`,
`skills/worktree-isolator/SKILL.md.j2`). Nothing ever calls `worktree create plan`, and
`stages/plan.md.j2`'s flag-**off** branch has no isolation step at all — the preflight
at line 73 is gated purely on `feature_branch_workflow`. So Production's `[execute,
plan]` behaves identically to `[execute]`. Under flag-**on**, `scope` is ignored
entirely: every stage template (`research`/`spec`/`plan`/`execute`/`review`/`verify`/
`wrapup`) renders `task-preflight` keyed only on the flag.

`branch_prefix: hm-` is likewise self-documented as dead —
`worktree-isolator/SKILL.md.j2:102` says *"reserved for Phase 9 (currently
informational)"*, and the real branch naming is `hm/<slug>` (slash, not dash).

**F6 — base-dirty is flag-off-intrinsic, not Side-specific.**
Under `feature_branch_workflow: true`, *every* `/hm:` stage runs inside
`.worktrees/<slug>/` on `hm/<slug>`, so `RESEARCH-*.md` / `SPEC-*.md` / `PLAN-*.md` /
`REVIEW-*.md` land on the task branch and base `main` stays clean until wrapup
squash-lands. Under flag-off there is no plan/research/spec/review isolation at all
(F5), so those deliverables are written straight to the base working tree and sit there
uncommitted until `/hm:wrapup` stages them.

That is *by design*, not an accident: deliverables are deliberately excluded from
`_HARNESS_CHURN_PREFIXES`/gitignore (wrapup commits them), and
`worktree._is_deliverable_path` (`worktree.py:147-153`) exists precisely so the
create-guard **forgives** them — otherwise every plan→execute would self-block. The
finalize filter does *not* forgive them, so they stay stash-preserved.

Consequence for the user's ask: **"disable worktree in Side" and "main not dirty" pull in
opposite directions.** No isolation ⇒ the docs have nowhere to live but the base tree.

**F7 — no supported way to change any of this.**
No worktree question in `interview.py`; no worktree override in
`cli._apply_dimension_overrides` (`cli.py:1110-1129` — the docstring lists `worktree`
only as a *preset-coupled rebuild*, not a user knob); no worktree entry in
`/hm:configure`'s multi-select dimension list
(`templates/commands/hm/configure.md.j2:31-72`). Yet `docs/HOW-IT-WORKS.md:1344` and
`:500` instruct the reader to "check `harness.yaml.worktree.scope`" as if it were
settable.

**Available workaround today (verified by code path, not run):** hand-editing
`feature_branch_workflow: true` into a Side `harness.yaml` **does** survive re-render —
`interview.answers_from_harness_yaml` (`interview.py:861-881`) overlays the on-disk
`worktree` dict onto the preset default and keeps the key when it is a real bool
(`interview.py:877`, bool-strict). Editing `scope` does **not** survive (F1).

---

### Approach A — Make the worktree block config-driven (minimal correctness fix)

| Field | Content |
|---|---|
| Approach | Emit `scope` (and drop or emit `branch_prefix`) from `config.worktree` in both preset `.j2`; add `worktree.scope` to Side/Production preset extras. |
| Assumption | The four-knob axis is worth keeping; only its plumbing is broken. |
| Evidence | F1, F7. Purely a template + preset-extras change; `answers_from_harness_yaml` already round-trips the whole `worktree` dict (F7 workaround note). |
| Trade-off | Cheapest and lowest-risk, but preserves three knobs that do nothing (F2, F5) — the confusion the user hit survives. |
| Compatibility | High. No runtime reader changes; `_scope_includes` already reads whatever is on disk. |
| Risk | **low** |

### Approach B — Approach A + make Side explicit (`feature_branch_workflow: false`)

| Field | Content |
|---|---|
| Approach | A, plus put `feature_branch_workflow: False` in Side's preset extras so the key is always present, and re-gate `cli.py`'s migration preflight on something real. |
| Assumption | The absent-key state is the actual defect; an explicit `false` is a decision the system should respect. |
| Evidence | F3, F4. The stderr warning fires on every Side project today; the absent-case is exactly the global CLAUDE.md "absent-case = feature black hole" pattern (count:8). |
| Trade-off | Silences the warning and makes Side's intent legible, but **locks Side out of the feature-branch model permanently** — an explicit `false` is respected by `cli.py:432`'s key-absent gate, so the auto-migration can never fire. Needs a deliberate opt-in path (`/hm:configure`) to compensate. |
| Compatibility | Medium — changes what existing Side re-renders emit. |
| Risk | **medium** |

### Approach C — Collapse to one axis + expose it (recommended)

| Field | Content |
|---|---|
| Approach | Retire `enabled` / `branch_prefix` / `scope` (or reduce `scope` to a derived value). Keep `worktree.feature_branch_workflow` as the single live boolean: `true` = per-task branch + all stages isolated, `false` = no isolation anywhere. Always emit it (Side `false`, Production `true`). Add a `Worktree isolation` dimension to `/hm:configure` and a `--worktree/--no-worktree` CLI flag, wired through `_apply_dimension_overrides`. |
| Assumption | Users want one comprehensible on/off, not a scope matrix. Supported by the fact that 3 of 4 knobs already do nothing. |
| Evidence | F2, F5, F7 — the collapse mostly *documents reality* rather than removing capability. |
| Trade-off | Largest blast radius: touches both preset templates, `execute.md.j2`'s flag-off branch, `worktree-isolator/SKILL.md.j2`, `loop.md.j2`, `_scope_includes`, `docs/HOW-IT-WORKS*.md`, and the e2e sandbox fixtures. Needs a migration for harnesses whose `scope` a user believed in. |
| Compatibility | Medium — `_scope_includes` must keep reading legacy `scope` for un-re-rendered harnesses. |
| Risk | **medium-high** |

**Recommendation: C**, with A as the mechanical first phase. Rationale: A alone fixes the
hand-edit-reversion bug but leaves a user staring at three inert keys and the same
"뭔가 많이 잘못된 듯" reaction. C is the only option that makes the rendered config
describe what the system actually does. This is informational — `/hm:plan` decides.

**Note the trade-off C does *not* resolve:** turning isolation off in Side means plan
deliverables land in the base tree (F6). If the user wants both, that needs a separate
decision (see Open Questions Q3).

---

## 🧪 Sandbox verification (both presets, end-to-end)

Two throwaway git repos were rendered with the real CLI
(`python -m harness_maker.cli make <dir> --autoloop --preset {Side,Production}
--targets claude-code --locale en --dev-mode task-driven`) and probed. Every row below
is an observed result, not an inference.

### V1 — Rendered `worktree:` block

| Preset | Rendered block | `_scope_includes(execute)` | `_scope_includes(plan)` | `_feature_branch_workflow_enabled` |
|---|---|---|---|---|
| Side | `scope: [execute]`, `branch_prefix: hm-` | **True** | False | **False** + stderr warning |
| Production | `scope: [execute, plan]`, `branch_prefix: hm-`, `feature_branch_workflow: true` | True | True | True |

Side's interview answer is `{'enabled': False}` yet execute isolation reads **True** —
F2 reproduced end-to-end.

### V2 — Which stages actually isolate

`grep -c` over the seven rendered `.claude/commands/hm/*.md`:

| Stage | Side `task-preflight` | Side `worktree create execute` | Production `task-preflight` |
|---|---|---|---|
| research / spec / plan / review / verify / wrapup | **0** | 0 | **1** each |
| execute | 0 | **1** | 1 |

**This is the dirty-main mechanism, measured.** Under Side, six of seven stages have no
isolation step at all, so every deliverable they write lands in the base working tree.
Production isolates all seven.

### V3 — Hand-edit round-trip (`--update`)

Edited a Side `harness.yaml` to `scope: []` **and** `feature_branch_workflow: true`, then
re-rendered with `make --update`:

| Key | Before | After re-render | Verdict |
|---|---|---|---|
| `scope` | `[]` | **`[execute]`** | **silently reverted** — no warning, no message (F1 reproduced) |
| `feature_branch_workflow` | `true` | `true` | **survived** — the workaround is real |

After the surviving flag, all four checked stages (`research`/`plan`/`execute`/`wrapup`)
re-rendered **with** `task-preflight` and Side behaved exactly like Production. So a Side
project *can* run the feature-branch model — just not through any supported interface.

### V4 — Migration never fires for Side

A pristine, fully-committed, clean-live-state Side repo re-rendered with `make --update`:
the `worktree:` block came back byte-identical, no `migrated to the feature-branch
worktree workflow` message, no warning. F4 reproduced: the `enablement_preflight` is
unreachable for Side under every condition.

### V5 — **New finding: preset flip Production→Side silently downgrades the git model**

`make <side2> --preset Production` → block becomes `scope: [execute, plan]` +
`feature_branch_workflow: true`. Immediately flipping back with `--preset Side` →
`feature_branch_workflow` is **dropped with zero output**.

Cause: `answers_from_harness_yaml` round-trips the on-disk `worktree` dict, but
`_apply_dimension_overrides` then rebuilds the preset extras from `_build_answers`
(`cli.py:1131-1139`), and Side's extras have no such key. The **upgrade** direction is
guarded by `enablement_preflight`'s clean-live-state probe; the **downgrade** direction
has no guard at all. A project with live `hm/<slug>` task worktrees flipped to Side is
moved back onto the legacy stash model without being told — the precondition class of
`[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3).

Severity note: this is worse than F4, because F4 only denies a capability while V5 can
strand in-flight state.

### V6 — **New finding: `/hm:health` has zero worktree signals**

`cli health` on both sandboxes: Side `structural=76/100 personalization=88/100`,
Production similar. `grep -i worktree` over both generated
`.claude/observability/dashboard.md` files returns **nothing**. Neither the Side
`enabled:False`/`scope:[execute]` contradiction, nor the absent
`feature_branch_workflow`, nor the V5 downgrade produces any health signal. The only
surface is `_feature_branch_workflow_enabled`'s one-shot stderr line, which appears
mid-command output and is easy to miss — consistent with the user not noticing until now.

### V7 — Side turns isolation on while disabling the skill that documents it

Side's `skills.enabled` omits `worktree-isolator` (Production includes it), yet Side's
`scope: [execute]` makes `/hm:execute` isolate. Not a functional break —
`execute.md.j2` calls the CLI directly *because* skill dispatch is unreliable — but it is
a third instance of the same incoherence: the config says one thing, the render does
another. Side also omits `conditional-router`, `security-scanner`, `context-linter`, and
enables only `code-reviewer`; those are coherent with `security.on_finding.high: warn`
and `max_review_rounds: 2`.

### V8 — **New finding: deliverable write instructions are never `<WT>`-prefixed**

In *both* presets, the concrete write line is bare:
`Write to `work-docs/PLAN-{slug}.md`` (`plan.md:459` prod / `:437` side),
`Write to `work-docs/RESEARCH-{slug}.md`` (`research.md:321`). Only the preflight
preamble's generic sentence — *"Treat that exact string as `<WT>` for every
Read/Write/Edit"* — routes them into the worktree, and only `<WT>`-prefixed **loop**
paths (`plan.md:199`) are explicit.

This is a **second, independent dirty-main mechanism that also applies to Production**:
an LLM that follows the concrete instruction literally writes the deliverable to the
base tree even with the flag on. Worth confirming against the user's actual observation
before assuming the Side axis is the whole story.

### Defaults sanity pass (non-worktree axes)

Side vs Production diff is otherwise coherent: `main_loop.max_rounds` 5/null,
`max_review_rounds` 2/3, reviewers 1/5 enabled, `security.on_finding.high` warn/block,
`spec_gate` warn/block. One item to flag separately: **both** presets rendered
`autonomy.level: "auto_safe"` with `autopilot_persistent: true` — that is the documented
non-tty auto-flip of `--autoloop` (`cli.py:398-402`), not a preset default, but it means
a `--autoloop`-generated Side project auto-arms autopilot every session.

---

## ⚠️ Pitfalls

1. **Do not "fix" the dirty base by teaching the create-guard or the churn filter to
   ignore deliverables harder.** `_is_deliverable_path` already forgives them at
   create-time, and the finalize filter deliberately does *not*, so they stay
   stash-preserved. Widening the finalize filter would make plan documents
   silently droppable — the exact class of the count:3
   `[fail:design] worktree-finalize-pulls-orphan-wip-into-main`.
2. **Do not auto-commit deliverables per stage as a dirty-base workaround without
   path-scoping.** `[wiki:pattern] squash-to-shared-base-must-scope-the-commit-to-its-own-paths`
   and `[fail:design] task-land-squash-commits-whole-index-sweeps-concurrent-base-churn`
   (2026-06-21) record that any bare commit onto a shared base sweeps a concurrent
   session's staged churn into it.
3. **Removing `scope` must keep a legacy reader.** `_scope_includes` is what an
   un-re-rendered user harness still runs through; deleting it strands every project that
   has not run `/harness-maker:make` since.
4. **An explicit `feature_branch_workflow: false` is not the same as an absent key.**
   `cli.py:432` treats explicit values as decisions and skips migration. Approach B
   trades a warning for a permanent lock-out unless a `/hm:configure` opt-in ships in the
   same change.
5. **A render-grep test will not catch F1.** The disk file is *correct* after a render —
   it is correct-and-not-what-the-user-wrote. The regression test must be a
   *round-trip*: write `scope: []`, re-render, assert it survived (global CLAUDE.md
   checklist #2, "preprocessing problems are invisible to file inspection").
6. **`branch_prefix: hm-` does not match the real branch name `hm/<slug>`.** Anything
   that starts honoring it must reconcile the dash/slash mismatch first.

---

## ❓ Open Questions

- **Q1** — Keep the `scope` matrix (A/B) or collapse to one boolean (C)? Binding
  constraint: whether any user has ever meaningfully set `scope` — evidence says no,
  since it was never settable.
- **Q2** — Should Side default to isolation **on** or **off**? Side currently *answers*
  off and *behaves* on (F2). Whichever way the contradiction is resolved changes existing
  Side projects' behavior on next re-render.
- **Q3** — If Side ends up isolation-off, what happens to plan/research deliverables?
  (a) accept an uncommitted base tree until wrapup, (b) auto-commit per stage
  (path-scoped — see Pitfall 2), (c) keep flag-on for Side too and make "disable" mean
  something narrower. **This is the question that decides whether the user's second
  complaint is actually fixed.**
- **Q4** — Migration for existing Side harnesses: does a re-render flip them, warn, or
  leave them alone? `cli.py`'s `enablement_preflight` exists but is unreachable for Side
  (F4).
- **Q5** — Retire `branch_prefix` outright, or implement it? It is dead in both
  directions today.
- **Q6** — Should a Production→Side preset flip be allowed to silently drop
  `feature_branch_workflow` (V5)? Options: refuse with a live-state probe symmetric to
  `enablement_preflight`, warn loudly, or preserve the on-disk flag across preset flips.
- **Q7** — Should `/hm:health` gain a worktree dimension (V6)? Candidate signals:
  `worktree_axis_coherent` (answers vs rendered), `feature_branch_workflow_present`.
- **Q8** — Should every deliverable write instruction be `<WT>`-prefixed (V8)? This is
  independent of the preset axis and would reduce base dirt in Production too. **Ask the
  user which preset they actually observed the dirty main in** — if Production, V8 is the
  primary cause, not the Side axis.

---

## 📚 Sources

No external sources. Every claim above is grounded in this repository at the commit
under `.worktrees/worktree-side-defaults`:

- `src/harness_maker/templates/harness-yaml/Side.yaml.j2:76-81`
- `src/harness_maker/templates/harness-yaml/Production.yaml.j2:76-81`
- `src/harness_maker/interview.py:861-881`, `:1323`, `:1339-1343`
- `src/harness_maker/cli.py:386-445`, `:1110-1140`
- `src/harness_maker/worktree.py:147-153`, `:2302-2312`, `:3635-3664`
- `src/harness_maker/reconcile.py:5-7`, `:161-165`
- `src/harness_maker/synthesize.py:769`
- `src/harness_maker/templates/stages/execute.md.j2:62-85`
- `src/harness_maker/templates/stages/plan.md.j2:73-75`
- `src/harness_maker/templates/skills/worktree-isolator/SKILL.md.j2:17-41`, `:102`
- `src/harness_maker/templates/commands/hm/configure.md.j2:31-72`
- `tests/e2e/sandbox/.claude/harness.yaml:9`, `:93-95`
- `tests/e2e/sandbox-plugin-test/.claude/harness.yaml:9`, `:93-95`
- `docs/HOW-IT-WORKS.md:500`, `:1344`

Live checks run during this research:

- `_build_answers(preset=Side).worktree == {'enabled': False}` /
  `_build_answers(preset=Production).worktree == {'enabled': True, 'feature_branch_workflow': True}`
- Two sandbox renders + probes — see **🧪 Sandbox verification** (V1–V8). Sandboxes live
  under the session scratchpad at `…/scratchpad/sbx1/{side,side2,prod}` and are
  disposable.

---

## 🔗 Related Internal Docs

- `[[PLAN-worktree-cross-session-data-loss-defense]]` — the 5-layer defense that the
  flag-off path still relies on.
- `[[PLAN-multisession-worktree-concurrency]]` — the per-task feature-branch model
  (ADR-001…010) that flag-on activates.
- `[[PLAN-worktree-deliverable-blocks-create]]` — origin of `_is_deliverable_path`;
  directly relevant to Q3.
- `[[PLAN-worktree-base-artifact-pollution]]` — `_HARNESS_CHURN_PREFIXES`, and why
  deliverables are deliberately *not* gitignored.
- `[wiki:pattern] squash-to-shared-base-must-scope-the-commit-to-its-own-paths`
- `[fail:design] task-land-squash-commits-whole-index-sweeps-concurrent-base-churn`
- `[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3)
- `[[project_feature_branch_migration_behavior]]` (auto-memory) — "Side(enabled:False)는
  자동마이그 skip" — independently corroborates F4.
