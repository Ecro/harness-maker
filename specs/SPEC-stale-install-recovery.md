---
type: spec
task_slug: stale-install-recovery
status: approved
created: 2026-11-19
tags: [hooks, plugin-update, codex-bootstrap, release, readme]
test_framework: pytest
interview_rounds: 2
summary: A plugin update prunes the versioned cache dir every rendered hook points at; heal those refs at SessionStart, let the Codex bootstrap fall back to the plugin source, auto-tag version bumps on main, and document the update flow.
---

# SPEC — Stale-install recovery after a plugin update

## Intent

Every hook harness-maker renders into a project (`.claude/settings.json`, `.codex/hooks.json`) runs
`uv run --no-project --with "$HOME/.claude/plugins/cache/harness-maker/harness-maker/<X.Y.Z>" …`.
A plugin update prunes the old `<X.Y.Z>` directory, so from that moment until the user re-renders,
**every** project hook fails in `uv` before Python starts — including the `PreToolUse` gates
(`permission_gate`, `worktree_gate`). Observed 2026-11-19 on `~/SIDE/edgelog`: rendered at 0.65.2,
cache pruned to 0.65.6, SessionStart failed with `error: Failed to parse`.

`work-docs/PLAN-render-degrades-live-harness.md` ADR-002 chose a render-time-only existence check and
wrote down the falsifier: *"if the incident recurs on a harness rendered after this fix, that is the
evidence that the render-time check was the wrong half."* edgelog is that recurrence. ADR-002 rejected
a SessionStart probe because "a broken ref breaks the SessionStart hook that would carry the warning";
that premise does not hold for the **plugin-bundled** hook (`hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}`),
which always runs from the live install — it delivered its drift message on edgelog while the project
hooks failed. This SPEC supersedes ADR-002 on that point.

