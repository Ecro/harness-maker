---
type: baseline-delta
task_slug: dev-mode-spec-driven
created: 2026-08-23
render_sha: 9c01f375605f
supersedes_sha: 774b73e4
---

# BASELINE-DELTA — `dev_mode: task-driven → spec-driven`

## What moved, and why it is not this task's feature work

`.claude/harness.yaml` had `dev_mode: task-driven` while the repository holds **186 SPECs and
185 machine SPECs**. Every stage was rendering with the spec gate off. Flipping the config to
`spec-driven` turns that gate on, and the gate is made of mandated calls — so the surface moved.

The fold is attributed to the config flip, not to `probe-envelope-contract`. That task's own
surface change was net-negative and needed no fold: `review` lost 1,384 chars and its
`round_trips` stayed at 39, exactly as its PLAN predicted, and `_ATOMIC_RATCHET["review"]` was
lowered 71143 → 70153 in the same commit. Those numbers appear below because the two changes
land in adjacent commits, not because they share a cause.

## The direction: this fold makes the shipped surface LARGER

Say it outside the tables, because a reader scanning eight rows of mixed signs will not add
them up. **The aggregate grew: claude +8,831 chars, codex +8,789.** Two commands rose, two
fell, and the rises are roughly six times the falls.

That is the correct outcome and it is still a cost. Turning the spec gate on buys enforcement
this repository was configured to skip while holding 186 SPECs, and enforcement is made of
mandated calls — `plan` alone gained eleven round trips. Nothing here is waste to be trimmed
later; the trade is the gate's value against ~8.8k chars and thirteen calls per variant, and
it is being recorded rather than absorbed so a future reader can re-open it. ADR-010 is the
rule this fold follows: a baseline moves in its own attributed commit, never as a side effect
of the change that tripped it.

The class ADR-010 exists to stop is `ratchet-rebaselined-by-its-own-subject` (count 2), and this
fold sits one step from it. The change that tripped the baseline — flipping `dev_mode` — is a
one-line config edit that could trivially have been amended into the same commit as its own
re-freeze, with the numbers moving and nothing saying why. What keeps it out of that class is
not restraint: it is that the fold names the six calls it added, the two it added elsewhere and
the one it removed, each traced to a rendered line rather than to the delta. A re-freeze whose
justification is the size of the delta is the failure mode; a re-freeze whose justification is
the diff that produced it is the remedy.

## Per-key attribution

### Claude variant — `aggregate_chars` 435000 → 443831 (+8,831)

| key | chars | round_trips | cause |
|---|---|---|---|
| `plan` | 60633 → 69954 (+9,321) | 15 → 26 (+11) | the spec-need gate: `spec_need marker-read`, `marker-fresh`, `prefilter`, `record`, `waiver-set`, plus the `git diff --name-only $(git merge-base HEAD <base>)` that feeds them, and the prose that carries the gate's decision table |
| `verify` | 22225 → 24673 (+2,448) | 13 → 15 (+2) | `spec_need op-check` and `spec_need waiver-check` |
| `wrapup` | 47597 → 46043 (−1,554) | 29 → 28 (−1) | the **only drop from the flip**: `spec_machine waiver-check --dev-mode task-driven` is the task-driven oracle-waiver advisory, which spec-driven does not render |
| `review` | 91909 → 90525 (−1,384) | 39 → 39 (0) | `probe-envelope-contract`, not the flip — the retired `repo_probe` prose and its six `probe_flags` sites. `round_trips` is unchanged because the flags appended to existing `!` lines and the `mktemp` was prose |

### Codex variant — `aggregate_chars` 367917 → 376706 (+8,789)

| key | chars | round_trips | cause |
|---|---|---|---|
| `hm-plan` | 54888 → 64164 (+9,276) | 14 → 14 (0) | same gate as `plan`. `round_trips` does not move because the codex rule counts `Bash(` call sites and the gate's calls render as prose-embedded in the stage skill |
| `hm-verify` | 19618 → 22072 (+2,454) | 12 → 14 (+2) | same two `spec_need` calls as `verify` |
| `hm-wrapup` | 45806 → 44249 (−1,557) | 29 → 28 (−1) | same advisory drop as `wrapup` |
| `hm-review` | 87227 → 85843 (−1,384) | 34 → 34 (0) | `probe-envelope-contract`, as above |

### Keys with no independent claim

`payload_digest` and `render_sha` moved because the generator recomputes them; they carry no
statement of their own and are listed so neither reads as an unexplained edit. `render_sha`
9c01f375 is the base-reachable commit the regeneration ran from.

## What was checked, not assumed

- **Only four commands moved per variant.** Eight keys across two variants, and the same four
  logical commands in each. A fifth would have meant the flip reached somewhere the spec gate
  does not, and would have been a finding rather than rounding.
- **The added and removed calls were named by diffing two real renders**, not inferred from the
  numbers: the same blueprint rendered at `DevMode.TASK_DRIVEN` and `DevMode.SPEC_DRIVEN`, then
  compared line by line. The `wrapup` drop was found that way and is the reason this fold is a
  mixed direction rather than a uniform rise.
- `_CLAUDE_ROUND_TRIPS` was re-baselined in `tests/structural/test_roundtrip_budget.py` with the
  same attribution inline, per that file's own instruction to re-baseline in the phase's commit
  and name the calls.

## How this was missed until CI

The config change was applied and pushed **without re-running the suite**. The local full suite
that reported `pytest=0` ran in the task worktree before `harness.yaml` was copied into it, so
it measured the task-driven render. CI ran the spec-driven one and went red on seven structural
tests. The green was real about the state it measured and stale about the state that shipped —
the same failure mode this repository has now recorded several times, arriving through a
configuration change rather than a code change.
