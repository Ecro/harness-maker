---
type: plan
task_slug: probe-envelope-contract
status: complete
created: 2026-08-22
tags: [harness-maker, plan, python, review-gate, agent-tools, canary-removal]
interview_rounds: 3
adrs: 6
validator_pass_policy: single-pass (user rule 2026-08-22: plan-validator runs once; no re-validation after fixes)
validator_outcome: MAJOR_REVISION_TERMINAL
surface_allowance:
  reason: "Net-negative task. Allowance declared at zero so the ratchet stays armed."
  chars: 0
  round_trips: 0
summary: "Retire the repo_probe canary; invert the existing agent-tools allowlist to cover all 15"
---

# PLAN — retire the `repo_probe` canary, invert the agent-tool allowlist

## 🎯 Executive Summary

**TL;DR.** Delete the `repo_probe` canary and everything that carries it. In its place, fix the
gate that already guards agent tool boundaries but only covers 2 of the 15 agents it should.

**What.** `repo_probe` asks a reviewer agent to return a verbatim line from a file outside the
diff, as proof its repository access is live. It shipped in 0.53.0 and was demoted to advisory in
the same release: a live `/hm:review` failed 7 of 7 lenses that had demonstrably read outside the
diff. The contract asks for "one top-level field beside your findings array"; reviewers return
narrative prose and there is no array for it to sit beside.

**Why remove rather than repair.** The canary's target is a reviewer whose repository access is
not live. Every instance of that class this repository has actually shipped was decided at
**render time**:

| Shipped defect | Shape |
|---|---|
| `is_codex` hardcoded `False` | every `{% if is_codex %}` gate dead for its whole lifetime |
| `agy --print --sandbox` | every antigravity vote answered the literal string `--sandbox`, exit 0 |
| `.claude/hooks/hooks.json` | every hook dead in Claude Code for months |

Repairing the canary means designing an output shape reviewers actually emit, which only a live
dispatch per release can confirm — a contract on four agent bodies, priced per release, for a
class that has never failed at run time here.

**Why not leave it advisory.** It reports `probe_failed: [all seven]` on every Production review.
A reader learns to skip that line within two reviews, and the day tool access genuinely breaks the
screen is identical. A detector pinned at a 100% noise floor is worse than no detector.

**What is honestly lost.** Any run-time signal that a specific dispatch used its tools. The
replacement is **not** equivalent: it checks a rendered declaration, and a declaration is not an
observation. It cannot see a tool that is declared and unusable — wrong working directory, a
runtime that ignores the field, a model that simply does not call it. That gap is accepted
(ADR-001), and it is not a regression, because nothing detects those today either: the canary
could not, having produced a false negative on the one live run it saw.

**What is gained beyond parity — corrected.** An earlier revision of this PLAN claimed
`_READ_ONLY_AGENTS` held two of the eleven read-only agents and that nine were unguarded. **That
was false**, caught by the plan validator and verified at
`tests/structural/test_agent_frontmatter_merges.py:97-111`: the list holds **all eleven**. The
error came from reading the file through a `sed` range that skipped lines 101-109 and treating the
truncated output as the whole set. No currently-rendered agent moves from unguarded to guarded.

The gain that survives is narrower and still real. The existing gate checks **only** the eleven
names on that list; the complement — `autoloop-coder`, `executor`, `stage-delegate`,
`security-auditor` — is checked for nothing beyond a non-empty `tools:`. So the live hole is
**fail-open by default**: a new agent added to `_ALL_AGENTS` and not to `_READ_ONLY_AGENTS` is
silently unguarded, and the four write-privileged agents can gain any tool without a test noticing.
Inverting the list turns that default around and puts the exceptions under an exact-set assertion.
That is a smaller claim than the one this PLAN opened with, and it is the one the numbers support.

**Key decisions.** ADR-001 (remove; record the coverage gap) · ADR-002 (extend the existing gate,
do not add a second) · ADR-003 (derive both populations; enumerate only write-privileged
exceptions) · ADR-004 (absorb the retired CLI flags with an executable sunset) · ADR-005 (Codex
TOML is a non-goal) · ADR-006 (file a mutation receipt and shrink the debt list).

**Estimated impact.** ~8,080 chars removed from four rendered agent bodies (2,013 / 2,027 / 2,005
/ 2,035), plus the Step-3 paragraph and six `probe_flags` sites in `review.md.j2`. One existing
test file strengthened; one mutation receipt filed; one debt-list entry removed. Minor version
bump: `coverage_verdict` loses its `probe_failed` key and `exercised_lenses` / `coverage_verdict`
lose their required keyword-only `probe` — both consumer-visible.

## 📚 Prior Work

- `[wiki:architecture] narrative-output-needs-explicit-envelope` (2026-08-21) — when a contract
  depends on an agent's OUTPUT SHAPE rather than its behaviour, one real dispatch is the only
  evidence that counts, and it belongs before the contract is wired into a gate. Fixture-shaped
  output proves the validator, never the producer.
- `[fail:design] narrative-output-has-no-field-envelope` (count:1) — the same event as a failure
  entry. Records that the reviewers *did* read outside the diff, so the detector produced a false
  negative: the worse direction.
- `PLAN-bench-study-adoption` Phase 4 + ADR-010 — the canary's origin, and the re-freeze rule this
  PLAN expects **not** to need (Phase 3).
- CLAUDE.md, 2026-06-02 permission-enforcement correction — a reviewer's only enforced boundary is
  the absence of Bash from `tools:`; frontmatter `permissions:` was silently ignored and deleted
  in 0.40.0.
