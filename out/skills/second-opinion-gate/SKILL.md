---
generated_by: harness-maker
harness_maker_version: 0.52.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/second-opinion-gate/SKILL.md.j2
provenance: official
name: second-opinion-gate
description: Procedure /hm:review follows for the auto-fix loop's round-state contract
  (finding identity, monotonic progress, per-round voter state) in EVERY harness,
  and additionally for the cross-model second-opinion acceptance gate (oracle gathering,
  PIDA dispositions, the frozen finding set) when harness.yaml second_opinion.models
  is non-empty.
content_hash: 40f996146a429587aea42fee2641a05c985521eb08c25cf1782f0760002c7c9b
---

# second-opinion-gate

The procedure `/hm:review` follows to admit, refute and carry cross-model findings.

**Why this is a skill and not inline stage prose.** `/hm:loop` re-reads the whole review
stage on every iteration that lists `review` in `--per-iter-stages`, so a
character added to that stage is paid five times in the shipped command surface — which the
repo's `test_command_size_budget` / `test_aggregate_shipped_surface_does_not_grow` arms
deliberately refuse. A skill is loaded on demand and is not fanned out. The rules below are
binding on the main loop even though they live here.

Companion: the **`code-verifier` agent, mode B** owns the refutation *rubric*, the oracle-input
rules and the output schema. This file owns what the main loop does around it.

## 1. Finding identity (`/hm:review` Step 3.4) — applies to EVERY finding

Reviewers never emit `id`; an LLM-generated one differs per run, which defeats the point.
**Do not compute the hash yourself** — you cannot reproduce `json.dumps`'s exact separators, so a
hand-derived id changes between rounds and the round-2 merge matches nothing. Pipe the merged
findings through the stamper:

```bash
uv run --with $HOME/harness-maker hm codex_adapter stamp-ids < <the temp path you wrote>
```

**`Write` the payload to a file; never embed it in argv.** A single apostrophe in any finding
summary ends the quoted shell word, and the fallback when the command fails is an LLM-invented
id — the exact failure this step exists to prevent. Same rule as §4's disposition write.

It returns the same list with `id` filled, and:

- derives from each finding's **first-seen** `file`/`line`/`summary` via
  `harness_maker.codex_adapter.finding_id` — the same function the second-opinion adapter
  already uses, so both sides agree by construction;
- **keeps** any `id` already present (re-deriving on post-fix values is the bug this exists to
  prevent);
- disambiguates collisions with `-2`, `-3`, …. **Never** merge two findings onto one `id`: it is
  simultaneously the lifecycle key, the frozen-set join key and the ledger `finding_ref`, so a
  collision drops a record and double-counts a denominator.

**Why load-bearing:** the auto-fix loop carries findings across rounds by `id`. Without it the
loop matches on `file:line:summary`, all of which a fix moves — so a reworded finding reads as
new and the original as gone. That is how a corroborating voice vanishes with no code change
and the grade improves for free.

## 2. Oracle gathering (before the mode-B call)

Mode B needs a test oracle and `code-verifier` has no Bash, so the main loop runs it.

**Phase 0 is not a substitute.** It renders only when `reviewers.mechanical_checks` is
configured, sits above Round 1 so it runs once rather than per round, and is
stop-on-first-failure — so at this point it is absent or all-green by construction and could
never refute anything. This step is independent of that key.

**Do not build the command line yourself.** `Write` the adapted findings to a temp file and
call the gatherer, which owns every rule below:

```bash
cd <the task worktree> && uv run --with $HOME/harness-maker hm second_opinion_oracle --findings-file <path> --root .
```

The `cd` is load-bearing: `--root .` resolved at the base repo gives an empty
`git diff --name-only HEAD`, every path then fails the changed-set check, and the gatherer
reports "no oracle gathered" for **every** finding — a silent all-`unresolved` degradation that
looks exactly like a working run.

It prints the labelled blocks on stdout; inject them verbatim. It always exits 0 — a missing
oracle is less evidence, never a reason to fail the review.

**Why this is not a shell line with `<paths>` substituted in.** Those paths come from an
external model's `file` field, which has no schema constraint (`validate_payload` checks only
`severity` and `message`, and antigravity's `--json-schema` enforcement is
best-effort — `structured_output` can be absent on a SUCCESS reply), and the shipped
settings pre-approve `Bash(uv run pytest:*)` as a **prefix** rule — arbitrary trailing arguments,
no prompt. A value beginning with `-` is then consumed as an **option**, not a path, with no
shell metacharacter needed (`pytest --basetemp=<dir>` removes that directory). Putting the
filter in prose would have left the taint path in code and only the defence in prose.

