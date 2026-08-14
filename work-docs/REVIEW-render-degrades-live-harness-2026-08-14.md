---
type: review
task_slug: render-degrades-live-harness
status: APPROVED
created: 2026-08-14
run_id: 20260813T2330Z
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
grade: A
rounds: 2
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations:
    - uv.lock
  scenario_misses: []
  task_slug: render-degrades-live-harness
  computed_at: 2026-08-13T23:30:00Z
---

# REVIEW — render-degrades-live-harness (round 1)

## 🎯 Round 1 Summary

**Grade A by the letter table, and the letter is misleading.** Zero findings reached
`consensus-passed`, so `P0_count = P1_count = 0`. That is not evidence the change is clean —
it is an artifact of the tier-matching rule in Step 4a. Ten findings landed, **six of them
P0/P1**, and the orchestrator independently reproduced four of them at the interpreter. Every
pair that describes the same defect did so at *different* severity tiers (P0 vs P1, P1 vs P2),
and Step 4a forbids bridging tiers, so nothing could cluster into strong consensus.

`unverified_severe = TRUE` → `human_review_needed = TRUE` → **STOP for human review before
wrapup.** No auto-fix round was run: the grade cleared the threshold, so the Grade Gate takes
the APPROVED branch, and the top finding's remedy reverses a LOCKED ADR — a decision that is
the user's, not an auto-fix loop's.

**Voter pool:** 3 of 4 (code-reviewer, security-reviewer, codex). `antigravity` returned
`status: SUCCESS` with an empty response on two consecutive attempts — recorded `failed`,
warn-and-proceed.

### The four reproductions (orchestrator-executed, established fact)

| # | Claim | Observed |
|---|---|---|
| 1 | A preserved mixed group's **stale** `--with` beats the fresh template ref | user's `0.43.3` survives; template's `0.51.3` entry **gone** |
| 2 | Suppression is event-global | PreCompact `manual` lost `flush_session` after the user scoped only `auto` |
| 3 | A preserved entry deletes the template's gate outright | nested `Write|Edit` permission_gate gone; flat `*` spec_gate gone |
| 4 | A wheel install falls back to an unpublishable pin | `harness-maker==0.52.0.dev0` (old value was a resolvable `.whl` path) |

Three consecutive re-renders were byte-stable, so **every one of these is permanent** — the
harness cannot repair itself on the next `/harness-maker:make`.

## 🔍 Drift Findings

**P1 — scope drift: `uv.lock`.** Changed but named in no PLAN phase's scope. It is a
single line (`version = "0.51.1"` → `"0.51.3"`), the lockfile catching up to the 0.51.3
release completed earlier in the session. Legitimate content, wrong provenance — attributed
here rather than folded in silently.

No incomplete phases. Phase 3's scope (`surface_baseline.json`, `tests/snapshot/`) is
untouched, which is the PLAN's own stated expectation for a change that edits no template.

## ✅ Consensus Findings

**None.** See the Round 1 Summary for why that is a filter artifact, and §6 for the tier
disagreements that caused it.

## ⚠️ Weak Consensus

All three sit in the same suppression block (`render.py:1240-1262`); OBSERVE matches across
reviewers, CONCLUDE diverges, so each is `[2/3 weak]` and none is auto-fix eligible.

### P1 · `0f1fa143b4395384` · render.py:1254 — event-global suppression deletes an untouched sibling entry
`user_scoped` is a flat per-event `set[str]` with no matcher dimension, and
`_drop_commands_from_entry` is then applied to **every** template entry.
`Production.json.j2:102-117` ships `flush_session` + `worktree span-end` under **both**
`auto` and `manual`. A mixed user group under `auto` therefore empties the `manual` entry,
which is then not emitted at all.

This is a **deviation from the PLAN's own Phase 2 spec**, not an accepted cost — Phase 2
named the fix: *"Multi-matcher rule: a command shipped under several matchers is matched when
the entry's matcher is IN the set."* The implementation dropped that data structure when
ADR-003 was rewritten.

> **Fix:** key suppression by `(normalized_command, matcher)` and drop only from the entry
> whose matcher the user actually re-scoped.

