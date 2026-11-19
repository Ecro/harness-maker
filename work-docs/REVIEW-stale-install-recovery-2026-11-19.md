---
type: review
task_slug: stale-install-recovery
created: 2026-11-19
spec: "[[SPEC-stale-install-recovery]]"
plan: "[[PLAN-stale-install-recovery]]"
summary: Two code-reviewer rounds (11 + 2 findings, none critical), all accepted and fixed; codex second opinion skipped (CLI not installed).
---

# REVIEW — stale-install-recovery

- Reviewer: `code-reviewer` (round 1, round 2).
- Second opinion: `codex` → `skipped` ("CLI not installed: codex"); warn-and-proceed. No K=2
  consensus was possible, so every finding below is single-voter, verified by re-reading the cited
  code and covered by a new test where it is behavioural.
- RED (Phase A): `hm check --red` exit 0 — every AC test failed for a real reason before code.
- Live smoke: edgelog's real `settings.json`/`.codex/hooks.json` with refs rewritten to the pruned
  0.65.2 → heal repaired 6 + 4 hook commands, the repaired SessionStart hook exited 0.
- Known limit (SPEC non-goal, not a finding): permission `allow` rules and slash-command bodies
  that embed the old cache path are not healed; they stay consistent with each other and a
  re-render fixes both.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1-F1 | major | src/harness_maker/stale_ref_heal.py:`_dead_token` | Any `--with` naming harness-maker that does not expand to a dir (unexpanded var, URL, bare name) was treated as dead and repointed — a user's own hook could be rewritten. Resolution: fixed: only a fully expanded plugin-cache-shaped ref is healed; `test_user_chosen_refs_are_never_repointed` | accepted | code-reviewer |
| R1-F2 | major | src/harness_maker/release_autotag.py:`main` | `changed_in_push` compared only the manifest; a bump split across two pushes was never tagged. Resolution: fixed: all four files compared via `_versions_at(before)`; `test_partial_bump_then_completion_tags_once` | accepted | code-reviewer |
| R1-F3 | minor | src/harness_maker/release_autotag.py:`decide` | Version mismatch returned `error` on unrelated pushes. Resolution: fixed: `skip` first when the push did not change versions | accepted | code-reviewer |
| R1-F4 | minor | src/harness_maker/codex_setup.py:`run` | Fallback also fired when the engine crashed without a receipt, running the engine twice. Resolution: fixed: no fallback when stderr carries a Python traceback; `test_engine_crash_without_receipt_is_not_retried`. The engine prints a receipt on its own handled errors (scripts/codex_engine.py), so only unhandled crashes needed this | accepted | code-reviewer + scripts/codex_engine.py |
| R1-F5 | minor | README.md (Codex) | "offline" fallback overstated — a cold uv cache cannot build the plugin source. Resolution: fixed: "offline with a warm uv cache" | accepted | code-reviewer |
| R1-F6 | minor | src/harness_maker/stale_ref_heal.py:`_plugin_cache_ref` | A symlinked `~/.claude` resolved out of home and silently disabled the heal. Resolution: fixed: unresolved path tried first; `test_symlinked_claude_dir_still_heals` | accepted | code-reviewer |
| R1-F7 | minor | src/harness_maker/stale_ref_heal.py:`_expand` | `$HOMEDIR` matched the `$HOME` prefix. Resolution: fixed: separator/end lookahead; covered by the F1 test | accepted | code-reviewer |
| R1-F8 | minor | src/harness_maker/stale_ref_heal.py:`_heal_file` | `atomic_write` changed a committed file's mode to 0600 and replaced a symlink with a file. Resolution: fixed: write to the resolved target, restore mode; `test_heal_keeps_file_mode_and_symlink` | accepted | code-reviewer |
| R1-F9 | minor | .github/workflows/release.yml:10,105 | `dry_run` description and a comment claimed a dispatch never publishes — false once autotag dispatches on the tag ref. Resolution: fixed: text only, jobs unchanged (anticipated by SPEC Refinement Decisions; PLAN ADR-006 updated) | accepted | code-reviewer |
| R1-F10 | minor | tests/unit/test_release_autotag.py | `main()` and git history paths untested. Resolution: fixed: git-fixture test (partial bump, completion, all-zero `before`, existing tag) | accepted | code-reviewer |
| R1-F11 | minor | tests/unit/test_stale_ref_heal.py:AC-004 | Count assertion matched any digit. Resolution: fixed: asserts the full `(N hook command(s))` text | accepted | code-reviewer |
| R2-N1 | minor | src/harness_maker/stale_ref_heal.py:`_heal_file` | A dead ref escaped on disk in an unspliceable form was skipped silently. Resolution: fixed: reported as not repaired; `test_unspliceable_escape_and_unwritable_file_are_reported` | accepted | code-reviewer |
| R2-N2 | minor | src/harness_maker/stale_ref_heal.py:`heal_project` | An `OSError` on one file dropped the other file's repair and the report. Resolution: fixed: per-file `OSError` handling, reported; same test | accepted | code-reviewer |

## Gate fixes outside review

- `tests/unit/test_overhaul_p1_surface.py::test_ac004_plugin_hooks_unchanged` pinned
  `hooks/hooks.json`; updated to allow the `--plugin-root ${CLAUDE_PLUGIN_ROOT}` argument this SPEC
  adds (ADR-001), with the reason in the test comment.
- `tests/structural/test_dead_modules.py`: `release_autotag` added to `KEPT` — like
  `release_identity`, it is reached only from a CI workflow.
