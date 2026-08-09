# Pending Proposals

> Improvement proposals triggered by failure entries with count ≥ 3.
> Review and decide whether to ingest into the harness.

## RESOLVED 2026-08-07 — shipped as mechanical guards

The proposals below were implemented by PLAN-mechanical-guards-from-backlog and are removed
from the queue. Each guard carries a mutation receipt in
`.claude/observability/mutation-receipts.jsonl` naming the line to delete and the test that
dies with it.

| Retired proposal(s) | Shipped as |
|---|---|
| `snapshot-regen-order-guard`, `post-finalize-snapshot-regen-hook`, `snapshot-regen-count-11-escalate-to-mechanical`, and their RETIRE note | `tests/structural/test_no_golden_bakes_a_machine_path.py` — guards the PROPERTY (no machine-specific absolute path in any committed golden) **and** the `.worktrees` symptom the three prior proposals all targeted. Shipped property-only first, and that was **largely vacuous over count:13**: `synthesize._portablize_ref` rewrites the render machine's home to a literal `$HOME` before the golden is written, so a worktree capture emits `$HOME/…/.worktrees/<slug>` — which the property rule deliberately exempts. The three prior proposals were right that `.worktrees` is the discriminator; the correction was to keep both rules, since neither covers the other. |
| `dead-string-pin-guard` | `tests/structural/test_no_dead_string_pins.py` — **partially**. Its rule (b) (step-number pins) shipped and found 7 real offenders. **Its rule (a) was implemented, run, and REJECTED**: it flagged 19 legitimate anti-regression guards, because a negative pin's literal being absent from `src/` is the correct state for one, not a defect. The reasoning is recorded in that file so the rule is not re-proposed. |
| `CI gate — every new CLI surface must be driven in its shipped form` | `tests/structural/test_cli_surfaces_are_driven.py` — found `delegation_ledger` undriven; a driver test was added rather than an allowlist entry |
| `mutation-check-receipt-per-new-gate` | `hm mutation_receipt record` + `tests/structural/test_new_gates_file_a_mutation_receipt.py` — the **consumer**, without which the CLI was registered and inert (three reviewers and a cross-model voter said so in one round, correctly). A new `tests/structural/` gate now cannot land without a row; pre-existing gates sit on a shrink-only debt list. Six receipts, each earned by deleting the line and observing an **assertion** failure — a collection error was rejected as proof, since any line kills a module that way. Mechanises the OBLIGATION, not the proof: a false receipt is still possible, an absent one is not (module docstring states the limit rather than selling past it). |

## Proposal: orphan-worktree-prune-on-create (2026-05-17)
**Triggered by:** [fail:design] worktree-finalize-pulls-orphan-wip-into-main (count: 3 as of 2026-08-01, was 1 when this proposal was written; cost-per-incident is high — 139-file scope explosion + ~30 min cleanup)
**Proposed mechanism:** new step in `harness_maker.worktree create` — before creating a new worktree, run `git worktree prune` and delete any unreferenced `execute-*` branches whose HEAD is a WIP-commit and whose merge-base with the current main is the same commit as the worktree branch's parent. Add a `--debug-worktree` opt-out for users who want to inspect old WIPs.
**Rationale:** Orphan WIP commits from interrupted sessions stay on `execute-<timestamp>` branches; subsequent finalize-stage-only invocations risk merging their content into main if the worktree library's merge logic is not perfectly scoped to the active branch. Pruning at worktree-create time keeps the `.git` directory hygienic. Low risk — WIPs are recoverable via reflog if needed, and the user explicitly invokes worktree create when they intend a fresh start.