### P1 · `0ef2bb7208c8777a` · render.py:1255 — the template's own blocking gate is dropped with zero diagnostic
`_merge_hooks_json` removes harness commands from its own emitted entries and says nothing,
while the same function emits `typer.echo(..., err=True)` for a far smaller event at `:1173`.
ADR-003's consequences explicitly rely on a warning — *"the render warning below tells them
so"* — that was never implemented. Silent removal of a blocking gate is the exact class this
PLAN is named after.

### P1 · `bc4af07871238250` · render.py:1253 — the preserved entry's **unvalidated** ref overrides Phase 1's validated one
The two halves of this PLAN conflict. Phase 1 validates the ref baked into the **template**
entry (`synthesize.py:192`). ADR-004 then suppresses that validated entry in favour of a user
entry whose `uv run --with <ref>` the render never inspects, because
`_normalize_hm_managed_command` deliberately elides the prefix. Reproduction #1 above is this
finding executing.

## 📝 Manual-Only Findings

### P0 · `1733864e8c6b2bff` · render.py:1108 — mixed-group preservation freezes a stale ref and deletes the fresh copy
The most severe finding in the review, and single-source only because the second voice
(`bc4af07871238250`) filed it at P1.

`_strip_shipped_commands` returns a mixed group's hooks **verbatim**, including the baked
`uv run --with <path>`, and ADR-004's suppression then deletes the template's fresh-path copy.
A user whose `/hooks` UI appended a command beside `spec_gate` — *the shape ADR-003 names as
the way the collision actually arises* — keeps a dead cache path forever after the next
`/plugin update`. Blocking PreToolUse gate → `Edit` refused → and re-render no longer repairs
it.

**The PLAN predicted this failure and attributed it to the branch it rejected.** ADR-003's
Context, verbatim:

> Under (b) the rule would keep the user's stale copy of *our old entry* and drop the command
> from the new template entry — silently reverting the gate to the previous release's matcher.
> That is this PLAN's own title's failure mode, reintroduced by its fix.

The adopted mixed-group rule has the **identical** property whenever the group is mixed. No
ADR states an answer. ADR-004's only stated consequence is about *where* the gate is enforced
("the harness yields its own gate to the user's matcher"), not whether the preserved copy
still executes.

> **Fix (needs a decision, not an edit):** rewrite the preserved hook's `--with` to the
> current install ref before suppressing, or suppress only on a raw-text match. Either
> reverses part of ADR-004.

### P1 · `eead20acb79501d4` · render.py:1242 — flat suppression IS the rule ADR-003 rejected as unsound
ADR-006 justified the flat path on the claim that ADR-003 is a structural no-op there. True of
**preservation**; false of **suppression**. A flat entry holds one command, so mixed-group
evidence is structurally unavailable — the flat branch keys purely on "a user entry carries
this command under a different matcher", which is exactly the matcher-difference inference
ADR-003 was rewritten to remove. If harness-maker changes a flat matcher between releases, the
Cursor harness silently keeps the previous release's matcher forever.

### P1 · `91a86a3d53cf1cef` · synthesize.py:116 — a local/pre-release version is pinned without any index check *(codex, PIDA `accepted`)*
`_pinned_distribution_ref` returns `harness-maker=={version}` for any non-empty version. The
only fallback keys on version **absence**, not on index absence. A `.dev0` / `+local` build
whose cache path disappears renders a pin nothing can resolve — reproducing the exact lockout
Phase 1 exists to prevent.

### P2 findings
- `f221afdc443668fd` · synthesize.py:192 — a **working** wheel/sdist `file://` ref (no
  `pyproject.toml` beside a `.whl`) is now rewritten to a possibly-unpublished pin. This is a
  regression against an install class that worked before the change.
- `f33952126fd7684b` · synthesize.py:183 — `print(file=sys.stderr)` where ADR-001 specifies
  `typer.echo(..., err=True)`; CLAUDE.md also forbids `print` for control flow.
- `a535692f35a36b53` · tests/unit/test_render_settings_hooks.py:542 — no test ships one command
  under two template matchers, and none re-merges the output. The first gap is what let the
  event-global defect through; the second is why its permanence went unmeasured.
- `7d3343e3bb4be974` · render.py:1259 *(codex, PIDA `accepted`)* — the P2-tier statement of the
  event-global defect.

## 🤝 Disagreements

Three same-defect pairs split across severity tiers. Per Step 4c these are **not** merged and
no middle severity is synthesized; they are the direct cause of the empty consensus set.

