---
type: plan
task_slug: workflow-step-audit
status: planning
created: 2026-07-29
tags: [harness-maker, plan, python, workflow, latency, render]
research_doc: "[[RESEARCH-workflow-step-audit]]"
interview_rounds: 5
adrs: 18
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Collapse deterministic serial CLI chains and fan out research gathering — no gate weakened"
---

# PLAN — Workflow round-trip reduction

## 🎯 Executive Summary

**TL;DR** — Replace three deterministic serial CLI chains with three thin composite
CLIs, fan out `research` Phase 1 into read-only subagents, and fix two `execute` rules
that double its turn count. Every quality gate keeps its current semantics. A
ceiling-and-floor ratchet plus a post-hoc re-measurement receipt prove the reduction is
real rather than relocated.

**What / why.** Each `!` line in a rendered `/hm:` command is one main-loop turn at
200–430K context. The canonical fused workflow mandates 56 of them; `wrapup` alone
mandates 30 and `verify` 13. Almost none of those turns carry a judgment — they run
deterministic checks whose only LLM-relevant output is the final verdict. Measured share
of active wall-clock: `execute` 21.1%, `wrapup` 14.6%, `research` 12.4%, `plan` 9.7%,
`review` 5.2%. `review`, the stage that does the most analysis, has the *fewest*
main-loop turns per run (91) because its work happens in parallel subagents. That
asymmetry is the whole thesis.