- CLAUDE.md, "Agent Selection Guide" — a hand-maintained agent list went stale three times, and
  each replacement was "a better hand list". ADR-003 is the attempt not to write a fourth.
- `tests/structural/test_new_gates_file_a_mutation_receipt.py:8-27` — "population is derived, debt
  is enumerated, and those are different things", and the debt list "may only shrink". ADR-003 and
  ADR-006 follow it.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Direction | Scope | Repair the probe's output shape, weaken it, derive it from citations, or remove it? | A fenced-section contract / C path+line only / D collect cited paths / E remove | **E + static replacement** | User asked the downsides of removal first; chose removal once the three shipped defects showed the class is render-time | ADR-001 |
| 2 | Gate scope | Architecture | What does the structural gate assert? | minimum only / minimum + reverse prohibition / full fixed table | **minimum + reverse prohibition** | A reviewer gaining Bash is a security-boundary regression; same cost | ADR-002 |
| 3 | Compatibility | Contract | `lens_coverage check` drops `--diff-files`/`--rev`; a 0.53.0-rendered harness still passes them and argparse exits 2 | absorb + deprecate / immediate break / permanent no-op | **absorb + one-line deprecation** | PyPI is immutable; a break kills `/hm:review` on every un-re-rendered harness — the risk that demoted the probe | ADR-004 |
| 4 | Scope re-confirm | Risk tolerance | Interview #1 was decided on a false number (nine unguarded agents). With the corrected figure — zero agents change guard status, the gain is a fail-open default and exact-set cover of four write-privileged agents — does the full scope still hold? | proceed as planned / canary removal only (drop Phase 1) / re-open | **proceed as planned** | Asked after the validator caught the error and after the corrected trade was stated in full; the fail-open default is a real defect independent of the miscount | ADR-002 |

Ambiguities resolved without a question, and why:

- **read-only classification** — the 5-term gate scored 2/5. CLAUDE.md records the stale-hand-list
  failure three times; the mutation-receipt gate already states the governing rule. → ADR-003.
- **check layer** — the blueprint, following `test_is_codex_matches_output_path.py`. `.claude/` is
  gitignored here, so a disk-reading test would be non-hermetic in CI.
- **version bump** — minor, by the same reasoning that made the addition minor in 0.53.0.

## 📐 Architecture Decision Records

### ADR-001: Retire the `repo_probe` canary and record the coverage gap
**Status:** Accepted (2026-08-22, via /hm:plan interview)
**Context:** The canary detects nothing today: advisory, and failing on every lens. Repairing it
means designing an output shape reviewers actually emit, confirmable only by a live dispatch per
release. Its target class has, in this repository, only ever failed at render time.
**Decision:** Delete `ProbeCheck`, `_probe_ok`, `probe_failures`, `build_probe_check`, the `probe`
parameter, the `probe_failed` verdict key, the `return_envelope` partial and the `probe_flags`
wiring. **Record in this ADR that run-time detection of tool access is now uncovered** — the
static gate checks a declaration, not a dispatch.
**Consequences:**
- ✅ Net surface reduction; the 100%-noise advisory line disappears.
- ✅ The gate that replaces it is deterministic and cannot produce a false negative of the
  canary's kind, because it observes a rendered artefact rather than model output.
- ⚠️ **Accepted coverage gap**: a tool declared but unusable at run time (wrong cwd, a runtime
  that ignores `tools:`, a model that never calls it) is undetected. Not a regression — the
  canary could not see it either, and produced a false negative on its one live run.
- ⚠️ Re-introducing a run-time probe later costs a fresh design plus a baseline fold.
**Rejected alternatives:**
- Repair the shape (a fenced `## Repo probe` section) — rejected: a contract on four agent bodies
  whose correctness needs a live dispatch each release, for a class that has never failed at run
  time here. Not a strawman: this is the option the PLAN was originally opened to write.
- Weaken to `path`+`line` — rejected: proves the model named a path, not that it read one.
- Derive from cited paths in findings — rejected: changes the measured property to "did a finding
  point outside the diff", which a legitimate diff-local review fails.
- Leave advisory — rejected: a 100% noise floor trains readers to ignore the line that would
  report a real break.
**Source:** Interview #1

### ADR-002: Extend the existing tool-boundary gate; do not add a second one
**Status:** Accepted (2026-08-22, via /hm:plan interview + cross-model second opinion)
**Context:** The first draft of this PLAN specified a new `tests/structural/
test_agent_tool_boundaries.py`. Codex refuted the premise and it was verified at source:
`tests/structural/test_agent_frontmatter_merges.py` already renders every agent (`:27,31-43`),
requires a non-empty `tools:` on all of them (`:114-126`), parses both YAML shapes
(`_granted_tools`, `:129-142`), and prohibits Write/Edit/Bash (`:145-162`) for
`_READ_ONLY_AGENTS` — which holds **all eleven** read-only agents (`:97-111`), not two as an
earlier revision of this PLAN asserted. A second gate would create two competing definitions of
the same policy, free to drift. What the existing gate does **not** do is check anything outside
that list: the four write-privileged agents are unconstrained, and a new agent is unguarded until
someone remembers to add it.
**Decision:** Strengthen the existing file. Replace `_READ_ONLY_AGENTS` with `_WRITE_PRIVILEGED`
and invert the parametrisation, so the prohibition runs over the derived population and the
enumerated list holds only the exceptions. Add the read-minimum assertion (below) to the same file.
**Consequences:**
- ✅ One definition of the policy.
- ✅ The default flips from fail-open to fail-closed: a new agent is guarded on the day it renders.
- ✅ The four write-privileged agents come under an exact-set assertion for the first time.
- ⚠️ **Zero currently-rendered agents change guard status.** The benefit is prospective, and this
  ADR says so rather than letting the Executive Summary's earlier overclaim stand.