What the gatherer enforces, so you do not have to:
<!-- @hm:oracle-command-surface -->

0. **Toolchain gating** — the commands come from the project's root-level `toolchains` block
   in `harness.yaml`, read from the **base** repo (a worktree may gitignore `.claude/`). A path
   whose file type no entry claims gets **zero** commands run and is listed in the no-oracle
   tail with its extension. Running a tool that cannot parse the subject does not produce a
   degraded oracle, it produces a fabricated one — output that reads to the mode-B rubric as
   either a false `accepted` or, once truncated, a silent `unresolved`. With no `toolchains`
   key at all, `.py`/`.pyi` keep the historical Python checks and every other extension gets
   nothing; a **malformed** block is fail-closed (no oracle) rather than falling back.
1. **Path filtering** — rejects option-shaped (`-…`), absolute, `..`-traversing and
   metacharacter-bearing paths, and anything outside `git diff --name-only HEAD`. Command
   templates are tokenised **before** `{path}` is substituted, so a path containing a space
   stays one argv element.
2. **Budget** ≤ 4000 characters total, ≤ 1500 per command.
3. **Visible truncation** — `[… truncated N chars …]`, so a fragment announces itself.
4. **Association** — every per-path block is labelled with the finding `id` it was gathered for
   and the toolchain that produced it; findings that got none are listed explicitly as
   `unresolved` territory, not refutation, **grouped by cause** (unusable path vs uncovered
   file type — those have opposite remedies). Output from a repo-scoped command is emitted as
   an **unlabelled** project-wide block on purpose: a repo-wide failure can come from anywhere
   in the tree, so labelling it with every covered id would manufacture corroboration.
5. **Redaction** — value-shaped (not keyword-shaped): API/GitHub/AWS keys, `Bearer` values,
   credentialed URLs, bare JWTs, and whole PEM blocks via a stateful mode. ANSI stripped.
   (`hm two_pass_review redact` is **not** this control — it rewrites PR metadata fields in a
   context JSON and cannot process a byte stream.)

These commands run under the normal Bash sandbox. **Never** pass `dangerouslyDisableSandbox`
here — that escape belongs only to the model-invoker calls.

## 2b. The mode-B call

One call with **every** enabled model's findings together, so cross-model duplicates can be
marked. Claude Code / Cursor:

```
Task(subagent_type="code-verifier", description="Mode B PIDA: <slug>",
  prompt="MODE: B (cross-model PIDA)\n\nsecond_opinion_findings: <adapted JSON, all models, ids verbatim>\nfull_context: <Pass 2 non-redacted diff>\noracle_blocks: <labelled, budgeted, credential-filtered per §2>\n\nReturn ONLY the mode-B JSON.")
```

Codex:

```
@code-verifier MODE: B (cross-model PIDA)
second_opinion_findings / full_context (Pass 2, non-redacted) / oracle_blocks
```

## 3. Applying the dispositions

Mode B emits the ledger vocabulary directly, so there is nothing to translate:

- `accepted` → enters the Step 4 consensus filter as a voter.
- `rejected` / `duplicate` → dropped; never a voter.
- `unresolved` → enters as `manual-only`: no vote, not auto-fix eligible, not a grade input.

Agent launch failure → record every finding `unresolved` and say so. A failed verifier must
never silently promote findings to voters.

**`unresolved` is the one documented exception to the `unverified_severe` scan.** That scan is
otherwise purely tag-based (every `manual-only`/`weak-consensus` P0/P1 sets it). A finding whose
`source` is an enabled second-opinion model *and* whose disposition is `unresolved` does not set
it, because PIDA could neither support nor refute it even with an oracle. Everything else still
does — including a finding PIDA `accepted` that consensus then rejected.

## 4. Recording the dispositions (once per review, at the base root)

**Reconcile the verdict set against the input set first.** The writer validates each row's
*shape* but cannot check membership — it never sees the findings you sent. So before writing:

- drop any disposition whose `id` is not in the frozen round-1 set, and **report how many were
  dropped**;