**Key decisions:** [ADR-001](#adr-001) scope · [ADR-002](#adr-002) three thin CLIs ·
[ADR-003](#adr-003) composites orchestrate, never reimplement · [ADR-004](#adr-004)
verify's two-call verdict split with evidence-bound Check 1b · [ADR-005](#adr-005)
verify binds an explicit subject and emits SKIPPED, not a vacuous PASS ·
[ADR-006](#adr-006) `wrapup land` stops before the destructive land ·
[ADR-007](#adr-007) typed staging manifest · [ADR-008](#adr-008) four-way test-selection
classification · [ADR-009](#adr-009) per-file type checks · [ADR-010](#adr-010) research
fan-out contract · [ADR-011](#adr-011) three-part ratchet including an aggregate total ·
[ADR-012](#adr-012) measurement reporting discipline · [ADR-013](#adr-013) rejected:
collapsing per-stage preflight · [ADR-014](#adr-014) rejected: verify delegation ·
[ADR-015](#adr-015) out of scope: workflow ordering · [ADR-016](#adr-016) the verify
semantics change is bounded to run-level aggregation · [ADR-017](#adr-017) release
ordering owns the module-before-template constraint.

**Estimated impact (inference, to be measured — see [ADR-012](#adr-012)):** mandated
round-trips removed from a full pipeline run, concentrated in `verify`
(**13 → 7** — the six checks own only 8 of those 13 calls and become 2; the preflight,
Gate-0, `task-refresh` and autopilot calls all stay, see the correction under
[Phase 1](#phase-1--extend-clipys-verify-command-into-the-two-call-composite)) and
`wrapup` (of which the 7-call git tail becomes 3). The
`research` fan-out and the `execute` Phase C/D rules are expected to matter more than
the CLI collapse in wall-clock terms, because they attack the two largest stages, but
neither has a per-run prediction attached to it here on purpose.

## 📚 Prior Work

- `[[RESEARCH-workflow-step-audit]]` — the measured baseline and the per-step verdict
  table this plan implements.
- `[[RESEARCH-token-economy-step-pruning]]` / `[[PLAN-token-economy-step-pruning]]` —
  established that stage prose costs O(1) cached tokens while a turn costs O(context).
  This plan is the latency-side companion and does **not** re-attempt prose trimming.
  Its withdrawn ADR-017 (a "documentation-only" trim that deleted runtime instructions)
  is why [ADR-011](#adr-011) keeps a floor.
- `[wiki:architecture] carry-is-a-main-loop-phenomenon` — **corrects a claim in the
  research doc**: delegation reduces what is *added* to the prefix, not what is already
  in it. The measured wrapup improvement is a *turn* (latency) effect, not a carry
  (cost) effect, and this plan states it only as the former. Same entry supplies the
  prefix composition that makes the `research` fan-out worth doing: Bash output is 27.9%
  of the carried prefix and `grep`/`rg` alone is 10.8%.
- `[wiki:architecture] harness-economics-observability` — the instrument used for the
  turn-attribution table, and the source of the constraint in [ADR-013](#adr-013).
- `tests/structural/test_command_size_budget.py` — the existing ceiling+floor ratchet
  whose shape [ADR-011](#adr-011) extends.
- CLAUDE.md learned correction 2026-06-08 (absent-case, count:8, most-recurring) — the
  reason [ADR-008](#adr-008) and [ADR-004](#adr-004) both name their absent case.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | → ADR |
|---|---|---|---|---|---|---|
| 1 | 1 | Scope | Scope boundaries | How far does this PLAN lock? | T1 mechanical + research fan-out; execute parallel + review Pass-2 deferred | ADR-001 |
| 2 | 1 | Composite shape | Architecture | Thin per-chain CLIs vs generic stage-runner vs prose-only | Three thin per-chain CLIs | ADR-002 |
| 3 | 1 | verify ownership | Contract shape | Who owns the gate verdict? | CLI owns mechanical checks; LLM owns Check 1b | ADR-004 |
| 4 | 1 | Regression proof | Testing depth | What proves the round-trips dropped? | Ratchet test **and** post-hoc re-measurement | ADR-011, ADR-012 |
| 5 | 2 | Phase D absent-case | Failure handling | What happens to a changed file with no test hint? | That phase runs the full suite, loudly | ADR-008 |
| 6 | 2 | Phase C granularity | Implementation phasing | What replaces "check after each edit"? | Per-file | ADR-009 |
| 7 | 2 | research fan-out | Architecture | Which agents, how many, what digest contract? | 3 read-only `Explore`, citations + verbatim snippets mandatory | ADR-010 |
| 8 | 2 | Workflow ordering | Scope boundaries | Fix verify↔wrapup order now? | Out of scope — design assumes wrapup → verify | ADR-015 |
| 9 | 3 | `wrapup land` boundary | Risk tolerance | How much does the composite swallow? | Steps 6 → 7.6 only; `task-land` and `commit-base-memory` stay explicit | ADR-006 |
| 10 | 4 | verify semantics scope | Contract shape | How much of verify's shipped verdict semantics may change? | Minimal: run-level aggregation only; Check 3's no-baseline PASS preserved | ADR-005, ADR-016 |
| 11 | 4 | pop/land deadlock | Failure handling | How is the legacy-ref deadlock closed? | Pre-scan for live legacy refs; stop rather than pop | ADR-006 |
| 12 | 4 | fan-out agent | Architecture | Which agent, given `Explore` is not a rendered asset? | Claude target only; cursor/codex keep the serial path | ADR-010 |

Two decisions were taken by the planner without a round, per the "never ask trivial
questions" rule, and are recorded as assumptions: the three new CLIs follow the existing
module-per-concern layout under `src/harness_maker/`, and each phase lands as its own
commit per the repo's git convention.

Findings from the cross-model second opinion (codex + antigravity, both `invoked`) were
folded into ADR-003, ADR-005, ADR-007, ADR-008, ADR-011 and ADR-012 rather than being
deferred; the reconciliation table is in [§🔍 Plan Validation](#-plan-validation).

## 📐 Architecture Decision Records

### ADR-001: Scope is T1 mechanical work plus the research fan-out
**Status:** Accepted (2026-07-29, via /hm:plan interview)
**Context:** The research doc ranked candidates in three risk tiers. Shipping all of them
at once mixes zero-risk mechanical collapse with parallel-writer hazards and a
precision-affecting review change.
**Decision:** This PLAN ships the mechanical composites, the two `execute` rule changes,
and the `research` fan-out. `execute` per-phase parallel workers and the `review`
Pass-2 merge are deferred to separate PLANs.
**Consequences:**
- ✅ Every change in scope is either deterministic or read-only; no parallel writers.
- ⚠️ The single largest wall-clock lever (`execute` at 21.1%) is only partially
  addressed — by the Phase C/D rules, not by parallelism.
**Rejected alternatives:**
- T1 only — leaves `research` (12.4% of wall-clock, 154 turns/run) untouched.
- All tiers — the `review` Pass-2 merge cannot be decided without an A/B on the existing
  `verifier_false_drop_n` / `verifier_false_keep_n` telemetry, which this PLAN does not
  run.
**Source:** Interview #1

### ADR-002: Three thin per-chain CLIs, not a generic stage-runner
**Status:** Accepted (2026-07-29, via /hm:plan interview)
**Context:** Each serial chain could be collapsed by a purpose-built CLI or by one
generic runner executing a declared recipe.
**Decision:** Ship `harness_maker.verify_run`, `harness_maker.wrapup_land`, and a
`spec_machine check --all` subcommand. No generic runner.
**Consequences:**
- ✅ Each CLI maps 1:1 onto prose that already exists, so a render test can assert the
  correspondence and a reviewer can diff intent against implementation.
- ⚠️ Three modules instead of one abstraction; a fourth chain later means a fourth module.
**Rejected alternatives:**
- Generic `stage_ops run <recipe>` — introduces recipe-vs-prose drift, a failure mode
  that render-grep cannot detect (the same class as the second-opinion silent-skip bugs
  recorded in CLAUDE.md).
- Prose-only ("issue independent calls in one message") — zero enforcement and not
  ratchetable.
**Source:** Interview #2

### ADR-003: A composite orchestrates existing functions; it never reimplements one
**Status:** Accepted (2026-07-29, via cross-model second opinion)
**Context:** Codex raised that `post_commit_pop` alone handles multi-repo discovery,
live-session ownership filtering, refs created mid-scan, and partial-pop recovery. A
composite that re-derives any of that becomes a second, weaker implementation of a
safety-critical path.
**Decision:** Every composite CLI in this PLAN is sequencing plus receipts. It calls the
existing public functions (`post_commit_pop`, `drain`, `verification_cache.check` /
`mark_pass`, `compute_readiness`, `parse_dashboard`, `spec_machine.validate` /
`cross_validate`, `spec_quality.evaluate`) unchanged. Any behavioral change to those
functions is out of scope for this PLAN.

> **Applied to verify — the composite is an EXTENSION, not a new module.** Validation
> pass 2 established that `cli.py:1844 `@app.command("verify")`` already implements this
> stage's mechanical side: `_verify_structural_check` (`cli.py:1935`) wraps
> `parse_dashboard` and carries the no-baseline PASS rule, and `_write_verify_jsonl`
> (`cli.py:2016`) writes the same `verify-<date>.jsonl` record. A separate
> `harness_maker.verify_run` module would therefore be a **second producer of one durable
> record** — precisely what this ADR forbids. The verify work extends the existing command
> instead. Two consequences, both improvements: the phase gets smaller, and Check 3 gains
> a **real executable differential oracle** (old function vs. new call path) where the
> LLM-judged checks can only have golden per-fixture expectations.
**Consequences:**
- ✅ The safety properties of the existing code are inherited rather than re-derived.
- ✅ Unit tests for the composites can assert *delegation* (the function was called with
  the right arguments) instead of re-testing the callee's semantics.
- ⚠️ Where the current prose does something the library does not expose (the staging
  loop), that logic must be written once — see [ADR-007](#adr-007) — and is the single
  exception, called out explicitly rather than left implicit.
- ⚠️ **Second called-out deviation:** base-root resolution moves from the shipped
  template's ambient `"$(pwd)"` (`wrapup.md.j2:634`) to an explicit, git-validated
  `--base` argument. That is a fix, not a reimplementation — an ambient cwd is the
  documented footgun (`[[feedback_bash_cwd_persists_across_calls]]`: a bare `cd` moves
  every later relative command, and base and worktree are near-identical so the
  misfire succeeds) — but it is a behavior change and is named here rather than
  smuggled in under "sequencing".
**Rejected alternatives:**
- Reimplementing the pop/drain sequence inside the composite for a tighter receipt —
  rejected; the receipt is not worth a second implementation of a path that has caused
  three documented contamination incidents.
**Source:** Second opinion (codex P0/P1)

### ADR-004: verify splits into a mechanical CLI call and an evidence-bound Check 1b
**Status:** Accepted (2026-07-29, via /hm:plan interview + second opinion)
**Context:** Five of verify's six checks are deterministic. Check 1b (every SPEC In-Scope
Scenario is covered by a passing test or an explicit waiver) is a judgment. A single
`--check1b pass|fail` enum would let the caller rubber-stamp it, and antigravity noted
the caller would have to decide it *before* seeing the mechanical results.
**Decision:** Two calls. Call 1 `verify_run checks --root … --subject …` runs the
mechanical checks and returns their results without writing the record. The LLM then
judges Check 1b. Call 2 `verify_run finalize --check1b-evidence-file <path>` validates
the evidence, applies the stop-at-first-FAIL ordering, writes the JSONL record, and
returns the verdict. The evidence file must enumerate every SPEC scenario with its test
node id or PLAN waiver reference, and carries the SPEC content hash and the diff hash it
was judged against.
**Consequences:**
- ✅ The checks' own mandated calls collapse from 8 to 2 (whole command 13 → 7 — see
  Phase 1's correction), with the judgment preserved and now *auditable*: today it is
  asserted in prose and recorded nowhere.
- ✅ Absent, malformed, or stale (hash-mismatched) evidence is a **FAIL**, not a skip.
  `--force` may override it exactly as it overrides any other check, and the override
  reason lands in the same JSONL field.
- ⚠️ A SPEC-less task must still produce an evidence file; for that case it declares
  `scenarios: []` with `reason: "no SPEC"`, which the CLI accepts and records.
**Rejected alternatives:**
- CLI owns all six checks with a name-matching heuristic for 1b — accepted-looking tests
  that never assert the scenario would pass.
- CLI executes, LLM reconstructs the verdict — keeps 6–8 round-trips for no safety gain
  over this design.
**Source:** Interview #3, second opinion (codex P1, antigravity P1)

### ADR-005: verify binds a subject, discriminates skip reasons, and aggregates them into the run verdict
**Status:** Accepted (2026-07-29, via cross-model second opinion; revised after plan-validator MAJOR_REVISION)
**Context:** Both models flagged, from different angles, that under this repo's
`exec-rev-wrap-ver` ordering ([ADR-015](#adr-015)) `wrapup` squash-lands and **deletes
the task worktree** before verify runs, so verify could report PASS over a state it
never examined. The validator then showed the first version of this ADR only *relabelled*
the hole: it governed Check 5's per-check value and never said how a skip aggregates into
the run verdict; it overloaded `SKIPPED` with the existing stopped-after-FAIL meaning
with no discriminator; and it never touched Check 5's own trigger, which
(`verify.md.j2:143`) fires only for `.worktrees/execute-*` and therefore **never matches
the flag-on per-task worktree `.worktrees/<slug>/` at all** — the check was already
inert before the land.
**Decision:** Four parts.
1. `verify_run` takes `--subject <worktree-path | commit-range>`. A subject that cannot
   be determined is a **FAIL** (`subject-undetermined`), never a pass.
2. Each per-check record carries `skip_reason ∈ {post-land, stopped-after-fail,
   not-applicable}` so "not inspectable" is distinguishable from "not reached" by a
   downstream consumer of `verify-<date>.jsonl`.
3. **Run-level aggregation:** a run containing any check skipped with
   `skip_reason: post-land` **and no FAILed check** emits run verdict `PARTIAL` with
   `uninspected: [<check ids>]` — never a bare `PASS`. `PARTIAL` is not a FAIL: it does
   not block, it refuses to claim what it did not inspect. **A run with any FAILed check
   is `FAIL`, never `PARTIAL`** — without that clause a `--force` run could report
   PARTIAL over a real failure and slip past `wrapup_receipt.py:393`, which raises
   `verify-result-inconsistent` only when the result is literally `PASS`.
   **Downstream mapping (mandatory — `PARTIAL` is a new value in two fixed contracts):**
   `PARTIAL` maps to Gate-0 receipt verdict **`pass`** (`iter_receipts.py:37` is
   `Literal["pass","fail","skipped"]`; extending that enum is not in scope) and to **exit
   code 0** (the stage contracts `0 for PASS or --force; non-zero for FAIL`). Both
   mappings are stated in `verify.md.j2`'s Gate-0 receipt `pass` criterion and asserted
   by a render test. This matters more than it looks: under this repo's
   `exec-rev-wrap-ver` ordering ([ADR-015](#adr-015)) Check 5 is post-land on **every**
   run, so `PARTIAL` is the normal verdict, not an edge case.
4. Check 5's trigger is extended to the flag-on task worktree (`hm/<slug>` /
   `.worktrees/<slug>/`) so it is capable of firing at all.
**Consequences:**
- ✅ The vacuous post-land PASS is closed at the level that matters — the run verdict —
  rather than at the per-check label.
- ✅ A check that was silently inert for every flag-on user since the feature-branch
  workflow shipped starts running.
- ⚠️ `PARTIAL` and `skip_reason` are **additive schema fields and a new run verdict**.
  This is a user-visible semantics change and is bounded by [ADR-016](#adr-016);
  Check 3's no-baseline PASS rule is explicitly NOT changed.
**Rejected alternatives:**
- Per-check `SKIPPED` only (the first version of this ADR) — relabels, does not close.
- Reusing `SKIPPED` without a `skip_reason` — leaves two meanings indistinguishable in
  the durable record.
- Making a post-land skip a FAIL — would fail every run under this repo's own default
  workflow ordering, which [ADR-015](#adr-015) deliberately left in place.
- Inferring the subject from cwd — the exact ambiguity the finding is about.
**Source:** Second opinion (codex P0, antigravity P0 — weak consensus, both retained); Interview #10

### ADR-006: `wrapup land` covers Steps 6 → 7.6 and stops before `task-land`
**Status:** Accepted (2026-07-29, via /hm:plan interview)
**Context:** Steps 6 through 7.7 are **six** fixed-order calls in the render — stage
(`:579`), commit (`:606`), `post-commit-pop` (`:639`, with `owned-crumb-clear`
`&&`-chained onto it rather than as its own call), `drain` (`:656`), `task-land`
(`:683`), `commit-base-memory` (`:708`) — but 7.7 `task-land` deletes the worktree the
caller is standing in and is the only step that can lose work. (Planning said "seven";
the line-level map taken during execute Phase 0 says six. The target below is unchanged:
the four calls of Steps 6 → 7.6 become one, leaving three.)
**Decision:** The composite performs **legacy-ref pre-scan** → stage → commit →
`post-commit-pop` → `owned-crumb-clear` (only on pop success) → `drain`, as **one**
mandated call. **The pre-scan runs BEFORE staging** so an abort produces no commit —
otherwise every retry would leave another committed state behind while hitting the same
scan. An explicit `--allow-legacy-ref` escape flag exists, matching the escape-flag
convention every layer of the 5-layer defense already follows. `task-land` and `commit-base-memory` remain explicit, separately invoked
steps in the stage prose, unchanged. The wrapup git tail (Steps 6 → 7.7 inclusive)
therefore renders as **3** calls.
**The legacy-ref pre-scan (added after plan-validator).** Codex flagged that
`post-commit-pop` restores base WIP *before* `task-land`, and `task-land` self-aborts on
a dirty base. The first version of this PLAN discharged that by asserting the
`feature_branch_workflow` path never produces a deferred stash. **That invariant is
false as stated.** `worktree.py:3330` skips a ref only when its `session_uuid` is
truthy AND unowned; `worktree.py:3339-3342` routes a **legacy ref with an empty
`session_uuid`** straight past the ownership gate to `_session_marker_present`. With an
empty crumb, a live legacy ref *is* popped, the base becomes dirty, and the land
deadlocks. So the composite scans for live legacy (no-uuid) refs **before staging**; if
any exist it stages nothing, commits nothing, reports them with the manual resolution
path, and exits non-zero. The remediation text it prints **must** carry the
`git stash show -p <ref>` preview obligation — CLAUDE.md's LLM behavior contract forbids
recommending `git stash drop` without a diff preview, and this is exactly the moment a
user reaches for it. The ordering and semantics of the shipped flow are otherwise
untouched.
**Consequences:**
- ✅ The destructive step keeps its own visible invocation, its own stderr, and its own
  operator decision point.
- ✅ The single input class that can produce the deadlock is gated, rather than the
  deadlock being discovered mid-land.
- ⚠️ A harness carrying live legacy refs now gets a loud stop at wrapup instead of a
  silent pop. That is the intended trade: the alternative is a base it cannot land from.
- ⚠️ `owned-crumb-clear` is inside the swallowed range (today it is `&&`-chained onto the
  pop at `wrapup.md.j2:634`), so the composite must reproduce its ordering constraint —
  clear only after a *successful* pop — and Phase 2 asserts both directions.
**Rejected alternatives:**
- Swallow 6 → 7.7 (7 → 1 call) — hides the only work-losing step behind a receipt.
- Stage+commit only — leaves most of the chain in place.
- Move the pop after `task-land` — structurally removes the deadlock but reorders the
  shipped flow, and whether restoring user WIP onto an already-squashed base is
  semantically equivalent needs its own verification. Deferred, not dismissed.
- Test the real property and accept the risk — leaves a known deadlock reachable.
**Source:** Interview #9, #11; second opinion (codex P0); plan-validator critical 4

### ADR-007: The staging step uses a typed manifest, not a tolerate-everything loop
**Status:** Accepted (2026-07-29, via cross-model second opinion)
**Context:** Today's staging is `[ -e "$p" ] && git add "$p" 2>/dev/null || true` per
path. That shell form treats an absent optional path, a permission error, an invalid
pathspec, and a genuine `git add` failure identically — all silent successes. Porting it
verbatim into Python would encode the defect.
**Decision:** `wrapup_land` takes a typed manifest: `required` paths (PLAN; memory tier
files when memory is enabled) and `optional` paths (REVIEW, RESEARCH, SPEC, machine
SPEC). An absent **optional** path is recorded as `absent-optional` and continues. An
absent **required** path, or any `git add` failure on either kind, is a hard error with
the git stderr verbatim. The receipt lists each path with its disposition.
**Consequences:**
- ✅ The failure the current form hides — deliverables dropped from the commit — becomes
  loud. (Observed 2026-05-30: wiki + failures silently missing from a wrapup commit.)
- ✅ This is the one place [ADR-003](#adr-003) permits new logic, because no library
  function owns it today.
- ⚠️ A pre-existing behavior is being tightened, so a harness whose memory tier files do
  not exist yet must classify them as optional-until-created; Phase 2 covers that case.
**Rejected alternatives:**
- Port the loop as-is — reproduces a known silent failure in a new place.
- Full index-ownership enforcement (reject foreign staged paths) — a behavior change to
  the execute→wrapup handshake, out of scope. The receipt records a pre/post index
  manifest so foreign staged content is at least *visible*; the policy question is
  deferred.
**Source:** Second opinion (codex P0 ×2)

### ADR-008: Test selection classifies changed files four ways
**Status:** Accepted (2026-07-29, via /hm:plan interview, amended by second opinion)
**Context:** The interview locked "any changed file with no test hint → that phase runs
the full suite." Both models then observed that `build_test_hints()` skips every file
whose suffix is not `.py`, so in this repo — where most changes are `.j2` templates,
markdown and config — the rule selects FULL essentially always, adding machinery while
preserving the full-suite cost it exists to avoid.
**Decision:** The locked decision stands for what it protects (a source file with no
known test must never be silently untested), but the predicate is sharpened. A
`test_dep_map select` CLI classifies each changed path:
1. `source-with-hints` → run those tests.
2. `source-without-hints` (a `.py` file no test maps to) → **FULL**, loudly, with the
   file named.
3. `render-affecting` (`templates/**`, `*.j2`, snapshot fixtures) → run the render,
   structural and snapshot suites — a bounded, named set, not FULL.
4. `inert` (markdown, docs, `work-docs/**`, `.claude/memory/**`) → contributes no tests
   and never forces FULL on its own.
**The classifier is a total function.** Deletions and renames resolve against their
pre-change path. **Any path matching none of the four rules — in-root or out — falls to
an explicit `default → source-without-hints (FULL, loudly)` arm.** The validator caught
that the first version defaulted only *out-of-root* paths, leaving in-root non-matches
(`pyproject.toml`, `uv.lock`, `.github/workflows/*.yml`, `tests/fixtures/*.json`,
`.claude/harness.yaml`) selecting **zero** tests — trading an always-FULL bug for a
sometimes-NONE bug, which is strictly weaker than today and contradicts this PLAN's
headline promise.
**Consequences:**
- ✅ The absent case is explicit and, per CLAUDE.md's most-recurring failure class,
  tested for the *absent* branch and not only the present one — including the default
  arm, which is the branch the first version omitted.
- ✅ The rule can actually select a subset for this repo's dominant change shape.
- ⚠️ Class 3's suite list is a curated constant, so a newly render-sensitive suite could
  silently stop running per-phase. That consequence now has a **detector**: a test fails
  when a directory appears under `tests/` that is neither in the class-3 list nor
  explicitly excluded. `verify`'s one full-suite run per work unit remains the backstop.
**Rejected alternatives:**
- The literal locked rule — measured to degenerate to FULL, defeating its own purpose.
- Hints for ordering only, always FULL — saves only the 3-commands-to-1 turn merge.
**Source:** Interview #5, second opinion (codex P2, antigravity P2 — consensus)

### ADR-009: Phase C type-checks once per file, not once per edit
**Status:** Accepted (2026-07-29, via /hm:plan interview)
**Context:** `execute` Phase C currently mandates a compile/type check after *each edit*,
which makes every implementation phase cost two turns per edit.
**Decision:** Check after finishing a file. The boundary is mechanical, so the prose can
state it unambiguously and a reviewer can tell whether it was followed.
**Consequences:**
- ✅ Roughly halves the turn count of edit-heavy phases.
- ⚠️ An error introduced early in a multi-edit file surfaces later than today. Bounded
  by the fact that type/lint output names the file and line.
**Rejected alternatives:**
- "Coherent logical unit" — unenforceable and not ratchetable; degrades to no rule.
- Status quo — the single most turn-expensive instruction in the pipeline.
**Source:** Interview #6

### ADR-010: research Phase 1 fans out to three read-only agents with a citation contract
**Status:** Accepted (2026-07-29, via /hm:plan interview)
**Context:** Phase 1 gathers from seven source classes serially in the main loop, and
every result stays in the prefix for the rest of the session. `grep`/`rg` output alone is
10.8% of carried context.
**Decision:** **Claude target only, target-conditional in the template.** When
`claude-code` is among `targets`, dispatch three read-only `Explore` agents in a single
message — codebase, internal `work-docs` + memory, external web + library docs. Each
digest **must** carry citations and verbatim snippets for the claims it makes; the main
loop opens originals only for the one or two claims that decide the recommendation. For
`cursor` and `codex` targets the block renders the **current serial procedure
unchanged**.
**Why target-conditional.** The validator established that `Explore` is a Claude Code
built-in, **not an asset this harness renders**: every `Task(` dispatch in the shipped
stage templates targets a harness-rendered agent (`judgment-reviewer`, `plan-validator`,
`test-reviewer`). `research.md.j2` renders for all three targets, so an unconditional
block would emit a dispatch to an agent that cannot resolve on Codex or Cursor — the
CLAUDE.md checklist-#2 failure class where the disk content is right and only the
executed content differs, which a render-grep cannot catch.
**Consequences:**
- ✅ Parallel wall-clock instead of serial on the target that has the mechanism, and the
  bulk of grep output never enters the main-loop prefix.
- ✅ No target is shipped a dispatch that cannot resolve.
- ⚠️ The 12.4%-of-wall-clock saving accrues to Claude Code users only. Cursor and Codex
  users get today's behavior, not a regression.
- ⚠️ Total compute increases even as latency falls; [ADR-012](#adr-012) requires
  reporting main-loop turns, subagent turns and carry separately so this is visible
  rather than hidden inside a favourable headline.
- ⚠️ A digest can drop the decisive detail. The citation + snippet obligation is the
  mitigation, mirroring the `[elided: …]` discipline the review stage already imposes.
**Rejected alternatives:**
- Render a harness-owned read-only researcher agent dual-rendered to `.claude/agents/`
  and `.codex/agents/` — the product-correct answer and the one that would extend the
  saving to all three targets, but it adds an asset to maintain and a version-sync
  surface. Deferred as its own change.
- Unconditional `Explore` dispatch — ships a broken dispatch to two of three targets.
- Four `general-purpose` agents — write-capable agents are unnecessary privilege in a
  read-only stage, and four approaches the practical 3–5 concurrency ceiling.
- `head_limit` discipline only — no parallelism, and it merely restates a rule CLAUDE.md
  already carries.
**Source:** Interview #7, #12; plan-validator warning 12

### ADR-011: The ratchet has three parts, including an aggregate shipped-surface total
**Status:** Accepted (2026-07-29, via /hm:plan interview, amended by second opinion)
**Context:** The interview locked a round-trip ratchet. Both models then showed a
count-of-`!` proxy cannot detect the failure it exists to prevent: several commands can
be `&&`-chained onto one line, Codex renders shell steps as `Bash(...)` rather than `!`,
a `Task(` inside an example inflates the count, and per-command ceilings with slack
permit every command to grow while the total rises. The prior compaction effort failed
in exactly the aggregate direction (−4,437 in one command, +3,765 in a heavily-invoked
one, net +0.75%).
**Decision:** Three assertions, plus an explicit counting rule and an amendment protocol.

*Counting rule (rewritten after the validator showed the first one unimplementable).*
The first version said "counted only outside fenced example blocks". There is no such
discriminator: `wrapup.md.j2:569` is a real `!` command **inside** a ```bash fence,
`plan.md.j2:548` is a real `Task(` inside a fence, and `execute.md.j2:384` is a fenced
`Bash(` — implemented literally the counter returns 0 and asserts nothing. The rule is
therefore a **consistent proxy, not a semantic count**: count `^!`-prefixed lines in the
Claude render, `Bash(` call sites in the Codex render, and **all** `Task(` occurrences,
fences included — applied identically to the baseline and to every later measurement.
An example added is still surface added; consistency is what a ratchet needs, precision
is not.

1. **Round-trip count** per rendered command and per target variant — ceiling **and**
   floor, under the rule above. **The round-trip floor is EXACT EQUALITY (zero slack)**,
   unlike the character floor's `measured * 0.80`. This is not a stylistic choice: with
   20% slack, removing one call from a command that has more than five stays inside the
   floor, so two of the three mutation checks below could never fail — and the mutation
   checks are the only evidence the ratchet works at all. The Cursor variant is counted
   by the Claude rule (`.cursor/commands/hm-*.md` uses `!`; the templates branch only on
   `is_codex`).
2. **Per-command characters** — the existing `test_command_size_budget.py` table,
   extended to all seven atomic commands (today it holds five fused entries and none
   atomic).
3. **Aggregate shipped surface** — the sum of rendered characters across every atomic
   and fused command for every configured target variant, against the Phase 0 frozen
   baseline, with a required net decrease. Stored as **per-command entries, not one
   scalar**, so a legitimate future addition (an eighth command, a new target) adds an
   entry instead of forcing the constant to be relaxed.

**Mutation checks — pointed at the arm that actually catches each.** The validator
showed the first version's single mutation was aimed at the wrong arm: `&&`-chaining two
commands onto one line *reduces* both the count and the characters, so it passes the
ceiling and the aggregate and can only be caught by the **floor** (and the shipped
render already `&&`-chains at `wrapup.md.j2:634`, so it is not even anomalous). Three
mutations are required:
- `&&`-chain two real calls onto one line → must fail the **round-trip floor**.
- Delete one real `!` line → must fail the **round-trip floor**.
- Move characters from one command into another → must fail the **aggregate** arm.

**Re-baseline protocol — owned by each cutting phase, not by one late phase.**
`_RATCHET`'s `measured` constants are what a shrinking render trips
(`floor = measured * 0.80`, `test_command_size_budget.py:209`). **Each cutting phase
lowers its own command's floor in its own commit, naming the removed calls in the commit
message.** No phase may raise a ceiling to pass, and no phase may lower a floor for a
command it did not cut.

> **Why ownership is distributed.** The first revision put the floor arm in an early
> phase and the re-baseline in a late one that "owns the budget table outright" and
> depends on all the cutting phases. That is circular: the early phase freezes
> pre-change floors, the first cut drops below one, and the phase that could re-baseline
> has not run — so no cutting phase can satisfy "structural suite green". Distributing
> the re-baseline removes the cycle without weakening the ratchet, because a floor may
> still only move in the commit that justifies it.
**Consequences:**
- ✅ The known aggregate failure mode is caught by construction, and the ratchet can now
  actually fail — proven by three mutations rather than asserted.
- ✅ The floor keeps the ceiling from being met by gutting the render — the failure that
  produced the withdrawn ADR-017 of the prior plan.
- ⚠️ Freezing the baseline is a Phase 0 obligation: measured **after a fresh re-render**
  (see Phase 0), committed with the render's commit SHA, and never recomputed from
  post-change output.
- ⚠️ Counting examples inflates absolute numbers. Accepted: the ratchet is relative.
**Rejected alternatives:**
- Fence-based discrimination — no implementable referent; the counter would assert nothing.
- A `<!-- @hm:roundtrip -->` marker at each real call site — precise, but a new call
  without a marker is silently uncounted, which is a worse failure than counting examples.
- Round-trip count alone — the proxy breaks in the ways codex named.
- Character budget alone — does not measure turns, which is what latency is made of.
**Source:** Interview #4; second opinion (codex P1 ×2, antigravity P1 — consensus); plan-validator critical 1, suggestion 19

### ADR-012: Measurement claims report turns, subagent turns and wall-clock separately
**Status:** Accepted (2026-07-29, via cross-model second opinion)
**Context:** Both models flagged over-reading: the delegation before/after is 6 runs
versus 2, described as suggestive, and assistant turns are not wall-clock. The
`research` fan-out in particular is expected to *increase* total compute while decreasing
latency.
**Decision:** The success criteria report, for each stage, pre and post: **four**
quantities — main-loop assistant turns per run, subagent turns per run, active wall-clock
per run (identical 300 s idle-gap methodology), and **mean context / carry ratio** from
`economics composition --root .` — each with its sample count `n`. No single headline
number. A claim of improvement names which quantity moved and states `n`.

**Carry is the fourth quantity because the fan-out is the thing that risks it.**
Antigravity's "the ratchet ignores context bloat" was only half discharged by ADR-011
(shipped surface) and the turn/wall-clock pair: three digests plus their verbatim
snippets re-enter the main-loop prefix and stay there. CLAUDE.md already names
`economics composition` as the only verification for the carry rules, so this costs no
new methodology.

**Pre-registration.** Phase 0 records, before any measurement, at least one directional
prediction: **verify main-loop turns per run must be strictly lower post-change.** If
the post measurement does not show it, the receipt must either explain the discrepancy
or the composite is reverted. Without a pre-registered direction the receipt is a
description, not a check, and R8 would be unmitigated.
**Consequences:**
- ✅ A latency win paid for with compute — or with carry — is visible as exactly that.
- ✅ Phase 7 can now fail.
- ⚠️ With `n` in the single digits, the receipt will read "consistent with" rather than
  "caused by". That is the honest form.
**Rejected alternatives:**
- A single combined efficiency figure — reproduces the ratio failure mode that
  `[wiki:architecture] harness-economics-observability` ADR-002 forbids by construction.
- Reporting without a pre-registered direction — unfalsifiable.
**Source:** Second opinion (codex P2, antigravity P1/P2 — consensus); plan-validator warnings 13, 16

### ADR-013: Rejected — collapsing the per-stage `task-preflight` and Gate-0 calls
**Status:** Accepted (2026-07-29, via code inspection during Step 1)
**Context:** The research doc listed four `task-preflight --stage` calls and four Gate-0
receipt emissions in the fused workflow as redundant.
**Decision:** Both stay. `--stage` feeds `stage_spans.emit_event`, which is the span
source `economics.py` consumes for per-stage attribution (`worktree.py:4228`,
`economics.py:16`); collapsing them destroys the instrument that measures this work. One
Gate-0 receipt per stage *is* the autoloop's missing-stage detector
(`test_command_size_budget.py` AC-006).
**Consequences:**
- ✅ The measurement apparatus survives the optimization aimed at it.
- ⚠️ Eight round-trips per fused run stay on the table permanently.
**Rejected alternatives:**
- Collapse to one preflight and re-derive stage boundaries by adjacency — adjacency is
  precisely the weaker fallback the span mechanism replaced.
**Source:** Step 1 code investigation

### ADR-014: Rejected — adding `verify` to `delegation.stages`
**Status:** Accepted (2026-07-29, via derivation from ADR-004)
**Context:** The research doc proposed enabling the existing `stage-delegate` path for
verify.
**Decision:** Withdrawn. Once [ADR-004](#adr-004) reduces verify to two calls, the
delegate's brief derivation plus receipt reconciliation costs more round-trips than it
removes.
**Consequences:**
- ✅ No new dispatch on a stage that no longer needs one.
- ⚠️ verify keeps whatever prefix the session already accumulated; per
  `[wiki:architecture] carry-is-a-main-loop-phenomenon` delegation would not have fixed
  that anyway.
**Source:** Derived from Interview #3

### ADR-015: Out of scope — the verify↔wrapup ordering
**Status:** Accepted (2026-07-29, via /hm:plan interview)
**Context:** This repo sets `default_workflow: exec-rev-wrap-ver`, so wrapup commits and
squash-lands before verify runs; the shipped Production default is `exec-rev-ver-wrap`.
**Decision:** Not fixed here. Every design in this PLAN assumes wrapup runs first.
**Consequences:**
- ⚠️ verify's subject may be a landed commit range rather than a worktree — the reason
  [ADR-005](#adr-005) exists. Without ADR-005 this deferral would have shipped a vacuous
  post-land PASS.
- ⚠️ A verify FAIL still arrives after the commit has landed.
**Rejected alternatives:**
- Fix the config in this PLAN — the user scoped it out; it is a one-line change whenever
  they choose.
**Source:** Interview #8

### ADR-016: The verify semantics change is bounded to run-level aggregation
**Status:** Accepted (2026-07-29, via /hm:plan interview after plan-validator MAJOR_REVISION)
**Context:** The first draft's reconciliation table accepted codex's Check 3 finding with
"'current score could not be computed' is a FAIL, never the no-baseline PASS" while
Phase 1's scope said "(out): any change to the check semantics". The validator showed
this is a direct contradiction — `verify.md.j2:127` today PASSes exactly when the
`score:` line is missing — and that the asymmetric outcome is silent: keeping the shipped
PASS discharges nothing while the table claims acceptance.
**Decision:** Exactly one class of verify semantics change is in scope: the run-level
aggregation of not-inspectable checks ([ADR-005](#adr-005) parts 2–4 — `skip_reason`,
`PARTIAL`, and Check 5's trigger). **Check 3's no-baseline PASS rule is preserved
byte-for-byte.** The codex Check 3 finding is downgraded to *partially accepted*: its
API half is discharged (`readiness.compute_readiness`, `dashboard.parse_dashboard` are
named in the Technical Design), its FAIL-on-uncomputable half is **deferred** and
recorded as such.

> **"Byte-for-byte" applies to all three copies.** Validation pass 2 established that
> verify's semantics live in three places, not one: `templates/stages/verify.md.j2`,
> `cli.py`'s `verify` command (`_verify_structural_check` at `cli.py:1935` carries the
> no-baseline rule in code), and
> `templates/skills/verify-before-completion/SKILL.md.j2:78-83`. `verify.md.j2:208-210`
> states that changing the gating checks means changing that SKILL — and
> [ADR-005](#adr-005) part 4 does change one (Check 5's trigger). So the SKILL is in
> scope for that single change and out of scope for everything else, and the
> preservation claim is asserted against all three copies, not just the template.
**Consequences:**
- ✅ Phase 1's scope boundary and the reconciliation table now agree.
- ✅ Existing user harnesses without a dashboard baseline keep passing.
- ⚠️ An uncomputable current structural score still yields PASS. Named as a known,
  deferred gap rather than silently retained.
**Rejected alternatives:**
- Full fail-closed (uncomputable = FAIL) — introduces new FAILs in existing harnesses.
- Semantics freeze (no change at all) — leaves the vacuous post-land PASS, which is the
  defect two independent models raised at P0.
**Source:** Interview #10; plan-validator critical 3

### ADR-017: Release ordering owns the module-before-template constraint
**Status:** Accepted (2026-07-29, after plan-validator MAJOR_REVISION)
**Context:** R9's mitigation named the five-file version sync but no phase owned it. A
user re-renders, their rendered command calls `python -m harness_maker.verify_run`, and
their pinned version lacks the module — a hard failure at gate time.
**Decision:** The five-file version sync (`.claude-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`,
`src/harness_maker/__init__.py`) plus the CHANGELOG entry is Phase 8's scope, and the
ordering constraint is stated as a release invariant: **no rendered template may
reference a module in a release that does not contain it.**
**Consequences:**
- ✅ The failure mode has an owner and an exit criterion.
- ⚠️ Adds a phase whose whole content is release hygiene. Correct — CLAUDE.md's
  §버전업 정책 exists because this was already missed once at 0.4.9.
**Rejected alternatives:**
- Leaving it in the risk table — a mitigation with no owner is not a mitigation.
**Source:** plan-validator warning 15

### ADR-018: `hm` — a short console script, added because the ratchet and the mechanism were in conflict
**Status:** Accepted (2026-07-29, during execute, on the user's decision)
**Context:** Phase 4 landed its classifier, then could not land its template half. Every
mandated call carries the prefix `python -m harness_maker.` — 24 characters, **390
occurrences** across the shipped surface. So [ADR-002](#adr-002)'s central mechanism
(replace short inline command sequences with composite CLI calls) *adds* characters while
removing round-trips: measured, Phase 4's edit was **+220 characters in `execute` and
+1,100 in the Claude aggregate against −1 round-trip**, after compressing its prose twice.
[ADR-011](#adr-011) assertion 3 then failed, and its two escapes are both closed by
design — no phase may raise a ceiling, and the baseline may not be re-frozen once a phase
has cut. The conflict was structural, not local: Phase 1 replaces 6 short check lines
with 2 long CLI lines, Phase 2 replaces 4 with 1, and neither had established that it
came out net-negative.
**Decision:** Ship a `hm` console script (`[project.scripts]`, `harness_maker.hm:main`)
and rewrite every template call site from `python -m harness_maker.<mod>` to `hm <mod>`.
`hm` **dispatches**: `runpy.run_module(target, run_name="__main__")` is literally the
code path `python -m` takes, so argument parsing, exit codes and `SystemExit` semantics
are the module's own and there is no second implementation to drift
([ADR-003](#adr-003)). Module names are validated against an explicit `_DISPATCHABLE`
allowlist, and a structural test asserts the allowlist covers every module the rendered
surface actually calls — in **both** spellings, so the gate binds during and after the
rewrite.
**Measured result (rewrite applied, then REVERTED — read the scope note):** claude
**−6,216** chars, codex **−1,974**, round-trips **unchanged**. With that headroom Phase 4's
template half landed at −1 char and −1 round-trip, aggregate **−4,730 / −1,688**. The
saving and the unblock are both real and both reproducible.

> **⚠️ The rewrite is scoped, not shipped.** Applying it repo-wide turned the full suite
> red: **95 failures across 24 files**. The rewrite is not a template change — it is a
> change to a *literal that ~30 test files assert*, plus committed e2e sandbox fixtures,
> plus `settings.json` permission allow-rules (which did follow correctly:
> `Bash(uv run --with $HOME/harness-maker hm *)`). A blanket `sed` is also **unsafe**: it
> rewrote the long form inside *prose* that deliberately names it, including this work's
> own test docstrings, and it broke `commands/hm/make.md.j2:41` — the bootstrap that
> resolves the install location *in order to build the `--with` pin*, where `hm` does not
> exist yet. That is CLAUDE.md checklist #2's failure class, and
> `test_the_make_bootstrap_resolves_a_version_not_a_positional` caught it.
>
> **What landed:** `src/harness_maker/hm.py`, the `hm` entry in `[project.scripts]`,
> `tests/structural/test_hm_entrypoint.py` (9 tests, incl. exit-code parity against the
> real `python -m` form and an allowlist-coverage gate that reads BOTH spellings), and
> `_instruction_baseline.canonicalize` so the instruction gate treats the rename as a
> rename. All additive, all green.
>
> **Second attempt, also reverted — and now the scope is exact.** The targeted
> substitution *was* built and run: restrict the pattern to module names actually in
> `_DISPATCHABLE`, apply it only to `templates/{stages,commands/hm,agents/_partials}`,
> protect the bootstrap line with a sentinel, add `Bash(uv run --with … hm *)` to both
> settings presets' allow lists, and regenerate the snapshot fixtures. That works:
> **−6,195 chars (claude) / −1,974 (codex)**, essentially the full saving, with a much
> narrower blast radius than the blanket `sed`.
>
> It still leaves **59 failures across 18 test files**, and the remaining ones are NOT
> mechanically fixable. They assert the bare substring `"harness_maker.<mod>"` — without
> the `python -m ` prefix — so the module-restricted pattern does not match them, and a
> pattern that did would rewrite every `from harness_maker.<mod> import …` statement in
> the same files. Worse, the correct expectation differs per assertion: hooks and the
> bootstrap keep the long form, so a file-wide rule is wrong even where it is safe.
>
> **What Phase 0.75 must still do, per file, with judgment:**
> `test_render_stage_receipts.py` (21), `test_autopilot_template_render.py` (7),
> `test_wrapup_brief_rendered_argv.py` (5), `test_render_metrics_economics.py` (4),
> `test_codex_stage_procedures.py` (4), `test_stage_template_memory_loader.py` (4),
> `test_render_delivery_metrics.py` (2), `test_permission_syntax.py` (2), and ten files
> with one each. For each assertion: does it check a **stage/command** call (→ `hm X`) or
> a **hook / bootstrap / allow-rule** call (→ unchanged)?
>
> **Third pass — 59 → 10, and the tree is currently RED on those 10.** The mechanical
> layers are done: `python -m harness_maker.<mod>` in test literals, the bare
> `harness_maker.<mod>` substring inside membership assertions, then the same bare form
> everywhere except `import` / `setattr(` / `patch(` lines, then regex-ESCAPED literals
> (`harness_maker\.<mod>`) inside test regexes — that last one is why several files
> looked unfixable after the first two passes.
>
> **The 10 that remain need per-assertion judgment and are NOT mechanical:**
> `test_wrapup_brief_rendered_argv.py` (5 — extracts rendered argv and re-executes it),
> `test_permission_syntax.py` (2), `test_allow_literal_prune.py` (1),
> `test_delegation_cli_boundary.py` (1), `test_render_codex_permission_injection.py` (1).
>
> **One open risk was closed by measurement, and it was the big one.** The allow-rule
> form was the live functional worry: if `Bash(uv run --with <p> hm *)` did not match,
> every mandated call would hit a permission prompt. It does —
> `permission_syntax.rule_matches_command` returns True for ` *`, `:*` and `*` forms
> alike. The two `test_permission_syntax` failures are about the test's own hardcoded
> rule fixture (`… python -m harness_maker*)`, no dot), not about the shipped rule.
>
> `test_allow_literal_prune` needs a prune entry: the shipped literal
> `Bash(… python -m harness_maker.second_opinion_invoke:*)` is deliberately retired in
> favour of the `hm` form, and that file's contract is that no shipped literal
> disappears unaccounted for.
>
> One trap found the hard way and worth stating: the first blanket `sed` rewrote
> `_instruction_baseline.canonicalize`'s own replacement string, turning the
> rename-fold into a no-op — the gate silently stopped folding and reported every
> rewritten line as a removal. A rewrite that touches the tooling which validates the
> rewrite needs that tooling excluded explicitly.
**Consequences:**
- ✅ The cause is fixed at the source: `hm` exists, is dispatch-only, and is proven
  equivalent to `python -m` by exit-code parity rather than by assertion.
- ✅ The unblock is *measured*, not projected — Phase 4 was landed under it and then
  reverted with the rest.
- ⚠️ Until the rewrite ships, every cutting phase remains blocked by the original
  conflict. Nothing about that conflict changed; only the remedy is now in hand.
- ⚠️ `_EXEMPT_EXEC` in `test_command_size_budget.py` will need both spellings when the
  rewrite lands, or the autopilot block reads as a NEW fusion loss.
**Source:** execute Phase 4 blocker; user decision 2026-07-29

## 🏗️ Technical Design

**Current state.** Stage behavior lives entirely in Jinja2 templates under
`src/harness_maker/templates/stages/`. Each renders to `.claude/commands/hm/<stage>.md`;
fused workflows are composed by `workflow_fuse.fuse()`. Deterministic work is expressed
as `!`-prefixed shell lines the model executes one per turn.

**Affected components.**

| Component | Change |
|---|---|
| `src/harness_maker/cli.py` — `verify` command | **extended** (not replaced): the two-call split, `skip_reason`, run-level `PARTIAL`, subject binding. Already owns `_verify_structural_check` (:1935) and `_write_verify_jsonl` (:2016) |
| `templates/skills/verify-before-completion/SKILL.md.j2` | Check 5's trigger only (`:78-83`); every other gating rule untouched |
| `src/harness_maker/wrapup_receipt.py` | `verify-result-inconsistent` must treat `PARTIAL` correctly (`:393` matches only literal `PASS`) |
| `src/harness_maker/wrapup_land.py` | **new** — pre-scan/stage/commit/pop/drain orchestration (ADR-006, ADR-007) |
| `src/harness_maker/spec_machine.py` | additive `check --all` subcommand |
| `src/harness_maker/test_dep_map.py` | additive `select` CLI + four-way classification (ADR-008) |
| `templates/stages/verify.md.j2` | the checks' 8 `!` → 2 (whole command 13 → 7) |
| `templates/stages/wrapup.md.j2` | git tail 7 calls → 3 |
| `templates/stages/spec.md.j2` | 3 validation calls → 1 |
| `templates/stages/execute.md.j2` | Phase C granularity, Phase D selection |
| `templates/stages/research.md.j2` | Phase 1 fan-out block |
| `tests/structural/test_roundtrip_budget.py` | **new** — three-part ratchet (ADR-011) |
| `tests/structural/test_command_size_budget.py` | extended to all seven atomic commands |

**Dependencies.** No new third-party packages. The composites call only existing
harness-maker functions plus `git` via the established `subprocess.run(check=True,
capture_output=True, text=True, timeout=N)` convention — never `shell=True`.

**Data flow (verify).** `verify_run checks --root --subject` → JSON results (no record
written) → LLM judges Check 1b with the mechanical results in hand → writes the evidence
file → `verify_run finalize --check1b-evidence-file` → validates evidence against the
SPEC content hash and the diff hash → applies stop-at-first-FAIL → aggregates
`skip_reason: post-land` skips into a run-level `PARTIAL` with `uninspected[]`
([ADR-005](#adr-005)) → appends `.claude/observability/verify-<date>.jsonl` → prints the
text block and returns the exit code the stage already contracts for.

> **Diff-hash under a landed subject.** When `--subject` is a commit range the working
> diff is empty, so the evidence file's diff hash is computed over **the landed range's
> diff** (`git diff <base>..<tip>`), not `git diff HEAD`. Stating this closes the residual
> codex left open on the Check 1b finding: without it, a post-land evidence file would
> hash an empty diff and every stale evidence check would pass.

**Data flow (wrapup).** `wrapup land --worktree <WT> --base <BASE> --manifest-file <m>
--message-file <msg>` → stage each manifest path with its disposition (cwd = `<WT>`) →
commit (cwd = `<WT>`) → `post_commit_pop` (cwd = `<BASE>`, ownership env from the slug
crumb) → `drain` (cwd = `<BASE>`) → per-step receipt to stdout. The CLI never changes the
caller's cwd; both roots are explicit arguments resolved through git metadata, and a root
that is not a git worktree of the expected repo is refused rather than defaulted to
`Path.cwd()`.

**Design decisions referencing ADRs.** Composites are sequencing only
([ADR-003](#adr-003)); the only new logic is the staging manifest
([ADR-007](#adr-007)); unknown state never becomes PASS ([ADR-004](#adr-004),
[ADR-005](#adr-005)); measurement is three-part and pre-frozen
([ADR-011](#adr-011), [ADR-012](#adr-012)).

**API changes.** All additive. Existing `spec_machine` subcommands, `verification_cache`,
`post_commit_pop`, `drain` and `task-land` keep their current signatures and semantics.

## 📝 Implementation Plan

> **Namespace note.** Implementation-phase ids below are **labels**, ordered by the
> execution sequence stated next — not ordinals. `Phase 0.5` is named for where it runs
> (before any cutting), and is deliberately not renumbered: this document also contains
> the *research stage's* own Phase 0/0.5/0.75/1, a separate namespace, and a mechanical
> renumbering would corrupt those references. "Phase N" inside a stage description always
> refers to that stage's phases.
>
> **Ordering note.** Phases run 0 → 0.5 → 1 → 2 → 4 → 5 → 3 → 6 → 7 → 8. Phase 3
> (`spec_machine`) sits late deliberately: `spec` is measured at 0.9% of turns and 0
> invocations in this repo's transcript window, so it must not delay Phase 4, which
> carries the largest measured lever (`execute`, 21.1% of active wall-clock). The
> `merge_hazards` set is identical for all of 1–5, so the serial constraint is unaffected
> by the reordering.
>
> **Every phase's exit criterion additionally requires the full structural suite to be
> green.** Phases 1–5 each shrink a rendered command and therefore move
> `test_command_size_budget.py`'s floors; a phase that leaves that suite red is not done.

### Execution progress (updated by `/hm:execute`)

| Phase | Status |
|---|---|
| 0 — freeze the baseline | **DONE** — A.5 PASS, artifacts committed |
| 0.5 — floor arm + aggregate | **DONE** — A.5 PASS, 117 structural tests green |
| **0.75 — `hm` console script** (added during execute) | **DONE** — entrypoint + full template rewrite landed (`d98355d6`). See [ADR-018](#adr-018) |
| 1 — verify two-call composite | **SKIPPED — user decision, 2026-07-29.** Ranks first on mandated calls (−6) and last on wall-clock: `verify` does not appear in BASELINE §2's table at all, and it is the most expensive phase to build (five checks that do not exist in `cli.py` today + five golden fixtures). **PR-1 is therefore un-evaluated, not failed** — see `RECEIPT-workflow-step-audit.md` §0 |
| 2 — `wrapup_land` | **DONE** — module + 18-case unit matrix + template collapse. Criterion (j), the manual `/hm:wrapup` run, is outstanding |
| 4 — `test_dep_map select` | **DONE** — classifier (earlier commit) + template half (Phase C per-file, Phase D select-then-one-call) |
| 5 — research fan-out | **DONE, and dormant in this repo** — `targets` includes `cursor`, and Cursor reads the Claude command file, so the gate is `cursor not in targets`. Implemented and tested on both arms; renders nowhere here. See RECEIPT §2(b) |
| 3 — `spec_machine check --all` | **DONE** — Steps 4 + 4.5 collapse to one call. Δ 0 by ADR-011's rule (those were never `!` lines) but two real turns removed |
| 6 — round-trip arm | **DONE** — `tests/structural/test_roundtrip_budget.py`, exact equality, proven failing under all three mutations. Every ratchet re-baselined with a per-entry reason |
| 7 — re-measurement receipt | **PARTIAL** — `RECEIPT-workflow-step-audit.md`. The surface measurement is complete; the four ADR-012 turn/wall-clock quantities are `n = 0` because no stage has run against the change yet, and the receipt says so rather than reporting zeros as results |
| 8 — release sync | **DONE** — five files at `0.44.0` + CHANGELOG. The release invariant (no rendered template names an unregistered module) is already asserted by `test_command_surface_gate.py::test_tc1_every_template_invocation_is_registered` |

**Resume contract.** Phases 0 and 0.5 are the *measurement apparatus and the ratchet*,
which this PLAN deliberately ordered to land **before any cutting**. They are therefore a
coherent stopping point: nothing has been cut, every gate the later phases will be judged
against is now in place and demonstrably able to fail, and the working tree is green. A
later session resumes at Phase 1 with no reconstruction work — the two corrections
execute discovered (verify's real round-trip arithmetic, wrapup's real call count) are
recorded inline above, and the `dev_mode` axis rule under Phase 0.5 is a precondition
Phase 1 must respect.

**Two things Phase 1 must not repeat:**
1. Its first act should be to add its removals to `_ALLOWED_REMOVALS` keyed
   `verify@task-driven` **and** `verify@spec-driven` — Check 6's `!spec_need` calls exist
   only in the latter, and this repo renders the former.
2. `cli.py`'s `verify` command today runs **only** Check 3; checks 1/2/4/5 are emitted as
   literal `SKIPPED` records (`cli.py:1897-1903`). "Extend, do not replace" therefore
   means writing five checks that do not exist yet, not refactoring five that do — the
   differential oracle in exit criterion 1 has a real referent only for Check 3.

### Phase 0 — Re-render, then freeze the pre-change baseline
- **Status: DONE** (execute, 2026-07-29). Artifacts:
  `tests/structural/_surface_baseline.py` (generator),
  `tests/structural/surface_baseline.json` (frozen at `bc6932b2`, aggregate
  claude 828,690 + codex 311,029 chars),
  `work-docs/BASELINE-workflow-step-audit.md` (turn / wall-clock / carry table +
  pre-registered direction PR-1). Phase A.5 test-reviewer: **PASS** on the third
  invocation (two FAIL rounds, both discharged — see the note below). 13 tests green.
  - **Deviation, recorded rather than smuggled:** the "fresh re-render" is produced
    **in-process** by the generator, not written to `.claude/`. This repo gitignores
    `.claude/*`, so there is no committed render to refresh and a fresh worktree has
    none at all. Rendering in-process from the committed `.claude/harness.yaml` makes
    the render fresh by construction, which is what Pitfall 9 asked for; `render_sha`
    pins which templates produced it, and `assert_sha_is_durable` refuses to freeze
    against a commit a squash-land would delete.
  - **Two target variants, not three:** `.cursor/commands/` is dead code in
    `render.py:571-582`, so Cursor loads the Claude render. [ADR-011](#adr-011)'s
    "the Cursor variant is counted by the Claude rule" holds trivially.
- `depends_on`: `[]`
- `parallel_group`: `serial-a`
- `merge_hazards`: none
- **Scope (in):** (1) a **fresh re-render** of this repo's harness as the *first* action,
  with the render's commit SHA recorded in the baseline file; (2) a committed baseline
  **generator script** (`tests/structural/_surface_baseline.py`) that emits, per rendered
  command and per target variant, the character count and the round-trip count under
  [ADR-011](#adr-011)'s counting rule; (3) the current per-stage turn / wall-clock /
  carry table; (4) the pre-registered direction from [ADR-012](#adr-012).
  **(out):** any template or module edit.
- **Why the re-render is first:** `[[RESEARCH-workflow-step-audit]]` Pitfall 9 records
  that the local render is stale relative to `9f809f3f` (`feat(fuse): hoist shared stage
  prose`). Since [ADR-011](#adr-011) forbids ever recomputing the baseline, measuring
  against a stale render would permanently credit that earlier hoist to this PLAN.
- **Exit criterion:** the baseline file exists, is **non-empty and parses**, carries the
  render SHA, and was produced by the committed generator — the same generator Phase 6
  imports, so both sides compute the identical quantity. (A bare `… > <file>` redirection
  is not acceptable evidence: it creates the file even when the command errors.) The
  pre-registered direction is recorded before any post-change measurement exists.
- **Risk:** `low`
- **Rollback:** delete the baseline file and the generator.

### Phase 0.5 — Land the floor arm and the aggregate baseline BEFORE any cutting
- **Status: DONE** (execute, 2026-07-29). Phase A.5 test-reviewer: **PASS** on the second
  invocation (one FAIL round carrying two blocking issues, both discharged — the
  `dev_mode` blind spot below and a negative control that re-implemented the gate instead
  of invoking it). 117 structural tests green.
  Artifacts: `_ATOMIC_RATCHET` + `test_atomic_commands_within_budget` +
  `test_the_atomic_table_covers_every_atomic_command` +
  `test_aggregate_shipped_surface_does_not_grow` in `test_command_size_budget.py`;
  new `tests/structural/_instruction_baseline.py`, `instruction_baseline.json`,
  `test_instruction_preservation.py`.
  - **The exit criterion is met by the instruction gate, not by the floor.** Deleting
    line 55 of `templates/stages/review.md.j2` (a real `!second_brain search` call) made
    **exactly one** test fail — `test_no_unlisted_instruction_disappeared[executables-review]`
    — while every character-budget arm stayed green. At 20% slack a one-line deletion is
    ~0.5% of an atomic command, so the floor is structurally blind to it. A green floor
    is therefore **not** evidence that nothing was removed; say so wherever it is cited.
  - **The aggregate arm asserts non-increase, not the strict decrease [ADR-011](#adr-011)
    words.** At this phase the render *is* the baseline, so a strict `<` would fail by
    construction. The strict decrease is Phase 6's final re-verification and the
    Success Criteria bullet; the ratchet arm is the non-increase. **Residual, recorded:**
    nothing *obliges* Phase 6 to tighten `<=` to `<` except this PLAN's prose.
  - **A blind spot the first cut of this phase shipped, caught by the A.5 gate.** A
    stage template has one rendering per config arm that gates instructions.
    `verify.md.j2:153` wraps Check 6 — including two real `!spec_need` calls — in
    `{% if config.dev_mode == 'spec-driven' %}`. This repo's harness is `task-driven`, so
    the first instruction snapshot did not contain those lines and **could never report
    them as removed**; meanwhile `test_command_size_budget.py`'s fixture renders the
    *other* arm (`InterviewAnswers` defaults to `SPEC_DRIVEN`, `models.py:948`) with a
    20% floor that cannot see two deleted lines. Complementary blind spots, on the exact
    file [Phase 1](#phase-1--extend-clipys-verify-command-into-the-two-call-composite)
    edits — Phase 1 could have deleted Check 6 with the whole suite green.
    **Fix:** entries are keyed `<command>@<dev_mode>` and both arms are frozen
    separately. **Not a union** — a union leaves a line deleted from one arm visible via
    the other, which is the same hiding the gate exists to prevent. Verified by deleting
    `verify.md.j2:171` (spec-driven-only): exactly one arm fails,
    `test_no_unlisted_instruction_disappeared[executables-verify@spec-driven]`.
  - **Axes knowingly not covered:** `preset`, `targets`, `second_brain`,
    `second_opinion`, `delegation`, `worktree.feature_branch_workflow`. Each can gate a
    template block. A later phase that edits a block gated on one of them **must extend
    `AXES` first** — the same silent-projection trap, one axis over.
- `depends_on`: `[0]`
- `parallel_group`: `serial-a`
- `merge_hazards`: `tests/structural/test_command_size_budget.py`
- **Scope (in):** extend `test_command_size_budget.py` to all seven atomic commands
  (today: five fused entries, zero atomic) and add [ADR-011](#adr-011) assertion 3
  (aggregate, per-command entries) against Phase 0's baseline. **(out):** the round-trip
  arm, which needs the post-change renders and stays in Phase 6.
- **Note on ownership:** this phase *creates* the table entries; it does not own them
  afterwards. Under [ADR-011](#adr-011)'s re-baseline protocol each cutting phase lowers
  its own command's floor in its own commit. Without that distribution this phase and
  Phase 6 form a cycle — pre-change floors frozen here, the first cut drops below one,
  and the only phase permitted to re-baseline runs last.
- **Why before the cutting:** the floor exists to catch a size target met by deleting
  runtime behavior — the withdrawn ADR-017 failure of the prior plan. If it lands in
  Phase 6 it is measured from the already-reduced render, so the phases that actually
  delete (1–5) run unguarded. This is the validator's warning 11 and it is the reason
  this phase exists at all.
- **Exit criterion:** the extended suite is green against the **pre-change** render; a
  deliberate deletion of a runtime instruction from any atomic command fails it.
- **Risk:** `low`
- **Rollback:** revert to Phase 0.

### Phase 1 — Extend `cli.py`'s `verify` command into the two-call composite
- `depends_on`: `[0.5]`
- `parallel_group`: `serial-a`
- `merge_hazards`: `tests/structural/test_command_size_budget.py`, `tests/e2e/sandbox-plugin-test/.claude/commands/**` snapshots
- **Scope (in):** `cli.py`'s existing `verify` command (`:1844`) — **extended, not
  replaced**, per [ADR-003](#adr-003), because it already owns `_verify_structural_check`
  (`:1935`) and `_write_verify_jsonl` (`:2016`) and a new module would be a second
  producer of one durable record; `templates/stages/verify.md.j2`;
  `templates/skills/verify-before-completion/SKILL.md.j2:78-83` **for Check 5's trigger
  only**; `wrapup_receipt.py:393`'s `PARTIAL` handling; tests; render test. The bounded
  semantics change [ADR-016](#adr-016) permits (`skip_reason`, run-level `PARTIAL`,
  Check 5's trigger).
  **(out):** every other check semantic — in particular Check 3's no-baseline PASS rule,
  preserved byte-for-byte **in all three copies** — and `--force` behavior.
- **Round-trip target (restated TWICE — see the correction below).**
  The rendered `verify.md` carries 13 `!` lines today. The six checks collapse to **2**
  mandated calls; that is the design target and it is unchanged. The *derived*
  whole-command number is **13 → 7**, not the 13 → 4 this PLAN carried through planning.

  > **Correction, made during execute Phase 0 from a line-level map of the actual
  > render** (this repo is `dev_mode: task-driven`, so the render carries "The 5 Checks"
  > — Check 6 is the spec-driven arm and does not appear):
  >
  > | Owner | `!` lines | n |
  > |---|---|---|
  > | Check 2 — regression smoke | 130, 143, 144, 145, 146, 160 | 6 |
  > | Check 5 — worktree merge cleanliness | 189, 190 | 2 |
  > | Checks 1, 3, 4 | — | **0** |
  > | Gate-0 receipt guard ([ADR-013](#adr-013)) | 228 | 1 |
  > | `task-preflight` ([ADR-013](#adr-013)) | 298 | 1 |
  > | `task-refresh` — conditional drift remedy, not on the normal path | 307 | 1 |
  > | autopilot `gate-blocked` / `boundary` | 354, 360 | 2 |
  >
  > The checks own **8** calls, not 11. Collapsing them to 2 removes **6**, so
  > `13 − 6 = 7`. The earlier figure assumed everything except the two
  > [ADR-013](#adr-013) calls belonged to a check; the autopilot pair and the
  > `task-refresh` remedy are outside the six checks entirely and are shared blocks
  > present in every stage command — removing them is neither in scope nor desirable.
  > Checks 1, 3 and 4 contribute **zero** round-trips today (they read files and judge),
  > so the saving is bounded by Check 2 and Check 5 alone.

  **7** is therefore the number the ratchet measures.
- **Exit criterion (four parts):**
  1. **Semantics oracle — differential where one exists, golden where it cannot.**
     Check 3 gets a **real executable differential**: the extended path's verdict must
     equal `_verify_structural_check`'s on the same inputs, including the no-baseline
     PASS. Checks 1a/1b/4/5 are LLM- or filesystem-judged, so they get **golden
     per-fixture expectations** on a repo constructed to trip each in turn (drift verdict
     absent; suite red; structural drop > 5; unresolved high finding; unmerged path),
     with **stop-at-first-FAIL ordering asserted**. Stating this honestly matters: the
     first draft called the whole thing a "differential against the current 13-call prose
     sequence", and prose has no executable referent. What is falsifiable here is the
     stub — five hardcoded PASSes cannot pass fixtures built to fail.
  2. **Run verdict, not just check verdict.** For a landed-range subject the **run**
     emits `PARTIAL` with `uninspected: [5]` — never bare `PASS`; a run with any FAILed
     check is `FAIL`, never `PARTIAL`; an undetermined subject is `FAIL`; each skipped
     check carries the right `skip_reason`. **`PARTIAL` maps to Gate-0 verdict `pass` and
     exit code 0**, asserted by a render test against `verify.md.j2`'s receipt block, and
     `wrapup_receipt.py`'s consistency gate treats it correctly.
  3. Check 5 fires for a `hm/<slug>` worktree (it does not today) — in the template and
     in the SKILL.
  4. Whole-command round-trip count is 7; `pytest` for the touched modules and the full
     structural suite are green (this phase lowers `verify`'s own floor in this commit,
     naming the removed calls).
- **Risk:** `medium` — it is a gate; a false PASS is the worst outcome in this PLAN.
- **Rollback:** revert to Phase 0.5.

### Phase 2 — `wrapup_land` composite CLI
- `depends_on`: `[1]`
- `parallel_group`: `serial-a`
- `merge_hazards`: same shared budget table and snapshots as Phase 1
- **Scope (in):** `src/harness_maker/wrapup_land.py`; `templates/stages/wrapup.md.j2`
  Steps 6–7.6 **including `owned-crumb-clear`** (today `&&`-chained onto the pop at
  `wrapup.md.j2:634`, so it is inside the swallowed range); the legacy-ref pre-scan;
  `tests/unit/test_wrapup_land.py`. **(out):** Step 7.7 `task-land`,
  `commit-base-memory`, Step 8 push, and any change to `post_commit_pop` or `drain`
  themselves.
- **Call-count target (was contradictory across three places in the first draft):**
  Steps 6 → 7.6 render as **exactly 1** mandated call; the wrapup git tail
  (Steps 6 → 7.7 inclusive) renders as **3**.
- **Exit criterion:** unit tests over a temporary git repo cover —
  (a) an absent *optional* manifest path yields `absent-optional` and staging continues;
  (b) an absent *required* path is a hard error naming the path;
  (c) a `git add` failure surfaces git's stderr rather than being swallowed;
  (d) an empty index is reported, never silently committed;
  (e) `post_commit_pop` is called with the crumb-derived ownership set (delegation
      asserted, semantics not re-tested — [ADR-003](#adr-003));
  (f) a `--worktree`/`--base` that is not a git worktree of the expected repo is
      refused — **including a symlinked root and a deleted cwd** — rather than defaulted
      to `Path.cwd()`;
  **(g) the property that actually needs to hold: with an empty owned set,
      `post_commit_pop` leaves the base clean.** The test matrix **must** include a live
      legacy `.hm-finalize-stash-*` ref with an empty `session_uuid` plus a live session
      marker — the branch at `worktree.py:3339-3342` that bypasses the ownership gate.
      That case pops today, so the pre-scan of [ADR-006](#adr-006) must fire and the
      composite must exit non-zero **without staging and without committing** — the
      pre-scan runs first precisely so a retry does not accumulate commits. The
      remediation text is asserted to carry the `git stash show -p <ref>` preview
      obligation, and `--allow-legacy-ref` is asserted to bypass the scan;
  (h) `owned-crumb-clear` runs after a *successful* pop and does **not** run after a
      failed one;
  (i) **resume/idempotency:** after an injected pop failure (the commit has already
      happened — `post_commit_pop` returns 1 at `worktree.py:3218-3221`), a second
      invocation skips the already-satisfied steps rather than re-staging and
      re-committing;
  (j) **manual run** (moved here from Testing Strategy, where a gate on this phase had no
      business living): one real `/hm:wrapup` on a throwaway task branch, producing the
      receipt's per-path dispositions, the resulting commit's file list, and a clean base
      afterwards.
- **Risk:** `high` — it stages and commits immediately before a destructive land.
- **Rollback:** revert to Phase 1; the stage prose returns to its current seven calls.

### Phase 3 — `spec_machine check --all`
- `depends_on`: `[5]`
- `parallel_group`: `serial-a`
- `merge_hazards`: same shared budget table and snapshots
- **Scope (in):** additive subcommand in `spec_machine.py`; `templates/stages/spec.md.j2`
  Steps 4/4.5; tests. **(out):** the validation rules themselves, existing subcommands.
- **Exit criterion:** `spec_machine check --all --yaml … --md … --dev-mode …` returns one
  JSON object carrying the validate errors, the six cross-validate rule results and the
  `spec_quality` scores; existing subcommand tests still pass unchanged; `spec.md.j2`
  renders the three calls as one.
- **Risk:** `low`
- **Rollback:** revert to Phase 5 (this phase's `depends_on`).

### Phase 4 — `test_dep_map select` + execute Phase C/D rules
- **Status: HALF DONE.** The classifier landed and is green; the template half is
  written and measured but **reverted**, waiting on [ADR-018](#adr-018)'s rewrite.
  - Landed: `test_dep_map.py` — `classify_path` / `select_tests` / `main`, the four class
    constants, `RENDER_AFFECTING_SUITES`, `TESTS_DIRS_NOT_RENDER_AFFECTING`;
    `tests/unit/test_test_dep_map_select.py` (29 tests).
  - Reverted: `execute.md.j2` Phase C (per-file) + Phase D (select, then one `&&`-chained
    check call). It was landed under the `hm` rewrite at **−1 char and −1 round-trip**,
    so the design is proven; it comes back with Phase 0.75.
  - Two defects this phase's own tests caught: the class-3 detector immediately found two
    undeclared directories (`tests/ablation`, `tests/codex-compat`), and `lstrip("./")` —
    a CHARACTER-SET strip, not a prefix strip — was eating the leading `.` of
    `.claude/memory/…` and misclassifying it as non-inert.
- `depends_on`: `[2]`
- `parallel_group`: `serial-a`
- `merge_hazards`: same shared budget table and snapshots
- **Scope (in):** `select` CLI implementing the **total** four-way classification with an
  explicit default arm; the class-3 suite list as a committed constant plus its detector
  test; Phase C and Phase D prose in `templates/stages/execute.md.j2`; tests.
  **(out):** `build_test_hints()`'s existing mapping logic, the execute stage's own
  Phase A/A.5/B gates.
- **Exit criterion:** unit tests cover all four classes **and the default arm** — a `.py`
  file with no hint selects `FULL` and names the file; a `.j2` change selects the
  render/structural/snapshot set and not `FULL`; a markdown-only change selects neither;
  a deleted and a renamed path resolve against the pre-change path; **and an in-root path
  matching no rule (`pyproject.toml`, `uv.lock`, `.github/workflows/*.yml`,
  `tests/fixtures/*.json`, `.claude/harness.yaml`) selects `FULL`, not zero tests** — the
  branch whose omission would have made a lockfile bump strictly weaker than today.
  A separate test fails when a directory appears under `tests/` that is neither in the
  class-3 constant nor explicitly excluded. Render test asserts Phase D issues one
  combined lint+type+test call and Phase C says per-file.
- **Risk:** `medium` — a misclassification silently skips tests within a phase; bounded
  by verify's one full-suite run per work unit.
- **Rollback:** revert to Phase 2 (this phase's `depends_on`).

### Phase 5 — research Phase 1 fan-out
- `depends_on`: `[4]`
- `parallel_group`: `serial-a`
- `merge_hazards`: same shared budget table and snapshots
- **Scope (in):** `templates/stages/research.md.j2` Phase 1, **target-conditional per
  [ADR-010](#adr-010)**; render test. **(out):** Phase 0/0.5/0.75, the discovery coverage
  guard, the document schema, and any new agent asset (deferred).
- **Exit criterion:** the render test asserts, for the **Claude** render, the three-agent
  single-message dispatch block, the read-only agent type, and the citation +
  verbatim-snippet obligation; for the **Cursor and Codex** renders, that the serial
  procedure is unchanged and **no `Explore` dispatch appears**. In every render the seven
  source classes are still enumerated (redistributed, not deleted). A general assertion
  covers the class of bug: **every dispatched `subagent_type` in every rendered stage
  command resolves to an agent available on that target** — a render-grep that only
  checks presence would pass on prose naming an agent that cannot resolve.
- **Risk:** `low` — prose plus a read-only dispatch on one target.
- **Rollback:** revert to Phase 4 (this phase's `depends_on`).

### Phase 6 — Round-trip arm + re-baseline
- `depends_on`: `[1, 2, 3, 4, 5]`
- `parallel_group`: `serial-b`
- `merge_hazards`: `tests/structural/test_command_size_budget.py` (shared — each cutting
  phase already re-baselined its own command's floor); must land after every template edit
- **Scope (in):** `tests/structural/test_roundtrip_budget.py` (assertion 1 of
  [ADR-011](#adr-011) — the floor arm and the aggregate landed in Phase 0.5); a **final
  aggregate re-verification** against Phase 0's baseline.
  **(out):** raising any ceiling to make a phase pass; re-baselining any command's floor
  — that belongs to the phase that cut it ([ADR-011](#adr-011)). This phase deliberately
  does **not** "own the budget table outright": that framing is what produced the
  0.5 ↔ 6 cycle.
- **Exit criterion:** the suite is green **and demonstrably fails** under all three
  mutations — `&&`-chaining two real calls onto one line fails the round-trip **floor**;
  deleting one real `!` line fails the round-trip **floor**; moving characters from one
  command into another fails the **aggregate** arm. (The first draft aimed its single
  mutation at the ceiling, which that mutation passes — and the shipped render already
  `&&`-chains at `wrapup.md.j2:634`, so it is not even an anomaly.)
- **Risk:** `medium` — a ratchet that cannot fail is worse than none; the three mutation
  checks are the proof it can.
- **Rollback:** revert to Phase 3.

### Phase 7 — Re-measurement receipt
- `depends_on`: `[6]`
- `parallel_group`: `serial-c`
- `merge_hazards`: none
- **Scope (in):** a receipt in `work-docs/` reporting, per stage, pre/post main-loop
  turns, subagent turns, active wall-clock **and mean context / carry**, each with `n`,
  using Phase 0's methodology and generator verbatim. **(out):** any code change.
- **Exit criterion:** the receipt reports all **four** quantities separately per
  [ADR-012](#adr-012), states `n` for every figure, labels any `n < 3`, **and evaluates
  the Phase 0 pre-registered direction** — verify main-loop turns per run strictly lower
  post-change. If the direction does not hold, the receipt either explains the
  discrepancy or the composite is reverted. Without this the phase could not fail: a
  receipt showing every stage got slower at `n=1` satisfied the first draft's criterion.
- **Risk:** `low`
- **Rollback:** delete the receipt.

### Phase 8 — Release sync
- `depends_on`: `[7]`
- `parallel_group`: `serial-c`
- `merge_hazards`: the five version files
- **Scope (in):** the five-file version sync (`.claude-plugin/plugin.json`,
  `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`,
  `src/harness_maker/__init__.py`) plus the CHANGELOG entry, per [ADR-017](#adr-017).
  **(out):** the tag push and the release workflow, which CLAUDE.md's release procedure
  owns.
- **Exit criterion:** all five files carry the same version; the CHANGELOG names the new
  modules; and the release invariant holds — **no rendered template references a module
  absent from this release** (asserted by importing every `python -m harness_maker.<mod>`
  target found in the rendered commands).
- **Risk:** `low` — but its absence is a hard failure at gate time for any user who
  re-renders against an older pin.
- **Rollback:** revert the version bump.

**Why every phase is serial.** Phases 1–5 each edit a different stage template and a
different module, yet all five change rendered command sizes and therefore collide in
`tests/structural/test_command_size_budget.py` and in the rendered snapshot fixtures.
`merge_hazards` is non-`none` for all of them, which is exactly the gate
[ADR-001](#adr-001) deferred parallel execution behind — this PLAN is its own worked
example. The ordering *within* the serial chain is not arbitrary: Phase 4 is pulled ahead
of Phase 3 because it carries the largest measured lever and `spec` carries the smallest.

## 🧪 Testing Strategy

- **Unit** — `verify_run` (per-check delegation, evidence validation, stale-hash
  rejection, subject binding); `wrapup_land` (the seven cases in Phase 2's exit
  criterion, over a temp git repo); `spec_machine check --all` (composition equals the
  three calls); `test_dep_map select` (four classes plus deletions, renames,
  out-of-root).
- **Render** — one test per edited template asserting the new call shape and that no
  runtime instruction was dropped. The existing `test_fused_loses_no_instruction`
  (`test_command_size_budget.py:337`) does **not** cover this change class: it compares an
  *atomic* render against its *fused* render, so an instruction deleted from
  `verify.md.j2` disappears from both sides and the differential stays exactly the exempt
  block — green. (`_FINGERPRINT` at `:85` is likewise a fixed 3-entry dict of hoisted
  body sentences, not headings.) What is needed instead: a **pre-change vs post-change
  instruction-set** assertion for the five edited atomic commands, built from the
  existing `headings()` / `executable_lines()` helpers, with each phase's intended
  removals enumerated in an explicit per-phase allowlist. Anything removed and not
  listed fails.
- **Structural** — the three-part ratchet, with the three mutation checks that prove it
  can fail (Phase 6), and the floor arm landing *before* the cutting phases (Phase 0.5).
- **Integration** — one end-to-end `verify_run` run against this repo, and one
  `wrapup_land` run in a scratch clone, both behind the existing `INTEGRATION=1` guard.
- **Manual** — the one real `/hm:wrapup` on a throwaway task branch is **Phase 2's exit
  criterion (j)**, not a note in this section. A gate that guards the highest-risk change
  in the PLAN but lives only in an adjacent prose section is the kind that gets skipped.
- Full suite is ~6 minutes; run it in the background and read the exit code from a file
  rather than trusting the notification.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `verify_run` returns PASS over a state it did not inspect (post-land) | medium | high | [ADR-005](#adr-005) subject binding + `skip_reason` + **run-level `PARTIAL`**; undetermined subject is FAIL; Phase 1 asserts the **run** verdict, not just the check verdict |
| R10 | The composite preserves the record shape but drifts on verdict semantics | medium | high | Phase 1 exit criterion 1 — differential oracle against the current 13-call sequence, including stop-at-first-FAIL ordering |
| R11 | A live legacy no-uuid stash ref is popped and deadlocks `task-land` | low | high | [ADR-006](#adr-006) pre-scan stops before popping; Phase 2 exit criterion (g) constructs exactly that ref |
| R12 | Phases 1–5 delete runtime behavior to meet a size target, unguarded | medium | high | Phase 0.5 lands the floor arm **before** any cutting |
| R13 | The baseline is frozen against a stale render, crediting a prior change to this PLAN | high | medium | Phase 0 re-renders first and records the render SHA |
| R2 | Check 1b becomes a rubber stamp | medium | high | [ADR-004](#adr-004) evidence file bound to SPEC + diff hashes; absent or stale evidence FAILs |
| R3 | `wrapup_land` drops a deliverable from the commit | medium | high | [ADR-007](#adr-007) typed manifest; required-vs-optional split; git stderr surfaced |
| R4 | The pop/land ordering deadlocks on a deferred stash | low | high | Phase 2 exit criterion (g) tests the documented-but-untested invariant; failure is a blocker, not a workaround |
| R5 | The ratchet passes while the surface grows | medium | medium | [ADR-011](#adr-011) aggregate total against a pre-frozen baseline + two mutation checks |
| R6 | Phase D selection silently skips a needed suite | medium | medium | [ADR-008](#adr-008) class 2 is fail-safe; verify still owns one full-suite run per work unit |
| R7 | research digests lose the decisive detail | medium | medium | [ADR-010](#adr-010) citation + verbatim snippet obligation; main loop reads originals for deciding claims |
| R8 | The improvement is claimed but not real | medium | medium | [ADR-012](#adr-012) separate turn / subagent-turn / wall-clock reporting with `n` |
| R9 | Downstream users' rendered harnesses reference a CLI their pinned version lacks | low | high | The five-file version sync ships the new modules in the same release as the templates that call them |

## ✅ Success Criteria

- [ ] `verify.md.j2`'s six checks render as **2** mandated calls (whole-command round-trip
      count **13 → 7**; the checks own 8 of the 13, and the preflight, Gate-0,
      `task-refresh` and autopilot calls are all preserved — see Phase 1's correction),
      Check 3's verdict equals `_verify_structural_check`'s on the executable
      differential, and the remaining checks match their golden fixtures — except the
      bounded change [ADR-016](#adr-016) permits.
- [ ] `PARTIAL` maps to Gate-0 verdict `pass` and exit code 0, asserted by a render test,
      and `wrapup_receipt.py`'s consistency gate does not silently accept a PARTIAL over
      a FAILed check.
- [ ] `wrapup.md.j2` Steps 6–7.6 render as **exactly 1** mandated call; the git tail
      (Steps 6 → 7.7) renders as **3**; `task-land` and `commit-base-memory` remain
      separate and unchanged.
- [ ] `spec.md.j2` renders one validation call in place of three.
- [ ] `execute.md.j2` Phase C says per-file; Phase D issues one combined check call and
      selects tests through `test_dep_map select`.
- [ ] `research.md.j2` dispatches three read-only agents in one message with the citation
      contract **on the Claude render only**; Cursor and Codex renders keep the serial
      path and contain no unresolvable dispatch; all seven source classes survive in every
      render.
- [ ] `tests/structural/test_roundtrip_budget.py` is green **and** demonstrably fails
      under all three mutation checks.
- [ ] Aggregate rendered surface across all commands and target variants is **lower**
      than Phase 0's frozen baseline, which was taken **after a fresh re-render** and
      produced by the committed generator Phase 6 re-invokes.
- [ ] Phase 7 receipt reports per-stage pre/post main-loop turns, subagent turns, active
      wall-clock **and carry**, each with `n`, and evaluates the pre-registered direction.
- [ ] All five version files agree and no rendered template references a module absent
      from the release.
- [ ] `uv run ruff check`, `ruff format --check`, `mypy --strict`, and the full `pytest`
      suite are green.
- [ ] No quality gate's semantics changed: the plan interview, ADR promotion, Phase A.5
      test-reviewer, review consensus filter and grade gate, verify's fail-closed rule,
      and wrapup's memory count++ / promotion steps are byte-for-byte intact except where
      an ADR above names the change.

## 🔍 Plan Validation

**Cross-model second opinion — both models `invoked`** (codex 12 findings, antigravity
6). Reconciliation:

| Finding | Source | Consensus | Disposition |
|---|---|---|---|
| Ratchet proxy cannot detect the aggregate failure | codex P1 ×2, antigravity P1 | consensus-passed | **Accepted** → ADR-011 (three parts + frozen baseline + mutation checks) |
| "Any uncovered file → FULL" degenerates to always-FULL | codex P2, antigravity P2 | consensus-passed | **Accepted** → ADR-008 (four-way classification) |
| Delegation n=2 over-read; turns ≠ wall-clock | codex P2 (null-location), antigravity P2 | consensus-passed | **Accepted** → ADR-012; the executive summary states the effect as latency-only |
| verify's subject disappears after the land | codex P0, antigravity P0 | weak-consensus (reasoning diverges: torn-down worktree vs cwd) | **Accepted, both readings** → ADR-005 covers subject binding *and* the SKIPPED-not-PASS rule |
| Composite's partial-failure state before `task-land` | codex P1, antigravity P1 | weak-consensus | **Partially accepted** — the receipt enumerates completed steps and the CLI never changes the caller's cwd; antigravity's cwd-leak mechanism is incorrect (the composite takes explicit roots), so only the residual is adopted |
| pop-before-land can deadlock the squash-land | codex P0 | manual-only | **Accepted** → Phase 2 exit criterion (g) tests the untested invariant; ADR-006 records the reopening condition |
| Staging loop conflates absent / permission / add failure | codex P0 | manual-only | **Accepted** → ADR-007 |
| No index-ownership boundary | codex P0 | manual-only | **Partially accepted** — pre/post index manifest in the receipt; rejecting foreign staged paths is a behavior change to the execute→wrapup handshake and is deferred |
| `--check1b` needs evidence, hash binding, staleness | codex P1 | manual-only | **Accepted** → ADR-004 |
| Check 3 has no named deterministic scoring API | codex P1 | manual-only | **Partially accepted** — the API half is discharged (`readiness.compute_readiness()`, `dashboard.parse_dashboard()` named in the Technical Design). The FAIL-on-uncomputable half is **deferred**: `verify.md.j2:127` today PASSes when the `score:` line is missing, so changing it is a user-visible verdict change that [ADR-016](#adr-016) puts out of scope. Recorded as a known gap, not silently retained |
| `post-commit-pop` complexity understated | codex P1 | manual-only | **Accepted** → ADR-003 (delegate, never reimplement); Phase 2 asserts delegation only |
| Base/worktree resolution absent-cases (symlink, deleted cwd, sibling) | codex P1 | manual-only | **Accepted** → Technical Design refuses a non-matching root rather than defaulting to cwd; Phase 2 exit criterion (f) |
| Antigravity: `--check1b` forces a blind pre-verdict | antigravity P1 | manual-only | **Accepted** → ADR-004's two-call shape resolves the ordering |

**plan-validator (pass 1): `MAJOR_REVISION`** — 7 critical, 10 warning, 3 suggestion.
Every load-bearing citation was verified against the source before folding:
`worktree.py:3330-3342` (legacy empty-uuid refs bypass the ownership gate — the invariant
Phase 2 (g) asserted is false), `test_command_size_budget.py:52-59,209` (five fused
entries, zero atomic; `floor = measured * 0.80`), `verify.md.j2:127` (the shipped
no-baseline PASS), `verify.md.j2:143` (Check 5 matches only `.worktrees/execute-*`, so it
never fires under `feature_branch_workflow`), and the fence collision between
`wrapup.md.j2:569` (real command) and `execute.md.j2:384` (fenced `Bash(`). All confirmed.

Resolution of the 7 critical items:

| # | Critical | Resolution |
|---|---|---|
| 1 | Round-trip counting rule unimplementable ("outside fenced blocks" has no referent) | [ADR-011](#adr-011) rewritten as a consistent proxy; mutations re-pointed at the **floor** arm; third mutation added |
| 2 | ADR-005 relabels the vacuous post-land PASS instead of closing it | [ADR-005](#adr-005) rewritten: `skip_reason` enum, **run-level `PARTIAL`**, Check 5 trigger extended; Phase 1 asserts the run verdict (Interview #10) |
| 3 | Check 3 reconciliation contradicts Phase 1's scope | [ADR-016](#adr-016): the semantics change is bounded to run-level aggregation; the Check 3 row is downgraded to partially-accepted (Interview #10) |
| 4 | Phase 2 (g) asserts a false invariant and would pass trivially | [ADR-006](#adr-006) legacy-ref pre-scan; (g) restated as the real property with the bypass branch in the test matrix (Interview #11) |
| 5 | The classifier is not total — in-root non-matches select zero tests | [ADR-008](#adr-008) explicit default arm → FULL; class-3 constant gains a detector; Phase 4 asserts the default branch |
| 6 | Baseline frozen against a stale render, and `>` redirection is not evidence | Phase 0 re-renders first, records the render SHA, and emits the baseline from a committed generator Phase 6 re-invokes |
| 7 | No oracle for "semantics preserved" — a stub satisfies the criterion | Phase 1 exit criterion 1: differential test against the current 13-call sequence including FAIL ordering |

Warnings resolved in place: `owned-crumb-clear` named in [ADR-006](#adr-006) + Phase 2
scope with both ordering directions tested (w8); the three contradictory call-count
targets collapsed to one (w9); the `_RATCHET` re-baseline protocol added and every phase
now requires the structural suite green (w10); the floor arm split into Phase 0.5 so
Phases 1–5 land against a live ratchet, and the "no instruction dropped" test points at
the existing fingerprint mechanism (w11); `Explore` made target-conditional (w12,
Interview #12); Phase 7 given a pre-registered direction (w13); the manual wrapup run
moved into Phase 2 as criterion (j) (w14); the five-file version sync given an owner in
[ADR-017](#adr-017) + Phase 8 (w15); carry added as a fourth measured quantity (w16);
resume/idempotency contract added as Phase 2 criterion (i) (w17). Suggestions: the
base-root pinning deviation is now called out in [ADR-003](#adr-003) (s18); the aggregate
baseline is stored per-command so additions do not force relaxation (s19); phases
reordered to 0 → 0.5 → 1 → 2 → 4 → 5 → 3 → 6 → 7 → 8 (s20).

**plan-validator (pass 2 — final, per the stage's one-re-run rule): `MAJOR_REVISION`.**
All **7 pass-1 criticals confirmed discharged**. The revision itself introduced 5 new
criticals, which the user elected to fix and finalize without a third pass. Both
load-bearing claims were verified before folding: the rendered `verify.md` has 13 `!`
lines including the preflight (`:298`) and Gate-0 (`:228`) calls [ADR-013](#adr-013)
preserves — so "≤ 2" was unachievable; and `cli.py:1844 @app.command("verify")` already
implements Check 3 (`_verify_structural_check` `:1935`) and writes the same JSONL
(`_write_verify_jsonl` `:2016`).

| # | New critical | Resolution |
|---|---|---|
| 1 | Round-trip floor slack unspecified — under `measured*0.80` a one-call reduction stays inside the floor, so two of three mutations could never fail | [ADR-011](#adr-011): the round-trip floor is **exact equality**, explicitly unlike the character floor |
| 2 | "verify ≤ 2 `!` lines" contradicts [ADR-013](#adr-013) | Restated: the six checks become 2 calls; the whole-command count is 13 → 4 |
| 3 | Phase 0.5 ↔ Phase 6 **circular dependency** — pre-change floors frozen early, re-baseline owned by a phase that runs last | [ADR-011](#adr-011): each cutting phase re-baselines its own command's floor in its own commit; Phase 6 no longer "owns the table outright" |
| 4 | `PARTIAL` unmapped in two fixed contracts, and under this repo's ordering it is the **normal** verdict | [ADR-005](#adr-005): `PARTIAL` → Gate-0 `pass`, exit 0, render-test asserted; and PARTIAL is never emitted over a FAILed check (which also closes `wrapup_receipt.py:393`) |
| 5 | verify's semantics live in **three** places; a new module would be a second producer of one JSONL | Phase 1 **extends `cli.py`'s existing command** instead. Smaller phase, and Check 3 gains a real executable differential; the SKILL is in scope for Check 5's trigger only |

Warnings also folded: stale rollback targets corrected to each phase's own `depends_on`;
the legacy-ref pre-scan moved **before staging** and given an `--allow-legacy-ref` escape
plus an asserted remediation text carrying the `git stash show -p` obligation; the
"no instruction dropped" test replaced (the cited `test_fused_loses_no_instruction`
compares atomic-vs-fused, so a deletion from both sides passes) with a pre/post
instruction-set assertion and a per-phase removal allowlist; Cursor counted by the Claude
rule. **Deliberately not done:** renumbering `Phase 0.5` to an integer — this document
carries two `Phase` namespaces and a mechanical renumber would corrupt the research-stage
references; the namespace is stated instead.

**Known gaps carried forward, recorded rather than closed:** an uncomputable current
structural score still yields PASS ([ADR-016](#adr-016)); foreign staged content is made
visible by the index manifest but nothing acts on it; a concurrent base HEAD move between
the pop and the land is unhandled; the research fan-out saving accrues to Claude Code
users only; and this PLAN was finalized on a validator verdict of MAJOR_REVISION with the
five findings above fixed but **not re-validated** — that is a user decision, recorded
here so a reader does not mistake it for an APPROVED plan.
