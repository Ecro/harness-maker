---
type: plan
task_slug: hm-overhaul-p1-c
spec: specs/SPEC-hm-overhaul-p1.md
spec_hash: bd01dacb
scope: PR-C (AC-001, AC-002, AC-008; IRR-001; the Cursor rows of IRR-006)
version: 0.63.0
status: planning
surface_allowance:
  chars: 332
  round_trips:
    research: 3
  reason: "Research Phase 1 takes the Explore fan-out branch once the Cursor half of its condition is gone (+615 chars, +3 dispatches), net of 283 chars of Cursor text removed."
  delta_doc: BASELINE-DELTA-hm-overhaul-p1-c.md
---

# PLAN: overhaul phase 1, PR-C (Cursor target removal)

The SPEC holds the ACs. This PLAN holds the order of work, the calls the SPEC leaves to the
implementer, and the AC→test map. PR-S (AC-003…011) is out of scope.

## Phases

1. **RED.** Write the AC tests (map below) and run them against the unchanged tree.
2. **Render and code.** Remove `Target.CURSOR`, `templates/cursor/`, the Cursor-only paths in
   `render.py` / `synthesize.py` / `presets.py` / `readiness.py` / `git_disposition.py`, the Cursor
   branches of the help/make/configure templates, and `.cursor-plugin/plugin.json`. Keep `hook_host`,
   the `.cursor` sweep root and the `.cursor` backup.
3. **Brownfield.** `targets: cursor` (harness.yaml or `--targets`) is dropped with one
   `cursor target removed` warning per `make` run; `agent_models.<a>.cursor` warns once and is ignored;
   `.cursor/hooks.json` joins `_SWEEP_NEVER_DELETE` and gets a pristine-exact retire path; every kept
   `.cursor/` file prints the SPEC's KEPT text; an emptied `.cursor/` is removed.
4. **Suite.** Delete Cursor-only tests, update the rest, regenerate snapshots whose only change is a
   removed Cursor line.
5. **Docs and version.** 0.63.0 across four files; CLAUDE.md (version table, Targets, Cursor sections),
   README, CHANGELOG `### Removed`.
6. **Bind.** `spec_machine mark-tested` for AC-001/002/008; `approval-status` stays `approved`.

## ADRs

- **ADR-001: the db19f023 reference is read with `git archive`, not `git worktree add`.** AC-001,
  AC-002 and AC-008 need the db19f023 renderer at test time. `git archive db19f023 src` gives the same
  bytes as a checkout and writes nothing into `.git/` (no `worktrees/` entry to leak when a test dies,
  no lock contention between xdist workers). The SPEC's oracle (`git show`/`git worktree add`) names
  the source of truth, the db19f023 tree; this reads exactly that tree. Both sides run under the same
  interpreter with `PYTHONPATH=<side>/src`, so the dependency set is identical.
- **ADR-002: the targets drop happens at parse time, the warning once in `make`.** `_parse_targets`,
  `_ask_targets` and `--targets` drop `cursor` silently (an empty result becomes `[claude-code]`), and
  `make` prints the single warning from the raw inputs (the on-disk yaml and the flag), so a tree that
  has `cursor` in both still gets one line. Runtime readers of harness.yaml never see a `Target`; they
  read strings, so nothing outside `make` warns (IRR-006: "Nothing warns at stage run time").
- **ADR-003: `AgentModelSpec.cursor` stays as a parseable, inert field.** IRR-006 keeps every key
  loadable under `extra="forbid"`. The value no longer feeds the Claude model (the
  `_alias_by_cursor_id` fallback goes), and `make` warns once per agent that sets it.
- **ADR-004: `.cursor/hooks.json` pristine = manifest hash AND every entry harness-managed AND no
  top-level key beyond `version`/`hooks`.** The SPEC's two conditions, plus the top-level check: a
  merged file keeps a user's top-level key ("existing survives"), and that is user content the hash
  cannot vouch for. It only ever keeps more, never deletes more.
