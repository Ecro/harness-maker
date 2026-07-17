---
type: plan
task_slug: command-surface-registry
status: planning
created: 2026-07-01
tags: [harness-maker, plan, cli, dx, self-description]
interview_rounds: 1
adrs: 6
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Give the plugin a self-describing command surface so LLMs stop misrouting python -m calls"
---

## 🎯 Executive Summary

**TL;DR** — The plugin renders ~230 `python -m harness_maker.<module>` invocations
across 27 templates, but has no single description of its own command surface. An LLM
reconstructing those strings from prose mis-transcribes them (observed 2026-07-01:
`python -m harness_maker.autopilot_caps on`, which does not exist). We give the plugin a
**hand-maintained command registry** — one source of truth for every `python -m` entry
point and its subcommands — and wire it into a runtime "did-you-mean" guard (B) and CI
validation tests (C), while collapsing the single odd-one-out (`autopilot` on Typer) into
the dominant dot-form convention (A).

**What / Why** — The root cause is NOT "two balanced conventions." Evidence: dot-form is
230:1 dominant (33 modules) and `autopilot` is the lone Typer `python -m` call. The LLM
applied the *dominant* pattern to the wrong verb. The graceful fix makes the tool
**self-describing and forgiving** rather than adding per-module band-aids.

**Key Decisions**
- ADR-001 — Down-unify `autopilot` to dot-form (not Typer-unify everything).
- ADR-002 — Introduce `command_registry.py` as a **hand-maintained** SSOT for the
  `python -m` surface (introspection can't cover manual-dispatch modules like `worktree`).
- ADR-003 — Keep the Typer `autopilot` command as a thin backward-compat alias, and
  **extract shared validation** so the two entry points can't drift.
- ADR-004 — Registry-driven shared misroute guard on **subcommand-bearing** modules only;
  multi-owner verbs list all owners.
- ADR-005 — CI hard-fail: template↔registry parse test (T-C1) + **behavioral** parity
  test (T-C2) that survives all three parser shapes.
- ADR-006 — Registry classifies every `python -m` module by parser shape; flag/hook/gate
  modules are explicitly guard-exempt.

**Estimated impact** — 1 new module (`command_registry.py`), `autopilot.py` gains a
`main()`, ~13 subcommand-bearing module entries gain a 1-line guard call, autopilot
validation extracted to a shared helper, 1 template invocation flips to dot-form (+
re-render), 3 new test files. No user-facing behavior change; existing rendered harnesses
keep working (Typer alias retained).

## 📚 Prior Work

- **This session's fix (committed `f695bbcc`)** — a hand-written `on`/`off` redirect in
  `autopilot_caps.main()` (note: it currently redirects to the *Typer* form). This PLAN
  *generalizes and replaces* it with the registry-driven shared guard (Phase 2), pointing
  at the new dot-form.
- **CLAUDE.md checkpoint #6 (bidirectional mapper)** — a registry the parsers can silently
  drift from is a "registry that lies." ADR-005's T-C2 is the reverse check that keeps the
  registry honest.
- **CLAUDE.md checkpoint #2 (external consumer parser)** — the consumer here is the LLM
  reconstructing command strings; the registry + guard is the parser-tolerance layer.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Unification direction | Architecture | Typer-unify all vs down-unify autopilot to dot-form vs skip A | **Down-unify autopilot to dot-form** (230:1 evidence) | ADR-001 |
| 2 | Backward compat | Contract | Keep both (Typer alias) vs remove Typer | **Keep both — Typer thin alias** | ADR-003 |
| 3 | Guard breadth | Architecture | Shared helper on all modules vs autopilot-only | **Shared helper, all standalone modules** → refined by validator to **subcommand-bearing modules only** | ADR-004, ADR-006 |
| 4 | Validation strength | Risk/Testing | CI hard-fail vs advisory | **CI hard-fail** | ADR-005 |

> My initial (pre-evidence) recommendation was "Typer-unify all". The 230:1 dot-form
> measurement reversed the *direction* of A; the A/B/C structure was retained. Recorded
> per the "no fold without new evidence / update WITH evidence" contract.

## 📐 Architecture Decision Records

### ADR-001: Down-unify `autopilot` to dot-form, not Typer-unify the surface
**Status:** Accepted (2026-07-01, via /hm:plan interview)
**Context:** Templates use dot-form 230× across 33 modules; only `autopilot` uses Typer
space-form. The lone exception is what the LLM misrouted.
**Decision:** Add a dot-form entry point to `autopilot.py` (`python -m harness_maker.autopilot on`)
so all `autopilot*` operations share the dominant convention. Do NOT migrate the other 32
modules to Typer.
**Consequences:**
- ✅ Removes the odd-one-out that caused the confusion.
- ✅ Tiny blast radius (one module gains `main()`, one template line flips).
- ⚠️ The `python -m` surface stays dot-form; Typer remains the *console-script* surface
  (`harness-maker health`) — a separate, non-confused axis.
**Rejected alternatives:** Full Typer unification (230 rewrites, rejected by evidence);
skip A (leaves the exceptional verb in place).
**Source:** Interview #1

### ADR-002: `command_registry.py` — hand-maintained SSOT for the `python -m` surface
**Status:** Accepted (2026-07-01, via /hm:plan interview)
**Context:** No module knows the full command surface. Auto-introspection cannot build it:
`worktree` (the most-referenced module, 47×) dispatches manually (`if sub == "task-create"`),
so it exposes no argparse subparsers to read.
**Decision:** Add `src/harness_maker/command_registry.py` holding a **hand-maintained**
`MODULES: dict[str, ModuleSpec]` where `ModuleSpec = {shape, subcommands, entry}`.
`subcommands` is a `frozenset[str]` (possibly empty for flag/hook/gate modules). Derive
`TYPER_ALIASES: frozenset[str]` and a reverse index `resolve_owners(verb) -> frozenset[str]`
(multi-owner — see ADR-004). The registry is authoritative; T-C2 (ADR-005) keeps it honest.
**Consequences:**
- ✅ One place answers "what commands does this tool expose?" — the plugin describes itself.
- ✅ Powers B and C from one artifact.
- ⚠️ Hand-maintained → MUST have a drift test (T-C2), else it silently lies.
**Rejected alternatives:** Pure auto-introspection (impossible for manual-dispatch modules);
per-module hard-coded verb lists (N sources of truth, no cross-module did-you-mean).
**Source:** Interview #1, #3

### ADR-003: Retain the Typer `autopilot` command as a thin alias + extract shared validation
**Status:** Accepted (2026-07-01, via /hm:plan interview)
**Context:** Already-rendered harnesses call `python -m harness_maker autopilot on` (Typer).
The Typer command (`cli.py:2012`) already calls `write()/clear()` — so KEEPING it needs no
change — **but** it carries inline validation NOT in `write()/clear()`: level whitelist
(`cli.py:2053`), unknown-action rejection (`:2045`), pipeline comma-split + canonical
default (`:2056+`). A new `autopilot.main()` duplicating that validation would drift.
**Decision:** Keep the Typer command. Extract the level/action/pipeline validation into one
shared helper (e.g. `autopilot.parse_toggle_args(...)`) called by BOTH `cli.autopilot_cmd`
and the new `autopilot.main()`. Both then delegate to `write()/clear()`.
**Consequences:**
- ✅ Zero breakage for un-re-rendered harnesses; both paths validate identically.
- ⚠️ Two live entry points until migration soak ends (accepted; a parity test covers them).
**Rejected alternatives:** Remove Typer command (breaks harnesses); leave validation
duplicated (guaranteed drift — the risk this ADR exists to kill).
**Source:** Interview #2, validator warning W4

### ADR-004: Registry-driven shared misroute guard on subcommand-bearing modules; multi-owner verbs
**Status:** Accepted (2026-07-01, via /hm:plan interview)
**Context:** The LLM can invent an invocation present in NO template (`autopilot_caps on`);
render-time validation can't catch inventions — only a runtime guard can. But the guard's
"argv[0] is a wrong subcommand" check is only meaningful for modules that HAVE subcommands.
For flag/stdin/hook/gate modules, `argv[0]` is a flag or payload — the check is meaningless
and would break hook/gate invocations. Also real verb collisions exist: `write` →
{second_brain, iter_receipts}, `read` → {second_brain, iter_receipts}, `validate` →
{spec_machine, second_brain}.
**Decision:** `command_registry.misroute_guard(module, argv) -> int | None`, called at the
top of the entry of every **subcommand-bearing** module only. "Subcommand-bearing" is
defined by a **non-empty `subcommands` set** (`bool(spec.subcommands)`), NOT by shape
membership — `shape` is only a dispatch hint for T-C1/T-C2 (validator R2 W2). Returns
`None` when `argv[0]` is a valid subcommand of `module`, else
prints and returns exit `2`: if `resolve_owners(argv[0])` is non-empty it names EACH
correct command (`python -m harness_maker.<owner> <argv[0]> …`, trailing args preserved —
listing all owners when >1); otherwise it lists this module's valid subcommands. The guard
only fires when `argv[0]` is a non-flag token (does not start with `-`).
**Consequences:**
- ✅ Catches LLM inventions; cross-module + multi-owner did-you-mean.
- ✅ Flag/hook/gate modules untouched (guard-exempt).
- ⚠️ Entry-point names are non-uniform (`second_brain._cli`, `spec_inventory.__main__`,
  others `main`) — Phase 0 enumerates them explicitly, no blind grep.
**Rejected alternatives:** Guard on every `__main__` module (breaks flag/hook/gate);
autopilot-family-only (leaves 30+ modules with cryptic argparse errors).
**Source:** Interview #3, validator criticals C1 & C3

### ADR-005: CI hard-fail — template↔registry (T-C1) + behavioral parity (T-C2)
**Status:** Accepted (2026-07-01, via /hm:plan interview)
**Context:** Two drift vectors: (1) a template invocation whose module/subcommand no longer
exists, (2) a hand-maintained registry that lies about a module's real subcommands. The
originally-proposed argparse-introspection parity is infeasible: `worktree` has no
subparsers, autopilot's `on/off` may be a choices-positional, and subparser `dest` names
differ (`cmd` vs `command`).
**Decision:** Two hard-fail tests.
- **T-C1 (template↔registry):** from RENDERED assets (not raw `.j2`, to avoid Jinja
  tokens), extract every `python -m harness_maker[. ]<...>` invocation. Assert the module
  is a known registry module; if that module's `subcommands` set is non-empty, assert the
  first non-flag token ∈ that set (or ∈ `TYPER_ALIASES` for the space-form). Flag/hook/gate
  modules (empty `subcommands`) pass on module-existence alone.
- **T-C2 (behavioral parity):** for each `(module, subcommand)` in the registry, verify the
  subcommand is recognized (not misrouted). **Invocation policy splits by shape** because
  manual-dispatch subcommands EXECUTE on bare invocation (no required-arg gate) —
  discovered R2: `worktree cleanup-all`/`drain`/`prune-branches`/`finalize`/`task-land`/
  `post-commit-pop` run destructively against `Path.cwd()` (rmtree `.worktrees/*`, delete
  `hm/*` branches, reap refs) with no arg gate:
    - **subparser / arg-gated subcommands** → invoke in-process via `main(argv)`/`_cli(argv)`
      in a monkeypatched tmp root; a missing-required-arg error is fine (proves recognition).
    - **manual-dispatch mutating subcommands (worktree family)** → do NOT invoke live.
      Assert recognition via the guard-unit path (the token ∈ registry `subcommands`, so
      `misroute_guard` returns `None`) with the real handler stubbed; OR, when a live path
      is wanted, run inside a throwaway `git init` tmp with explicit `monkeypatch.chdir`.
  Also assert a synthetic bogus verb DOES trigger the redirect (safe — it never reaches a
  handler).
**Consequences:**
- ✅ Template↔code drift and registry lies both become red CI.
- ✅ T-C2 survives subparser, manual-dispatch, and choices-positional shapes.
- ⚠️ Manual-dispatch subcommands execute on invocation → they are recognition-checked via
  the guard (stubbed handler) or a sandboxed `git init` tmp, never bare in the real cwd.
**Rejected alternatives:** argparse-introspection parity (infeasible per above);
advisory-only (a silent-drift class the interview rejected).
**Source:** Interview #4, validator criticals C2 & warning W5

### ADR-006: Registry classifies every `python -m` module by parser shape
**Status:** Accepted (2026-07-01, via /hm:plan interview)
**Context:** Guard scope (ADR-004) and T-C1/T-C2 (ADR-005) all depend on knowing each
module's parser shape. The three shapes behave differently.
**Decision:** Every template-referenced `python -m` module is registered with `shape ∈
{subparser, manual-dispatch, flagonly}`. **Guard scope is the non-empty `subcommands` set,
not the shape** (validator R2 W2): `subparser` + `manual-dispatch` modules carry an
enumerated `subcommands` set (guarded); `flagonly` carries an empty set (guard-exempt, T-C1
module-existence only). `shape` is a **dispatch hint** consumed by T-C2's invocation policy
(subparser → live-invoke; manual-dispatch → stub/sandbox). Phase 0 pins the full table.
**Consequences:**
- ✅ Single classification resolves scope, guard-signature, and T-C2 behavior at once.
- ⚠️ A new `python -m` module must be added to the registry or T-C1 goes red — intended
  (forces self-description of new commands).
**Source:** validator criticals C1/C2 + suggestions S6/S7

## 🏗️ Technical Design

**Current State (measured 2026-07-01)**
- `cli.py` — 13 Typer `@app.command`s (console-script surface + `autopilot` toggle with
  inline validation at `:2045/:2053/:2056`).
- `autopilot.py` — functions `write()/clear()/load()` only, **no** `main()`/`__main__`.
- Subcommand-bearing modules — **argparse-subparser (12):** autopilot_caps, autopilot_ledger,
  codex_ledger, high_diff, iter_receipts, memory_md, observability.verification_cache,
  second_brain (`_cli`), spec_inventory (`__main__`), spec_machine, spec_mutation, spec_need.
  **manual-dispatch (1):** worktree (`main`, `if sub == …`).
- Flag/stdin/hook/gate modules (guard-exempt) — codex_adapter, drift_monitor,
  memory_retrieve, refdocs_index, review_telemetry, spec_quality, telemetry, two_pass_review,
  feedback.{draft_writer,footer,telemetry_grep}, gates.{permission_gate,spec_gate,worktree_gate},
  hooks.{autopilot_autoarm,autopilot_guard,flush_session,loop_gate,post_write_reminder,
  sessionid_envfile,sessionstart_drift}.
- Known verb collisions: `write`→{second_brain, iter_receipts}, `read`→{second_brain,
  iter_receipts}, `validate`→{spec_machine, second_brain}.
- No command registry.

**Data Flow (guard, multi-owner)**
```
python -m harness_maker.autopilot_caps on --level x
  → autopilot_caps.main(["on","--level","x"])
    → misroute_guard("autopilot_caps", ["on",...])
        "on" ∉ autopilot_caps.subcommands ; "on" is non-flag
        resolve_owners("on") == {"autopilot"}
      → prints 'python -m harness_maker.autopilot on --level x' ; return 2
```

**Design Decisions** — all trace to ADR-001…006.

## 📝 Implementation Plan

### Phase 0 — Command registry + pinned surface inventory (foundation)
- **depends_on:** []
- **parallel_group:** serial-foundation
- **merge_hazards:** none (new file only)
- **Scope (in):** create `src/harness_maker/command_registry.py`; hand-enumerate every
  template-referenced `python -m` module into `MODULES` with `{shape, subcommands, entry}`
  (using the pinned table in Technical Design as the seed, verified against source);
  `TYPER_ALIASES`; multi-owner `resolve_owners(verb) -> frozenset[str]`. Reserve the
  `autopilot` entry (filled in Phase 1).
- **Scope (out):** guard wiring, template edits, autopilot main().
- **Exit criterion:** `uv run python -c "from harness_maker.command_registry import MODULES, TYPER_ALIASES, resolve_owners; assert resolve_owners('boundary')=={'autopilot_caps'}; assert resolve_owners('write')=={'second_brain','iter_receipts'}; assert MODULES['worktree'].shape=='manual-dispatch'; assert MODULES['telemetry'].subcommands==frozenset()"` passes (exercises unique verb, a KNOWN collision, a manual-dispatch module, and a flagonly module).
- **Risk:** low
- **Rollback:** delete the new file.

### Phase 1 — A: autopilot down-unification + shared validation helper
- **depends_on:** [0]
- **parallel_group:** serial-A
- **merge_hazards:** re-rendered assets (regeneration touches many files) → serial vs any
  template-touching work; `cli.py` autopilot command.
- **Scope (in):** extract level/action/pipeline validation from `cli.autopilot_cmd` into a
  shared helper in `autopilot.py`; add `main(argv)` + `__main__` to `autopilot.py` using
  that helper (`on`/`off` recognized as a subcommand token), delegating to `write()/clear()`;
  point `cli.autopilot_cmd` at the same helper; register `autopilot: {on, off}` (shape
  `subparser` or choices-positional — either passes behavioral T-C2) in the registry; flip
  the one template line to `python -m harness_maker.autopilot on`; re-render.
- **Scope (out):** other modules' guards (Phase 2).
- **Exit criterion:** `uv run python -m harness_maker.autopilot on --level auto_safe --pipeline research,plan --root <tmp>` writes the marker; `... autopilot off` clears it; `uv run python -m harness_maker autopilot on ...` (Typer alias) still works; a test asserts the Typer path and the dot-form path accept/reject an identical good/bad input matrix (shared-helper parity); snapshot/render tests green.
- **Risk:** medium (re-render surface + validation extraction)
- **Rollback:** revert to Phase 0 state.

### Phase 2 — B: registry-driven shared misroute guard
- **depends_on:** [0, 1]
- **parallel_group:** serial-B
- **merge_hazards:** the ~13 subcommand-bearing module entry files (prologue edit);
  `autopilot_caps.py` (replace the one-off guard) — independent files sharing the guard
  contract.
- **Scope (in):** implement `misroute_guard` (multi-owner) in `command_registry.py`; insert
  the call at the top of every subcommand-bearing module's entry (`main`/`_cli`/`__main__`),
  per the Phase 0 `entry` field; delete the hand-written guard in `autopilot_caps.py`.
- **Scope (out):** flag/hook/gate modules (guard-exempt); CI tests (Phase 3).
- **Exit criterion:** `uv run python -m harness_maker.autopilot_caps on` prints the
  `python -m harness_maker.autopilot on` redirect and exits 2; a parametrized test asserts,
  for every subcommand-bearing module, a bogus verb redirects and a real subcommand is
  recognized; a multi-owner case: `python -m harness_maker.spec_need write` (spec_need owns
  `marker-write`, not `write`) → the redirect lists BOTH owners `iter_receipts` and
  `second_brain`.
- **Risk:** medium (touches many entry points)
- **Rollback:** revert to Phase 1 (git retains the one-off guard).

### Phase 3 — C: CI hard-fail validation tests
- **depends_on:** [0, 1, 2]
- **parallel_group:** serial-C
- **merge_hazards:** none (test files only).
- **Scope (in):** T-C1 (template↔registry, from rendered assets, subcommand-bearing modules
  validate first-token, flagonly modules validate module-existence, hook/gate invocations
  covered by flagonly registration); T-C2 (behavioral parity — subparser/arg-gated
  subcommands invoked in-process in a tmp root; manual-dispatch mutating subcommands
  recognition-checked via the guard with a stubbed handler (or a sandboxed `git init` tmp),
  never bare in the real cwd; bogus verb asserted misrouted).
- **Scope (out):** version bump / release (user-gated, out of this PLAN).
- **Exit criterion:** both tests pass on `main`; a deliberately-broken template invocation
  makes T-C1 red; removing a real subcommand from the registry (or adding a bogus one) makes
  T-C2 red.
- **Risk:** low
- **Rollback:** remove test files.

## 🧪 Testing Strategy

- **Unit:** registry shape + multi-owner reverse index incl. a collision (Phase 0); shared
  autopilot validation helper accept/reject matrix across both entry points (Phase 1); guard
  redirect messages incl. trailing-arg passthrough, cross-module + multi-owner did-you-mean,
  and flag-first argv NOT firing (Phase 2).
- **Integration:** `uv run python -m harness_maker.autopilot …` real dot-form + Typer-alias
  invocation writing/clearing a marker in a tmp root.
- **CI (Phase 3):** T-C1 (template parse-validity, rendered assets) + T-C2 (behavioral
  parity). Both hard-fail.
- **Regression:** migrate the existing `test_autopilot_caps.py` redirect tests to assert the
  shared-guard behavior (pointing at the new dot-form), not the deleted one-off.
- **Determinism:** re-render snapshot tests stay green after the template flip; mask
  `generated_at`.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hand-maintained registry drifts from real parsers | med | high | T-C2 behavioral parity — hard CI fail (ADR-005) |
| Guard wired onto a flag/hook/gate module, breaking it | med | high | ADR-004 scope = subcommand-bearing only; Phase 0 `shape` field is the gate; T-C1 flagonly registration proves exemption |
| Multi-owner verb → wrong/ambiguous redirect | med | med | reverse index returns a set; guard lists all owners (ADR-004); Phase 0 asserts a known collision |
| autopilot Typer vs dot-form validation drift | med | med | shared validation helper + parity test (ADR-003) |
| T-C2 invocation causes side effects (worktree cleanup-all/drain/prune-branches mutate on bare invocation) | **high** | **high** | shape-split invocation (ADR-005): manual-dispatch mutating subcommands recognition-checked via the guard with a stubbed handler or a sandboxed `git init` tmp + `monkeypatch.chdir`, NEVER bare-invoked in the real cwd; only arg-gated subcommands live-invoked |
| Re-render churn breaks snapshot tests | med | low | run full snapshot suite in Phase 1; mask volatile fields |
| Non-uniform entry names miss a module | med | med | Phase 0 `entry` field enumerated per module (`main`/`_cli`/`__main__`) |

## ✅ Success Criteria

- [ ] `python -m harness_maker.autopilot on/off` works (dot-form); Typer alias retained;
      both share one validation helper.
- [ ] Any `python -m harness_maker.<subcommand-bearing-mod> <wrong-verb>` prints a
      registry-driven did-you-mean (all owners when the verb is owned elsewhere), exits 2.
- [ ] Flag/hook/gate modules are guard-exempt and unaffected.
- [ ] `command_registry.py` is the single source of truth; guard + both tests import it.
- [ ] T-C1 and T-C2 hard-fail on injected drift; green on `main`.
- [ ] Full `ruff check` + `mypy --strict` + `pytest` green.
- [ ] No user-facing behavior change; un-re-rendered harnesses keep working.

## 🔍 Plan Validation

**Round 1 — plan-validator (opus): MAJOR_REVISION.** 3 critical + 2 warning + 2 suggestion.
All resolved in this revision:
- **C1 (scope 12 vs 35 modules)** → ADR-004 + ADR-006 pin scope to subcommand-bearing
  modules; flag/hook/gate modules enumerated as guard-exempt.
- **C2 (T-C2 introspection infeasible: worktree manual-dispatch, autopilot shape, dest
  names)** → ADR-005 reframes T-C2 as behavioral parity (invoke + assert not-misrouted),
  uniform across all three shapes.
- **C3 (reverse-index verb collisions write/read/validate)** → ADR-002/004 multi-owner
  `resolve_owners -> frozenset`; guard lists all owners; Phase 0 exit asserts a collision.
- **W4 (Typer alias validation not extracted)** → ADR-003 + Phase 1 add a shared validation
  helper + parity test.
- **W5 (T-C1 over-match hook/gate + Jinja tokens)** → ADR-005 T-C1 runs on rendered assets,
  flagonly modules validated on module-existence only.
- **S6 (TYPER_ALIASES vs TYPER_COMMANDS)** → standardized on `TYPER_ALIASES`.
- **S7 (pin enumeration)** → full module table pinned in Technical Design + ADR-006.

**Round 2 — plan-validator (opus): re-validation.** Confirmed **all 7 round-1 findings
genuinely closed**. Found 1 NEW critical introduced by the C2 fix + 1 warning + 1
suggestion — all resolved in-plan (no 3rd validator pass, per the "re-run once only /
no-infinite-loop" rule; resolution path recorded here):
- **R2-C1 (behavioral T-C2 destroys real worktrees)** — `worktree` cleanup-all/drain/
  prune-branches/finalize/task-land/post-commit-pop EXECUTE on bare invocation (no arg
  gate) against `Path.cwd()`. → ADR-005 + Phase 3 + Risks now split T-C2 invocation by
  shape: manual-dispatch mutating subcommands are recognition-checked via the guard
  (stubbed handler) or a sandboxed `git init` tmp, never bare-invoked; only arg-gated
  subcommands are live-invoked.
- **R2-W2 (shape enum vs guard-scope predicate)** — guard scope is now `bool(spec.subcommands)`
  (non-empty subcommand set), not shape membership; `shape` demoted to a T-C1/T-C2 dispatch
  hint (ADR-004, ADR-006). autopilot `{on,off}` is guarded regardless of parser shape.
- **R2-S3 (Phase 2 wording)** — muddled parenthetical replaced with the correct
  `spec_need write` multi-owner example.

**Validator convergence:** round 1 surfaced 7 (structural); round 2 confirmed those closed
and surfaced 1 fix-induced critical + 2 minor, now resolved. Outcome recorded as
MAJOR_REVISION_RESOLVED with the full resolution path above (per the stage's
"resolution path fully recorded" completion condition).