- ⚠️ Adding a legitimately write-privileged agent requires an allowlist edit. Intended — that edit
  is the deliberate act being recorded.
**Rejected alternatives:**
- A new parallel gate — rejected on Codex's finding, verified at source: duplicate policy, and
  `_READ_ONLY_AGENTS` would be left free to drift against the new list.
- Leave the gate alone — rejected, but it is the closest call in this PLAN now that the count is
  corrected. It loses the fail-closed default and the exception-set assertion; it costs nothing.
- Full fixed table of all 15 agents — rejected: needs editing on every intentional change, which
  is the stale-hand-list pattern CLAUDE.md records failing three times.
**Source:** Interview #2; revised by cross-model second opinion (codex, P1)

### ADR-003: Derive both populations from what renders; enumerate only the exceptions
**Status:** Accepted (2026-08-22, via /hm:plan + cross-model second opinion)
**Context:** ADR-002 needs two populations. The draft claimed "every agent the blueprint renders
(derived, never enumerated)"; Codex showed that is false as stated — `synthesize._agent_files`
iterates the hand-maintained `_ALL_AGENTS` constant (`synthesize.py:465`), and
`trajectory-monitor.md.j2` carries `tools: Read, Grep, Bash` while being deliberately absent from
it (`synthesize.py:426-429`), so it renders nowhere. Separately, "every agent must grant Read and
Grep" has no contract source: a future agent may legitimately need neither.
**Decision:** Two derived populations, one enumerated exception list.
- **Write/exec prohibition** — population = the agent `FileEntry` paths the blueprint actually
  emits, read from the blueprint rather than by importing `_ALL_AGENTS`, so the gate describes
  what ships. Exceptions live in `_WRITE_PRIVILEGED`, mapping each agent to its permitted set with
  a one-line reason: `autoloop-coder`, `executor`, `stage-delegate` (Write/Edit/Bash) and
  `security-auditor` (Bash only).
- **Read minimum** — population = `{d["agent"] for d in lens_dispatch("Production")}`, the review
  stage's own dispatch table (`conditional_router.py:141-160`). These are the agents the canary
  targeted and the ones a review is unapprovable without. Derived, not listed.
**Consequences:**
- ✅ A new agent is covered by the prohibition the moment it renders.
- ✅ The read minimum is asserted only where a contract requires it, so a future read-less agent is
  not blocked by a rule nothing justifies.
- ⚠️ `trajectory-monitor` has a template and no render. Out of scope and recorded here so the next
  reader does not mistake it for a gate hole: an agent that renders nowhere grants nothing.
- ⚠️ Two populations means two ways to be vacuous. Phase 1's assertion 3 covers both.
**Rejected alternatives:**
- Import `_ALL_AGENTS` — rejected: makes the gate tautological with the renderer's constant rather
  than with its output.
- Classify by name suffix — rejected: `code-verifier`, `plan-validator`, `stuck` and
  `consensus-arbiter` are read-only and match no suffix.
- Require Read+Grep on every agent — rejected on Codex's finding: no contract source, and it would
  block a legitimate future agent.
**Source:** derived from `test_new_gates_file_a_mutation_receipt.py:21-27`; revised by cross-model
second opinion (codex, P1 + P2)

### ADR-004: The retired CLI flags are absorbed with a deprecation line and an executable sunset
**Status:** Accepted (2026-08-22, via /hm:plan interview + cross-model second opinion)
**Context:** `lens_coverage check` gains `--diff-files` / `--rev` from the rendered `review.md.j2`.
A harness rendered by 0.53.0 keeps passing them until its owner re-renders, and `argparse` exits 2
on an unknown argument, which would kill `/hm:review` at Step 3.
**Decision:** Keep both flags registered with `help=argparse.SUPPRESS`, ignore their values, and
emit exactly one stderr line naming the remedy. **The sunset is executable, not a note**: the
compatibility test asserts `__version__ < "0.55.0"`, so the release that reaches 0.55.0 turns it
red and the removal cannot be forgotten.
**Consequences:**
- ✅ An un-re-rendered harness keeps working and its owner learns why.
- ✅ The expiry is enforced by the suite rather than by memory.
- ⚠️ Two dead parameters survive one minor version, by design.
- ⚠️ The comparison is on parsed version **tuples**, not strings. `"0.100.0" < "0.55.0"` is True
  lexicographically, so a string arm would silently stop firing if the minor series ever reached
  three digits — the same silent direction this ADR set out to close.
**Rejected alternatives:**
- Immediate removal — rejected: PyPI is immutable and this is the failure mode that forced the
  probe to advisory before publication.
- Permanent silent no-op — rejected: a knob with no caller and no expiry is the defect class this
  PLAN exists to remove.
- A prose "remove next version" note — rejected on Codex's finding: the compatibility test would
  positively require the flags to stay, preserving them indefinitely.
**Source:** Interview #3; sunset arm added by cross-model second opinion (codex, P2)

