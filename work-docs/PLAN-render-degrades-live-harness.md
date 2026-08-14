---
type: plan
task_slug: render-degrades-live-harness
status: complete
created: 2026-08-13
tags: [harness-maker, plan, python, render, hooks, settings]
interview_rounds: 3
adrs: 6
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Stop a re-render from silently disabling a working harness: install-ref existence + matcher-aware hook merge"
---

# PLAN — A re-render must not silently disable a working harness

> **EXECUTE STATUS.** Phases 1, 2, 2b **DONE**; Phase 3 **no-op confirmed**.
> `tests/unit/test_install_ref.py` 20 pass · `tests/unit/test_render_settings_hooks.py` 53 pass ·
> `ruff check` / `ruff format` / `mypy --strict` clean on both touched modules. Neither
> `surface_baseline.json` nor any `tests/snapshot/*.expected.yaml` moved (`git status` empty for
> both), which is Phase 3's predicted outcome — no template changed.
>
> **Discrimination verified by reverting each fix:** ADR-003 reverted → 3 tests red; ADR-004
> reverted → 6 red. The four assertions in `test_install_ref.py` that Phase 1 predicted would
> break did break, and were updated to inject a resolvable `tmp_path` project rather than
> asserting on a path whose existence depends on the runner.
>
> **Known limit:** the full local gate suite (`tests/structural tests/snapshot tests/unit`) runs
> very slowly on this machine and did not finish inside the stage's wait budget — the same
> discrepancy recorded earlier this session (CI completes the whole suite in ~8m37s). Zero
> FAILED/ERROR lines were produced before it was cut off. **CI is the authoritative full-suite
> check for this change.**
>
> **Phase 1 D.5 gap (stated, not fixed):** the `dist.version`-absent branch of
> `_pinned_distribution_ref` (bare-name second fallback, for a harness predating the 0.15.3 PyPI
> publication) has no test exercising it. **Partly closed by Phase 4** — the version-present-but-
> unpinnable branch now has five, though the absent case itself is still untested.

> **EXECUTE STATUS — Phase 4 (REVIEW round 1 remediation).** **DONE.** ADR-007/008/009/010
> implemented after the user chose the recommended option on all four round-1 decisions.
> `tests/unit/test_render_settings_hooks.py` + `tests/unit/test_install_ref.py` = **91 pass** ·
> `ruff` / `mypy --strict` clean · `surface_baseline.json` and `tests/snapshot/` still untouched.
>
> **All four round-1 reproductions re-run and now correct:** the stale `0.43.3` ref is refreshed
> to `0.51.3` under the user's own matcher; PreCompact `manual` keeps both commands when only
> `auto` is scoped; the flat template entry ships again; a `.whl` ref passes through and a
> `.dev0` version falls to the bare name. The merge reaches a fixed point after one render.
>
> **Discrimination re-verified by reverting each of the five fixes** (ADR-007 → 3 red,
> ADR-008 → 2 red, ADR-009 → 1 red, ADR-010a → 2 red, ADR-010b → 5 red). The **first** ADR-009
> probe came back green and that was a bad probe, not a bad test: flipping the schema gate open
> runs the nested path, whose `_harness_commands_in` reads `hooks[]`, which a flat entry does not
> have — so nothing was dropped and the "revert" was a no-op. Re-probed by restoring the deleted
> flat branch's actual behaviour, which is red. **A green revert-probe is a claim about the
> probe first and the test second.**
>
> **Defect found in Phase 4's own first cut, fixed before landing:** the ambiguity warning was
> derived from the branch-3 fall-through, so it printed "not suppressing `<cmd>`" for a command
> branch 1 had already suppressed on another entry of the same event. It is now derived from
> what was actually dropped, and `test_the_warning_does_not_fire_when_the_command_was_suppressed_somewhere`
> pins it.

## 🎯 Executive Summary

**What:** two independent defects that shipped together in a 0.51.1 re-render and each left a
working project worse off, with no diagnostic.

1. **A — stale install-ref.** Every rendered hook command embeds `harness_maker_src_path`.
   Nothing checks that the path *exists*, so a render can bake a cache directory that is gone.
   The hooks are `PreToolUse` **blocking** gates, so when they fail to execute, every `Edit` is
   refused — including the edits that would fix it.
2. **B — a scoped user hook is silently unscoped.** When a user wraps a harness command in
   their own matcher (to exempt `projects/`, say), the merge strips that command out of the
   user's entry and reinstates the template's bare entry. Claude Code runs every matching
   hook, so the exemption stops existing.

**Why one unit:** same trigger (a re-render of a healthy project), same failure signature
(silent degradation of something that worked), same blast radius (the hook layer). Fixing one
and not the other leaves the same class alive.

