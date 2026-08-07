# Pending Proposals

> Improvement proposals triggered by failure entries with count ≥ 3.
> Review and decide whether to ingest into the harness.

## Proposal: snapshot-regen-order-guard (2026-05-10)
**Triggered by:** [fail:test] snapshot-regen-inside-worktree (count: 3)
**Proposed mechanism:** rule update in CLAUDE.md + execute stage procedure note
**Rationale:** The regen-before-finalize failure has happened 3 times: once in the worktree itself, once after squash-merge with stale paths, and once in deep-interview-llm-delegation where regen ran before worktree finalize. The correct order (finalize → regen → full pytest) is buried in the execute stage procedure. Adding an explicit ordered checklist note to execute.md.j2 (Phase 6/7 sequence for snapshot tests) would prevent this class of error automatically in every future exec-rev loop. Consider also adding a pre-regen assert that checks `git diff --name-only HEAD | grep 'templates/.*\.j2'` to confirm the template changes are present in main before regen runs.

## Proposal: post-finalize-snapshot-regen-hook (2026-05-17)
**Triggered by:** [fail:test] snapshot-regen-inside-worktree (count: 5)
**Proposed mechanism:** new step in `harness_maker.worktree finalize` CLI — when finalize-stage-only runs and the merged diff includes any `templates/**/*.j2` path, automatically invoke `tests/snapshot/regenerate.py` from the main repo root before returning and stage the regenerated `tests/snapshot/*.expected.yaml` files alongside.
**Rationale:** The 2026-05-10 proposal added documentation but did not automate the regen step. count:5 means humans still forget the sequence even with the doc. Automating inside the worktree CLI makes regen byte-deterministic with respect to main's filesystem path. Implementation: after `git checkout <wt-branch> -- .` in finalize-stage-only, check `git diff --staged --name-only | grep -q 'templates/.*\.j2$'`; if yes, `subprocess.run([sys.executable, 'tests/snapshot/regenerate.py'], cwd=main_repo, check=True, timeout=120)`, then `git add tests/snapshot/*.expected.yaml`.

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

## Proposal: snapshot-regen-count-11-escalate-to-mechanical (2026-07-17)
**Triggered by:** [fail:test] snapshot-regen-inside-worktree (count: 13 as of 2026-08-01; this proposal was written at count: 11)
**Proposed mechanism:** the two existing proposals for this entry were written at count:3 and count:5; it is now at **count:13** and neither prevention shipped. The 2026-08-01 dep-map task is a data point FOR the mechanical guard: `hm cli make --update` already refuses to run from inside `.worktrees/`, that rail held, and the phase's self-harness re-render was deferred rather than bypassed. Promote to a mechanical guard: make `tests/snapshot/regenerate.py` refuse to run when `git rev-parse --show-toplevel` resolves inside a `.worktrees/` path (hard exit + one-line remedy), rather than relying on a prose reminder.
**Rationale:** 11 recurrences is the highest count in the tier and the escalation last-mile visibly stalled — proposals exist but stop at count:5, so nobody re-read them as the count tripled. This is the canonical "prose guard failed N times → promote to mechanical" case, and the count itself is the evidence. Recording the update here so the staleness is visible rather than frozen at the count where the last proposal happened to be written.

## Proposal: dead-string-pin-guard (2026-07-26)
**Triggered by:** [fail:test] test-pins-retired-implementation-name (count: 4 as of 2026-08-01; this proposal was written at count: 3) — **scope needs widening**: two of the three fresh 2026-08-01 instances are *positive* pins, not negative ones (a phrase spanning a line wrap, and step-number literals like `"3. **Verify build**"` that broke on a correct renumber), so the negative-assertion lint below would not have caught them. Add a second, cheaper rule to the same check: flag any string literal in `tests/**` that contains a leading step number (`^\d+\. `) or that spans what is a line wrap in the source artifact — both are prose accidents, never contracts.
**Proposed mechanism:** a mechanical check, not another prose reminder — the last two recurrences were both committed by someone who already knew the rule. Add a test-suite lint that flags any *negative* string assertion (`assert "<literal>" not in <x>`) whose literal appears nowhere else in `src/` or `templates/`. A negative pin on a string the tree no longer contains cannot fail, so it is dead weight masquerading as a guard. Emit it as a `ruff`-style custom check or a meta-test over `tests/**`.
**Rationale:** Three occurrences, and the third landed *inside a test written to guard this exact family* — which is the strongest possible evidence that awareness is not the missing ingredient. Each time the sequence was identical: pin prose, later reword the prose correctly, and the assertion silently stops testing anything (a positive pin turns red and gets noticed; a negative pin turns permanently green and does not). The literal-vs-tree cross-reference is fully deterministic and repo-owned, so it needs no runtime and no external tool — the same shape as `test_ci_codex_pin_matches_the_verified_version`, which closed [fail:test] advisory-check-fails-unseen.

