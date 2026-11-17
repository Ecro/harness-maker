---
type: review
task_slug: opus55-stale-cuts
status: APPROVED
created: 2026-11-17
reviewers_invoked: [code-reviewer]
review_base: 735db8fdf6d588e8214b6b21363b6ab1120d85c4
---

# REVIEW — opus55-stale-cuts

Diff under review: `735db8fd` (main, 0.65.5) to the task worktree, uncommitted. One independent
reviewer, given the SPEC, the PLAN, the reviewer role file and the diff; it probed real
0.65.5-to-HEAD re-renders rather than reading only.

## Summary

Round 1: no P0, no P1, three P2, four P3. Six accepted and fixed, one rejected. Round 2 (the
same reviewer, on the fixes only): no P0, no P1, one P2, three P3, all accepted and fixed. The
four code fixes of round 1 were confirmed by probe. No third round: round 2's fixes are a test,
a log call, a comment and a template comment.

What the reviewer was told beside the diff: tests that pinned the old render were edited to
match, the SPEC was corrected several times after approval (each time re-approved by the agent
under the DRI's 15:31Z "do not ask" instruction), and ACs of older SPECs were retired.

## Findings

| id | sev | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F-001 | P2 | `src/harness_maker/reconcile.py` (sweep) | An edited Codex copy of the retired skill was kept while its pristine `agents/openai.yaml` was deleted, so the kept copy lost `allow_implicit_invocation: false` and could trigger itself in Codex. | accepted | - |
| F-002 | P2 | `src/harness_maker/render.py` (`_merge_hooks_json`) | A pristine 0.65.5 Codex project kept `"Stop": []` in `.codex/hooks.json` after the re-render; no test saw it because the fixture always added a user hook. | accepted | - |
| F-003 | P2 | `specs/SPEC-hm-overhaul-p1.machine.yaml` AC-009; `tests/unit/test_overhaul_p1_kept.py` | A live AC of an older SPEC was contradicted: its hot-tier test had been rewritten to assert the opposite and stayed bound, against PLAN ADR-007. | accepted | - |
| F-004 | P3 | `src/harness_maker/hooks/flush_session.py` | The stub exited 1 with stdin closed (`sys.stdin` is `None`). | accepted | - |
| F-005 | P3 | `src/harness_maker/render.py` (`_HARNESS_RETIRED_HOOK_INVOCATIONS`) | A single command string that chains a user step before ours (`my.sh && uv run … flush_session`) normalises to the retired identity and the whole entry is dropped. | rejected | PLAN ADR-001: the existing mechanism, unchanged for the six entries retired before; the `.backup-<ts>/` copy is the recovery path. Changing the matcher is its own task. |
| F-006 | P3 | docstrings and messages in `memory_md.py`, `_boundary_helpers.py`, four test files | Text still presented `flush_session` or the skill as live. | accepted | - |
| F-007 | P3 | `CHANGELOG.md` | "4 fewer files" holds only with the `codex` target; `claude-code` alone loses 2. | accepted | - |
| G-001 | P2 | `tests/render/test_opus55_stale_cuts.py` (`test_ac_006_the_stub_survives_a_closed_stdin`) | The new test closed fd 0 after interpreter start, where `sys.stdin` still exists, so it passed on the pre-fix stub and did not guard F-004. | accepted | - |
| G-002 | P3 | `src/harness_maker/reconcile.py` (sweep) | The `guards-kept-skill` keep was counted in "N orphan(s) kept" but not written to the orphan log. | accepted | - |
| G-003 | P3 | `src/harness_maker/render.py` (`_merge_hooks_json`) | The comment said the emptied event held only retired hooks; the branch is also reached when every entry was dropped as malformed (unchanged code, where the result used to be `[]`). | accepted | - |
| G-004 | P3 | `src/harness_maker/templates/settings/Production.json.j2:9` | The ADR-006 staging comment still listed `flush_session` with no retirement note. | accepted | - |

## Fixes

- F-001: `reconcile._guards_a_kept_skill`; the sweep keeps `agents/openai.yaml` while the
  `SKILL.md` beside it is kept. Test `test_ac_005_an_edited_codex_copy_keeps_its_invocation_policy`.
- F-002: the merge drops an event whose every entry was a retired harness hook; an empty list
  the user wrote stays. Tests `test_ac_005_a_pristine_rerender_leaves_no_empty_event`,
  `test_an_event_emptied_by_retirement_is_not_left_behind`,
  `test_an_empty_event_the_user_wrote_stays`.
- F-003: the rewritten test and the inverted `_ROWS` row are deleted, the test id is unbound
  from AC-009, and the SPEC's Refinement Decisions state the amendment (PLAN ADR-010).
- F-004: `contextlib.suppress(Exception)`; test `test_ac_006_the_stub_survives_a_closed_stdin`.
- G-001: the test closes fd 0 before exec (`preexec_fn`) and first proves `sys.stdin` is `None`
  in that child. Run against the pre-fix `suppress(OSError, ValueError)`: FAILED; against the
  fix: passed.
- G-002: the keep is written to the orphan log. G-003, G-004: comments reworded.
- Pre-existing and left alone (G-003's probe): the merge drops a hook entry with no string
  `command`, such as a `type: prompt` hook. Its own task.
- RED evidence for F-001, F-002 and F-004 is the reviewer's probe output on the pre-fix tree
  (the deleted yaml, `'Stop': 0`, the traceback with rc=1); the tests were written with the fix,
  and round 2 confirmed the F-001 and F-002 tests would be red on the pre-fix code.

## Checked clean by the reviewer

No reader of the removed surface is left in `src/`, the templates, `docs/`, the READMEs or
`scripts/`. A user's hook survives in its own group, inside our group and in Codex `Stop`.
`cursor_retire` and the legacy `hooks.json.j2` still match pristine legacy files. A
`harness.yaml` that lists the retired skill gets one warning from `make`, `--add` and `--remove`
work, `--add skill:worktree-isolator` fails with a clear message. The 0.65.5 path fixture
equals a real 0.65.5 render. The `test_hook_host` control is sound. Nothing under
`### Do not change` changed; no version bump.

## Not verified

- Whether the real Codex CLI re-prompts for hook trust after `.codex/hooks.json` changes.
- The interactive interview path (only `--autoloop` was run).
