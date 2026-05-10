# Pending Proposals

> Improvement proposals triggered by failure entries with count ≥ 3.
> Review and decide whether to ingest into the harness.

## Proposal: snapshot-regen-order-guard (2026-05-10)
**Triggered by:** [fail:test] snapshot-regen-inside-worktree (count: 3)
**Proposed mechanism:** rule update in CLAUDE.md + execute stage procedure note
**Rationale:** The regen-before-finalize failure has happened 3 times: once in the worktree itself, once after squash-merge with stale paths, and once in deep-interview-llm-delegation where regen ran before worktree finalize. The correct order (finalize → regen → full pytest) is buried in the execute stage procedure. Adding an explicit ordered checklist note to execute.md.j2 (Phase 6/7 sequence for snapshot tests) would prevent this class of error automatically in every future exec-rev loop. Consider also adding a pre-regen assert that checks `git diff --name-only HEAD | grep 'templates/.*\.j2'` to confirm the template changes are present in main before regen runs.