## Proposal: RETIRE the three snapshot-regen proposals (2026-07-26)
**Triggered by:** [fail:test] snapshot-regen-inside-worktree (count: 11) — **now superseded**
**Proposed mechanism:** none — withdraw `snapshot-regen-order-guard`,
`post-finalize-snapshot-regen-hook`, and `snapshot-regen-count-11-escalate-to-mechanical`.
**Rationale:** all three propose guarding against regenerating snapshots inside a
worktree, and that is no longer a defect. `tests/snapshot/regenerate.py:107-125` pins
`_HARNESS_MAKER_PKG_ROOT` and `_compute_install_ref`, making the fixtures
worktree-invariant by construction — verified empirically on 2026-07-26 by regenerating
from a worktree four times and grepping every fixture for the worktree path (zero hits).
Building a mechanical guard now would enforce the obsolete guidance, and that guidance is
actively harmful: refusing to regenerate in the worktree is what forces a hand-merge of
generated artifacts at land time. The count:11 history is left in place for audit.

## Proposal: mutation-check-receipt-per-new-gate (2026-07-27)
**Triggered by:** [fail:test] assertion-invariant-over-named-dimension (count: 8 as of 2026-08-06; this proposal was written at count: 5) — the sixth instance is the strongest argument yet for the mechanical receipt: a test asserting the telemetry record rejects unknown keys was green **both before and after** the field it was written for existed, satisfied all along by `extra=forbid`. A "name the wrong implementation this assertion rejects" receipt would have had no answer to write.
**Proposed mechanism:** a mechanical receipt, because prose has now failed five times —
including once inside `PLAN-token-economy-step-pruning`, whose ADR-010 is *itself* the
prose rule "mutation-check every gate". Proposal: extend the `/hm:execute` Phase D exit
contract so that every test **added or modified** in the diff must be named in a
machine-readable mutation receipt (`.claude/observability/mutation-receipts-<slug>.jsonl`,
one row per test: `{test_node, code_deleted, suite_rc_after_delete}`), and have `/hm:review`
Step 3 fail-closed when a diff adds a test node with no corresponding row. The check that
makes it non-vacuous is `suite_rc_after_delete != 0` — a row claiming a deletion that
left the suite green is exactly the invariant assertion this entry describes, and it
becomes visible as data instead of as a claim in a commit message.

**2026-08-01 (count 5, PLAN-autopilot-advance-noop):** the fifth instance is the strongest
argument yet for the mechanical form, because the gate in question was written *by the same
change that shipped the defect it was meant to catch*, survived two review rounds green, and
its docstring correctly described the failure mode it was not testing. A mutation receipt
would have caught it in one line: deleting the `--slug` append instruction leaves
`assert "--slug" in partial` passing, so `suite_rc_after_delete == 0`.
**Rationale:** four recurrences, and the failure mode is stable across all of them: the
assertion holds in the broken world because the fixture pair does not straddle the
dimension the test is named after. The current guard is ADR-010's instruction to "name the
wrong implementation the assertion rejects and verify it fails" recorded **in the commit
message** — unverifiable, unqueryable, and skipped without a trace. The 2026-07-27
instance had both fixture turns carrying cache-write tokens so the creation-gated branch
could not execute in either variant; a mutation receipt would have recorded
`suite_rc_after_delete = 0` for that test and the gate would have refused it. This is the
same "prose guard failed N times → promote to mechanical" shape as
`wrapup-close-marker-integrity-guard` and `dead-string-pin-guard`, and it is now the
highest-leverage one: the entry is cited as prior work by the plans that then reproduce it.

**Supporting evidence (2026-07-27, PLAN-token-economy-step-pruning Phase 2).** Not a new
proposal — the same mechanism, observed again with a twist that argues for it more sharply.
Phase 2 DID produce the ADR-010 receipt this proposal wants (7 mutants, 7 killed, 0
survivors, re-run after BOTH review rounds), and **four of the seven mutants turned out to
be held by exactly one test each** — precisely the fragile binding a machine-readable
`{test_node, code_deleted, suite_rc_after_delete}` row would make queryable instead of
leaving it as a sentence in a PLAN table. It also shows the proposal's ceiling: the receipt
was green while review round 2 still found 7 defects, because four of those lived in prose
(SPEC notes, PLAN frontmatter, an ADR's own enumeration) that no mutation check reads. So
the gate is worth building for what it covers, and must not be sold as covering more —
see `[fail:design] unverified-number-in-spec-justification`.

## Proposal: CI gate — every new CLI surface must be driven in its shipped form (2026-07-30)
**Triggered by:** [fail:test] shipped-entry-point-not-exercised (count: 3)
**Proposed mechanism:** structural test + CLAUDE.md checkpoint
**Rationale:** Three separate work units have now shipped a change that was correct in the
Python library and dead at the invocation the product runs — most recently two new entrypoints
(`codex_adapter stamp-ids`, `second_opinion_oracle`) that every rendered call site invoked as
`hm <module> …` while `hm._DISPATCHABLE` did not list them, so each exited 2. Unit tests called
`main([...])` directly and were green throughout. An automated guard would have caught all three:
extend `tests/structural/test_hm_entrypoint.py` from "every module the rendered surface calls is
dispatchable" to "every module in `command_registry.MODULES` that any rendered artifact calls is
BOTH dispatchable AND resolves through `hm` in a subprocess", and scan every rendered surface
(commands, `.claude/skills/*/SKILL.md`, agent bodies) rather than commands alone — the skills half
was added this round and immediately found a pre-existing miss (`refdocs_index`). The library/product
seam is the recurring shape; the gate should live at the seam, not in the library.

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