| Defect | Voice A | Voice B |
|---|---|---|
| Stale/unvalidated ref wins over the validated template ref | code-reviewer **P0** (`:1108`) | security-reviewer **P1** (`:1253`) |
| Event-global suppression | code-reviewer **P1** (`:1254`) | codex **P2** (`:1259`) |
| Fallback pin may be unresolvable | codex **P1** (`:116`) | code-reviewer **P2** (`:192`) |

**Reviewer self-correction worth recording.** security-reviewer opened at P0 with an attacker
framing — a forged `settings.json` entry neutering `permission_gate` — and in Pass 2 **dropped
the premise itself**: anyone who can write `.claude/settings.json` can already register
arbitrary hook commands, so a gate defined by that file cannot be a boundary against it. What
it kept is the non-adversarial residue (silent suppression, unvalidated ref) at P1. It also
dropped two of its own four findings against ADR-001/ADR-002's stated accepted costs. That is
the redaction protocol working as designed.

## 🧊 Cross-model findings (frozen @ round 1)

`frozen_at_round: 1` · `models: [codex, antigravity]` · statuses updated in place at round 2 (never deleted)

```yaml
- id: 7d3343e3bb4be974
  source: codex
  severity: P2
  file: src/harness_maker/render.py
  line: 1259
  summary: Command-global suppression removes valid registrations under unrelated template matchers.
  evidence: >-
    user_scoped is a per-EVENT set of normalized commands and _drop_commands_from_entry then
    removes each command from EVERY template entry. Production.json.j2 ships flush_session and
    worktree span-end twice in PreCompact, under auto and manual. Scoping either under auto
    also deletes it from manual. No new test covers one command under multiple matchers.
  needs_relaxation: false
  disposition: accepted
  oracle_result: >-
    Repro: user scoping under auto also stripped flush_session from the untouched manual
    matcher; render.py drops user_scoped from every entry.
  status: resolved
  resolution: ADR-008 (round 2) — suppression keyed by (command, matcher); verified by
    test_scoping_one_matcher_leaves_the_sibling_entry_intact, shown red with the fix reverted.

- id: 91a86a3d53cf1cef
  source: codex
  severity: P1
  file: src/harness_maker/synthesize.py
  line: 116
  summary: Pinning an unavailable local or pre-release version leaves rendered blocking hooks unresolvable.
  evidence: >-
    An installed file-based build may have a non-published version such as 0.51.3.dev1 or
    0.51.3+local. _pinned_distribution_ref emits harness-maker==<version> without verifying it
    exists on the index. The tests cover only an assumed-published synthetic version.
  needs_relaxation: false
  disposition: accepted
  oracle_result: >-
    Repro: dev version 0.52.0.dev0 yields harness-maker==0.52.0.dev0; no index-resolvability
    check on the pinned branch.
  status: resolved
  resolution: ADR-010b (round 2) — only a plain PEP 440 release is pinned; verified by
    test_a_non_release_version_falls_back_to_the_bare_name (4 params), red when reverted.
```

**antigravity:** `status: failed` on both attempts — `SUCCESS` reply with an empty `response`
and no usable `structured_output`. Documented intermittent agy behaviour; no findings, no vote.

## Iteration 2 (Grade: A → A) — human-directed remediation, not the auto-fix loop

The auto-fix loop never ran: the grade cleared its threshold at round 1, and the top finding's
remedy reverses a LOCKED ADR. The four decisions went to the user, who chose the recommended
option on each. What follows is therefore an **ADR amendment plus implementation**, recorded
here as an iteration because it changes the code under review.

**PLAN amended first** — ADR-004 marked amended, ADR-006 marked superseded, ADR-007…ADR-010
added with their consequences and rejected alternatives, and Phase 4 added with its own scope,
exit criteria and predicted breakage.