### ADR-005: Codex agent TOML is out of scope
**Status:** Accepted (2026-08-22, via /hm:plan)
**Context:** `.codex/agents/*.toml` carries `name`, `description`, `model_reasoning_effort` and
`developer_instructions`. It has no `tools` field, so there is no boundary there to gate.
**Decision:** The gate covers `.claude/agents/*.md`, which Claude Code and Cursor share. Codex is
recorded as a non-goal.
**Consequences:**
- ✅ The gate makes no claim it cannot check.
- ⚠️ A Codex reviewer has no expressed tool boundary. Pre-existing, unchanged, worth its own task.
**Rejected alternatives:**
- Add a `tools` key to the TOML for symmetry — rejected: Codex does not read one, so it would be a
  field nothing enforces, which is what this PLAN is removing.
**Source:** verified against `.codex/agents/code-reviewer.toml`

### ADR-006: File the mutation receipt and shrink the debt list
**Status:** Accepted (2026-08-22, via /hm:plan)
**Context:** `test_agent_frontmatter_merges.py` sits on the debt list at
`test_new_gates_file_a_mutation_receipt.py:61`, so it currently ships without a receipt. That list
is "finite, frozen, and allowed only to shrink".
**Decision:** File a receipt for the strengthened gate and remove the file from the debt list in
the same phase.
**Consequences:**
- ✅ The debt list shrinks by one, which is the only direction it may move.
- ✅ The author has to answer "which line, deleted, turns this red?" for a gate that is about to
  guard nine more agents.
- ⚠️ If Phase 1 is reverted, the debt-list entry must be restored with it. Named in the rollback.
**Rejected alternatives:**
- Leave it on the debt list — rejected: strengthening a gate is exactly when its receipt is
  cheapest to produce, and the list may only shrink.
**Source:** `test_new_gates_file_a_mutation_receipt.py:21-27,61`

## 🏗️ Technical Design

**Current state.** `lens_coverage.py` holds `ProbeCheck` (frozen dataclass, empty-`diff_files`
fail-closed in `__post_init__`), `_probe_ok` (five invalidity modes plus the
`no-out-of-diff-file` escape verified against the repository), `probe_failures`, and
`build_probe_check` (reads `git ls-tree` for membership and `git show <rev>:<path>` for content,
never the working tree — R11). `coverage_verdict` carries a `probe_failed` key that moves nothing.
`exercised_lenses`, `probe_failures` and `coverage_verdict` take a required keyword-only `probe`.

**Affected components.**

| Path | Change |
|---|---|
| `src/harness_maker/lens_coverage.py` | remove the probe machinery and the `probe` parameter; absorb the two CLI flags |
| `src/harness_maker/templates/agents/_partials/return_envelope.md.j2` | delete |
| `src/harness_maker/templates/agents/{code,security,concurrency,test}-reviewer_body.md.j2` | drop the include |
| `src/harness_maker/templates/stages/review.md.j2` | drop `probe_flags` (line 2 and six use sites: 275, 277, 785, 787, 1015, 1017) and the Step-3 paragraph at 237-252 |
| `tests/structural/test_agent_frontmatter_merges.py` | invert `_READ_ONLY_AGENTS` → `_WRITE_PRIVILEGED`; add the read-minimum and non-vacuity assertions |
| `tests/structural/test_new_gates_file_a_mutation_receipt.py` | remove line 61 from the debt list |
| `tests/unit/test_lens_repo_probe.py`, `tests/unit/test_lens_coverage_probe_cli.py`, `tests/render/test_render_repo_probe.py` | delete; add one ADR-004 compatibility test |
| `tests/unit/test_agent_body_partials.py` | drop the partial from its inventory |
| `.claude/observability/mutation-receipts.jsonl` | one row |
| five version files + CHANGELOG | 0.53.0 → 0.54.0 |
| `uv.lock` | derived: `uv run` rewrites the project version after the 5-file bump |
| `tests/unit/{test_lens_coverage,test_render_lens_axis,test_review_input_boundaries}.py` | 21 `probe=None` call sites — the consumer-visible half of dropping the parameter |
| `tests/snapshot/*.expected.yaml` (8) | `body_sha256` for `agents/{code,concurrency,security,test}-reviewer.md`, `stages/review.md` and `commands/hm/review.md` — 6 entries per fixture, no other key |

The last three rows were **absent from the first revision of this table** and the drift gate
flagged them as 13 paths outside scope. They are mechanical consequences rather than new work,
which is exactly why they were easy to omit — and a scope list that omits the consequences of its
own edits cannot tell drift from completion.

**Dependencies.** None added.

**Data flow after the change.** `lens_coverage check` reads only the per-round result files and
the run id. The verdict is `{exercised, missing, blocks_approval}`; `blocks_approval` keeps its one
meaning — a lens did not deliver a result.

**API changes.** `exercised_lenses(round_dir, run_id)` and `coverage_verdict(round_dirs, run_id,
preset)` lose their keyword-only `probe`. `probe_failures`, `ProbeCheck` and `build_probe_check`
are gone. `coverage_verdict`'s return loses `probe_failed`.

## 🚫 Non-Goals

Collected here because they were scattered across four sections and a reader mid-`/hm:execute`
should not have to find them:

- **Codex agent TOML** — no `tools` field exists there to gate (ADR-005).
- **`trajectory-monitor`** — has a template and renders nowhere; an agent that renders nowhere
  grants nothing (ADR-003).
- **Whether a declared tool is actually used at run time** — the accepted coverage gap this PLAN
  opens (ADR-001). The canary could not see it either.
- **A universal Read+Grep minimum** — asserted only over the `lens_dispatch` population, which has
  a contract requiring it (ADR-003).

## 📝 Implementation Plan

### Phase 1 — Strengthen the existing gate before removing the canary

**Status: DONE.**