- **ADR-005: the KEPT text is used only for `.cursor/` paths the manifest knows.** A file the harness
  never rendered (a user's own `.cursor/rules/mine.mdc`) is not "you edited it"; it keeps the existing
  generic orphan-sweep line.
- **ADR-006: the `schema` parameter of the hooks merge is removed, not narrowed.** With the flat arm
  gone, `Literal["nested"]` would be a parameter with one value. Every caller passed `"nested"`.
- **ADR-007: Cursor prose in stage templates is left to PR-S.** PR-C removes Cursor branches (anything
  keyed on a cursor target or a Cursor-only variable) and the Cursor option lists. The
  "`AskQuestion` (Cursor) or `AskUserQuestion`" prose in stage bodies stays: PR-S rewrites or deletes
  every one of those files, and changing them twice would churn the strictness and snapshot references
  twice. `help`, `make`, `configure` and the plugin's `commands/make.md` are edited here (named by AC-001).
- **ADR-008: AC-008 is a preservation property and is green before the change.** PR-C does not touch a
  hook module, so the property holds at the base; its RED is recorded as `green_before` (the SPEC's
  `--green-ok` waiver), and PR-S re-checks it when it stubs three entry points.

## AC→test map

| AC | Test id | Oracle |
|---|---|---|
| AC-001 | `tests/unit/test_overhaul_p1_cursor_removal.py::test_ac001_render_equals_reference_without_cursor` | differential vs db19f023 render of T minus cursor |
| AC-001 | `tests/unit/test_overhaul_p1_cursor_removal.py::test_ac001_cursor_only_paths_absent` | removed-symbol list from the AC-001 note; kept list |
| AC-001 | `tests/unit/test_version_sync.py::test_four_manifests_share_one_version` | four version files, no fifth manifest |
| AC-002 | `tests/unit/test_overhaul_p1_cursor_removal.py::test_ac002_cursor_brownfield_table` | the AC-002 golden table, 0.62 trees from db19f023 |
| AC-008 | `tests/integration/test_overhaul_p1_hook_commands.py::test_ac008_every_shipped_hook_command_is_safe` | differential exits vs db19f023 modules |

## RED evidence

Run on 2026-10-16 against the unchanged tree (base 0da08d03), before any `src/` edit.

```
FAILED tests/unit/test_version_sync.py::test_four_manifests_share_one_version
  AssertionError: ['.claude-plugin/plugin.json', '.codex-plugin/plugin.json', '.cursor-plugin/plugin.json']
FAILED tests/unit/test_overhaul_p1_cursor_removal.py::test_ac001_cursor_only_paths_absent
  AssertionError: Cursor-only code still present: ['.cursor-plugin/plugin.json',
  '.cursor/ in _SIBLING_TREE_PREFIXES', '.cursor/ in resolve_output_path', 'Target.CURSOR',
  '_alias_by_cursor_id', 'cursor branch in commands/hm/help.en.md.j2', 'cursor branch in
  commands/hm/help.ko.md.j2', 'cursor branch in commands/hm/make.md.j2', 'cursor branch in plugin
  commands/make.md', 'cursor_model context', 'flat schema in render._entry_identity', 'flat schema in
  render._merge_hooks_json', 'flat schema in render._render_hooks_json_merged', 'flat schema in
  render._strip_shipped_commands', 'presets.CURSOR_MODEL_IDS', 'readiness Cursor advisory',
  'render._is_cursor_command', 'render._is_cursor_mcp_json', 'render._is_cursor_mdc',
  'synthesize._cursor_target_files', 'templates/cursor/']
FAILED tests/unit/test_overhaul_p1_cursor_removal.py::test_ac001_render_equals_reference_without_cursor
  targets=claude-code,cursor preset=Side worktree=False: file sets differ: only at db19f023 [],
  only at HEAD ['.cursor/hooks.json', '.cursor/mcp.json', '.cursor/rules/harness.mdc']
  ... .claude/commands/hm/help.md -54,1 +54,1: ['| targets | `claude-code, cursor` |']
  ... .claude/commands/hm/research.md -136,11 +136,1: ['Run these in parallel where ...']
  ... .claude/harness.yaml -11,1 +11,1: ['targets: [claude-code, cursor]']
FAILED tests/unit/test_overhaul_p1_cursor_removal.py::test_ac002_cursor_brownfield_table
  pristine: 'cursor target removed' x0; .cursor/rules/harness.mdc not deleted; .cursor/mcp.json not
  deleted; .cursor/hooks.json not deleted; .cursor/ not removed; targets ['claude-code', 'cursor',
  'codex'] != ['claude-code', 'codex']
  mdc-edited / hooks-merged-user-entry / mcp-edited: KEPT warning x0, the other files not deleted
  cursor-only: targets ['cursor'] != ['claude-code']
  agent-models-cursor: no warning naming agent_models.code-reviewer.cursor
  fresh-targets-flag: .cursor/* rendered, targets ['claude-code', 'cursor'] != ['claude-code']
  (fresh-no-cursor passes: the control row)
PASSED tests/integration/test_overhaul_p1_hook_commands.py::test_ac008_every_shipped_hook_command_is_safe
  green_before, as ADR-008 expects: PR-C changes no hook module (waived as `--green-ok AC-008`)
```

The first AC-008 run errored in the fixture (`autopilot.write` needs `AtomicStage` members, not
strings); that was a test bug, fixed before the run above, not a RED.
