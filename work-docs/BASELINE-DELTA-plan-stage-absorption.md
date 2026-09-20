# Baseline delta — plan-stage-absorption

Attribution for the surface movement in `PLAN-plan-stage-absorption.md`.
Every figure below was measured by `tests/structural/_surface_baseline.py` against
`865e3ef578f5`, not estimated.

## Measured outcome

Re-measured at each fold as the phases landed — six times in all, the last of them folding the
review round-2 fixes. These are the final figures
from `tests/structural/_surface_baseline.py`, and both ratchets are re-frozen to them in the
same commit. The intermediate numbers are not kept: a delta document that lists a superseded
measurement beside the current one invites a reader to cite the wrong row.

| Target / command | before | after | delta | round trips |
|---|---|---|---|---|
| **`claude` aggregate** | 444697 | **401697** | **−43000 (−9.7%)** | — |
| **`codex` aggregate** | 378032 | **340105** | **−37927 (−10.0%)** | — |
| `claude/execute` | 51627 | 62670 | +11043 | 18 → 25 |
| `codex/hm-execute` | 50501 | 61595 | +11094 | 17 → 24 |
| `claude/spec` | 35251 | 47904 | +12653 | 7 → 12 |
| `codex/hm-spec` | 30733 | 43586 | +12853 | 7 → 12 |
| `claude/plan` | 66702 | **removed** | −66702 | −29 |
| `codex/hm-plan` | 61880 | **removed** | −61880 | — |

**The aggregate went DOWN, and that is the direction this task was for.** It is *smaller*, not
larger — the shipped surface fell 9.7 % on Claude and 10.0 % on Codex. Two commands grew and
one 66,702-char command disappeared. Every other command moved by under 100 characters, all of
it prose retargeted off a stage that no longer exists.

That direction is worth stating plainly because the intermediate measurements pointed the other
way: at the end of Phase 1 the surface was **up** 5,002 chars, exactly as ADR-002 predicted while
both stages still rendered. A reader who stopped there would have recorded a cost-reduction task
as a cost-increase one.

## Who may re-freeze these, and why it is not this task's subject

`render_sha` and `payload_digest` move mechanically — `payload_digest` is a hash over the whole
frozen payload, so it changes whenever any command does, and `render_sha` records the commit the
capture was taken at. Neither carries information of its own; both are recorded here because a
changed key with no attribution row is indistinguishable from an unnoticed one.

**ADR-010** is the rule that both ratchets fold together, and the reason the fold belongs to the
phase that moved the render rather than to a later tidy-up. The failure it guards against is
`ratchet-rebaselined-by-its-own-subject`: a gate whose own subject regenerates it is not a gate,
it is a recording. That is why `comprehension_zero_cost_golden.json` was **restored, not
regenerated**, during this task — its `source_sha` must name a commit where the comprehension
partial did not exist, and re-capturing it at HEAD would have made AC-003 compare `minimal`
against itself. `surface_baseline.json` is the opposite case: this task removed a command
outright, `assert not missing` has no allowance escape, and the re-freeze is forced rather than
chosen.

## The sub-100-character movers, named individually

Every remaining baseline key that moved, so none of them is an unnoticed one. All of it is prose
that named a stage which no longer exists, plus one shared partial:

| Command (both targets) | Movement | Cause |
|---|---|---|
| `help` / `hm-help` | −50 | the `/hm:plan` row left the command table and the pipeline diagram |
| `loop` / `hm-loop` | +71 | `--per-iter-stages` example retargeted to `spec`, stage-name list 7 → 6 |
| `research` / `hm-research` | +41 | "role separation vs `/hm:plan`", the next-stage pointer and the Open-Questions consumer now name `/hm:spec` |
| `review` / `hm-review` | −12 | `second_opinion_dispatch.md.j2`'s caller comment says `"review" \| "spec"` |
| `verify` / `hm-verify` | −32 | Check 6's remediation line points at `/hm:spec <slug>` instead of `/hm:plan` re-entry |
| `wrapup` / `hm-wrapup` | −12 | the autopilot picker interpolates `autonomy.pipeline`, which lost `plan` |
| `execute` / `hm-execute` | +11043 / +11094 | Steps 0, 0.1, 0.2, 0.3 — see the section above |
| `spec` / `hm-spec` | +12653 / +12853 | Step 4.6 — see the section above |
| `render_sha`, `payload_digest` | mechanical | see the ownership section above |

The `wrapup` movement deserves its own note: **no wrapup template was edited.**
`step_manifest.md.j2` interpolates `config.autonomy.pipeline | join(' → ')` into every stage's
autopilot picker, so removing `plan` from the pipeline moved that string in all of them. Tracing
it is what surfaced a second stale copy — the hardcoded fallback pipeline in
`harness-yaml/Production.yaml.j2`, which still listed `plan` for the config-absent case.

## Why the `surface_allowance` was retired rather than re-measured