| # | id | Disposition |
|---|---|---|
| 1 | `1733864e8c6b2bff` | **resolved** — ADR-007. A preserved harness command is refreshed to the template's text before suppression. |
| 2 | `0f1fa143b4395384` · `7d3343e3bb4be974` | **resolved** — ADR-008. Suppression keyed by (command, matcher), three branches, abstaining when ambiguous. |
| 3 | `eead20acb79501d4` | **resolved** — ADR-009. Flat suppression withdrawn; ADR-006 superseded. |
| 4 | `0ef2bb7208c8777a` | **resolved** — ADR-008's branch 3 emits the warning ADR-003 had promised and never implemented. |
| 5 | `bc4af07871238250` | **resolved** — subsumed by ADR-007: the preserved entry can no longer carry an unvalidated ref. |
| 6 | `91a86a3d53cf1cef` · `f221afdc443668fd` | **resolved** — ADR-010. Installable archives accepted; only a plain release is pinned. |
| 7 | `f33952126fd7684b` | **resolved** — both warnings moved to `typer.echo(err=True)`; the `sys` import is gone. |
| 8 | `a535692f35a36b53` | **resolved** — the multi-matcher case and an idempotency assertion both added. |

Fixes applied: 8 findings across 4 ADRs · Remaining: 0 · New issues introduced: **1, caught and
fixed before landing** (see below).

**All four round-1 reproductions re-run, all now correct.** The stale `0.43.3` ref is refreshed
to `0.51.3` under the user's own matcher; PreCompact `manual` keeps both commands when only
`auto` is scoped; the flat template entry ships again; a `.whl` passes through and `0.52.0.dev0`
falls to the bare name. The merge reaches a fixed point after one render — stability now
describes the right output rather than freezing the wrong one.

**A defect in the remediation itself.** The first cut derived the ambiguity warning from the
branch-3 fall-through, so it announced "not suppressing `<cmd>`" for a command branch 1 had
already suppressed on another entry of the same event. A diagnostic that lies is worse than
none, because the next reader trusts it. Fixed to derive from what was actually dropped, and
pinned by `test_the_warning_does_not_fire_when_the_command_was_suppressed_somewhere`.

**Discrimination re-verified against all five fixes** (ADR-007 → 3 red, ADR-008 → 2 red,
ADR-009 → 1 red, ADR-010a → 2 red, ADR-010b → 5 red). Recording one honest miss: the **first**
ADR-009 probe came back green, and that was a bad probe rather than a non-discriminating test —
flipping the schema gate open runs the nested path, whose `_harness_commands_in` reads `hooks[]`,
which a flat entry does not have, so the "revert" changed nothing. Re-probed by restoring the
deleted flat branch's actual behaviour: red. **A green revert-probe is a claim about the probe
first and the test second.**

### Round 2's selective re-review — and what it overturned

**I nearly skipped this step, and the structural gate caught me.** Round 2's fixes went out
self-reviewed; `test_review_payload_persisted` went red because no round-2 payload existed,
and the honest way to clear it was to actually run the re-review rather than waive it or
manufacture a capture. The re-review then found a defect in the remediation that I had already
closed the round on — so the paragraph above, which read `human_review_needed: false`, was
wrong when written.

**The defect: ADR-008's branch 2 was the very inference ADR-009 had just withdrawn.** Branch 2
dropped a command outright whenever it had one template home and the user's matcher differed —
which cannot distinguish "the user chose this matcher" from "this is the matcher harness-maker
shipped last release". Reproduced: a `/hooks`-UI group carrying `Write|Edit` against a template
now shipping `Write|Edit|MultiEdit` leaves `spec_gate` registered only under `Write|Edit`, so
**MultiEdit is permanently ungated with no diagnostic** — and the templates themselves record
that exact matcher divergence. security-reviewer filed it P1, code-reviewer P2; **the tier split
made it manual-only for the third time in this review.**

