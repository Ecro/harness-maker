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
