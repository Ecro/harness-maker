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