- `depends_on`: `[]`
- `parallel_group`: `serial-1`
- `merge_hazards`: `.claude/observability/mutation-receipts.jsonl` (append-only, one row);
  `test_new_gates_file_a_mutation_receipt.py`'s debt list (one deletion).
- **Scope in:** `tests/structural/test_agent_frontmatter_merges.py`,
  `tests/structural/test_new_gates_file_a_mutation_receipt.py` (debt line only), the receipt row.
- **Scope out:** every file listed for Phase 2. The canary stays live and advisory through this
  phase, so a failure here leaves the tree in the shipped 0.53.0 state.
- **Exit criterion:** `uv run pytest tests/structural/test_agent_frontmatter_merges.py
  tests/structural/test_new_gates_file_a_mutation_receipt.py -q` green, **and** the receipt's named
  line actually kills the gate — delete it, re-run, watch it go red, restore. File the row with
  `uv run python -m harness_maker.mutation_receipt record --gate
  'tests/structural/test_agent_frontmatter_merges.py::<name>' --deletes '<file>:<line>' --slug
  probe-envelope-contract`.
  **The `--deletes` target must be a file Phase 2 does not touch** — a `tools:` line in an agent
  dispatcher template (e.g. `templates/agents/code-reviewer.md.j2:5`) is the natural choice.
  Naming a line inside `return_envelope.md.j2` or a `*_body.md.j2` include would leave a receipt
  pointing at deleted code one phase later, and `test_new_gates_file_a_mutation_receipt.py:113-115`
  only checks that a row exists — a dangling receipt stays green, which is exactly the
  unfalsifiable answer ADR-006 exists to prevent.
- **Risk:** low
- **Rollback:** revert the three files **including the debt-list line** (ADR-006).

The gate gains three assertions:

1. **write/exec prohibition over the derived population** — every agent the blueprint emits, except
   those in `_WRITE_PRIVILEGED`, grants none of Write/Edit/Bash; a `_WRITE_PRIVILEGED` agent grants
   exactly its recorded set, so a silent widening of an exception is caught too.
2. **read minimum over the lens population** — every agent in `lens_dispatch("Production")` grants
   Read and Grep.
3. **non-vacuity, against INDEPENDENT sources** — three sub-arms, because the previous revision's
   version compared the blueprint population against itself (`X == X`, which passes on an empty
   set and is therefore weaker than the count floor it replaced — caught by the plan validator):
   - the blueprint's agent `FileEntry` paths equal the `agents/*.md` files the render actually
     writes to disk. Two different producers; catches a render that drops a file.
   - the population is non-empty. Cheap, and the one thing `X == X` could never say.
   - `lens_dispatch("Production")`'s agents are a **subset** of the blueprint population. Two
     genuinely different sources; catches a lens dispatching to an agent that renders nowhere —
     not hypothetical, given `trajectory-monitor`.

Assertion 3 is what stops the other two being vacuous. Its first revision did not: comparing a
derived set against its own derivation is the `[fail:test] assertion-invariant-over-named-dimension`
shape, and the mutation receipt for it could not have been produced.

### Phase 2 — Remove the canary

**Status: DONE.**

- `depends_on`: `[1]`
- `parallel_group`: `serial-2`
- `merge_hazards`: `review.md.j2` — the largest template, edited by any concurrent review-stage
  task; the six `probe_flags` sites sit on lines other tasks touch.
- **Scope in:** the six source paths and the four test paths in the Affected Components table.
- **Scope out:** `surface_baseline.json`, `_ATOMIC_RATCHET`, the five version files.
- **Exit criterion:** `uv run pytest -q` green; `uv run ruff check src/ tests/`,
  `uv run ruff format --check src/ tests/`, `uv run mypy --strict src/` clean; **and the sweep
  below returns only the ADR-004 compatibility test**:
  `rg -n 'repo_probe|ProbeCheck|probe_failed|probe_failures|build_probe_check|return_envelope|probe_flags|repo-access probe' src/ tests/ docs/`
  plus `rg -n -- '--diff-files\b|--rev\b' src/ tests/` for the same allowance. **The word
  boundaries are load-bearing**: unanchored, `--rev` matches `--revision`, `--reverse` and every
  `git rev-parse` written with a leading dash, turning a binary criterion into a judgement call.
  Expected: exactly the ADR-004 compatibility test's own occurrences and nothing else.
- **Risk:** medium — a missed `probe_flags` site leaves a flag the CLI now only absorbs, which is
  silent rather than loud. The widened sweep is the mitigation, and it is widened in three
  directions the draft's version missed: the include and variable names, the retired flags
  themselves, and the prose phrase — over `tests/` and `docs/` as well as `src/`.
- **Rollback:** revert to Phase 1's commit; the gate survives.

ADR-004's compatibility test is part of this phase, with three arms, because each covers a
different way to go green wrongly: exit 0 with the flags present; the deprecation line reaches
stderr; and `__version__ < "0.55.0"`. Without the second, deleting the warning stays green; without
the third, the flags live forever.

### Phase 3 — Re-render, bump, and confirm the surface prediction

**Status: DONE.**

- `depends_on`: `[2]`
- `parallel_group`: `serial-3`
- `merge_hazards`: the five version files move together; `surface_baseline.json` if the prediction
  below is wrong.
- **Scope in:** `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`,
  `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`, CHANGELOG,
  and `_ATOMIC_RATCHET["review"]` in `tests/structural/test_command_size_budget.py`.