## Proposal: health-check-no-concrete-id-in-agent-frontmatter (2026-05-31)
**Triggered by:** [fail:review] reviewer-subagent-model-unsupported (count: 3)
**Proposed mechanism:** prevention ALREADY SHIPPED as the unit test `test_agent_model_alias_rendering` (renders the real pipeline, fails if a concrete `claude-*` id reaches any `.claude/agents/*.md` `model:` line). Optional additional surface: a `/hm:health` Layer-1 sub-check that scans an *installed* `.claude/agents/` (the dogfood/user install, which the unit test does NOT cover because it is gitignored and rendered out-of-band) and flags any concrete id — catching stale installs that predate a re-render.
**Rationale:** the unit test guards the *template/render* path going forward; it cannot catch an already-rendered stale install (the exact state this repo's own gitignored `.claude/` is in until `/hm:make --update`). A health check closes that residual gap. No new mechanism needed for the render path itself.

## Proposal: wrapup-close-marker-integrity-guard (2026-06-20)
**Triggered by:** [fail:render] wrapup-eof-append-outside-marker (count: 3)
**Proposed mechanism:** a MECHANICAL post-write guard (prose instruction has now failed 3×). Two complementary options: (a) a `PostToolUse` Write/Edit hook (or a wrapup Step 6 pre-stage assertion) that, when the touched path is `.claude/memory/{wiki,failures}.md`, runs `grep -c "@hm:/user:entries" <file>` and HARD-FAILS the wrapup if the count is 0 (close marker deleted) — the cheapest possible regression catch, byte-deterministic, no integration suite needed; (b) make `harness_maker.memory_retrieve.parse_entries` emit a `stderr` warning naming the file when the close marker is absent, so the corruption is loud at every retrieval instead of a silent zero-result.
**Rationale:** Three recurrences (2026-05-17 content-after-marker, 2026-05-20 marker-deleted, 2026-06-20 marker-overwritten) all share one root: a wrapup append touching the close-marker line. The standing fix added prose ("name the marker, insert ABOVE it") + a verification-suite note, but under autopilot/dogfooding pressure the LLM still overwrote the marker. The failure is invisible until an INTEGRATION-tier test runs, and was mis-triaged as a brittle test before being root-caused — costing a full phase of delay. A 1-line `grep -c` assertion at wrapup time would have caught all three at the moment of damage. This is the canonical "prose guard failed N times → promote to mechanical guard" case.

## Proposal: re-review-the-fix-not-just-the-suite (2026-08-05)
**Updated 2026-08-07 — count:5, and the mechanism this proposal describes was RUNNING.**
PLAN-multisession-marker-scoping ran four review rounds and **three of the four rounds' fixes each
introduced a defect worse than the one they closed**, every time on a green four-gate run. The
round-N+1 delta re-review proposed below did happen — that is how the new defects were found — so
the finding is that re-review **detects** this class but does not **stop** it: the task still
closed at grade B / CHANGES_REQUESTED with a consensus-passed P1 open, because each round's repair
was aimed at a rule (who may take over a marker) for which no correct rule existed. Two additions
this instance argues for: (a) the round-N+1 prompt should ask whether any **existing assertion was
edited or loosened** as part of the fix, not only whether new defects appeared — see the new
[[fail:test] assertion-amended-to-match-the-fix]]; (b) when round 3 is still repairing the same
mechanism, the loop should be required to escalate to "is this mechanism constructible at all?"
rather than schedule round 4 — here the answer was no (no liveness signal outlives the CLI:
[[fail:design claim-record-used-as-access-control-list]]), and one round spent asking would have
been cheaper than two spent patching.
**Triggered by:** [fail:test] fix-introduced-defect-passes-all-gates (count: 5 as of 2026-08-07; this proposal was written at count: 3) — the fourth instance is PLAN-harness-diet Phases 2-6: 14 findings over four rounds, 11 of them introduced by this task's own fixes, seven while fixing the other four. It also sharpens the proposal: three of the eleven were a single class-default flip re-fixed four times, so the receipt should demand an ENUMERATION (the grep and its full result set) whenever a fix changes a shared default or a shared allowlist, not just a re-review of the diff.
**Proposed mechanism:** make the review stage's auto-fix loop re-review the FIX DELTA, not
only re-run the suite. Round N applies fixes; round N+1 currently recomputes a grade from a
green suite, which is exactly the signal that cannot see a fix-introduced defect — the suite
was green before the fixes too.
**Rationale:** three occurrences now, all the same shape: the fixes for round-1 findings
introduce fresh defects that every automated gate passes. The 2026-08-05 instance produced
five — a half-updated en/ko pair, a comment contradicting the test docstring written beside
it, a dual-target edit that reached only one target, stray whitespace in a shipped artifact,
and a newly-added gate that was itself too narrow (English-only). All five were found by
re-spawning a reviewer on the delta with the prior findings and the applied fixes named
explicitly; none were found by the suite. The cheap version is a required round-N+1 dispatch
scoped to the changed files with the round-N finding list attached, asking only "did any fix
introduce a new defect, and is each new test sound?" — not a full re-review. Note the
recurrence was invisible until 2026-08-05 because this entry's heading carried a
`previous_count` field the writer rejects; see [[fail:design prev-count-heading-freezes-counter]].
Two of the five defects were in a gate added by the same round, which suggests the prompt
should ask specifically about newly-added tests.