It was declared three times (5009 → 8905 → 9476) and then dropped. The mechanism does not fit
this change: a **removed command has no allowance escape** — `test_surface_baseline`'s
`assert not missing` fails outright when a command vanishes from the render, so re-freezing the
baseline is forced. Once it is re-frozen, a declared `round_trips` headroom double-counts
(`baseline 21 + headroom 3 ≠ render 21`). Declaring and re-freezing are alternatives, not
complements.

So **both ratchets fold in this commit** — `surface_baseline.json` and
`test_command_size_budget.py`'s per-command dict — which is the rule ADR-010 exists to enforce
after `43234d0e` folded one and left the other.

## What the characters buy

`/hm:execute` gains `Step 0`, `Step 0.1` and `Step 0.2`. **None of it is new procedure.**
They are the removed `/hm:plan` stage's `Step 5`, `Step 1.7` and `Step 1.5`, relocated to the
owner the SPEC assigns them to:

### `Step 0` — authorship (was `plan` Step 5)

The PLAN document is INV-class state: it outlives a context window and five later stages read
it. SPEC-plan-stage-absorption removes the *stage*, not the *document*, so something has to
write it and no human gate stands in front of that. Carries the frontmatter contract block, the
required-section list and the seven mandatory per-phase fields.

### `Step 0.1` — the SPEC-need pair (was `plan` Step 1.7), spec-driven only

`verify.md.j2` Check 6 reads `spec_need_verdict` and treats an **absent** key as `PASS (N-A)`.
`plan.md.j2` was its only producer, so deleting that template without this step would not have
turned anything red — it would have turned Check 6 permanently green. That is the repo's
`absent-case = feature black hole` class (count:8), and closing it is IRR-003.

### `Step 0.2` — the per-iter PLAN (was `plan` Step 1.5)

`/hm:loop` iterations scope a `PLAN-{slug}-iter{N}.md` with `derived_from` / `iter` / `phase` /
`loop_mode`. The ADR-halt rule travels with it, reworded IDE-neutrally — the original sentence
named `AskUserQuestion`, a Claude-only tool, and `test_no_claude_tool_calls_in_codex_output`
caught it reaching `.agents/skills/hm-execute/SKILL.md`.

## Round trips

**One new call per target**, both the same call: `hm spec_need frontmatter-upsert` in Step 0.1.

It exists because of the oracle, not for convenience. AC-002's oracle is a **property** over
arbitrary prior frontmatter states — preserve what is there, guarantee presence afterwards — and
a prose instruction has no execution surface for a property to quantify over. A test could only
grep the template's text, which is the shape CLAUDE.md records as having shipped four
silent-skip bugs. The verb is **IRR-004** (public API/CLI contract, `source: execute`), raised
during implementation and accepted by the DRI, who re-issued the SPEC approval the append
invalidated.

Its discrimination is not assumed. Two hand-built mutants were run against
`tests/unit/test_spec_need_frontmatter_upsert.py`: removing preservation (always overwrite) and
making the write a no-op. Both were killed — 2 failed each, 5 passed on the restored source.

## Two ratchets, not one — both folded here

`surface_baseline.json` measures the rendered command's characters; `test_command_size_budget.py`'s
table counts mandated calls. They are different counters, and folding one while leaving the other
is invisible until the allowance retires — which is when it is hardest to diagnose. **Both are
re-frozen in this commit**, per ADR-010, at `865e3ef578f5`.

## `instruction_baseline.json` absorbed three other tasks' unattributed drift

Regenerating that baseline removed `plan@spec-driven` / `plan@task-driven` — expected, the
command is gone — and also moved `spec`, `wrapup` and `execute`. **The `wrapup` movement is not
this task's**, and the non-Step-4.6 half of `spec`'s is not either.

The baseline was last frozen at `374a5125`. Three commits since then changed those templates
without re-freezing it:

- `543f3f8c` feat(spec): the DRI accepts the SPEC — added `spec_machine approve` /
  `approval-status`
- `2d303b14` feat(memory): capture code-absent project facts in the shared wiki
- `0311e4e1` feat(memory): read the proposal backlog — added `proposals summary`,
  `memory_retrieve`

So the ratchet was already loose when this task arrived, and a regeneration is the only way to
make the digest check pass again. Recording it here so the movement carries the three commits'
names rather than disappearing under this SPEC's. **What this task actually added to that
baseline** is `spec`'s `### Step 4.6` heading plus its `spec-validator` ledger line, and
`execute`'s Step 0 block.

## Round 2 of `/hm:review` moved these numbers a last time

The nine consensus-passed fixes added 720 characters to each target, and the baseline was
re-frozen on top of them rather than left at the pre-review figures. Where they went: `execute`
gained the Step 0 note explaining why the SPEC-need pair is NOT in the authored frontmatter, the
`--rationale` quoting rule, and `--root` on the `frontmatter-upsert` recipe; `spec` lost a stale
backticked `plan` reference. The relocation of `Step 0.3` after `Step 0.2` moved bytes without
adding any.

Re-freezing after the review round is the point, not an afterthought: a baseline pinned before
the fixes would have recorded a surface the repo does not ship, and the next task would inherit
the gap as unexplained drift.
