---
generated_by: harness-maker
harness_maker_version: 0.5.6
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/worktree-isolator/SKILL.md.j2
provenance: official
name: worktree-isolator
description: Isolate /hm:execute changes inside a disposable git worktree. Read harness.yaml.worktree.scope
  to decide whether to engage; on success merge back and clean up; on failure preserve
  the worktree for inspection.
content_hash: 5301cc02a594968ca7861982eddfd2448d7a9eff084f390f5e2b4b2a7ae693c5
---

# worktree-isolator

Disposable worktree isolation for `/hm:execute` (and any stage listed in
`harness.yaml.worktree.scope`). Wraps `harness_maker.worktree` lifecycle
primitives so all file mutations land in `.worktrees/<workflow>-<ts>/` rather
than the live working tree.

## Triggers

- `/hm:execute` invocation
- Any `/hm:<stage>` whose name appears in `harness.yaml.worktree.scope`
- Autoloop iteration boundaries (each iter gets its own worktree)

## Behavior

Four-step flow, executed deterministically by the orchestrator:

1. **/hm:execute invoked → read `harness.yaml.worktree.scope`.**
   Parse the `worktree.scope` list (e.g. `[execute]` for Side, `[execute, plan]`
   for Production). If the current stage name is absent, skip isolation and run
   the stage in-place — this preserves the lightweight default for stages where
   isolation costs more than it saves.

2. **If "execute" (or current stage) in scope → call `worktree.create()`.**
   ```python
   from harness_maker import worktree
   wt = worktree.create(workflow="execute", base_dir=Path.cwd())
   # wt = <repo>/.worktrees/execute-<UTC-iso8601-minute>/
   ```
   Branch name matches the directory basename. The worktree starts from the
   current HEAD of the base repo.

3. **Run workflow inside the worktree.**
   Switch the agent's working directory to `wt`. All Write/Edit/Bash tool calls
   issued by the executor agent land inside the worktree branch — the base
   repo's working copy is untouched until step 4. Reviewer agents may still
   read the base repo (they have read-only permissions per M12 privilege
   separation).

4. **On success → `worktree.merge()` then `worktree.cleanup(on_success=True)`.
   On failure → `worktree.cleanup(on_success=False)` with backup preserved.**
   ```python
   try:
       run_workflow(stage="execute", cwd=wt)
   except Exception:
       worktree.cleanup(wt, on_success=False)   # non-force: keeps dirty WT for inspection
       raise
   else:
       worktree.merge(wt, strategy="squash")
       worktree.cleanup(wt, on_success=True)    # force: drop the now-merged branch WT
   ```
   Failure path uses non-force `git worktree remove`, so a dirty worktree
   stays on disk under `.worktrees/` for manual triage. The autoloop blocker
   recovery path (`worktree.cleanup_all(force=True)`) sweeps these up later.

## Output

- Side effect only: clean working tree on success, preserved worktree on
  failure. No structured findings — observability flows through the standard
  telemetry hook.

## Configuration knobs (harness.yaml)

```yaml
worktree:
  scope: [execute]            # which /hm:<stage> commands trigger isolation
  branch_prefix: hm-          # reserved for Phase 9 (currently informational)
```

<!-- @hm:user:extensions -->
<!-- Project-specific worktree rules (extra cleanup commands, branch naming, etc.). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