- a finding you sent with **no** disposition back is `unresolved`, not absent — add it;
- a duplicated `id` keeps the first verdict; report the collision.

Without this, an omitted, duplicated or invented `id` lands in the ledger as acceptance-rate
data and there is no downstream check that can tell. Mode B's own `stats` block
(`input_n == accepted_n + rejected_n + duplicate_n + unresolved_n`) is your first signal that
the set is wrong.

Then `Write` the reconciled array to a temp path as `{"dispositions": [...]}` — **never**
argv-embedded (shell quoting, `ARG_MAX`, and finding text must not be shell-expanded) — and make
one call:

```bash
cd <the task worktree> && uv run --with $HOME/harness-maker hm second_opinion_invoke --record-disposition --disposition-file <the literal temp path> --slug "<slug>" --stage review
```

- The invoker resolves the **base** repo root, so rows survive `task-land`. A row written
  relative to cwd from inside `.worktrees/<slug>/` lands in a gitignored path and is destroyed
  at land time — that regression is why this entrypoint exists.
- `slug` and `stage` come from **argv only**; do not duplicate them inside the payload.
- Exit is **0 even when nothing was recorded** — an unwritten calibration row must never fail a
  review. The signal is a `[second-opinion] disposition rows NOT recorded: <reason>` line on
  **stderr**. **Surface it**, or a review that recorded nothing looks identical to one that
  recorded everything.

## 5. Round-state contract (auto-fix loop, rounds 2..N)

> **A disposition is not a lifecycle transition.** The four PIDA values
> (`accepted`/`rejected`/`duplicate`/`unresolved`) and this section's lattice
> (`pending`→`resolved`/`stale`) are **orthogonal** and neither implies the other. `/hm:review`
> Step 4e now assigns a disposition to every finding on every path, so the two vocabularies are
> both present on the same record; treating a `rejected` as a `resolved` would let the progress
> invariant read a re-classification as work done and keep a stalled loop running.

**Round order — pinned end to end.** Merge the previous round's re-review output by `id` → stamp
`id`s on new findings → determine `caused_by` → group and evaluate the trigger → batch re-derive
on a fire → select fixes → apply → verify build, reverting on failure → selective re-review →
recompute grade → progress invariant → append the iteration record. Determining `caused_by`
**before** the trigger is what makes arm (b) reachable at all: computed at record-append time it
would arrive after fix selection, and a lone regression finding would take the fast path —
reproducing the chain the batch step exists to stop. Verify and re-review stay INSIDE the round —
a break reverted only next round means a full round built on a broken tree.

**Two-arm batch trigger.** Re-derive the underlying model before editing when **either**
(a) ≥2 of this round's findings share a subsystem / state model, **or** (b) any finding **new
this round** carries a non-null `caused_by`. Otherwise patch per finding as before — a lone,
unattributed finding keeps the fast path, which is the majority case and must not get slower.

`caused_by` is stamped **once**, at a finding's first appearance, and never recomputed. That is
well-defined across a `stale`-then-re-report because `codex_adapter.finding_id` hashes
`[source, file, line, message]` and freezes it: a re-report at a shifted location is a different
`id` (genuinely new — arm (b) may fire), and one at an unchanged location keeps its `id` (not
new — no re-fire, because nothing regressed). Arm (b)'s domain is findings new this round, not
the merged voter state; evaluating it over the merge would make it true from round 3 onward.

**Per-group block.** On a fire, emit for each group before editing: `group_key` (default: the
dominant file-path stem shared by the group, free text allowed with the derived prefix recorded
alongside), `covered_finding_ids`, the model's dimensions enumerated, and the single consolidated
edit. Patching the reported cell without re-deriving the table is what produced 9 of 30 findings
in the case this contract comes from.

**`caused_by` grammar.** It shares the iteration record's `Status` cell with a different enum, so
the encoding is literal: `Applied · caused_by=#7` / `· caused_by=none` / `· caused_by=unknown`,
and the same `· caused_by=` suffix on `Skipped — overlap` and `Reverted — build failure`. Without
one grammar, rounds encode it differently, arm (b) misses attributions, and the counters disagree
with the rows they are derived from — with nothing able to detect it.

