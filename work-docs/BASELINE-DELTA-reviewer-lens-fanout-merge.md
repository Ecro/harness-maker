# BASELINE-DELTA — reviewer-lens-fanout-merge

Re-freeze of `tests/structural/surface_baseline.json` and the `review` entry of
`tests/structural/test_roundtrip_budget.py`, in the same commit as the template edit that
caused them. Per-key attribution per **ADR-010**: every key whose value moved is named below with
the command that owns it, so a later reader can tell a deliberate delta from a drifted one.

**Precondition, asserted rather than assumed.** `load_active_allowances(Path("."))` returned
`NONE` before the whole-file re-freeze — run as a command, not read off a sentence. A peer
PLAN holding a live allowance would make a whole-file re-freeze absorb its unlanded growth,
which is what forced a revert on 2026-09-12
(see `BASELINE-DELTA-workflow-steps-vs-model-capability`, Phase 7).

## Why this document exists, and who may write it

A re-freeze is a change measuring itself. The generator re-renders the very templates this task
edited and writes down whatever it finds, so "the baseline is green" after a re-freeze carries no
information about whether the edit was intended — that is
**`ratchet-rebaselined-by-its-own-subject`**, and a ratchet silently re-based by its own subject is
indistinguishable from one that was never tripped.

What makes it safe is not the re-freeze but this document, and only under two rules (ADR-010):
the phase that **moved** a key is the phase that re-freezes it, in the **same commit**; and every
moved key gets a row naming the command that owns it. A key that moved with no row is the failure
mode — the test enforcing that is `test_every_changed_key_has_an_attribution_row`, which reads this
file and compares it against the actual diff of `surface_baseline.json`, so the document cannot
drift from what happened.

## What moved

| File | Key | Before | After | Delta |
|---|---|---|---|---|
| `surface_baseline.json` | `surface.claude.review.chars` | 86 171 | 85 923 | **−248** |
| `surface_baseline.json` | `surface.claude.review.round_trips` | 39 | 33 | **−6** |
| `surface_baseline.json` | `surface.codex.hm-review.chars` | 82 433 | 82 319 | **−114** |
| `surface_baseline.json` | `surface.codex.hm-review.round_trips` | 34 | 28 | **−6** |
| `surface_baseline.json` | `aggregate_chars.claude` | 427 617 | 427 369 | **−248** |
| `surface_baseline.json` | `aggregate_chars.codex` | 362 440 | 362 326 | **−114** |
| `surface_baseline.json` | `payload_digest` | `160b87ec…` | `7e061a32…` | rewritten |
| `surface_baseline.json` | `render_sha` | `2ff7f035…` | `9ea26255…` | re-pinned |
| `test_roundtrip_budget.py` | `review` | 39 | 33 | **−6** |

## Per-key attribution

Every changed key belongs to one command, and that command is `review`. No other entry in
either variant moved — the generator re-rendered 15 claude commands and 10 codex skills and
only these two artifacts differ.

- `review` (`surface.claude.review.*`) and `hm-review` (`surface.codex.hm-review.*`) — the four
  core reviewer lenses (`design`, `functionality`, `robustness`, `consistency`) shared the
  `code-reviewer` agent and differed only by one brief sentence, so four dispatches meant four
  independent re-reads of one diff for four questions one agent can hold at once. They now leave
  in **one** call carrying all four briefs. Both rendered dispatch blocks — Step 3's round 1 and
  Step C2's confirmation pass — loop over `conditional_router.lens_dispatch_groups`, so the
  −3 lands twice.
- `aggregate_chars` — the sum over each variant's commands; it moves by exactly the one command's
  delta because nothing else moved.
- `payload_digest` — mechanical, rewritten by the generator over the new per-command values.
- `render_sha` — the base commit the generator ran against, re-pinned from `2ff7f035` to
  `9ea26255`. It moves on every re-freeze by construction and is owned by no command: it records
  *when* the baseline was taken, not *what* changed. The previous value was the squash-land of
  `token-efficiency-autopilot-ux-speed`; the new one is the baseline re-freeze that closed
  `workflow-steps-vs-model-capability` Phase 7, which is this worktree's base tip.

## Why the two arms differ (−248 vs −114)

The counting rule charges a dispatch differently per variant. On claude a dispatch is
`Task(subagent_type=…, description=…, prompt=…)`; on codex it is
`spawn_agent(agent_type=…, message=…)` with **no description**. Removing three dispatches
therefore saves more on claude than on codex, while the added prose — the accountability line and
the two-level stamp instruction — costs both arms the same.

**That difference was not free, and the ratchet caught it twice.** On the first render the codex
arm *grew* 106 chars over the Phase 0 aggregate with a 0-char allowance, tripping
`test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow`. Taking a
`surface_allowance` would have contradicted this task's own re-freeze precondition, so the prose
was trimmed instead — and that trim also fixed a latent template bug: the stamp instruction had
enumerated the core lens names through a `selectattr` chain over all seven lenses, using
`loop.last` from that outer loop to separate four names, which is the wrong loop.

It happened a **second** time after `/hm:review`, when fixing four review findings in the
rendered prose put BOTH arms over (claude +91, codex +225). Trimmed again. The numbers above are
the state after both trims, and the pattern is worth naming: **every prose fix to a rendered
command is a surface change, and the ratchet is the only thing that says so.**

## Round-trip counting, stated because the number looks larger than the edit

ADR-011's rule counts **every** `Task(` / `spawn_agent(` individually, even though all of them
leave in a single message. So the −6 is a cost in the metric, not in turns: the review still
dispatches once per round and now waits on four replies instead of seven. No mandated CLI call
was added, removed or chained by this task — the entire −6 is dispatch lines.
