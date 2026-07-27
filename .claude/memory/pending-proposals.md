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
**Triggered by:** [fail:design] worktree-finalize-pulls-orphan-wip-into-main (count: 1; cost-per-incident is high — 139-file scope explosion + ~30 min cleanup)
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

## Proposal: ruff-format-in-execute-not-just-wrapup (2026-07-09)
**Triggered by:** [fail:lint] wrapup-final-verify-skips-ruff-format-check (count: 3)
**Proposed mechanism:** execute + review stage procedure note (run `ruff format` after edits, not only `ruff check`) OR a pre-commit format-fix hook. **Updated 2026-07-25 — this mechanism has a gap.** It assumes the failure mode is "format was never run". A second mode exists: format IS run and its exit code is discarded, because the command was piped (`ruff format --check … | tail -1` makes `$?` the tail's). Neither a procedure note nor a format-fix hook catches that. Add: gate commands must never be piped — redirect and record one `rc` per check (`cmd > f 2>&1; echo "rc=$?" >> f`). See `[fail:lint] gate-exit-code-lost-through-pipe`.
**Rationale:** Observed again in PLAN-second-opinion-multi-model wrapup: `ruff check` passed clean at execute AND review, but `ruff format --check` at wrapup found 7 unformatted files (long-line reflows the auto-fixer left un-normalized). Because `ruff check` ≠ `ruff format`, code that passes every lint gate in execute/review can still fail the wrapup format gate, forcing a late reformat + re-verify. A note in execute.md.j2 / review.md.j2 Phase D to run `ruff format` (not just `ruff check`) after edits — or a PostToolUse format-on-write hook scoped to `*.py` — would keep the tree format-clean continuously and stop wrapup from being the first place format is checked.

## Proposal: snapshot-regen-count-11-escalate-to-mechanical (2026-07-17)
**Triggered by:** [fail:test] snapshot-regen-inside-worktree (count: 11)
**Proposed mechanism:** the two existing proposals for this entry were written at count:3 and count:5; it is now at **count:11** and neither prevention shipped. Promote to a mechanical guard: make `tests/snapshot/regenerate.py` refuse to run when `git rev-parse --show-toplevel` resolves inside a `.worktrees/` path (hard exit + one-line remedy), rather than relying on a prose reminder.
**Rationale:** 11 recurrences is the highest count in the tier and the escalation last-mile visibly stalled — proposals exist but stop at count:5, so nobody re-read them as the count tripled. This is the canonical "prose guard failed N times → promote to mechanical" case, and the count itself is the evidence. Recording the update here so the staleness is visible rather than frozen at the count where the last proposal happened to be written.

## Proposal: dead-string-pin-guard (2026-07-26)
**Triggered by:** [fail:test] test-pins-retired-implementation-name (count: 3)
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
**Triggered by:** [fail:test] assertion-invariant-over-named-dimension (count: 4)
**Proposed mechanism:** a mechanical receipt, because prose has now failed four times —
including once inside `PLAN-token-economy-step-pruning`, whose ADR-010 is *itself* the
prose rule "mutation-check every gate". Proposal: extend the `/hm:execute` Phase D exit
contract so that every test **added or modified** in the diff must be named in a
machine-readable mutation receipt (`.claude/observability/mutation-receipts-<slug>.jsonl`,
one row per test: `{test_node, code_deleted, suite_rc_after_delete}`), and have `/hm:review`
Step 3 fail-closed when a diff adds a test node with no corresponding row. The check that
makes it non-vacuous is `suite_rc_after_delete != 0` — a row claiming a deletion that
left the suite green is exactly the invariant assertion this entry describes, and it
becomes visible as data instead of as a claim in a commit message.
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