**Key decisions:** an absent ref falls back to the PyPI name rather than failing the render
([ADR-001](#adr-001)); the check is render-time only, and the cost of that is recorded rather
than hidden ([ADR-002](#adr-002)); a differing matcher is the signal of deliberate scoping
([ADR-003](#adr-003)); when the user has scoped our command, the template's own entry is
dropped so it cannot double-fire ([ADR-004](#adr-004)).

**Estimated impact:** 2 Python modules (`synthesize.py`, `render.py`), 2 new unit test files.
No template change, no schema change, no new config key.

## 📚 Prior Work

- `[fail:process]` class this repo already carries: a line whose whole purpose was avoiding a
  stale pin *fell back to a stale pin* (the `awk '{print $NF, $0}'` positional-parameter
  incident, CLAUDE.md §2). Defect A is the same shape from the other direction — the guard
  meant to keep the ref portable does not keep it **usable**.
- `[wiki:architecture] hooks-load-from-settings-not-hooksjson` (2026-07-17) — Claude Code reads
  project hooks **only** from settings files. `.claude/hooks/hooks.json` is dead weight there,
  so this work touches `settings.json` and nothing else on the Claude side.
- `render.py:1132-1146`'s own comment already anticipates B's neighbourhood: *"When it does (a
  dev_mode flip retiring spec_gate), gate it on positive provenance — a prior-render manifest —
  not on a forgeable prefix."* It reasoned about **retirement** and not about **re-scoping**,
  which is the gap this PLAN closes.
- CLAUDE.md 2026-06-08 — absent-case = feature black hole (`count:8`). Both fixes here activate
  on a condition most users never hit, so both need the absent branch tested directly.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | Absent install-ref | Failure handling | Fail the render, or fall back? | PyPI name + loud warn | `harness-maker` has been on PyPI since 0.15.3, so the fallback is real rather than theoretical | ADR-001 |
| 2 | Scoped-hook merge rule | Contract shape | What happens to a user entry carrying our command under a different matcher? | Preserve the user's entry; drop the template's | Locked with its consequence: keeping both would double-fire | ADR-003, ADR-004 |
| 3 | Scope | Scope boundaries | How far this unit? | A + B only | `.cursor/hooks.json` orphan sweep is a separate PLAN | — |
| 4 | Last line of defence | Observability | Add a `/hm:health` smoke that the ref still resolves? | Render-time check only | Cost recorded in ADR-002 — the "rendered fine, cache pruned later" window stays unwatched | ADR-002 |
| 5 | Deliberate-vs-accidental | Contract shape | How do we know a user entry is deliberate scoping? | Matcher differs from the template's | Mechanical, no new state; a mistyped matcher is preserved too | ADR-003 |

Exit gate: 4 candidates generated, 0 passed (template-entry removal and `--update` repair were
both already settled by the choices above).

## 📐 Architecture Decision Records

### ADR-001: An unresolvable install-ref falls back to the PyPI name
**Status:** Accepted (2026-08-13, via /hm:plan interview)
**Context:** `synthesize._compute_install_ref()` returns the `file://` path from
`direct_url.json` — the cache directory of whichever version the *rendering process* was
installed from. That path is baked into every hook command. When the directory later disappears
(a plugin update prunes old versions), every `uv run --with <gone>` fails. The hooks are
`PreToolUse` blocking gates, so the project loses `Edit` entirely.
**Decision:** Three parts, all load-bearing:

1. **Where.** The check goes **inside the `file://` branch at `synthesize.py:128`, on the
   decoded `unquote(urlparse(url).path)` value, BEFORE `_portablize_ref` wraps it.**
   `_portablize_ref` is applied *inside* every return, so a check placed after
   `_compute_install_ref()` sees the literal string `$HOME/...`; Python does not expand it and
   `Path.exists()` would be False for **every valid home-cache install** — the dominant install
   path. That would force the whole fleet to the fallback: a broader silent degradation than
   the defect being fixed.
2. **What.** The predicate is `(p / "pyproject.toml").is_file()`, **not** `p.exists()`. The
   function's own docstring records the 0.15.0 incident where an *existing* archive
   `lib/python3.12` directory was baked and every hook failed with "does not appear to be a
   Python project". An existence-only guard would not have caught this repo's one documented
   instance of the class.
3. **Fallback value.** `harness-maker=={dist.version}` — `dist` is already in scope at
   `synthesize.py:115`. If that exact release is not on the index (any harness rendered by
   <0.15.3 predates PyPI publication), fall back to the bare name with a second warning.

The warning goes to `typer.echo(..., err=True)` (the channel `render.py:1093` already uses) and
is deduplicated once per process — `_compute_install_ref` is called from four sites
(`synthesize.py:202`, `:648`, `:723`, `:889`), so an undeduplicated warning fires four times per
make.
**Consequences:**
- ✅ The rendered harness is usable rather than bricked; the user can still edit their way out.
- ✅ Pinning the version removes the drift the first draft accepted: the hooks run the same gate
  implementation as the templates rendered beside them.
- ⚠️ Hooks then require network on first resolve. Accepted: a slow hook beats a dead one.
- ⚠️ The bare-name second fallback reintroduces version drift for pre-0.15.3 harnesses, where
  the alternative is nothing at all.
**Rejected alternatives:**
- Fail the render — Rejected: it refuses to write a working `settings.json` at exactly the
  moment the user is repairing a broken one, and if hooks already block `Edit` the manual path
  out is the hardest one available.
- Unversioned `harness-maker` as the primary fallback — Rejected: `dist.version` is free at the
  call site, and an unpinned name lets a harness rendered by 0.51.x execute a future release's
  `spec_gate`.
- `p.exists()` — Rejected: see part 2.
**Source:** Interview #1; sharpened by validator critical #1 and warnings #7/#8

### ADR-002: The existence check is render-time only
**Status:** Accepted (2026-08-13, via /hm:plan interview)
**Context:** Two moments can break the ref: the render bakes a path that is already gone, or
the render bakes a valid path that is pruned later.
**Decision:** Check at render time only. No `/hm:health` smoke, no SessionStart probe.
**Consequences:**
- ✅ Small, self-contained, no new runtime surface.
- ⚠️ **The second window stays unwatched, and it may be the one that actually fired here.** The
  reported incident is equally consistent with "0.51.1 re-render baked 0.43.3" and with "0.43.3
  was valid when baked and pruned afterwards". This decision covers the first and not the
  second. Recorded rather than hidden: if the incident recurs on a harness rendered *after* this
  fix, that is the evidence that the render-time check was the wrong half.
**Rejected alternatives:**
- `/hm:health` smoke — Rejected for scope; the cost above is the price.
- SessionStart warning — Rejected: it is self-defeating. A broken ref breaks the SessionStart
  hook that would carry the warning.
**Source:** Interview #4

### ADR-003: A MIXED group is the evidence of user ownership — a differing matcher is not
**Status:** Accepted (2026-08-13, via /hm:plan interview; **replaces** a matcher-difference rule
the validator showed to be unsound)
**Context:** The first draft said "a different matcher means the user deliberately re-scoped
it". That is **not derivable**. `_merge_hooks_json` takes exactly two inputs — the on-disk file
and the freshly rendered template — and the render manifest stores `{path, content_hash,
timestamp}` (`render.py:19`, `:1541`) with **no per-hook matcher record**. So a matcher
difference is provably ambiguous between (a) the user re-scoped our command and (b)
**harness-maker's own template matcher changed between releases**. Under (b) the rule would
keep the user's stale copy of *our old entry* and drop the command from the new template
entry — silently reverting the gate to the previous release's matcher. That is this PLAN's own
title's failure mode, reintroduced by its fix.
**Decision:** Ownership is decided by **evidence present in the entry**, not by inference. A
user entry is treated as theirs — and its harness commands preserved — only when the entry is
**mixed**: it contains at least one command that is not harness-managed. A pure-harness entry
is indistinguishable from our own older entry, so it keeps today's behaviour (stripped).
**Consequences:**
- ✅ No inference, no new state, no migration. A mixed group is a fact you can read off the
  entry, so case (b) cannot be misread as case (a) — the unsoundness is removed rather than
  documented.
- ✅ Matches how the `/hooks` UI actually creates the collision: it appends the user's command
  **into an existing group**, producing exactly the mixed shape.
- ⚠️ **A user who scoped ONLY our command — a wrapper containing `spec_gate` and nothing else —
  is still flattened.** This is the sharpest cost of the decision and it may be the reported
  incident's exact shape. Such a user's remedy is to keep any second command in the group (even
  a no-op) until provenance lands, and the render warning below tells them so.
- ⚠️ The harness still cannot honour a pure re-scope, so the "projects/ exemption" use case is
  only partially served.
**Rejected alternatives:**
- Matcher difference = deliberate — Rejected: unsound, per the Context above. This is the
  validator's critical finding and the reason this ADR was rewritten.
- Prior-render provenance in the manifest — Rejected **for scope, not for correctness**: it is
  the right answer (`render.py:1142`'s own comment says so) and remains the documented upgrade
  path. It needs a new manifest field plus a migration, and existing users stay unprotected
  until their manifest is first written.
- Require an `@hm:scoped` marker — Rejected: every existing wrapper predates the marker, so the
  next re-render flattens exactly the population the fix is for (the count:8 absent-case shape).
**Source:** Interview #5; rewritten after validator critical #3

### ADR-004: When a mixed group retains our command, the template drops it — command-level
**Status:** Accepted (2026-08-13, via /hm:plan interview); **amended by ADR-007 and ADR-008
(2026-08-14, REVIEW round 1)** — the suppression stands, but only after the preserved command's
text is refreshed (ADR-007) and only against the template entry it actually shadows (ADR-008).
**Context:** ADR-003 alone preserves the command inside the user's mixed group, but the
template's own entry still ships it. Claude Code runs **every** matching hook, so it would fire
twice and the user's narrower matcher would buy nothing.
**Decision:** When a preserved mixed group retains a harness command, that **command** is
removed from the template's emitted entry for the same event — at the command level, not the
entry level. Sibling commands, their order and their per-hook metadata are preserved using the
existing `{**entry, "hooks": kept}` shape (`render.py:1045`). A template entry left with zero
commands is not emitted.
**Consequences:**
- ✅ Exactly one registration per command per event — the invariant
  `_normalize_hm_managed_command` already protects.
- ⚠️ **The harness yields its own gate to the user's matcher**, `spec_gate` included. Anyone
  auditing "is spec_gate enforced everywhere" must read the merged `settings.json`, not the
  template.
- ⚠️ Asymmetric across schemas until Phase 2b lands (see ADR-006).
**Rejected alternatives:**
- Keep both entries — Rejected: it *is* the bug.
- Entry-level removal — Rejected: it would drop un-scoped co-located commands
  (`permission_gate`, `worktree_gate`) along with the scoped one. Both models caught the
  pseudo-code reading this way.
**Source:** Interview #2

### ADR-005: Retirement stays matcher-unconditional
**Status:** Accepted (2026-08-13, via /hm:plan interview; validator critical #4)
**Context:** `_strip_shipped_commands` strips against `shipped_cmds |
_HARNESS_RETIRED_HOOK_INVOCATIONS` (`render.py:1031`). A **retired** command has no template
entry, therefore **no template matcher**. Any per-command matcher gate applied to the union
would have nothing to compare and would silently kill retirement — the mechanism by which a
hook removed from the template gets removed from an existing user's disk.
**Decision:** The ADR-003 ownership rule applies to `shipped_cmds` **only**.
`_HARNESS_RETIRED_HOOK_INVOCATIONS` remains unconditional: a retired command is removed even
from a mixed group.
**Consequences:**
- ✅ Retirement keeps working, and it is the one case where provenance is positive by
  construction — membership in that list is curated and gated by
  `test_retired_invocations_absent_from_current_templates`.
- ⚠️ A user who scoped a hook we later retire loses it. Correct: it is retired.
**Rejected alternatives:**
- Apply the ownership rule to the union — Rejected: two defensible readings of one ADR produced
  opposite test outcomes; this names the reading.
**Source:** validator critical #4

### ADR-006: Flat (Cursor) gets its own suppression logic
**Status:** Accepted (2026-08-13, via /hm:plan interview); **SUPERSEDED by ADR-009
(2026-08-14, REVIEW round 1)** — the flat path has no ownership evidence to gate on, so its
suppression is withdrawn rather than kept unsound.
**Context:** `_strip_shipped_commands` returns flat entries unchanged (`render.py:1026-1027`),
and flat identity is `(matcher, command, "")` (`:1005`), so a user's re-scoped flat entry
already survives on identity alone — ADR-003 is a structural no-op there. But ADR-004's
double-fire suppression has no flat implementation, so Cursor would still register both.
**Decision:** Implement flat-side suppression too: when a flat user entry carries a harness
command that the template also ships under a different matcher, omit that command's template
entry. A flat entry holds one command, so "command-level" and "entry-level" coincide.
**Consequences:**
- ✅ All three consumers (`settings.json`, `.codex/hooks.json`, `.cursor/hooks.json`) behave
  consistently; no asymmetry to document or explain later.
- ⚠️ Touches the highest-risk shared function on both schema paths. Phase 2b is separated from
  2a for exactly this reason.
**Rejected alternatives:**
- Declare flat out of scope — Rejected by the user: the asymmetry would have to be documented,
  tested and eventually removed anyway.
**Source:** Interview #6

### ADR-007: A preserved harness command is refreshed from the template before suppression
**Status:** Accepted (2026-08-14, REVIEW round 1 decision; **amends ADR-004**)
**Context:** REVIEW round 1's P0. `_strip_shipped_commands` returned a mixed group's hooks
**verbatim**, including the baked `uv run --with <path>`, and ADR-004 then deleted the
template's fresh-path copy. `_normalize_hm_managed_command` elides that prefix for identity, so
a stale copy and a fresh copy are indistinguishable to the merge. Reproduced: a user entry
carrying `…/0.43.3/… spec_gate` survived while the template's `…/0.51.3/…` entry disappeared,
and three consecutive re-renders were byte-stable — permanent, unrepairable by re-render. This
is the failure ADR-003's Context predicted and attributed to the branch it *rejected*; the
adopted mixed-group rule has the identical property whenever the group is mixed.
**Decision:** Before suppressing, **rewrite each preserved harness command's text to the
template's current text for the same normalized identity**. The user's matcher, entry order,
sibling commands and per-hook metadata are untouched — only the command string is refreshed.
A command with no template counterpart (retired, or shipped elsewhere) is left alone.
**The template entry is the source of the replacement text — no new plumbing.** `install_ref`
is not threaded into `_merge_hooks_json`; the freshly rendered entry in `new_entries` already
carries the correct, validated command string, so a `dict[normalized_cmd, raw_template_cmd]`
built beside `shipped_cmds` is the whole mechanism.
**Consequences:**
- ✅ Both ADR-003's and ADR-004's intent are satisfied at once: the user's scoping survives
  **and** the command that runs is the one this release validated (Phase 1's whole point).
- ✅ Re-render becomes the self-healing path again — a stale ref is repaired on the next
  `/harness-maker:make` instead of being frozen by it.
- ⚠️ A user who *deliberately* pinned an older `--with` inside a harness command loses that
  pin. Accepted: pinning our gate to an unvalidated build is the defect, not a feature; the
  supported way to run different code is a command of their own.
**Rejected alternatives:**
- Suppress only on a raw-text match — Rejected: safe (the gate never dies) but it silently
  reinstates the original defect for exactly the stale population, since a stale user ref never
  byte-matches and the broad template entry then ships beside the narrow one.
- Withdraw ADR-004's suppression entirely — Rejected: it also erases the `projects/` exemption
  use case this PLAN exists for.
**Source:** REVIEW round 1, finding `1733864e8c6b2bff` (code-reviewer P0, corroborated by
security-reviewer `bc4af07871238250` at P1)

### ADR-008: Suppression is keyed by (command, matcher), and stays its hand when ambiguous
**Status:** Accepted (2026-08-14, REVIEW round 1 decision; **amends ADR-004**, restores the
multi-matcher rule Phase 2 specified and the implementation dropped)
**Context:** `user_scoped` was a flat per-event `set[str]` applied to **every** template entry.
`Production.json.j2:102-117` ships `flush_session` + `worktree span-end` under **both** `auto`
and `manual`, so a mixed user group under `auto` emptied the `manual` entry, which was then not
emitted at all. Reproduced. Phase 2 had named the fix — *"a command shipped under several
matchers is matched when the entry's matcher is IN the set"* — and building `user_scoped`
without a matcher dimension is what lost it.
**Decision:** Resolve suppression per (normalized command, template entry) with a three-branch
rule, most specific first:
1. A template entry whose matcher **equals** the preserved user entry's matcher → suppress
   there. (The `/hooks` UI case: it appends into our existing group, so the matchers match.)
2. Else, if the command is shipped under **exactly one** template matcher → suppress there.
   (The deliberate-wrapper case: the user's narrow matcher shadows the single broad entry.)
3. Else — a differing user matcher **and** several template matchers — **suppress nothing** for
   that command, ship every template entry, and warn. Ambiguous ownership resolves toward
   duplication, never toward deletion.
**Consequences:**
- ✅ PreCompact `manual` survives a user scoping `auto`; the reported `projects/` case still
  works, because `spec_gate` ships under a single matcher (branch 2).
- ✅ The bias is stated and one-directional: a duplicate hook is noisy and self-evident, a
  deleted hook is silent. Branch 3 chooses the recoverable failure.
- ⚠️ Branch 3 can leave a genuine double-fire in place for a multi-matcher command. Accepted,
  and the warning names it so the user can scope the other matcher too.
**Rejected alternatives:**
- Suppress from every entry (the shipped behaviour) — Rejected: it is the defect.
- Suppress from no entry when the matcher differs — Rejected: that is branch 3 applied
  universally, and it would break the single-matcher case this PLAN was written for.
**Source:** REVIEW round 1, findings `0f1fa143b4395384` (code-reviewer P1) and
`7d3343e3bb4be974` (codex P2, PIDA `accepted`)

### ADR-009: Flat (Cursor) suppression is withdrawn
**Status:** Accepted (2026-08-14, REVIEW round 1 decision; **supersedes ADR-006**)
**Context:** ADR-006 justified flat suppression on the observation that "a user's re-scoped flat
entry already survives on identity alone — ADR-003 is a structural no-op there." That is true of
**preservation** and false of **suppression**. A flat entry holds exactly one command, so the
mixed-group evidence ADR-003 was rewritten to depend on is *structurally unavailable*; the flat
branch could only key on "a user entry carries this command under a different matcher", which is
verbatim the matcher-difference inference ADR-003 rejected as unsound. Its case (b) applies
unchanged: if harness-maker changes a flat matcher between releases, the on-disk entry survives
on identity, suppresses the new template entry, and Cursor runs the previous release's matcher
forever with no diagnostic.
**Decision:** Remove flat-side suppression. On the flat path the template's entries are always
emitted; a user's re-scoped entry continues to survive on identity, so both are registered.
`_drop_commands_from_entry` loses its `schema` parameter along with the dead flat arm.
**Consequences:**
- ✅ The unsound inference is deleted rather than documented — the same standard ADR-003 set.
- ⚠️ **Cursor double-fires** a re-scoped harness command until manifest provenance lands. That
  is the asymmetry ADR-006 was written to avoid, now accepted deliberately: Cursor's duplicate
  is visible and harmless, and the alternative is a silent version-lock.
- ⚠️ ADR-006's "all three consumers behave consistently" goal is dropped. Documented here so a
  later reader does not re-derive flat suppression as a missing feature.
**Rejected alternatives:**
- Restrict flat suppression to a raw-text match — Rejected for the same reason as in ADR-007:
  it never fires for the population that matters, so it is complexity that buys nothing.
- Keep ADR-006 and document the limitation — Rejected by the user.
**Source:** REVIEW round 1, finding `eead20acb79501d4` (code-reviewer P1)

### ADR-010: The install-ref fallback accepts installable archives and refuses to pin a non-release version
**Status:** Accepted (2026-08-14, REVIEW round 1 decision; **amends ADR-001**)
**Context:** Two defects in Phase 1 as built. (a) `_is_resolvable_project` requires a
`pyproject.toml` **beside** the path, so a wheel/sdist install — whose PEP 610 `direct_url.json`
points at `…/harness_maker-X-py3-none-any.whl` — is rejected even though `uv run --with <whl>`
resolves it fine. That is a regression against a currently-working install class. (b)
`_pinned_distribution_ref` pins **any** non-empty version; its only fallback keys on version
*absence*, not on index absence, so a `0.52.0.dev0` or `1.2.3+local` build renders a pin nothing
can resolve — reproducing the exact lockout Phase 1 exists to prevent.
**Decision:** (a) `_is_resolvable_project` also accepts a path that **is** a file with an
installable archive suffix (`.whl`, `.tar.gz`, `.zip`). (b) `_pinned_distribution_ref` pins only
a **plain release** version — `^\d+(\.\d+)*(\.post\d+)?$` — and otherwise falls through to the
bare `harness-maker`, warning that the local version is not indexable.
**No `packaging` dependency.** It is not in `pyproject.toml`'s `dependencies` and is only ever
present transitively, so a regex over the release grammar is used rather than an import that
would work on the maintainer's machine and fail on a user's.
**Consequences:**
- ✅ The wheel/sdist install class works again, and a dev build degrades to a resolvable bare
  name instead of an unresolvable pin.
- ⚠️ A dev build's hooks then run **whatever release PyPI serves**, not the dev code. Accepted:
  ADR-001 already accepts a version skew between hooks and templates as the price of a live
  hook, and an unresolvable pin is not a stricter guarantee — it is a dead gate.
- ⚠️ Archive acceptance is suffix-based, not content-validating. A corrupt `.whl` still renders.
  Out of scope: the render cannot install to find out.
**Rejected alternatives:**
- Probe the index before pinning (`uv pip download`) — Rejected: network at render time, for a
  check that is stale by the time the hook runs.
- Keep pinning and let the dev build fail — Rejected: it is the reported incident's shape.
**Source:** REVIEW round 1, findings `91a86a3d53cf1cef` (codex P1, PIDA `accepted`) and
`f221afdc443668fd` (code-reviewer P2)

### ADR-011: Suppression subtracts, it does not delete — the template keeps the residual matcher
**Status:** Accepted (2026-08-14, REVIEW round 2 decision; **amends ADR-008's branch 2**)
**Context:** Round 2's re-review found that ADR-008's branch 2 — "the command has exactly one
template home, so the user's differing matcher unambiguously shadows it, drop it" — is the
**same matcher-difference inference ADR-003 rejected and ADR-009 withdrew flat suppression
over**, kept alive on the nested path. `_merge_hooks_json` has no provenance, so a user entry
carrying a matcher different from today's template cannot be distinguished between "the user
chose it" and "it is the matcher harness-maker itself shipped last release". Under the second
reading branch 2 pins the gate to the retired matcher **forever**. Reproduced: a `/hooks`-UI
mixed group carrying `Write|Edit` against a template that now ships `Write|Edit|MultiEdit`
leaves `spec_gate` registered only under `Write|Edit` — **MultiEdit permanently ungated, no
diagnostic**, reproducing on every subsequent render. The templates themselves record that
exact matcher divergence (`Production.json.j2:39` vs `cursor/hooks.json.j2:43`).
**Decision:** Do not choose between the two readings — **serve both**. When branch 2's
conditions hold, subtract the user's matcher terms from the template's and keep shipping the
**residual**:
- residual is empty (the user covers everything this entry did) → drop, as before;
- residual is a strict narrowing → drop the command from the entry **and re-emit it as its own
  entry under the residual matcher**, hook dict carried over verbatim so `timeout` /
  `statusMessage` survive;
- residual equals the template matcher (the two are disjoint) → do nothing; there is no overlap
  and therefore no double-fire;
- either matcher is not decidable → branch 3, unchanged.
`_matcher_terms` decides only a **tool-name alternation** (`Write|Edit|MultiEdit`, `Bash`,
`auto`). `*` and any regex-shaped matcher return None. Every matcher both settings templates
ship is an alternation or `*`, so the decidable path covers every real case and the
undecidable one degrades to the conservative branch.
**Consequences:**
- ✅ Coverage and scoping are both preserved, which neither prior branch could do: the user
  owns `Write|Edit`, the template still gates `MultiEdit`, and no tool is gated twice.
- ✅ The reading that is *right* no longer has to be guessed, so the absence of provenance
  stops being load-bearing on this path.
- ⚠️ A user's group can now be joined by a narrow template entry they did not write. It is
  harness-owned and re-derived every render, so it is not user state, but it is new output
  shape.
- ⚠️ Term subtraction is set-based on tool NAMES. A matcher that is a genuine regex is never
  subtracted — correct, but it means the `*` entries never take this path.
**Rejected alternatives:**
- Warn and keep dropping — Rejected: both round-2 reviewers proposed it as the minimal repair,
  and it is honest, but a warning does not restore the gate. MultiEdit stays ungated and the
  user has to hand-edit; the silent-coverage-loss class is exactly what this PLAN is named for.
- Remove branch 2 (suppress only on an exact matcher match) — Rejected: it reinstates the
  original defect B for any user who scoped with a new matcher.
**Source:** REVIEW round 2, findings `<security-reviewer P1 render.py:1312>` and
`<code-reviewer P2 render.py:1312>`; user chose the residual option.

### ADR-012: The double-fire warning is per (command, template matcher, user matcher)
**Status:** Accepted (2026-08-14, REVIEW round 2 decision; **amends ADR-008's branch 3**)
**Context:** The warning was keyed per command — "warn when NO entry gave this command up" —
which is narrower than the condition it claims to surface. A command suppressed on one template
entry and left on another is a real double-fire that stayed silent. The inverse was also wrong:
matchers that cannot both match the same tool (`Custom` vs `auto`) were treated as ambiguous.
**Decision:** After the emitted set is built, warn for every (command, template matcher, user
matcher) triple where the template still ships the command and the two matchers **can both
fire** — their term sets intersect, or either is not decidable (overlap is assumed). The
message names both matchers.
**Consequences:**
- ✅ The warning describes what actually happens. It no longer stays silent on a partial
  suppression, and it no longer cries wolf on disjoint matchers — a diagnostic that cries wolf
  is one the next reader learns to ignore.
- ⚠️ Undecidable matchers warn conservatively, so a `*` template entry beside any user entry
  carrying the same command always warns. Correct: `*` really can fire alongside anything.
**Source:** REVIEW round 2, finding `<code-reviewer P2 render.py:1326>`

### ADR-013: The source-tree install ref is held to the same resolvability bar
**Status:** Accepted (2026-08-14, REVIEW round 2 decision; **amends ADR-001/ADR-010**)
**Context:** ADR-007 refreshes a preserved user hook to the template's command text on the
premise that the template's ref is validated. It was validated on the `file://` branch only —
`_compute_install_ref`'s two `_HARNESS_MAKER_PKG_ROOT` returns (distribution not found, and
`direct_url.json` unparseable) handed it back unchecked. That constant is exactly what the
0.15.0 incident shows going wrong: imported from a uv archive it resolves to
`…/lib/python3.12`, which has no `pyproject.toml`. In that state ADR-007's refresh would
overwrite a user's still-working invocation with a dead one.
**Decision:** Both returns go through `_pkg_root_ref`, which applies `_is_resolvable_project`
and falls back to the pinned (or bare) distribution name with the same warning. The premise is
made true rather than assumed.
**Consequences:**
- ✅ Every branch of `_compute_install_ref` now returns something resolvable or an explicit
  fallback, so ADR-007's refresh can no longer propagate a dead ref.
- ⚠️ A genuine source-tree install whose root somehow lacks `pyproject.toml` now renders the
  distribution name instead of the path. That state is already broken; the fallback is the
  strictly better of two bad outcomes.
**Rejected alternatives:**
- Check the template's text inside `render.py` before refreshing — Rejected: it would couple
  the merge to path resolution and leave the bad value reachable everywhere else.
**Source:** REVIEW round 2, finding `<code-reviewer P2 render.py:1126>`

### ADR-014: The refresh splices the `--with` token; it does not replace the command
**Status:** Accepted (2026-08-14, REVIEW round 2 decision; **supersedes ADR-007's mechanism**,
keeps its intent)
**Context:** ADR-007 replaced a preserved harness command with the template's text wholesale.
That discards two things the user meant. (a) Everything **before** `python -m`: every Cursor
command carries a `CLAUDE_PROJECT_DIR=… PATH=…` prefix, and a user may add their own env
assignment or PATH shim. (b) It never fires at all for a command the user gave **arguments**,
because `_normalize_hm_managed_command` folds trailing args into the identity — so the one
population that most needs a fresh ref keeps a dead one forever.
**Decision:** Key the refresh on the **module** (`_command_module`, the `harness_maker.<mod>`
before any argument) and replace only the `--with <value>` span (`_splice_install_ref`).
Identity still keys on the whole invocation — two invocations with different flags really are
different hooks — but freshness keys on the module, because the module is what determines which
code must be reachable.
**Consequences:**
- ✅ User prefix and user arguments both survive a refresh, and an arg-bearing command is
  refreshed rather than skipped.
- ✅ One mechanism now serves nested and flat alike (ADR-015 depends on this).
- ⚠️ A command with no `--with` at all is left untouched. Correct — there is no ref to refresh.
**Source:** REVIEW round 2, findings `06ee540d605f09bf` (prefix) and `320a65cf4880936a`
(arg-drift); user chose the splice over a warning.

### ADR-015: Flat (Cursor) suppression is restored, on ADR-011's terms
**Status:** Accepted (2026-08-14, REVIEW round 2 decision; **supersedes ADR-009**)
**Context:** ADR-009 withdrew flat suppression because the only action available was
delete-or-not, and deleting on a matcher difference is the inference ADR-003 rejected. **ADR-011
supplied a third action — subtract — and that changes the calculus.** Measurement also showed
ADR-009's "visible and harmless" wording was wrong on both halves: the preserved flat entry
keeps its **pruned `--with`** (a dead blocking gate, reproduced), and `telemetry` on Cursor's
`postToolUse *` appends a row per invocation, so a duplicate **doubles the ledger denominator**
silently. Neither is visible and neither is harmless.
**Decision:** Route flat through the same three helpers as nested — refresh (ADR-014), residual
subtraction (ADR-011), and the overlap-gated warning (ADR-012). A flat entry holds one command,
so command-level and entry-level removal coincide; `_drop_commands_from_entry` and
`_residual_entries` regain a `schema` arm, and `_harness_commands_of` / `_entry_commands` read
both shapes.
**Consequences:**
- ✅ The realistic Cursor route — **harness-maker changes its own flat matcher** — is fully
  resolved: residual shipped, ref refreshed, no duplicate. Reproduced before and after.
- ⚠️ A template matcher of `*` is not decidable, so the `telemetry` case still emits both and
  warns. The ref is refreshed on both, so nothing is dead; the row still double-counts.
- ⚠️ Cursor's own matcher semantics are assumed to match Claude's tool-name matching. Every
  matcher both files ship is an alternation or `*`, so the assumption is only load-bearing for
  a matcher neither ships.
**Rejected alternatives:**
- Refresh only, no residual — Rejected by the user: it removes the dead gate but leaves the
  duplicate, and the duplicate is what doubles the telemetry denominator.
- Warn only — Rejected: same, minus the dead-gate fix.
**Source:** REVIEW round 2, finding `cfd9f83c72d2c45e`

### ADR-016: A user's argument-scoped variant suppresses the template's bare one — module-keyed
**Status:** Accepted (2026-08-14, REVIEW round 2 decision; **amends ADR-004's branch 1**)
**Context:** This is the reported incident, finally identified. A Claude Code hook `matcher`
matches **tool names**, so a `projects/` path exemption **cannot be expressed in a matcher at
all** — every example in this PLAN and its tests used `Edit(src/**)`, which is permission-rule
syntax, not a matcher. The user's "scope wrapper" was therefore an **argument**:
`spec_gate --exempt projects/`. Trailing args are part of the normalized identity, so an
identity-keyed rule never recognised their variant as ours; the template's bare copy kept
shipping beside it; both fired; the exemption bought nothing. That is the sentence this PLAN
was opened with, and nothing in ADR-003…015 addressed it.
**Decision:** Key the whole suppression axis on the **module**. A user entry carrying any
variant of module M under matcher m means the template's copy of M under m steps aside —
`user_scoped`, `shipped_matchers`, the drop set and the warning all switch from normalized
identity to module.
**Safe because no single event ships one module twice with different arguments** — verified by
rendering both settings templates × both `dev_mode`s and the Cursor template and scanning for a
module with more than one argument form per event. Module and identity therefore coincide on the
template side today; if that ever stops being true, this rule needs the finer key back.
**Consequences:**
- ✅ The reported incident is closed: the exemption survives, the ref is refreshed, and the
  co-located `permission_gate` is untouched. Reproduced.
- ⚠️ **A user who deliberately wanted BOTH variants to run loses the template's.** Stated as the
  sharpest cost. Their own variant survives, so nothing is unenforced; the harness just stops
  adding a second unscoped copy.
- ⚠️ The safety argument is an empirical property of today's templates, not an invariant. It is
  recorded here and re-checkable by re-running the scan.
**Rejected alternatives:**
- Warn only — Rejected by the user: the warning cannot restore the exemption, and the hand-edit
  it asks for is reverted by the next render.
- Match on a `--exempt`-style marker — Rejected: every existing wrapper predates any marker, the
  count:8 absent-case shape.
**Source:** REVIEW round 2 follow-up; identified from the ADR-011 test breakage.

## 🏗️ Technical Design

### Current state

| Element | Location | Fact |
|---|---|---|
| Ref computation | `synthesize._compute_install_ref()` | returns the `direct_url.json` `file://` path |
| Portability guard | `render._assert_portable_install_ref()` (`:119`) | checks `$HOME` substitution ONLY; never existence |
| Guard call sites | `render.py:167`, `:832`, `:1186` | settings, pure-json, merged-hooks — all three |
| Entry identity | `render._entry_identity()` (`:947`) | matcher IS part of identity — correct already |
| Command stripping | `render._strip_shipped_commands()` (`:1008`) | matcher-blind — **defect B** |
| Merge order | `render.py:1156` | `list(new_entries) + user_entries` — template always first |

### Data flow after the fix

```
_compute_install_ref()  ──► ref
                             │
        ┌────────────────────┴────────────────────┐
        │ file:// path?                           │ PyPI name / non-home system path
        ▼                                          ▼
   exists?  ──no──► warn + "harness-maker"      (unchanged)
        │yes
        ▼
   _assert_portable_install_ref()  (unchanged — $HOME substitution)
        │
        ▼
   baked into every hook command


_merge_hooks_json(event):
   shipped = template entries
   for each user entry:
       if identity ∈ shipped_identities:  drop (exact duplicate)
       else:
           keep commands whose matcher differs from the template's   ← ADR-003
           record those commands as "user-scoped"
   emit: template entries MINUS user-scoped commands, then user entries  ← ADR-004
```

## 📝 Implementation Plan

### Phase 1 — Install-ref existence fallback (ADR-001, ADR-002)

- **depends_on:** `[]`
- **parallel_group:** `serial-a`
- **merge_hazards:** none — `synthesize.py` only; Phase 2 touches `render.py`.
- **Scope — in:** `src/harness_maker/synthesize.py` (`_compute_install_ref`),
  **`tests/unit/test_install_ref.py` (EXISTING — not a new file)**.
- **Scope — out:** `render.py`, the portability guard, every template.
- **Four existing assertions break and are part of this phase, not collateral:**
  `test_install_ref.py:38` (`/tmp/hm`), `:123-126`
  (`/home/user/.claude/plugins/cache/harness-maker-local/harness-maker/0.15.1`), `:157`
  (`/home/dev/.cache/...`) and `:248-251` (`$HOME/.../0.42.0`) all assert that a **non-existent**
  `file://` path passes through verbatim. After the fix the first three return the fallback.
  Each must either inject an existing `tmp_path` fixture or assert the fallback explicitly.
  **`:248-251` must not be left as-is**: its outcome would depend on whether that cache
  directory happens to exist on the runner, which CLAUDE.md checkpoint 7 forbids outright.
- **Exit criterion:** `uv run pytest tests/unit/test_install_ref.py -q` passes — the EXISTING
  file, so the four assertions above are inside the gate. New cases: a path with
  `pyproject.toml` returns the `$HOME`-portablized form unchanged; a **missing** path returns
  `harness-maker==<version>`; an **existing directory without** `pyproject.toml` also returns
  the pinned fallback (the 0.15.0 archive shape); a non-`file://` ref is untouched; the warning
  fires once, on stderr, naming the rejected path.
- **Risk:** medium — every rendered hook consumes this value.
- **Rollback point:** branch tip.

> **Why the existing file, not a new one.** A new file plus an exit criterion that runs only
> that file is how the four breakages above go unnoticed: Phase 1 reports green, Phase 3 runs
> `tests/structural tests/snapshot` (no unit tests), and the red surfaces at wrapup or in CI.
> The fragmentation is not a style preference — it is the mechanism that hides the regression.

### Phase 2 — Matcher-aware hook merge (ADR-003, ADR-004)

- **depends_on:** `[1]`
- **parallel_group:** `serial-b`
- **merge_hazards:** `render._merge_hooks_json` is shared by `settings.json`, `.codex/hooks.json`
  and `.cursor/hooks.json` (nested and flat schemas). A change here moves all three.
- **Scope — in:** `src/harness_maker/render.py` (`_strip_shipped_commands` + the emit side of
  `_merge_hooks_json`), **`tests/unit/test_render_settings_hooks.py` (EXISTING)**.
- **Scope — out:** `_entry_identity` (already correct), every template, flat/Cursor (Phase 2b).
- **Required data structure (name it before coding).** `shipped_cmds` is today one flat
  event-wide set (`render.py:1122-1126`) and `_strip_shipped_commands` receives nothing else, so
  ADR-004 is not implementable against it. Build alongside `shipped_identities` a
  `dict[event, dict[normalized_command, set[matcher]]]`, reading the template side with the same
  `.get("matcher", "")` normalization `_entry_identity` uses (`:981-983`). **Multi-matcher
  rule:** a command shipped under several matchers is matched when the entry's matcher is IN the
  set.
- **Reconstruction shape:** `{**entry, "hooks": kept}` — the existing pattern at
  `render.py:1045`, which already preserves siblings, order and per-hook metadata.
- **Exit criterion:** `uv run pytest tests/unit/test_render_settings_hooks.py -q` passes,
  covering: a same-matcher duplicate is still stripped (**no regression** — the group-growth
  tests at `:407` and `:449` use matcher `"Bash"` on both sides and must stay green); a **mixed**
  group keeps its harness command; the template's entry loses that one command and keeps its
  siblings; a template entry left with zero commands is not emitted; a **pure-harness** user
  entry under a different matcher is still stripped (ADR-003's stated cost, pinned so it is
  visible); **a retired command is removed even from a mixed group** (ADR-005); and a user's own
  non-harness command is never touched.
- **Discrimination requirement:** each test must be shown to fail with the fix reverted. This
  repo has shipped three tests that walked the buggy line and asserted only fields the bug did
  not touch.
- **Risk:** high — this merge decides what lands in every user's `settings.json`.
- **Rollback point:** end of Phase 1.

### Phase 2b — Flat (Cursor) suppression (ADR-006)

- **depends_on:** `[2]`
- **parallel_group:** `serial-b`
- **merge_hazards:** same shared function; separated from 2a so a flat regression is bisectable.
- **Scope — in:** `render.py` flat branch (`:1026-1027` and the flat emit side),
  `tests/unit/test_render_settings_hooks.py` or the Cursor-specific suite, whichever already
  owns flat merge coverage.
- **Exit criterion:** a flat user entry carrying a harness command under a different matcher
  keeps it **and** the template's flat entry for that command is not emitted; existing flat
  round-trip tests stay green.
- **Risk:** high — `_strip_shipped_commands`'s flat branch is currently a documented no-op, so
  this is new behaviour on a path three consumers share.
- **Rollback point:** end of Phase 2.

### Phase 3 — Gate reconciliation

- **depends_on:** `[2]`
- **parallel_group:** `serial-gates`
- **merge_hazards:** frozen baselines move together.
- **Scope — in:** `tests/structural/surface_baseline.json` **only if** rendered bytes moved (no
  template changes here, so the expectation is that they do **not**),
  `tests/snapshot/*.expected.yaml` (same expectation), and a BASELINE-DELTA document **only if
  either did move**.
- **Exit criterion:** `uv run pytest tests/structural tests/snapshot -q` green. **If nothing
  moved, this phase writes nothing** — and that is the expected outcome, since neither fix
  changes a template.
- **Risk:** low. **The first draft's caveat here was false and is corrected:** it told the
  executor to "verify which branch is live before concluding", implying the fallback could move
  the baseline on this machine. It cannot. Four conftests pin `_compute_install_ref` to
  `$HOME/harness-maker` — `tests/structural/conftest.py:40`, `tests/render/conftest.py:37`,
  `tests/snapshot/regenerate.py:125`, `tests/unit/conftest.py` — so Phase 1 is **structurally
  invisible** to the structural and snapshot suites. Phase 2 only fires when an output file
  already exists, which temp-dir renders do not produce. The no-op expectation therefore holds,
  for that reason and not the stated one.
- **Known coverage limit (stated, not fixed):** because the ref is pinned in all four suites,
  none of them proves the repaired value actually reaches the three guarded render paths
  (`render.py:167`, `:832`, `:1186`). Phase 1 pins the function; nothing pins the wiring. Closing
  it needs one deliberately-unpinned render-level assertion — recorded as a follow-up rather
  than smuggled into this phase.
- **Rollback point:** end of Phase 2b.

### Phase 4 — REVIEW round 1 remediation (ADR-007, ADR-008, ADR-009, ADR-010)

- **depends_on:** `[2, 2b]`
- **parallel_group:** `serial-c`
- **merge_hazards:** same shared `_merge_hooks_json`; Phase 2b's flat suppression is **deleted**
  here, so this phase partially reverts its predecessor by design.
- **Scope — in:** `src/harness_maker/render.py` (`_strip_shipped_commands`,
  `_drop_commands_from_entry`, the emit side of `_merge_hooks_json`),
  `src/harness_maker/synthesize.py` (`_is_resolvable_project`, `_pinned_distribution_ref`, and
  the two warning calls), `tests/unit/test_render_settings_hooks.py`,
  `tests/unit/test_install_ref.py`.
- **Scope — out:** every template, `_entry_identity`, `_normalize_hm_managed_command` (the
  prefix-agnostic identity stays — ADR-007 fixes the *consequence*, not the primitive).
- **Known test breakage, part of this phase:**
  `test_flat_the_template_entry_is_suppressed_so_it_cannot_double_fire` asserts the behaviour
  ADR-009 withdraws. It must be **inverted**, not deleted — the assertion that both entries now
  ship is what pins ADR-009 against a future re-derivation.
- **Exit criterion:** `uv run pytest tests/unit/test_render_settings_hooks.py
  tests/unit/test_install_ref.py -q` green, plus new cases:
  a preserved harness command's text is **refreshed** to the template's (ADR-007); a stale
  `--with` does not survive a re-render; PreCompact-shaped two-matcher template keeps `manual`
  when the user scopes `auto` (ADR-008 branch 1); a single-matcher command is still suppressed
  under a differing user matcher (branch 2); a multi-matcher command under a differing user
  matcher suppresses **nothing** and warns (branch 3); flat emits both entries (ADR-009); a
  `.whl` ref passes through unchanged (ADR-010a); a `.dev0`/`+local` version falls to the bare
  name (ADR-010b).
- **Discrimination requirement:** unchanged from Phase 2 — every new test shown red with its fix
  reverted.
- **Risk:** high — same merge, and this phase changes what Phase 2 just shipped.
- **Rollback point:** end of Phase 2b.

### Phase 5 — REVIEW round 2 remediation (ADR-014, ADR-015, ADR-016) + IDE matcher parity

- **depends_on:** `[4]`
- **parallel_group:** `serial-d`
- **merge_hazards:** the same shared `_merge_hooks_json`; this phase moves the suppression axis
  from normalized identity to module, so every helper that consumed the drop set moves with it.
- **Scope — in:** `src/harness_maker/render.py` (`_command_module`, `_splice_install_ref`,
  `_refresh_ref`, `_entry_commands`, `_harness_commands_of`, plus the schema arms of
  `_drop_commands_from_entry` / `_residual_entries` / `_warn_live_double_fires` and the emit
  block), `src/harness_maker/templates/cursor/hooks.json.j2` (spec_gate matcher),
  `src/harness_maker/templates/settings/Production.json.j2` (the Jinja comment that described
  the divergence as intentional), `tests/unit/test_render_settings_hooks.py`.
- **Scope — out:** `synthesize.py` (untouched this phase), `_normalize_hm_managed_command` (the
  identity primitive is unchanged — only what the *suppression* keys on moved).
- **Template change, and what it does NOT move.** Aligning Cursor's spec_gate matcher changes
  rendered bytes, but `.cursor/hooks.json` is in **neither** `surface_baseline.json` (grep
  count: 0) nor any snapshot, so Phase 3's no-op prediction survives and **no BASELINE-DELTA is
  required**. That absence is itself the defect's cause and is why this phase adds the parity
  test rather than relying on a baseline to have caught it.
- **Exit criterion:** `uv run pytest tests/unit tests/structural tests/snapshot tests/render -q`
  green, covering: the reported incident (an argument-scoped variant beside the template's bare
  copy → exactly one registration, exemption intact, siblings untouched); a flat matcher change
  → residual entry + refreshed ref, no duplicate; a flat `*` template matcher → both emitted,
  both refreshed, warned; a splice preserving a user prefix and trailing arguments; and Cursor ↔
  Claude matcher parity for every blocking gate.
- **Unpredicted breakage, and the reason it matters:**
  `tests/unit/test_render.py::test_render_cursor_hooks_json_includes_spec_gate_when_spec_driven`
  asserted `"Write|Edit" in matchers` and selected the spec_gate entry *by* that matcher — a
  green guard holding the defect in place. With `.cursor/hooks.json` absent from the baseline
  and every snapshot, that test was the file's entire coverage. Inverted, with the reason in its
  docstring. **This was not in the phase's predicted-breakage list, which is the finding:** the
  scan that justified the template change looked at templates, not at what pinned them.
- **Discrimination requirement:** unchanged — each new test shown red with its fix reverted, and
  a **green revert-probe must be diagnosed as a bad probe before it is accepted as a bad test**
  (Phase 4 produced two of those).
- **Risk:** high — the suppression axis changed, and a template that three IDEs read changed.
- **Rollback point:** end of Phase 4.

## 🧪 Testing Strategy

| Layer | Covers |
|---|---|
| Unit — `test_install_ref_fallback.py` | ADR-001's four branches, including the absent case |
| Unit — `test_hook_merge_scoping.py` | ADR-003 + ADR-004 across both schemas, plus the no-regression arm |
| Structural | that neither fix moved the rendered surface (expected no-op) |
| Manual | render a harness whose ref points at a deleted cache dir, confirm `settings.json` carries `harness-maker` and the warning appeared |

The manual step is not automatable end-to-end: the failure mode is "Claude Code refuses Edit",
which no in-process test observes. What the unit tests pin is the value that reaches disk.

## ⚠️ Risks & Mitigation

| # | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R1 | The PyPI fallback resolves a different version than the user's plugin | med | med | Warning names the substitution explicitly; ADR-001 records it as the accepted trade |
| R2 | ADR-002's unwatched window is the one that actually fired | med | high | Stated in the ADR with the falsifying observation named — a recurrence after this fix is the signal |
| R3 | A harness gate can now be narrowed by a surviving user edit | med | med | ADR-004 states it; auditors must read the merged file, not the template |
| R4 | The merge change regresses the duplicate-stripping the 2026-05-28 triplication fix installed | low | high | Explicit no-regression arm on the same-matcher path |
| R5 | New tests are false greens | med | med | Phase 2 requires each to be shown failing with the fix reverted |

## ✅ Success Criteria

- [x] The existence check sits **inside** the `file://` branch at `synthesize.py:128`, before
      `_portablize_ref` — a valid home-cache install still renders the `$HOME/...` form
- [x] The predicate is `pyproject.toml`, so the 0.15.0 archive shape is rejected too
- [x] A rejected path renders `harness-maker==<version>`; a pre-0.15.3 harness falls back to the
      bare name with a second warning
- [x] The warning is on stderr and fires **once**, not four times
- [x] The four existing `test_install_ref.py` assertions are updated, and none of them depends
      on whether a path happens to exist on the runner
- [x] A **mixed** group keeps its harness command; the template drops that one command and keeps
      its siblings
- [x] A **pure-harness** user entry is still stripped (ADR-003's stated cost, pinned by a test)
- [x] A **retired** command is removed even from a mixed group (ADR-005)
- [x] Same-matcher group-growth (`:407`, `:449`) and all retirement tests stay green
- [x] Flat/Cursor suppression works and existing flat round-trip tests stay green (ADR-006)
- [x] Every new test demonstrated failing with its fix reverted
- [x] `tests/structural` and `tests/snapshot` green; a BASELINE-DELTA exists **iff** bytes moved

## 🔍 Plan Validation

**Pass 1 — `MAJOR_REVISION`** (4 critical, 5 warning, 2 suggestion). Cross-model ran first; both
models returned `invoked` — codex 12 findings, antigravity 4.

The validator **refuted four** of the sixteen with code evidence, which is why they are not in
the plan:

| Finding | Refutation |
|---|---|
| codex: existing group-growth tests depend on matcher-blind stripping | Both use matcher `"Bash"` on **both** sides (`:427-428`, `:449-450`); a matcher-aware gate strips identically. **But the underlying observation led to a hazard nobody named** — a retired command has no template matcher at all → ADR-005 |
| codex: the PLAN's title over-claims vs ADR-002 | The shortfall is ADR-002's own bolded headline consequence and risk-register row R2; an aspirational title over a documented gap is not a defect |
| antigravity: matchers may be `None`/missing/`""` | `_entry_identity` reads `.get("matcher", "")` and returns `None` for non-str (`:981-983`), so malformed entries are dropped before `_strip_shipped_commands`. The classes collapse to `""` first |
| antigravity: ADR-002's window has no diagnostic | ADR-002 considered and rejected both candidates; the SessionStart rejection is sound *on the code* — a broken ref breaks the hook that would carry the warning |

**Resolution of the 4 critical critiques:**

| # | Critique | Resolution |
|---|---|---|
| C1 | The check as diagrammed runs **after** `_portablize_ref`, so `Path.exists()` on `$HOME/...` is always False → the whole fleet forced to the fallback | ADR-001 now fixes the insertion point at `:128` pre-portablize, and the false "`_assert_portable_install_ref` substitutes" label is gone — it raises, it never substitutes |
| C2 | Phase 1's exit criterion ran a **new** file while four assertions in the existing `test_install_ref.py` break | Phase 1 moved onto the existing file; the four are named with line numbers and `:248-251`'s runner-dependence is called out |
| C3 | **ADR-003 unsound** — no provenance exists at merge time, so matcher difference cannot distinguish "user re-scoped" from "our own matcher changed"; ADR-003+004 would silently revert the gate to the previous release's matcher | Interview round 3 → ADR-003 **replaced**: ownership is decided by the *mixed-group* evidence, not by inference. Its cost (a pure re-scope is still flattened) is stated as the sharpest consequence |
| C4 | Retirement has no template matcher, so a per-command matcher gate would kill it | New ADR-005: the ownership rule applies to `shipped_cmds` only |

Warnings resolved as: the command→matcher map named in Phase 2's scope (W5), flat given its own
ADR-006 + Phase 2b after the user chose to design it rather than exclude it (W6), the pinned
`harness-maker==<version>` fallback (W7), the `pyproject.toml` predicate (W8), and Phase 3's
false caveat corrected with the four conftest pins that actually govern it (W9). Suggestions
resolved as the stderr/once warning contract and the command-level pseudo-code fix.

**Residual risk:** these revisions were applied after the pass-1 verdict and have **not** been
re-validated. The validator-pass cap is 2, so one re-validation remains available and is the
obvious next step given C3 rewrote an ADR outright.