The same session exposed three neighbours: the Codex `hm-make` bootstrap resolves the engine only from
PyPI and its `make` action drops `--update`; release 0.65.6 merged (#69) without a `v0.65.6` tag, so
the plugin (served from GitHub `main`) is 0.65.6 while PyPI has no 0.65.6; and the README has no
update procedure while its Reconcile section tells users to `rm .claude/harness.yaml`.

## Outcomes

1. After a plugin update, the first Claude Code session in a project repairs the project's dead
   harness-maker hook refs without a re-render, and tells the user what it did.
2. A Codex `hm-make` run succeeds when the plugin's release is not (yet) on PyPI, and `--update` works.
3. A version bump merged to `main` is tagged and released without a human pushing the tag.
4. The README tells a user what to do after a plugin update and what breaks if they skip it.

## In-Scope Scenarios

- **S1 (normal — heal).** Given a project whose `.claude/settings.json` holds harness-maker hooks whose
  `--with` target directory no longer exists, and the plugin-bundled SessionStart hook runs from a live
  install, when the session starts, then exactly those `--with` tokens are replaced with the live
  install ref, every other byte of meaning in the file is unchanged, and `additionalContext` names the
  repair and says to restart the session.
- **S2 (edge — nothing to do / not ours).** Given a project whose harness-maker refs are all live, or
  whose dead `--with` belongs to a non-harness-maker command, or which has no `.claude/harness.yaml`,
  when the session starts, then no file is written.
- **S3 (failure — cannot heal safely).** Given a malformed `settings.json`, or a running install whose
  own ref is not a resolvable directory, when the session starts, then no file is written and the hook
  still exits 0 with its normal drift output.
- **S4 (Codex bootstrap).** Given a plugin whose `harness-maker==X.Y.Z` is not resolvable from the
  index, when `codex_setup.py make <project> --update` runs, then the engine runs from the plugin root
  with `--update`, and the receipt records the source used.

## Non-Goals

- Healing **inside a Codex session**. `.codex-plugin/plugin.json` declares no hooks, so Codex has no
  always-live hook to carry a repair. `.codex/hooks.json` is healed when a Claude Code session starts
  in the same project; Codex-only users recover via `hm-update` (S4).
- Re-rendering at SessionStart. The heal splices refs only; templates, the stamped
  `harness_maker_version` and the drift notice are unchanged — the user still runs `/hm:make --update`.
- Healing other rendered surfaces (slash-command `!` lines, skill bodies). They run on demand, fail
  visibly, and are fixed by the re-render the drift notice asks for.
- Changing `release.yml`'s jobs, publish chain or Trusted Publisher subject.
- Healing a dead PyPI-pinned ref (`--with harness-maker==X`); only directory refs are judged dead.
- Healing from a Codex-launched process: the heal runs only when `CLAUDE_PLUGIN_ROOT` is set
  (the plugin-bundled Claude hook); the rendered Codex SessionStart copy of `sessionstart_drift`
  skips it.
- Restructuring or shortening the README.

## Constraints

| Constraint | Source |
|---|---|
| pytest; ruff; mypy --strict | CLAUDE.md |
| Python only — workflow logic in a `harness_maker` module, not shell scripts | CLAUDE.md |
| The SessionStart hook always exits 0 and never starves the drift notice | `sessionstart_drift.run` contract |
| Writes are atomic (no plain `open(path, "w")`) | implementation-patterns.md |
| Ownership = `python -m harness_maker.<module>` suffix, never path enumeration | wiki `hooks-merge-identity-keys-on-module-namespace` |
| The ref splice reuses `render._splice_install_ref` (ADR-014): only the `--with` token changes | PLAN-render-degrades-live-harness ADR-014 |
| Liveness reuses `hook_host._with_target_is_live` semantics (`$HOME`/`~` expanded) | hook_host.py |
| New ref = `synthesize._compute_install_ref()` of the running process; heal only when it is a resolvable directory | wiki `render-must-not-degrade-live-harness` |
| A tag created with `GITHUB_TOKEN` triggers no workflow; the auto-tag job dispatches `release.yml` with `ref` = the tag | GitHub Actions semantics |

## Irreversible Decisions

| ID | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | A push to `main` that changes the four version files tags `vX.Y.Z` and publishes to PyPI + GitHub Release with no human step | security/permission boundary | DRI accepted 2026-11-19: a version bump is always a deliberate release commit, `quality-gate` still runs first, and a missed tag (0.65.6) cost more than the removed step. Publishes are immutable; deleting `autotag.yml` stops future ones only. |

## Acceptance Criteria

### AC-001: Dead harness-maker refs in settings.json are spliced to the live ref
Given a `settings.json` whose harness-maker hook commands name a missing `--with` directory, the heal
replaces the `--with` token that precedes `python -m harness_maker.` with `--with "<ref>"`
(double-quoted, JSON-escaped) and the file is **byte-identical outside the spliced spans**. Fixtures
include a home path with a space, a backslash path and a single-quoted original; each healed command
parses with `shlex` and its expanded target exists.

### AC-002: No write when there is nothing safe to heal
No file is written (content and mtime unchanged) when: all harness-maker refs are live; the only dead
`--with` is in a non-harness-maker command; `.claude/harness.yaml` is absent; the JSON is malformed;
the running install ref is not a plugin-cache directory (`~/.claude/plugins/cache/*/harness-maker/<ver>`
— a source checkout or `--plugin-dir` install is refused); `CLAUDE_PLUGIN_ROOT` is unset; or the file
changed between read and write (compare-and-swap). A command whose module the running install's
`command_registry` no longer lists is left as is and counted as unhealable.

### AC-003: `.codex/hooks.json` is healed by the same rule
The same splice applies to `.codex/hooks.json` when present, with AC-001/AC-002 semantics.

### AC-004: The SessionStart output reports the heal and the hook stays safe
When at least one ref was healed, `additionalContext` names each healed file and count, any
unhealable commands, that the file now differs from git, and — per AC-011's observation — whether a
session restart is needed; the drift notice is still emitted when versions differ. `run()` returns
0 and writes valid JSON on every input, including when the heal raises.

### AC-005: Codex bootstrap falls back to the plugin source
When the pinned engine run yields **no engine receipt** (uv could not build the environment —
unresolvable pin or offline), `setup()` retries once with `--with <plugin_root>` (only if
`<plugin_root>/pyproject.toml` exists) and the receipt carries `engine_source: "pypi" | "plugin_root"`.
A run that produced a receipt with an error is a real engine failure and is not retried. The fixture
uses the uv output captured live on 2026-11-19; a failing fallback ends `state != complete`.

### AC-006: The `make` action honours `--update`
`codex_setup.py make <project> --update` passes `--update` to the engine; without the flag it does not;
`skills/hm-make/SKILL.md` documents the flag.

### AC-007: Auto-tag decides from the four version files
A `harness_maker.release_autotag` decision function returns `tag vX.Y.Z` when the four version files
agree on X.Y.Z, the pushed range changed them, and the tag does not exist; `skip` when the tag exists
or the version did not change in the push; `error` when the files disagree. A tag that exists with no
release run is recovered by hand with `gh workflow run release.yml --ref vX.Y.Z` (documented).

### AC-008: The auto-tag workflow is wired to dispatch the release
`.github/workflows/autotag.yml` runs on push to `main`, fetches tags, calls `release_autotag` with the
push's `before`/`after` SHAs, creates the annotated tag, and dispatches `release.yml` with `--ref` the
tag; its permissions mapping is exactly `{contents: write, actions: write}` and it has a
`concurrency` group. Checked structurally by parsing the YAML.

### AC-009: CLAUDE.md release procedure matches the new flow
Within the release section: merging the version bump to `main` tags and releases automatically, keeps
manual `git tag` + push as a valid path (the job skips an existing tag), and keeps the
"no manual `gh release create`" rule.

### AC-010: README documents updating and drops stale advice
README has an `## Updating` section (plugin update → `/hm:make --update`, what breaks if skipped, what
the self-heal covers and does not); contains no `rm .claude/harness.yaml` upgrade advice, no
"(when published)" and no "Listings are **pending**"; the Codex section describes the plugin-source
fallback instead of "The engine must be published at the plugin's release version".

### AC-011: Same-session effect of the heal is measured and documented
A live experiment records whether a `settings.json` hook edit made at SessionStart takes effect in the
same Claude Code session, in `work-docs/RESEARCH-stale-install-recovery.md`; the README Updating
section and the AC-004 message state that observed behaviour and the README cites the record.

## Verification

| Scenario | AC | Mode | Test |
|---|---|---|---|
| S1 | AC-001, AC-003, AC-004 | unit | `tests/unit/test_stale_ref_heal.py` |
| S2, S3 | AC-002, AC-004 | unit | `tests/unit/test_stale_ref_heal.py` |
| S4 | AC-005, AC-006 | unit | `tests/unit/test_codex_setup_fallback.py` |
| — | AC-007 | unit | `tests/unit/test_release_autotag.py` |
| — | AC-008 | unit (structural) | `tests/structural/test_autotag_workflow.py` |
| — | AC-009, AC-010 | unit (doc grep) | `tests/structural/test_update_docs.py` |
| S1 | AC-011 | manual + doc grep | live Claude Code session recorded in `work-docs/RESEARCH-stale-install-recovery.md`; `tests/structural/test_update_docs.py` checks the record exists and the README cites it |

## Open Questions

none

## Refinement Decisions

- **Intent link:** `[intent] none` — no active/proposed intent plainly covers install recovery.
- **Release trigger mechanism (DRI locked "auto-tag on main"; mechanism mine):** a tag pushed with
  `GITHUB_TOKEN` does not start `release.yml`, so the job creates the tag and runs
  `gh workflow run release.yml --ref vX.Y.Z`. Every `release.yml` publish job gates on
  `startsWith(github.ref, 'refs/tags/v')`, which a dispatch on a tag ref satisfies, so `release.yml`
  stays unchanged except its `dry_run` input description. Rejected: a PAT secret (secret to rotate);
  folding the tag step into `release.yml` (rewrites every job's gating). Undo: delete one file.
- **Heal scope = SessionStart, Claude only, refs only.** Smallest change that removes the dead-gate
  window; re-render stays the user's call. Undo: remove the call in `run()`.
- **Never heal to a non-directory ref.** If the running install itself resolves to the PyPI-name
  fallback, healing would write a ref of a different kind; skip and leave the drift notice to drive
  a re-render.
- **Codex fallback keyed on resolution failure only.** A failing engine run with a resolvable pin is a
  real error and must surface, not be masked by a second attempt.
- **spec-validator round (MAJOR_REVISION, 13 critiques) — defaults taken:** tag only when the push
  changed the version (a missed tag must never attach an old version to new code); structural YAML
  test for the workflow; heal only to plugin-cache refs and only registry-known modules (a dev
  checkout must not become every project's gate; a retired module must not be reported "repaired");
  double-quoted token + byte-identical outside spans + CAS (committed file, concurrent writers);
  `CLAUDE_PLUGIN_ROOT` required (Codex copy skips); Codex fallback keyed on missing receipt, not
  stderr text (offline counts); AC-004 restart wording follows AC-011, whose record lives in a
  work-doc so the stamped SPEC is not edited. Undo cost for each: one phase.
- **0.65.6 gap (DRI, 2026-11-19):** `v0.65.6` tagged by hand on `02f3d71f` and pushed before this
  work lands, so the autotag job never sees an untagged current version.
- **Oracles:** AC-001..004 use golden fixtures built by hand from the edgelog failure shape (paths
  that do/don't exist under a tmp `$HOME`), not from the code's output. AC-005/006 use a fake runner
  recording argv. AC-007 uses a golden table. AC-008..010 assert against the files' text and the
  locked decisions above. AC-011 is an observation of the host, independent of our code.