- **Scope out:** any template edit — those belong to Phase 2.
- **Exit criterion**, as a reproducible command rather than a slash invocation:
  `uv run python -m harness_maker.cli make . ` applies; then **two greps over the same directory,
  because a negative result alone cannot distinguish clean from empty**:
  `rg --no-ignore -c 'Return envelope' .claude/agents/` finds nothing, and
  `rg --no-ignore -c 'Finding Schema' .claude/agents/` finds four — the positive control proving
  the path was searched and the bodies rendered. (`--no-ignore` is belt-and-braces: the validator
  argued `.gitignore:26` makes this vacuous, and that was **refuted by running it** — an explicit
  path argument is searched, four matches, rc=0. The flag keeps the criterion true if the ignore
  rules later change.) Then `uv run pytest tests/structural/ -q` green **without regenerating
  `surface_baseline.json`**; all five version files read 0.54.0.
- **Tracked effects of the re-render, enumerated.** `.gitignore:26` ignores `.claude/*`, but three
  tracked surfaces survive it and the previous revision claimed only one: (1) `.claude/harness.yaml`
  is negated at `:27` and the renderer rewrites its whole provenance block, not just the version;
  (2) `.claude/observability/mutation-receipts.jsonl`, written in Phase 1, is re-included by the
  observability negation block; (3) `worktree._ensure_harness_gitignore` appends to `.gitignore`,
  and `enablement_preflight` can flip `worktree.enabled` in `harness.yaml`. After reading the
  render, restore what this phase did not intend to change:
  `git checkout -- .claude/harness.yaml .gitignore` — leaving only the deliberate version stamp.
- **Risk:** medium — the exit criterion contains a prediction, and this repository's most recent
  surface estimate was 2.6× low.
- **Rollback:** revert the bump **and** the ratchet line; `git checkout -- .claude/harness.yaml
  .gitignore` if the render left churn. Phases 1-2 stand alone.

**The prediction, stated so it can be wrong.** `round_trips` is compared exactly, but `probe_flags`
appends to existing `!` lines and the `mktemp` is described in prose, so no `!` line and no
`Task(` / `Bash(` call site is added or removed: `review` should stay at 39 (confirmed against
`surface_baseline.json`). `chars` is a ratchet with a ×0.80 per-command floor and a 5% aggregate
floor; the cut is ~1-2k against `_ATOMIC_RATCHET["review"] = 71143`
(`test_command_size_budget.py:520` — **not** 70818, which the previous revision cited; that is the
*pre-probe* value, and the `:517` comment records `70818 -> 71143` as the +325 this PLAN is about
to delete). The floor is `int(71143 * 0.80) = 56914`; a 1-2k cut cannot breach it. The agent bodies
are not part of the command surface at all.