**Resolved by ADR-011 (user's decision): subtract, do not delete.** The template keeps the
*residual* matcher — user owns `Write|Edit`, template still gates `MultiEdit`, no tool gated
twice. Both readings are served, so the missing provenance stops being load-bearing here.
`_matcher_terms` decides only tool-name alternations; `*` and regex forms fall to the
conservative branch, and every matcher the templates ship is an alternation or `*`.

**Also from round 2:** ADR-012 made the warning per (command, template matcher, user matcher)
and gated it on whether the two matchers can actually both fire — it was silent on partial
suppressions and cried wolf on disjoint ones. ADR-013 held `_compute_install_ref`'s two
`_HARNESS_MAKER_PKG_ROOT` returns to the same resolvability bar, because ADR-007's refresh
*assumed* the template's ref was validated and it was validated on one branch of four.
Warning dedup and the archive-suffix gap were fixed as reported.

**A wrong model in my own tests, surfaced by ADR-011.** Every nested test used `Edit(src/**)`
as the user's "narrower matcher". That is permission-rule syntax — a Claude Code hook `matcher`
matches **tool names**. Once matcher subtraction became real the string stopped being decidable
and four tests failed, which is how the mistake surfaced at all. Replaced throughout with real
matchers (`Edit` ⊂ `Write|Edit`). **This also weakens the round-1 narrative**: a user cannot
express a `projects/` path exemption in a matcher at all, so the reported incident's on-disk
shape is probably a wrapper *command*, not a scoped matcher — see the open items.

**Declined this round** (user's call): the arg-drift / prefix-preservation warning, and the
Cursor duplicate warning.

| id | Sev | Where | Disposition |
|---|---|---|---|
| `4bc5772f5c4a46fa` | P1 | render.py:1312 | **resolved** — ADR-011 (residual matcher) |
| `99bbdd0e3d187951` | P2 | render.py:1312 | **resolved** — same fix, lower-tier voice |
| `06efff24ba670dd2` | P2 | render.py:1326 | **resolved** — ADR-012 (per-triple, overlap-gated) |
| `7c72c45db590c8a6` | P2 | render.py:1126 | **resolved** — ADR-013 (`_pkg_root_ref`) |
| `3727e32a3c776be5` | P2 | synthesize.py:349 | **resolved** — warning routed through the dedup set |
| `6b3ff6fc47cc4180` | P3 | synthesize.py:286 | **resolved** — `.tar.bz2` / `.tar.xz` added |
| `06ee540d605f09bf` | P2 | render.py:1129 | **declined** — prefix loss on refresh |
| `320a65cf4880936a` | P2 | render.py:1133 | **declined** — arg-drift, reproduced |
| `cfd9f83c72d2c45e` | P2 | render.py:1293 | **declined** — silent Cursor duplicate |

**Discrimination verified for all eight fixes.** ADR-011 → 2 red, ADR-012 → 1 red,
ADR-013 → 1 red, warning-dedup → 1 red, plus the round-2 four. The dedup probe was **green on
first attempt** — no test discriminated it, because I had implemented the reviewer's fix and
skipped the `err.count(...) == 1` assertion they asked for in the same breath. Added.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 10        | —   |
| 2         | A     | 8             | 0         | 1 (fixed in-round) |
| 2b (re-review) | A | 6            | 3 declined | 1 P1 found in round 2's own fix |
| 2c (declined reopened) | A | 4 + 1 template | 0 | 1 latent template bug found + fixed |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged
Status: **APPROVED**
human_review_needed: **true** — not because a finding is unresolved, but because the round-2
re-review overturned this review's own round-2 conclusion, and because the matcher-semantics
error below changes what the original incident probably was. A human should read the open items
before wrapup.
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0

## Round 2 follow-up — the reported incident, finally identified

The three declined P2s were reopened at the user's request, and chasing the first of them
produced the most important finding of this review.

**A Claude Code hook `matcher` matches TOOL NAMES.** `Edit(src/**)` — the string every nested
test in this work used as "the user's narrower matcher" — is permission-rule syntax and is not a
matcher at all. A `projects/` path exemption **cannot be expressed in a matcher**. So the
reported "scope wrapper" was an **argument**: `spec_gate --exempt projects/`. Trailing arguments
are part of the normalized identity, so the identity-keyed suppression never recognised the
user's variant as ours, the template's bare copy kept shipping beside it, and both fired. That
is the sentence this PLAN was opened with, and nothing in ADR-003 through ADR-015 touched it.

This surfaced only because ADR-011 made matcher subtraction real, which made `Edit(src/**)`
undecidable, which turned four tests red. **A wrong model in the tests was invisible until the
code became precise enough to disagree with it.**

| ADR | Decision | Verified |
|---|---|---|
| **014** | Refresh **splices the `--with` token**, not the whole command — keyed on the module, so a user's prefix and arguments survive and an arg-bearing command refreshes at all | prefix + `--exempt projects/` preserved, ref `/old`→`/new` |
| **015** | Flat suppression **restored** (supersedes ADR-009) on ADR-011's terms — subtract, refresh, warn | Cursor matcher change → residual `MultiEdit`, refreshed ref, no duplicate |
| **016** | Suppression keyed on the **module**, so an argument-scoped variant suppresses the template's bare one | exemption survives, one registration, `permission_gate` untouched |

**ADR-009's "visible and harmless" was wrong on both halves**, which is what justified reopening
it: the preserved flat entry keeps a *pruned* `--with` (a dead blocking gate), and `telemetry`
on `postToolUse *` appends a row per call, so the duplicate silently doubles the ledger
denominator. Refresh fixes the first everywhere; subtraction fixes the second wherever the
matcher is decidable.

**Separately, a latent bug found while gathering evidence, fixed at the user's direction:**
`cursor/hooks.json.j2` shipped `spec_gate` under `Write|Edit` while both settings templates used
`Write|Edit|MultiEdit` — **Cursor users' MultiEdit writes were not spec-gated at all**, and a
`Production.json.j2` comment described the divergence as intentional. Aligned, the comment
corrected, and a `test_cursor_and_claude_agree_on_every_blocking_gate_matcher` parity gate added
— red on the old matcher. `.cursor/hooks.json` is in **neither** the surface baseline (grep
count: 0) nor any snapshot, which is how this survived; Phase 3's no-op prediction therefore
still holds and no BASELINE-DELTA is needed.

**And the only thing pinning that matcher was a test asserting the wrong value.**
`test_render_cursor_hooks_json_includes_spec_gate_when_spec_driven` asserted
`"Write|Edit" in matchers` and pulled the spec_gate entry out *by* that matcher — so the bug
had a green guard. With no baseline and no snapshot covering the file, that test was the whole
of its coverage, and it was holding the defect in place. Inverted, with the reason written into
its docstring so the next reader does not "fix" it back. A test can be the last line of defence
and the thing defending the defect at the same time.

All four Phase 5 fixes were shown red with their fix reverted.

## Still open — read before wrapup

**1. Accepted costs, stated:**
- **ADR-016**: a user who deliberately wanted *both* their variant and the template's bare copy
  to run loses the template's. Their own survives, so nothing goes unenforced.
- **ADR-015**: a template matcher of `*` is not decidable, so the Cursor `telemetry` duplicate
  survives — warned, and both refs refreshed, so nothing is dead; the ledger still double-counts.
- **ADR-008 branch 3**: a warned double-fire for a multi-home command under a matcher the
  template does not use.
- **ADR-003, unchanged**: a group holding only our command is still flattened.
- **ADR-016's safety argument is empirical, not invariant** — "no event ships one module twice
  with different arguments" was verified by scanning today's templates. If that stops being
  true, the finer key is needed. Re-runnable.

**2. Housekeeping:** `uv.lock` scope drift stands as recorded. The `dist.version`-absent branch
still has no test. The round-1 telemetry row is stamped `terminal: true`, which was true when
written and is now wrong; the ledger is append-only and was left alone rather than rewritten.

**3. This review's own filter, three times over.** A defect the orchestrator reproduces cannot
become `consensus-passed`, and every same-defect pair split across severity tiers — including
round 2's P1/P2 split on the branch-2 finding. Four reproduced defects in round 1 and one in
round 2 all landed `manual-only`, and the grade stayed A throughout. **The letter carried no
information in this review; the prose carried all of it.** Worth its own PLAN.

## What a human has to decide

1. **ADR-004's suppression, as built, hands the gate to an entry the render never validates.**
   Fixing the P0 means either rewriting the preserved hook's `--with` before suppressing, or
   suppressing only on a raw-text match — both reverse part of a LOCKED ADR. That is the
   user's call, which is why no auto-fix round ran.
2. **The multi-matcher rule Phase 2 specified was not implemented.** Restoring it is not an
   ADR reversal — it is finishing the PLAN — and it independently fixes the PreCompact loss.
3. **ADR-006's flat justification does not cover suppression.** Cursor currently has the
   unsound branch ADR-003 was rewritten to remove.
4. **Phase 1 breaks a working wheel/sdist install class** and can pin an unpublishable
   version. Both are cheap to fix and neither touches an ADR.

## Note on this review's own machinery

A defect the orchestrator reproduces at the interpreter still cannot become
`consensus-passed` — only reviewer voices count, and only at matching tiers. Four reproduced
defects produced a grade of A. Worth its own PLAN.