## Proposal: ruff-format-in-execute-not-just-wrapup (2026-07-09)
**Triggered by:** [fail:lint] wrapup-final-verify-skips-ruff-format-check (count: 3)
**Proposed mechanism:** execute + review stage procedure note (run `ruff format` after edits, not only `ruff check`) OR a pre-commit format-fix hook. **Updated 2026-07-25 — this mechanism has a gap.** It assumes the failure mode is "format was never run". A second mode exists: format IS run and its exit code is discarded, because the command was piped (`ruff format --check … | tail -1` makes `$?` the tail's). Neither a procedure note nor a format-fix hook catches that. Add: gate commands must never be piped — redirect and record one `rc` per check (`cmd > f 2>&1; echo "rc=$?" >> f`). See `[fail:lint] gate-exit-code-lost-through-pipe`.
**Updated 2026-08-05 — the predicted failure happened, in the predicted place.** PLAN-harness-diet Phase 1: `/hm:execute` Phase D ran `ruff check` clean and never ran `ruff format --check`; the review's P0 found 7 files would reformat, gated by CI in `ci.yml:42`, `release.yml:50` and `nightly.yml:40` **before pytest**. This proposal named that exact gap on 2026-07-09 and has not been ingested, so the recurrence is a measure of the proposal backlog, not of new information. `[fail:lint] ruff-format-not-in-local-verify-pass` is now count:3 as well — the two sibling slugs describe one root cause and should be merged when this ships. Cheapest sufficient fix remains one line in `execute.md.j2` Phase D: add `uv run ruff format --check .` beside the existing `ruff check`, since the LLM mirrors the visible command list.
**Rationale:** Observed again in PLAN-second-opinion-multi-model wrapup: `ruff check` passed clean at execute AND review, but `ruff format --check` at wrapup found 7 unformatted files (long-line reflows the auto-fixer left un-normalized). Because `ruff check` ≠ `ruff format`, code that passes every lint gate in execute/review can still fail the wrapup format gate, forcing a late reformat + re-verify. A note in execute.md.j2 / review.md.j2 Phase D to run `ruff format` (not just `ruff check`) after edits — or a PostToolUse format-on-write hook scoped to `*.py` — would keep the tree format-clean continuously and stop wrapup from being the first place format is checked.

## Proposal: format-check in every local verify entry point, derived not enumerated (2026-08-05)
**Triggered by:** [fail:lint] ruff-format-not-in-local-verify-pass (count: 3)
**Proposed mechanism:** template change + structural test
**Rationale:** This entry sits at count 3 with no proposal of its own, while its sibling
`[fail:lint] wrapup-final-verify-skips-ruff-format-check` (also count 3) has one
(`ruff-format-in-execute-not-just-wrapup`, 2026-07-09). Two entries at the escalation
threshold describing the same missing command in two different stages is the argument for
stopping the per-stage patching: every rendered surface that tells the model to "run the
checks" should derive that command list from ONE place, so adding `ruff format --check`
once reaches execute, verify and wrapup together. Proposed guard: a structural test that
collects every rendered instruction block naming `ruff check` and asserts the same block
also names `ruff format --check` — cheap, byte-deterministic, and it fails loudly the next
time a new stage copies the four-gate list by hand and drops one.

## Proposal: a new gate must state its population, and a test must prove the population is complete (2026-08-05)
**Triggered by:** [fail:test] gate-scoped-to-the-artifact-being-fixed (count: 3)
**Proposed mechanism:** review-stage checklist item + non-vacuity assertion convention
**Rationale:** Three instances now, and the third recurred inside the very round whose
CLAUDE.md text records the second. The shape is always the same: a guard is written while
fixing artifact X, its collection step is shaped by X, and the identical defect survives in
the sibling artifacts the collection never reached — most recently a documented-command gate
that scanned only shell-TAGGED fences and therefore could not see README's untagged
paste-into-Claude bootstrap block, which is the install entry point, and a memory-fold
correspondence test that derived its expected pathspec from the rendered wrapup TEMPLATE and
so was structurally blind to a writer invoked from Python. Prose discipline has now failed
three times, so the proposal is mechanical: (a) every new gate must expose its collected
population as a value (a list of paths/fences/writers), (b) the gate's own test must assert
that population is non-empty AND contains at least one member the author did not touch in the
triggering fix, and (c) `/hm:review` gains a checklist line — "for each new gate, name the
sibling artifact class it does NOT cover" — because a gate whose blind spot is written down
is a known limitation instead of a silent recurrence.

## Proposal: a guard's remedy must be computed from the state the guard already inspected (2026-08-06)
**Triggered by:** [fail:design] remediation-instructs-refused-action (count: 3)
**Proposed mechanism:** construction convention for refusal messages + a review-stage checklist line
**Rationale:** Three instances, and the third is a strict escalation of the first two. Where the
earlier ones instructed an action the module merely refuses (a cache-diagnostics remediation
telling users to report a model id the table was just narrowed to reject), this one instructed
an action the module exists to PREVENT: the new `worktree.enabled` disable guard blocks a
true->false flip while a task worktree is live, and then told the user to `task-land <slug>` —
which, when that worktree belongs to a live peer session, is exactly the count:3
`worktree-finalize-pulls-orphan-wip-into-main` contamination the guard is protecting against.
The common mechanism is that the remedy string is authored as prose, from the single-session
case the author has in mind, while the disqualifying fact is already sitting in a variable the
guard just read — the registry row, the model table, the flag's presence. Prose review does not
catch it because the imperative is correct in the case the reader also has in mind. The proposal
is therefore structural rather than another "write better messages" note: (a) a refusal message
must be BUILT from the same inspected state that produced the refusal, not written alongside it
— if the guard consulted the registry to decide, the message renders the registry facts
(ownership, liveness, pid) it consulted; (b) every remedy must be checked against the guard's
own predicate, i.e. "if the user does exactly this, does the condition I am refusing on become
safe, or merely absent?"; (c) `/hm:review` gains a checklist line — "for each refusal or
remediation string, name the state that makes the suggested action unsafe, and show that state
is either impossible or named in the message." The concurrency-reviewer caught this instance by
reading the guard's inputs rather than its text, which is the review posture the checklist line
is trying to make routine.

## Proposal: a cache key may not fingerprint its own launcher (2026-08-06)
**Triggered by:** [fail:design] verification-cache-key-nondeterministic (count: 3)
**Proposed mechanism:** derive the verification key from repo state only, and make the
launcher-independence property a test rather than a scrubbing rule.
**Rationale:** Three instances, each one surviving the previous fix, and each time the symptom
is invisible because a permanently-cold cache looks exactly like a correctly-invalidated one.
Instance 1 scrubbed volatile VALUES out of `PATH`/`VIRTUAL_ENV`; instance 2 flipped the env
policy from blocklist to allowlist and added a two-subprocess stability test; instance 3,
measured during this wrapup, shows the key is still a function of the `uv run --with` ARGUMENT.
From one shell with an unchanged tree: `--with .` -> `fd7f934e...`, `--with /home/noel/harness-maker`
-> `3fd66ab5...` (the marker `/hm:verify` had just written), plain `uv run python -m ...` ->
`863e854c...`. The cause is that `PATH` carries `~/.cache/uv/archive-v0/<hash>/bin` and
`archive-v*` is deliberately NOT scrubbed — the comment says that path "encodes the identity of
the installed package, which is real signal", and it does, but it is ALSO a function of how the
caller spelled the dependency. The existing stability test cannot see this: it spawns two
subprocesses in the same invocation shape, and the shapes are what differ. The unifying
root-cause sentence this entry has carried since instance 1 is still unaddressed — a key that
fingerprints the ambient environment is invalidated by the launcher — so the proposal is to stop
fingerprinting the environment at all: hash repo state (root, HEAD, relevant diff, lockfiles) and
the TOOL VERSIONS already collected (`python`/`ruff`/`mypy`/`pytest --version`, which capture the
build-affecting facts the env vars were proxying for), and drop `_env_hash` entirely. Test to add
alongside: compute the key under three different launcher shapes and assert one value — the
property no previous fix stated.

## Proposal: a success message must be emitted from the same branch as the effect (2026-08-06)
**Triggered by:** [fail:lint] gate-exit-code-lost-through-pipe (count: 3), with
[fail:tooling] silent-no-op-patch-reports-success (count: 1) as the same-session sibling.
**Proposed mechanism:** ban unconditional success output in harness-authored scripts and in
one-off patch scripts; require per-check `rc` capture and a per-mutation match count.
**Rationale:** The entry's third instance is not a pipe at all — a background `pytest` run's
completion NOTIFICATION reported exit 0 while the run's own recorded `rc` was 1, which is the
fourth time this environment has done that. In the same session a `str.replace` patch script
printed "patched" after matching nothing (a two-space indent mismatch), so a P1 security fix was
recorded as Applied while the file was unchanged; it was caught two rounds later by a reviewer
re-reading the file. The two mechanisms differ — one discards a real verdict, the other never
produces one — but the operational rule is identical and cheap: **the string that says it worked
must be produced by the branch that did the work.** Concretely: (a) never pipe or redirect a gate
away from its `rc`; write `rc=$?` per check into the output file and read that file, never the
harness's exit-code notification; (b) any substitution must assert `new != old` or count matches
and print the count, and `Edit` (which errors on no-match) is preferred to any hand-rolled
replace; (c) `/hm:review` and `/hm:execute` should treat "reported Applied" as unverified until
the artifact is re-read — this round's REVIEW iteration table already carries a `Status` column
that would have shown the no-op if the re-read were routine rather than incidental.

## Proposal: a second execution model must gate every instruction that names the first (2026-08-08)
**Triggered by:** [fail:design] handoff-assumes-a-skipped-step (count: 3)
**Proposed mechanism:** structural test (render-grep over the shipped surface)
**Rationale:** The per-task worktree model was added alongside the ephemeral one and BOTH
render under the same `worktree.enabled` flag. Three instances followed, all the same shape —
an instruction written for the ephemeral model surviving unconditionally into the per-task
one. (1) `wrapup_land` assumed `finalize stage-only` had staged the code; it had not, and the
implementation was omitted from its own commit twice. (2) `execute.md` Step 5 still INSTRUCTED
that finalize, on a worktree `task-land` owns. (3) The loop told per-iter stages to run every
step, so `task-preflight` created a second `<WT>` and the iteration's work could strand on
`hm/<slug>` while loop-close finalized an empty worktree.

Each was fixed by hand, at the site, after it bit. What no one did was ask the general
question: *which other instructions name a command that only one model uses?* That list is
mechanically derivable. `worktree create`, `finalize`, `post-commit-pop` and `owned-crumb-add`
belong to the ephemeral model; `task-preflight`, `task-refresh`, `task-land` belong to the
per-task one. A structural test could assert that every rendered occurrence of either set sits
under a runtime discriminator (the `hm/*` branch check) or an explicit per-model override, and
fail on a bare one.

**Caveat the implementer should settle first:** a render-grep cannot tell a live instruction
from an explanatory mention — `/hm:health` names `worktree create` as content, and the loop's
own prose describes both models on purpose. That is the same exemption problem that made the
`dead-string-pin` rule's arm (a) unshippable at 19 false positives, so measure the false
positives against the tree BEFORE building the gate, and drop it if the ratio repeats.

---

## Proposal: a whole-file substring assertion may not stand in for a per-item claim (2026-08-08)
**Triggered by:** [fail:test] assertion-invariant-over-named-dimension (count: 10 — the
highest-count entry with no proposal of any kind, and the only one that grew this round).
**Proposed mechanism:** AST structural test over `tests/`, with a measured false-positive
count reported before it is enabled.

The tenth instance (antigravity-second-opinion-timeout) is the cheapest possible illustration:
a guard named for the presence of specific agy-envelope fixture LINES asserted
`"<literal>" in text` over the whole file. Deleting a real fixture line left it green, because
five unrelated occurrences of the same literal kept the substring true. The mutation-receipt
gate caught it; reading the assertion did not, and would not have — in isolation the line
looks exactly right.

The shape is mechanically detectable and does not need judgment about intent: an assertion
whose operator is a **whole-file / whole-blob containment test** (`in text`, `in content`,
`assert x in path.read_text()`) inside a test whose name or docstring claims something
**per-item or counted** (`each`, `every`, `all`, `_count`, `n_`, a plural noun). Such an
assertion can only fail when the LAST occurrence disappears, so its sensitivity is 1/N where
N is the number of occurrences — and N is invisible at the assertion site. The remedy is
already known and used elsewhere in this repo: parse the artifact and assert on the parsed
objects (count and field values), or assert on the specific line's full form, not on a
fragment that other lines also contain.

**Caveat the implementer must settle first, and the reason this is a proposal and not a
patch:** `"literal" in text` is *correct* for the large class of anti-regression pins where the
claim genuinely is "this string exists somewhere". Arm (a) of the `dead-string-pin` rule was
implemented, run, and rejected at 19 false positives for exactly this reason, and this rule
lives in the same neighbourhood. So the order of work is fixed: write the detector, run it
over `tests/` **first**, and publish the hit list with a hand-classification of true vs false
before writing a single line of enforcement. If the ratio resembles the `dead-string-pin`
result, record the measurement and close the proposal rather than shipping a gate the repo
will learn to suppress. A cheaper fallback that needs no classification: extend the
mutation-receipt obligation — a receipt for a containment-style assertion must name the
occurrence COUNT it observed, which makes 1/N sensitivity visible at authoring time without
forbidding anything.

---

## Proposal: a gate may not discover its own population from the string it forbids (2026-08-10)

**Triggered by:** [fail:test] gate-passes-because-its-subject-vanished (count: 3)

**Proposed mechanism:** a structural test over `tests/structural/` plus an authoring rule.

**Rationale:** the third instance (PLAN-second-opinion-oracle-polyglot) was not an accident
of migration like the first two — it was self-defeating *by construction*. The parity gate
asserted that no anchored surface still claims a fixed `pytest`/`ruff`/`mypy` command set, and
it built the list of surfaces to check by grepping for that same hardcoded triple. The moment
the fix landed the discovery predicate matched nothing, the per-surface loop iterated zero
times, and the gate would have reported PASS forever over a surface set nobody was auditing.
It can only be red in the world that existed before the fix. That is the same vacuous-population
shape as the two earlier instances, and it is now the class — not the incident — that keeps
recurring, so the entry's existing prescription ("add a non-vacuity assertion") is necessary but
has demonstrably not been enough to make authors notice at writing time.

Two candidate mechanisms, cheapest first:

(a) **Non-vacuity as a structural obligation, machine-checked.** A test over `tests/structural/`
that flags any test function which builds a collection by scanning files (`rglob` / `read_text` +
`in` / `re.search`) and then loops over it, without an `assert <collection>` / `assert len(...)`
before the loop. Byte-deterministic, no new runtime surface. Expected false-positive rate is the
open question — measure it over the existing suite and publish the hit list before enforcing, per
the precedent set by the `dead-string-pin` proposal above.

(b) **The authoring rule the instance actually proves:** a gate's POPULATION and its PREDICATE must
come from independent sources. The population is an enumeration (the rendered surface list, a
fixture manifest, a glob over a directory that exists in a clean checkout); the predicate is what
you assert about each member. When the same string supplies both, the gate's strength is inversely
proportional to the fix's success. This is a one-line addition to the mutation-receipt obligation:
a receipt for any scan-style gate must state the population SIZE it observed, which makes a
zero-size population visible at authoring time without forbidding any construction.

Recommend (b) first — it costs nothing and generalises — with (a) gated on the false-positive
measurement.

---

## Backlog note (2026-08-08) — count ≥ 3 entries with no proposal

Recorded so the gap is visible rather than re-discovered. This round produced no first-hand
evidence about either, so no mechanism is proposed for them here; whoever next trips one
should write the proposal from that instance rather than from this line.

| Slug | Count | Status |
|---|---|---|
| `[fail:test] test-pins-retired-implementation-name` | 4 | no proposal |
| `[fail:test] shipped-entry-point-not-exercised` | 4 | no proposal (the RESOLVED table's `test_cli_surfaces_are_driven.py` covers CLI surfaces only, not the general class) |
| `[fail:test] snapshot-regen-inside-worktree` | 13 | no proposal — added 2026-08-10. Highest count in the file and it was missing from this table entirely, which is its own signal. No first-hand instance this round, so no mechanism is proposed here; the obvious candidate (refuse `regenerate.py` when cwd is under `.worktrees/`) should be written by whoever next trips it |