**The ratchet must come down, and that is scope, not bookkeeping.** Deleting the +325 the ceiling
already banked plus ~1-2k more leaves `review` measuring well under 71143, and
`specs/SPEC-workflow-loop-efficiency.md:126` requires `_ATOMIC_RATCHET` be "updated deliberately,
never absorbed silently". Leaving it hands the next task ~2k of unattributed headroom. Phase 3
therefore lowers `_ATOMIC_RATCHET["review"]` to the post-removal measurement, with a comment line
in the existing `:513-519` style naming this PLAN. **If either arm goes red**, the contingency is the ADR-010 procedure and not a quiet
regeneration: fold from a base-reachable commit, in its own commit, with a
`work-docs/BASELINE-DELTA-probe-envelope-contract.md` attributing every moved key.
`surface_allowance` is declared at zero precisely so the ratchet stays armed while work is in
flight.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/conditional_router.py` — `ALL_LENSES`, `mandatory_lenses` and `LENS_DISPATCH`
  are the coverage vocabulary and Phase 1's read-minimum population reads them. Changing them to
  make the gate pass inverts the dependency.
- `src/harness_maker/review_consensus.py` — the consensus tags and disposition alias are a separate
  axis; the probe never fed them.
- `src/harness_maker/codex_ledger.py` — `DISPOSITION_VALUES` is the alias source
  `review_consensus` re-exports; unrelated and easy to touch by proximity.
- `src/harness_maker/synthesize.py` — `_ALL_AGENTS` and `_COMMUNICATION_VARIANT`. Phase 1 reads the
  blueprint's output, and editing the renderer to satisfy a test is the inversion ADR-003 forbids.
- `src/harness_maker/templates/agents/_partials/finding_schema.md.j2` — sits beside the deleted
  partial in all four bodies and describes an unrelated contract.
- Advisory: `blocks_approval` keeps exactly one meaning — a lens did not deliver a result. Do not
  route any new condition into it.
- Advisory: the debt list in `test_new_gates_file_a_mutation_receipt.py` may only shrink. Adding an
  entry to make a gate pass is forbidden; ADR-006 removes one.
- Advisory: the five version files move together or not at all.

## 🧪 Testing Strategy

**Unit.** ADR-004's compatibility test, three arms (exit 0, stderr line, version sunset). The
existing `lens_coverage` tests that do not concern the probe are kept and must stay green with the
`probe` parameter gone — they are the evidence that removal did not disturb the verdict.

**Structural.** The three assertions of Phase 1. Assertion 3 is set equality, not a count, so it
fails on both a silent shrink and a silent substitution. The mutation receipt is filed against
assertion 1's controlling line.

**Integration.** `uv run python -m harness_maker.cli make . ` then grep the rendered agent bodies
for the retired contract. This is the arm that catches a template include left behind — the source
can look clean while the render still carries it, which is `[wiki] is_codex`'s exact shape.

**Manual.** One `/hm:review` after Phase 3 to confirm Step 3 no longer mentions the probe and the
verdict prints three keys. Not a gate: a review's grade depends on the diff.

**Deliberately not tested.** Whether an agent with `Read` in `tools:` actually reads. That is what
the canary tried to test and could not; the gate makes the narrower claim it can check, and ADR-001
records the gap.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A `probe_flags` site or the include is missed | medium | low | Phase 2's sweep covers eight identifiers over `src/`, `tests/` and `docs/`; the CLI absorbs a stray flag rather than dying |
| The surface prediction is wrong | medium | low | Phase 3 names the ADR-010 contingency; `surface_allowance` is zero so the ratchet stays armed |
| The strengthened gate is vacuous | low | high | assertion 3 asserts set equality against the blueprint and `lens_dispatch`, not a count |
| Phase 1 reverted, debt-list line left deleted | low | medium | the rollback names the debt line explicitly (ADR-006) |
| An un-re-rendered harness loses the probe silently | high | none | intended — the check was advisory and reported only failures |
| A future write-privileged agent is blocked by the allowlist | medium | low | intended and loud; the fix is a one-line entry with a reason |
| Removing `probe_failed` breaks an unknown consumer | low | medium | verified: only `review.md.j2` reads it — `/hm:health`, `readiness` and the ledgers do not |
| The read-minimum blocks a future read-less agent | low | low | ADR-003 scopes it to the `lens_dispatch` population, where a review is unapprovable without it |

## ✅ Success Criteria

- [x] The Phase 2 sweep over `src/ tests/ docs/` returns only the ADR-004 compatibility test.
- [x] `test_agent_frontmatter_merges.py` guards all 15 rendered agents (it guards 11 today) and
      asserts the four write-privileged exceptions by exact set; it has a mutation-receipt row
      whose `--deletes` target is outside Phase 2's Affected Components; and
      `test_new_gates_file_a_mutation_receipt.py`'s debt list is one shorter.
- [x] Assertion 3's three sub-arms compare independent sources — deleting any one of them turns a
      distinct scenario red, and none is of the form `X == X`.
- [x] Deleting the receipt's named line turns that gate red; restoring it turns it green.
- [x] `lens_coverage check --diff-files X --rev Y` exits 0, prints the deprecation line, and the
      sunset arm fails once `__version__` reaches 0.55.0.
- [x] Full suite, ruff check, ruff format --check and mypy --strict are clean.
- [x] `uv run python -m harness_maker.cli make . ` applies; the negative grep finds nothing AND the
      positive control finds four; `.claude/harness.yaml` and `.gitignore` carry no unintended churn.
- [x] `_ATOMIC_RATCHET["review"]` was lowered to the post-removal measurement with an attributing
      comment, or an ADR records why the headroom is kept.
- [x] `tests/structural/` is green without regenerating `surface_baseline.json`, **or** the fold
      landed as its own commit with a BASELINE-DELTA row per moved key.
- [x] All five version files read 0.54.0.

## 🧾 Execution notes

What the phases actually did, including where this document was wrong.

**Phase 1.** A.5 round 1 returned FAIL with `blocking_issues` EMPTY — all six tests judged
sound, and the single gap was the ADR-006 half (receipt + debt-list) not yet done. Round 2
PASSED. Two facts were read from source rather than inferred: the receipt guard is
**file-granular** (`_receipted_files` maps rows to filenames, `:100-115`), so one row covers all
six functions; and `_LOCATOR_RE` has **no extension allowlist** by explicit design note, so a
`.md.j2:5` target is intended, not a hole. Both A.5 rounds ran without Bash and said so — their
mutation verdicts are static tracing, and the executed ones below are mine.

**Every mutation claim in this task was executed, not argued.** 6 gate assertions + the receipt's
own deletion claim + the absent-case test = 8 probes, all RED. One probe was itself wrong first:
`set() or {...}` does not produce an empty set (`set()` is falsy, so the dict comprehension is
returned) — the test was fine and the mutation was void. Re-run with `if False and …`.

**Phase 2.** The removal touched exactly the predicted set. `test_agent_body_partials`'s hash pins
moved for **exactly four** agents — the same four that gained the include in
PLAN-bench-study-adoption Phase 4 — which is the check worth making: a fifth would have meant the
deletion reached past the include. 21 `probe=None` call sites in three existing test files needed
updating; the PLAN did not name them, and they are the reason the `probe` parameter's removal is a
consumer-visible change rather than an internal one.

**Two things this PLAN got wrong, found by running it:**

1. The ADR-004 test pinned the verdict shape as three keys. The real verdict has **four** —
   `preset` predates this change entirely and is not probe-related. Production was correct and the
   pin was too narrow (§4.5's third case), so the test was widened, not the code.
2. Phase 3's positive control expects `Finding Schema` to appear in **four** rendered agents. It
   appears in **six** — `finding_schema.md.j2` is included by more agents than the four that
   carried the probe. The control's purpose (prove the directory was searched, so an empty result
   means clean rather than unsearched) is met; the number was wrong.

**Phase 3 — the surface prediction held.** `round_trips` for `review` stayed at 39 and all three
surface gates passed with no baseline regeneration, as predicted. `review` measured **70153**
against a pinned 71143 (−990, inside the predicted 1–2k), and `_ATOMIC_RATCHET["review"]` was
lowered to the measurement per W1 rather than left as slack.

**Phase D.5 — newly-reachable window.** The repair makes `lens_coverage check` accept flag values
it previously died on: any `--diff-files` path, existing or not, plus `--rev` alone. Covered by
`test_the_retired_flags_are_still_accepted`. The **absent case** — a re-rendered harness passing
neither, which is the normal path after this change — is covered by `test_omitting_them_is_silent`,
added because the other three arms all pass the flags and a warning moved outside its `if` would
have stayed green through every one of them. Verified RED under that exact mutation.

**Carried into wrapup — TWO items.**

1. **The base harness is pinned to this worktree.** Phase 3's re-render was run with
   `--directory <worktree>`, so every rendered `/hm:` command in the base now carries
   `uv run --with $HOME/harness-maker/.worktrees/probe-envelope-contract`. `task-land` deletes
   that path, after which every `/hm:` command in this project fails to resolve its `--with`
   target. It was not re-rendered back immediately because the plugin cache still holds 0.53.0,
   whose templates carry the probe — restoring the pin now would put the retired contract back
   into `.claude/agents/` in the middle of the review that reads them. **Fix at wrapup, after
   the land**: re-render from the plugin cache. The PLAN's Phase 3 exit criterion did not say
   which cwd to render from, which is how this got in.
2. `mutation_receipt.record` files at the **base** repo by design (the
`codex_ledger` row-loss lesson), and `.claude/observability/mutation-receipts.jsonl` is tracked.
The new row is therefore in base while wrapup commits in the worktree — the
`wrapup-memory-base-seam` shape. It must be staged from base or `task-land` will meet a dirty tree.

## 🔍 Plan Validation

**Outcome: `MAJOR_REVISION_TERMINAL`.** Read this literally, because it does not mean what the
name usually means here. One validator pass ran, by standing user rule (2026-08-22):
`plan-validator` runs exactly once per `/hm:plan` and is **not re-run after fixes**. So every
finding below was *applied* to this document, and **none of the fixes has been validated by
anything but the author**. `TERMINAL` normally records "a second pass ran and these survived it";
here it records "there will be no second pass". The difference matters to whoever reads this next:
the repairs in C2, W1 and W2 are unreviewed.

`/hm:execute` **proceeds**, carrying that as a known risk. The A.5 gate and `/hm:review` are the
next things that will look at this work.

The one item the validator correctly identified as the user's to decide — C1's cost/benefit, since
Interview #1 was answered on a false number — was put to the user with the corrected figures and
answered **proceed as planned** (Interview #4). Nothing is left open.

| # | Severity | Finding | Verified? | Disposition |
|---|---|---|---|---|
| C1 | critical | `_READ_ONLY_AGENTS` holds 11 agents, not 2; the claimed "nine unguarded" hole does not exist | ✅ at `:97-111` | **Applied and re-confirmed.** Count corrected in three places; the gain restated as fail-open→fail-closed for *future* agents plus exact-set coverage of the four write-privileged ones. The user was shown the corrected trade and chose the full scope anyway (Interview #4) |
| C2 | critical | Assertion 3 compared a derived set against its own derivation (`X == X`), strictly weaker than the count floor it replaced | ✅ by inspection of ADR-003's own wording | **Applied.** Three sub-arms against independent sources: blueprint↔rendered-disk equality, non-empty, `lens_dispatch ⊆ blueprint` |
| C3 | critical | `rg -c … .claude/agents/` is vacuously green because `.gitignore:26` ignores the directory | ❌ **REFUTED by running it** — 4 matches, rc=0; an explicit path argument is searched | **Not applied as stated.** The adjacent recommendation *was* adopted: `--no-ignore` for durability plus a positive control, since a bare negative cannot distinguish clean from empty |
| W1 | warning | `_ATOMIC_RATCHET["review"]` is 71143, not 70818; a net-negative task leaves ~2k unattributed headroom | ✅ at `test_command_size_budget.py:517,520` | **Applied.** Figure corrected; lowering the ratchet is now an explicit Phase 3 scope item citing `SPEC-workflow-loop-efficiency.md:126` |
| W2 | warning | Phase 3 understated the re-render's tracked effects | ✅ three surfaces confirmed | **Applied.** All three enumerated, with a `git checkout --` restore step and a matching rollback clause |
| W3 | warning | The mutation receipt could name a line Phase 2 deletes, leaving a dangling unfalsifiable receipt | ✅ `:113-115` only checks row existence | **Applied.** Phase 1 constrains the `--deletes` target to a file outside Phase 2's scope |
| W4 | warning | `--rev` unanchored matches `--revision`/`--reverse`/`rev-parse` | ✅ by inspection | **Applied.** Word boundaries plus an expected hit count |
| S1 | suggestion | Lexicographic version comparison mis-orders `0.100.0` | ✅ | **Applied.** ADR-004 specifies parsed tuples |
| S2 | suggestion | No `## Non-Goals` section | ✅ | **Applied.** Four scattered statements hoisted |

**Cross-model second opinion.** `codex`: `invoked`, 8 findings, all accepted and applied in
revision 2 — the validator re-checked each and confirmed six as genuinely resolved, escalating two
whose fix only appeared to resolve them (they became C2 and C3 above). `antigravity`: `skipped`
(`agy envelope status 'CANCELED'`, empty payload) — that model has no voice in this validation.

**What this validation is worth noting for.** Two of the three findings that mattered were about
*this PLAN's own verification*, not its design: a `sed` range that silently truncated a set, and an
anti-vacuity arm that was itself vacuous. Both passed a first reading. The one finding I could
refute, I refuted by running the command rather than reasoning about ripgrep's ignore semantics —
which is the same rule the canary this PLAN deletes was retired for violating.