**Counters.** The REVIEW Final Summary reports `unreviewed_fix_count` (fixes applied in the
terminal round, which the loop never re-reviewed), `regression_attributed_n` and
`attribution_unknown_n`. Count the last two over **distinct finding `id`s**, not iteration-record
rows: a reverted or overlap-skipped fix leaves its finding `pending`, so it emits another row
next round carrying the same `caused_by`. They gate nothing — they exist so an `A` grade is not
read as "settled".

**Lifecycle.** `pending` (**votes**) · `resolved` (a fix targeting it was applied **and** that
round's verification passed) · `stale` (target gone from the diff). The last two do not vote.
**"A fix touched it" is not enough for `resolved`** — the loop reverts a build-breaking fix, and
a reverted, overlap-skipped or never-attempted fix leaves the code unchanged, so the finding
stays `pending`.

**Monotonic progress.** Only `pending`→`resolved` and `pending`→`stale` count. **Never** counts:
any→`pending`; tag/cluster/severity churn with no status change; a finding appearing or
disappearing because a reviewer was re-spawned. Back-transitions are forbidden, so no status can
oscillate and the lattice is finite and acyclic — which is what makes termination provable
rather than hoped for.

**Early stop.** A round progresses iff ≥1 counted transition occurred. **One** non-progressing
round ends the loop: `CHANGES_REQUESTED`, exit reason `no-progress` (not `cap-exhausted`).
**Evaluated only for rounds that ran the fix step — round ≥ 2.** Round 1 is the initial review
and has no fix step, so zero transitions are reachable there; an unqualified test would exit
before a single fix was attempted and disable auto-fix entirely.

**Voter state**, keyed on the `id` from §1. Reviewers not re-spawned this round → carried
forward unchanged. Re-spawned reviewers → **merged by `id`, not replaced wholesale**: a finding
the reviewer no longer reports is **retained** unless the code at its target changed, and only
then marked `stale` with the changed hunk as the reason. Consensus clusters are rebuilt from
scratch each round, which is safe **only** because voices persist by `id` — over a wholesale
replacement, one reviewer's non-determinism drops a corroborating voice, pushes a cluster below
the consensus threshold, and improves the grade with no code change behind it.

**Do not re-invoke the models.** Each enabled model runs **exactly once per `/hm:review`
invocation**, in round 1. Rounds 2..N re-read the frozen set (§6) and update statuses.
Re-invoking injects a fresh stochastic voter every round, so `Remaining`/`New` can never drain
and the loop exits on the round cap instead of converging.

**Exit reason** is recorded in the final summary and is not cosmetic: `converged` (grade met the
threshold) · `no-progress` (nothing could improve) · `cap-exhausted` (rounds ran out **while
still progressing** — the one exit that says a higher cap would have helped) ·
`auto-fix-disabled`. Never report `cap-exhausted` for a run that stopped on `no-progress`;
conflating them hides whether the cap is set too low.

## 6. The frozen cross-model set (REVIEW report section)

This **is** the loop's working state, so it must survive a `/compact` and carry what Step 4's
predicates need — not just bookkeeping. Emit `frozen_at_round`, `models`, then per finding:

`id` (verbatim from the adapter — the join key, never re-derived) · `source` · `severity` ·
`file` · `line` · `summary` · `evidence` · `needs_relaxation` · `disposition` · `oracle_result` ·
`status` (`pending`|`resolved`|`stale`) · `invalidation_reason` (required when `stale`).

**No `symbol`/`reasoning`/`suggestion` keys.** The vendor schema
(`second-opinion-finding.schema.json`, `additionalProperties: false`) cannot produce them, so
they would be permanently null — and a key that never carries data reads as capability to the
next reader. Two expected consequences, not bugs:

- A cross-model-**only** cluster is **not auto-fix eligible**: the fixable-finding filter
  requires a concrete `suggestion`. Such a finding reaches a fix only inside a cluster that also
  holds a suggestion-bearing Claude voice.
- Step 4b's missing-reasoning rule does **not** demote it: that rule carries an exception for
  an `accepted` cross-model finding, whose `evidence` + `oracle_result` are read **as** the
  reasoning chain. Without the exception the rule would fire on every cross-model finding by
  construction and no cross-model vote could ever reach `consensus-passed`.

Update `status`/`invalidation_reason` in place each round. **Never delete a record** — a dropped
one is indistinguishable from one that never existed.

<!-- @hm:user:extensions -->
<!-- Project-specific additions to the second-opinion gate procedure. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
