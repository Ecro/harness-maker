---
generated_by: harness-maker
harness_maker_version: 0.7.4
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/uninstall.md.j2
provenance: official
content_hash: 9ed8454bd4537743f9f7a211fef63df3af1b0b967c7de1e6a61b288255b77110
---
# /hm:uninstall

> Remove harness-maker generated files from this project.

## Procedure

You (Claude) act as the orchestrator. Present consequences, confirm
intent, and dispatch the CLI.

### 1. Confirm intent

Use `AskUserQuestion`:

> **Remove harness-maker from this project?**
>
> This will delete all harness-maker–generated files (agents, commands,
> hooks, skills, etc.) from `.claude/`. Files you customized (containing
> `@hm:user:` markers) will be **skipped** with a warning.

Options:
- **Remove generated files** — keep `harness.yaml` for future reinstall
- **Remove everything** — also delete `harness.yaml`
- **Cancel**

If **Cancel**, stop.

### 2. Preview (dry-run)

```bash
!uv run --with /home/noel/harness-maker/.worktrees/execute-20260510T0331Z python -m harness_maker.cli remove "$(pwd)" --dry-run
```

Show the user the file list.

### 3. Dispatch

Based on option selected:

```bash
# Keep harness.yaml
!uv run --with /home/noel/harness-maker/.worktrees/execute-20260510T0331Z python -m harness_maker.cli remove "$(pwd)"

# Remove everything
!uv run --with /home/noel/harness-maker/.worktrees/execute-20260510T0331Z python -m harness_maker.cli remove "$(pwd)" --remove-yaml
```

### 4. Post-removal

Report:
- Files removed
- Files skipped (user blocks)
- Whether `harness.yaml` was kept or removed
- "To reinstall: `/harness-maker:make`"

<!-- @hm:user:extensions -->
<!-- Project-specific /hm:uninstall overrides. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
