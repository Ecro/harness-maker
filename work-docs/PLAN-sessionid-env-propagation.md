---
type: plan
task_slug: sessionid-env-propagation
status: complete
created: 2026-08-02
tags: [harness-maker, plan, python, readiness, autopilot, env-propagation, test-isolation]
interview_rounds: 5
adrs: 7
validator_outcome: MAJOR_REVISION_RESOLVED
validator_passes: 2
post_pass2_revision_unvalidated: true
summary: "HM_SESSION_ID is set-but-unexported; route it to subprocesses by explicit argument"
---

# PLAN — sessionid-env-propagation

## 🎯 Executive Summary

**TL;DR.** `HM_SESSION_ID` is not missing. It is set as a **shell variable and never
exported**, so every consumer that interpolates `"$HM_SESSION_ID"` in slash-command Bash
works, and every consumer that reads `os.environ` sees `None`. Route the id to subprocesses
by an explicit argument, correct the documentation that describes the wrong mechanism, and
isolate the tests that read the live environment.

**Why.** Four live defects follow from the one root cause:

1. `readiness.sessionid_envfile_live` reads `os.environ["HM_SESSION_ID"]`, is
   `hard_gate=True`, and floors the `guardrails` dimension to **0 in every real Claude Code
   session** — costing 21 (Side) to 26 (Production) composite points and printing a
   diagnosis that is factually wrong.
2. `autopilot` marker session-scoping reads the same variable, so the marker is **never**
   session-scoped. Verified live: arming and immediately querying reports
   `session_scoped: false`.
3. `tests/integration/test_fresh_install_readiness.py` reads the live environment and
   **fails from inside a Claude Code session** (Side 53 < 66, Production 46 < 72) while
   passing under `env -u CLAUDECODE`. CLAUDE.md's release procedure tells the operator to
   run this suite locally; from a Claude session it is unconditionally red.
4. `worktree._emit_stage_span` (:4262) and `_span_end_session_id` (:5048) use the same dead
   fallback, so every stage span emitted without an explicit `--claude-session-id` is
   session-less. Only `loop.md.j2:431,439` and `plan.md.j2:108` pass that flag, so
   `ambiguous_session_join` is structurally elevated for every other stage — **universally,
   not "on WSL2"**. Found by the plan-validator, not by the interview.
5. **Autopilot is already dark for `autonomy.autopilot_persistent: true` harnesses.**
   `hooks/autopilot_autoarm.py:33-43` deliberately threads `claude_session_id` from the
   SessionStart payload, so those markers are **already id-bearing**. The Bash-side
   `autopilot_caps boundary` then resolves id-less → `_is_own` false (`autopilot.py:373-374`)
   → `active_marker` `None` (`:546`) → `kill_switch`. This is a present-tense outage, not a
   hypothetical one; ADR-005 restores it rather than merely guarding against it. Found by
   the plan-validator's second pass.

**Key decisions.** ADR-001 (explicit-argument channel, tri-state `None`/`""`/value) ·
ADR-002 (root-conftest isolation with a declared opt-out) · ADR-003 (the narrative is
corrected **per context**, not blanket) · ADR-004 (absent case is a weight-0 self-accusing
signal, with its real surfacing channels named) · ADR-005 (autopilot uses the same channel,
**atomically**) · ADR-006 (`hard_gate` retained) · ADR-007 (span consumers included).

**Estimated impact.** `guardrails` returns from 0 to 100 in a healthy session; Production
composite recovers ~26 points. No user-facing behaviour of `/hm:loop` changes — it was never
actually broken.

## 📚 Prior Work

- **`[fail:design] runtime-env-gate-dead-on-arrival`** (2026-06-21) — the direct precedent.
  That fix moved the *session gate* from `CLAUDE_ENV_FILE` (hook-only) to `CLAUDECODE`
  (exported). This PLAN fixes the same class one layer down, in the *value* read. Its
  governing lesson: **a check that reads a runtime env var to gate behaviour needs a live
  probe in the target execution context; code review cannot verify env propagation.**
- **`[fail:design] invariant-changed-gates-not-rechecked`** (2026-08-01) — when a variable's
  *meaning* changes, every predicate reading it must be re-derived. This PLAN's own first
  draft committed that error twice (see the Interview Transcript, Round 5), which is why
  Phase 4 is a re-derivation pass rather than a copy-edit.
- **Global CLAUDE.md correction 2026-06-08** — "Absent-case = feature black hole" (count:8,
  most-recurring). ADR-004 exists solely to discharge it.
- `readiness._score_signals`'s own ADR-004 comment already documents the >100 additive sum
  that Round 4 rediscovered — the codebase knew, and the knowledge had not reached the
  callers choosing weights.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | Scope | Scope boundaries | How wide is this PLAN? | signal + tests | Two faces of one runtime-env assumption | — |
| 2 | Autopilot arming | Risk tolerance | Run this session on autopilot? | autopilot | Armed `auto_safe`, 7-stage pipeline | — |
| 3 | id channel | Architecture | How do subprocesses obtain the session id? | explicit arg | `export` semantics of the env-file are undocumented; a wrong guess kills the working shell path too | ADR-001 |
| 4 | Test isolation | Testing depth | Where does env isolation live? | root conftest autouse | `tests/unit/conftest.py` already pins; lift to root | ADR-002 |
| 5 | Narrative | Contract shape | How far to correct "empty on WSL2"? | all sites | **Amended by #11** | ADR-003 |
| 6 | Absent case | Failure handling | Behaviour with no `--session-id`? | tri-state self-accusing | Silent N-A reproduces 2026-06-21 exactly | ADR-004 |
| 7 | autopilot scope | Scope boundaries | Include autopilot session-scoping? | include | Same channel; override param already exists | ADR-005 |
| 8 | Gate strength | Risk tolerance | Keep `hard_gate` for genuine degradation? | keep | Genuine degradation self-stops `/hm:loop` after one iteration | ADR-006 |
| 9 | Unrendered harness | Failure handling | Grade for a stale render? | weighted non-gating | **Superseded by #10** | ADR-004 |
| 10 | Weight efficacy | Risk tolerance | New evidence: a ≤45-weight fail moves `guardrails` by zero | weight-0 + list visibility | Claiming a score effect that is provably 0 is a fake gauge | ADR-004 |
| 11 | ADR-003 premise | Contract shape | Validator refuted the blanket correction — `-z` branches are shell-context and fire correctly in Cursor/Codex | context split | "empty" is **correct** for shell sites, wrong only for `os.environ` sites | ADR-003 |
| 12 | span consumers | Scope boundaries | Validator found two more dead fallbacks at `worktree.py:4262,5048` | fix them (Phase 5) | Same root cause; deferring pays the re-investigation cost twice | ADR-007 |

**Rounds 4 and 5 were opened by evidence, not by the user.** Round 4: drafting established
that the Round-3 choice ("a weighted fail that shaves the composite") is arithmetically
impossible in `guardrails`, whose weights sum to 145 against a cap of 100 — answer #9 was
withdrawn. Round 5: the `plan-validator` returned MAJOR_REVISION, refuting the ADR-003
premise and surfacing two consumers the interview never reached.

## 📐 Architecture Decision Records

### ADR-001: Subprocess session id arrives by explicit argument, not by environment
**Status:** Accepted (2026-08-02, via /hm:plan interview)
**Context:** `hooks/sessionid_envfile.py:49` writes `HM_SESSION_ID=<v>` to `$CLAUDE_ENV_FILE`.
Claude Code sources that file into the Bash-tool shell, producing a **shell variable, not an
exported one**. Confirmed live: `echo "$HM_SESSION_ID"` prints the id while
`env | grep -c '^HM_SESSION_ID='` returns 0 and `os.environ.get("HM_SESSION_ID")` returns
`None`.
**Decision:** The slash-command shell — the only context that can see the value — passes it
explicitly (`--session-id "$HM_SESSION_ID"`). Python entry points accept an optional
keyword-only `session_id: str | None`, preferring the argument and falling back to
`os.environ`.
**Consequences:**
- ✅ Verifiable end-to-end without restarting a session; no dependence on undocumented
  env-file parser semantics.
- ✅ Reuses a shape already in the codebase — `autopilot.py:354`'s `session_id` override and
  `worktree create --claude-session-id`.
- ⚠️ **`None` and `""` are different states and must stay different — on the READINESS path.**
  `None` = the caller did not wire the probe. `""` = the caller wired it and the value was
  genuinely absent. Collapsing them there re-creates the bug this ADR removes.
- ⚠️ **The invariant does NOT extend to autopilot, and must not be retrofitted there.**
  `autopilot.py:242` (`effective_session_id = claude_session_id or _env_session_id()`) and
  `:371` (`env_id = session_id or _env_session_id()`) already treat `""` exactly like
  `None`. Since the 14 rendered call sites pass `--session-id "$HM_SESSION_ID"`
  unconditionally, Cursor/Codex/degraded sessions deliver `""`. **Phase 2's rule, stated
  once:** on the autopilot path `""` means id-less — env fallback, project-uuid ownership,
  exactly today's behaviour — and no new signal is emitted.
- ⚠️ **The call graph has an intermediate hop.** `cli.health_cmd` (`cli.py:1574`) does not
  call `compute_readiness`; it calls `ai_readiness.run_structural`, which calls it at
  `ai_readiness.py:128`. Two siblings do the same at `:64` (`run_ai_readiness`) and `:90`
  (`run_ai_readiness_structural`). All three must be threaded or the argument reaches
  nothing. `improvement.py` does **not** call `compute_readiness` (grep-verified — it only
  mentions it in a docstring); the first draft named it as the back-compat caller and was
  wrong.
**Rejected alternatives:**
- *Hook writes `export HM_SESSION_ID=…`* — Rejected because the env-file format is
  documented as `KEY=value` and nothing states whether a leading `export ` is stripped or
  absorbed into the key name. If absorbed, the currently-working shell path dies with it,
  observable only in a fresh session.
- *Probe `export` first, then choose* — Rejected as the primary path: it needs a session
  restart mid-plan and forces the PLAN to carry both branches.
**Source:** Interview #3, amended by plan-validator (call-graph correction)

### ADR-002: Environment isolation lives in a new root `tests/conftest.py`, with a declared opt-out
**Status:** Accepted (2026-08-02, via /hm:plan interview)
**Context:** `tests/unit/conftest.py:23-30` already pins `CLAUDECODE`, `CLAUDE_ENV_FILE` and
`HM_SESSION_ID` out — added by the 2026-06-21 fix for exactly this hazard.
`tests/{integration,e2e,render,structural}/conftest.py` do not, so
`test_fresh_install_readiness` reads the developer's live session. There is no
`tests/conftest.py`.
**Decision:** Create `tests/conftest.py` with an autouse fixture performing the three
`monkeypatch.delenv(..., raising=False)` calls; remove the duplicated block from
`tests/unit/conftest.py`. **The opt-out is specified here, once:** the fixture is a no-op for
a test carrying `@pytest.mark.live_env`, and that marker is registered in `pyproject.toml`.
**Consequences:**
- ✅ One owner. Every current and future test directory inherits it.
- ✅ Tests that must observe the live env have a named, greppable mechanism instead of an
  improvised `setenv`-after-autouse that depends on unpinned fixture ordering.
- ⚠️ Any test that legitimately needs the live env must be found and marked; an unmarked one
  silently gets the pinned environment.
**Rejected alternatives:**
- *Add the pin to `tests/integration/conftest.py` only* — Rejected: fixes the one file that
  broke and leaves `e2e`, `render`, `structural` to break the same way later.
- *Leave the opt-out unspecified* — Rejected: the executor would improvise it, and the
  improvised form is what later tests copy.
**Source:** Interview #4, amended by plan-validator (opt-out was asserted but undefined)

### ADR-003: The narrative is corrected **per context** — shell sites are already right
**Status:** Accepted (2026-08-02, via /hm:plan interview Round 5; supersedes the blanket
correction first drafted)
**Context:** Several sites assert the variable is *empty* in the degraded case. The first
draft treated all of them as wrong. The plan-validator refuted that: `loop.md.j2:520,524`
evaluate `[ -z "$HM_SESSION_ID" ]` **in shell**, the one context where the variable is
visible. Those branches are **correct and live** — they fire in Cursor and Codex (where the
variable is structurally absent) and on a genuine SessionStart-hook failure, and the inner
`[ -n "$CLAUDECODE" ]` sub-branch exists precisely to tell those two apart.
**Decision:** Split the sites by execution context.
- **Shell-context sites (correct — do not touch the condition):** `loop.md.j2:502,514,520,524`.
  Only their *attribution* changes: the case is Cursor/Codex/hook-failure, not "WSL2".
- **Python/`os.environ` sites (wrong — the mechanism is unexported, not empty):**
  `readiness.py:991-1030`, `stage_spans.py:181`, `worktree.py:2398-2399`, `metrics.md.j2:220`,
  and the CLAUDE.md loop-marker section.
**Consequences:**
- ✅ The next reader cannot re-derive the wrong probe from the wrong premise — which is
  exactly how this defect was produced.
- ✅ A currently-correct guard is not "corrected" into incoherence. Acting on the blanket
  premise would have been the same class of error this PLAN exists to fix.
- ⚠️ Touches `readiness.py` and `worktree.py`, forcing serial ordering against Phases 1 and 5.
**Rejected alternatives:**
- *Blanket correction of all six sites* — Rejected on the validator's evidence: it would
  rewrite a live guard's explanation to say its case cannot occur.
- *Delete the `-z` branches as dead code* (antigravity's proposal) — Rejected: they are not
  dead; they are the Cursor/Codex path.
**Source:** Interview #5, refuted and re-decided at Interview #11

### ADR-004: The absent case is an explicit weight-0 `sessionid_envfile_probe_wired` signal
**Status:** Accepted (2026-08-02, via /hm:plan interview; amended at #10 and by plan-validator)
**Context:** ADR-001 creates a third state — the caller passed no argument. Leaving it silent
reproduces `runtime-env-gate-dead-on-arrival` verbatim. Interview #9 first chose a weighted
non-gating failure; drafting then established that `guardrails`'s eleven weights sum to
**145** against a cap of 100, so **any single failure of weight ≤ 45 changes the score by
exactly zero**.
**Decision:** Emit a distinct signal `sessionid_envfile_probe_wired` with `weight=0` and
`hard_gate=False` whenever `CLAUDECODE` is set, the harness targets `claude-code`, no
`session_id` argument was supplied, **and** `os.environ` has no fallback value.
`sessionid_envfile_live` is not emitted in that state, so the hard gate cannot fire on a
merely-stale render.
**Consequences:**
- ✅ The dead-on-arrival mode is structurally unreachable: no silent branch remains.
- ✅ The declared weight matches the real effect. A weight of 15 would read as "this costs
  you points" while costing zero — a fake gauge, worse than an honest zero. Precedent for
  weight-0 non-gating signals already exists at `readiness.py:807` and `:883`.
- ⚠️ **The two surfacing channels are asymmetric, and the ADR relies on the weaker one.**
  `/hm:health` runs `run_structural`, whose only signal output is `signals_failed` — bare
  `"<dim>:<signal_id>"` strings (`ai_readiness.py:141-144`) rendered as a flat list, **with
  no remediation text**. The `/harness-maker:make --update` remedy reaches the user only via
  `/hm:ai-readiness`, where `improvement._extract_layer1_actions` turns `_layer1_priority(0)`
  into a P2 `ActionItem`. Accepted: `/hm:health` shows the id alone.
- ⚠️ **That second channel is conditional, so the signal MUST carry a non-null `action`.**
  `improvement.py:102` short-circuits on `if sig.passed or sig.action is None: continue`
  **before** `_layer1_priority` is reached. A `probe_wired` emitted informationally with
  `action=None` — the natural shape for a weight-0 non-gating signal — would silently lose
  the *only* remediation channel this ADR relies on, and the absent-case rule this ADR exists
  to discharge would bite the ADR itself. Phase 1 asserts the signal appears in
  `run_ai_readiness(...).actions` at priority P2 carrying the `--update` remedy.
- ⚠️ The `guardrails` (145) and `workflow_clarity` (130) over-cap is a **latent defect
  affecting their existing signals too**. Recorded in the risk register and in `failures.md`
  at wrapup; rebalancing is explicitly out of scope.
**Rejected alternatives:**
- *Silent N-A* — Rejected: it is the 2026-06-21 failure, restated.
- *`os.environ` fallback alone* — Rejected: unexported means that branch is permanently
  false, so the bug would relocate rather than close.
- *Rebalance `guardrails` to sum to 100 in this PLAN* — Rejected: it moves every existing
  score and re-pins the fresh-install floors, entangling an unrelated correction with a
  regression fix.
**Source:** Interviews #6, #9, #10; consequences corrected by plan-validator

### ADR-005: autopilot uses the same channel, and Phase 2 is **atomic**
**Status:** Accepted (2026-08-02, via /hm:plan interview)
**Context:** `autopilot.py:39` defines `_SESSION_ID_ENV` and reads it from the process
environment; `status()` (:585) has no `session_id` parameter and reads `_env_session_id()`
directly at `:638` and `:658`; `active_marker()` (:527) calls `_is_own(marker, project_root)`
at `:546` with no override. Only `_is_own` (:354) and the arm path accept one today.
**The status quo works only for manually-armed, id-less markers.** For
`autonomy.autopilot_persistent: true` harnesses, `hooks/autopilot_autoarm.py:33-43` already
stamps `claude_session_id` from the SessionStart payload, so the marker is id-bearing **today**
and the id-less Bash-side reader already resolves it as foreign — autopilot is dark there
right now (Executive Summary defect #5). For those harnesses this phase is a **restoration**,
not a regression guard.

**The atomicity requirement is not stylistic.** `_is_own` is **one-directional by design**
(ADR-007 of the autopilot work): ids are compared whenever *either* side has one. So the
moment `autopilot on --session-id <uuid>` writes an id-bearing marker, any consumer that
resolves id-less computes `env_id is None and marker_id is not None` → **foreign** →
`active_marker` returns `None` → `evaluate_boundary` returns
`proceed: false, halt_kind: "kill_switch"`. There are **14 such rendered call sites** (7
stages × `autopilot_caps boundary` + `gate-blocked`). A Phase 2 that lands the marker write
without them **turns autopilot completely off** — a regression created by the fix, worse
than the status quo, in which the id-less marker falls through to the project-scoped
`session_uuid` path and works.
**Decision:** Thread `session_id` through `status`, `active_marker`, `evaluate_boundary` and
the `autopilot_caps` CLI surface, and wire all 14 rendered call sites **in the same phase as
the marker write**. No partial landing is authorised.
**Consequences:**
- ✅ `foreign` / `degraded-idless` stop being the permanent verdict, so the `--force`
  escalation regains meaning.
- ✅ One channel, one mental model, one place to break.
- ⚠️ Phase 2 is large and indivisible. Its exit criterion must probe the *boundary* path,
  not just `on` → `status`, or the dark-autopilot regression ships green.
**Rejected alternatives:**
- *Defer autopilot to its own PLAN* — Rejected: it leaves the marker degraded while the user
  is actively running this session on autopilot.
- *Land the marker write first, wire callers next* — Rejected: that intermediate state is
  precisely the total-outage described above.
**Source:** Interview #7; blast radius established during Step 4 verification

### ADR-006: `sessionid_envfile_live` retains `hard_gate=True`
**Status:** Accepted (2026-08-02, via /hm:plan interview)
**Context:** The gate floors a 0.21–0.26-weight dimension to zero. It looked
disproportionate only because it fired unconditionally.
**Decision:** Keep `hard_gate=True` for the argument-supplied-and-empty state.
**Consequences:**
- ✅ Genuine degradation is severe — a `/hm:loop` started in that state self-stops after
  iteration 1 — and `guardrails`'s over-cap means the hard gate is the only mechanism there
  with any effect at all.
- ⚠️ A genuinely degraded session still drops ~26 composite points; that is now proportionate
  because it is now true.
**Rejected alternatives:**
- *Demote to weight 25* — Rejected on Round 4's arithmetic: 25 < 45, so the demotion is
  indistinguishable from deleting the signal.
**Source:** Interviews #8, #10

### ADR-007: The stage-span consumers are fixed in this PLAN, not deferred
**Status:** Accepted (2026-08-02, via /hm:plan interview Round 5)
**Context:** The plan-validator found two consumers the interview never reached:
`worktree.py:4262` (`_emit_stage_span`, `session_id=claude_session_id or
os.environ.get("HM_SESSION_ID") or None`) and `worktree.py:5048` (`_span_end_session_id`,
same fallback). Only `loop.md.j2:431,439` and `plan.md.j2:108` pass `--claude-session-id`, so
every other stage emits a session-less span and `ambiguous_session_join` is structurally
elevated — **universally, not on WSL2**. `metrics.md.j2:220` currently presents this as a
"stated limit, not an error". (Only `loop.md.j2` passes the flag to a *span-emitting*
command; `plan.md.j2:108` passes it to `worktree loop-mode-active`, which emits no span, so
the plan stage's own span is id-less too.)
**Decision:** Thread the explicit id through both span paths (Phase 5) rather than recording
the corrected, wider scope as a known defect — **but not via `worktree create`.**
> **`--claude-session-id` is PRESENCE-overloaded and MUST NOT be added to `worktree create`.**
> `worktree.py:2402` computes `is_loop_create = "--claude-session-id" in args` — on the flag's
> presence, never its value — and `:2444` stamps the span `hm:loop` on that basis. Adding it to
> `execute.md.j2:78,82` (the only other `worktree create` call site) would therefore (a)
> mislabel every standalone `/hm:execute` span as `hm:loop`, and (b) write a session-bearing
> marker header, which per CLAUDE.md's loop-marker contract makes the Stop-hook `loop_gate`
> content-match and **block a standalone `/hm:execute` from stopping**. The span id is routed
> through `task-preflight` instead (`worktree.py:5107` already parses the flag there and it
> carries no loop meaning on that path).
**Consequences:**
- ✅ One investigation closes all three consumer families; deferring pays the
  re-investigation cost a second time on the same root cause.
- ✅ `metrics.md.j2:220` can state a true limit instead of a WSL2-flavoured one.
- ⚠️ Widens the change surface into `stage_spans` and the metrics verification path, which
  has different evidence requirements from readiness (a span record, not a score).
- ⚠️ A negative render-grep is required, not optional: `execute.md.j2` must never gain
  `--claude-session-id`. The obvious implementation of this ADR is the harmful one.
**Rejected alternatives:**
- *Record as an out-of-scope risk* — Rejected by the user at Interview #12; it would leave
  `metrics.md.j2` documenting a limit whose real scope had silently widened during Phase 4.
- *Add `--claude-session-id` to every `worktree create` call site* — Rejected: it is the
  loop-vs-standalone discriminator, and overloading it hangs standalone `/hm:execute`.
**Source:** Interview #12 (opened by plan-validator); collision found by the validator's
second pass

## 🏗️ Technical Design

**Current state.** `readiness._dim_guardrails` (~`readiness.py:991-1035`) decides `in_session`
from the exported `CLAUDECODE`, then reads the unexported `HM_SESSION_ID` from `os.environ`.
`cli.health_cmd` (`cli.py:1517`) has no session-id parameter and reaches readiness only
through `ai_readiness.run_structural`. `autopilot.py:39` repeats the env read.
`worktree.py:4262,5048` repeat it again.

**Affected components.**

| Component | Change |
|---|---|
| `readiness.py` | `compute_readiness(..., *, session_id: str \| None = None)`; tri-state branch in `_dim_guardrails`; new `sessionid_envfile_probe_wired`; comment block corrected (ADR-003 Python set) |
| `ai_readiness.py` | thread `session_id` through **all three** `compute_readiness` call sites — `run_ai_readiness` (:64), `run_ai_readiness_structural` (:90), `run_structural` (:128) |
| `cli.py` | `health_cmd` gains `--session-id`; threads it through both the `--json-output` early-return (:1572) and the dashboard branch |
| `templates/commands/hm/health.md.j2` | `hm cli health .` gains `--session-id "$HM_SESSION_ID"` |
| `autopilot.py` | `status`, `active_marker` gain `session_id`; prefer it over `_env_session_id()` |
| `autopilot_caps.py` | `evaluate_boundary` + the `boundary` / `gate-blocked` CLI surface gain `--session-id` |
| `stage_end_summary.md.j2` (:44, :54) | the 14 rendered `autopilot_caps` call sites gain `--session-id "$HM_SESSION_ID"` |
| `worktree.py` | `:4262`, `:5048` span-id resolution (ADR-007); `:2398-2399` comment (ADR-003) |
| `tests/conftest.py` (new) | autouse env pin + `live_env` opt-out marker; duplicate removed from `tests/unit/conftest.py`; marker registered in `pyproject.toml` |
| `tests/unit/test_fleet_degraded_floor.py` | `:105-113` asserts `sessionid_envfile_live` **exists** under `claude_session_unset`; must be re-derived against the tri-state |

**Data flow (after).**

```
SessionStart hook ──► $CLAUDE_ENV_FILE ──► sourced into slash-command shell
                                            │  (shell var, NOT exported — unchanged)
                                            ▼
                   !uv run … --session-id "$HM_SESSION_ID"
                                            │
            ┌───────────────────────────────┼───────────────────────────┐
            ▼                               ▼                           ▼
   cli.health_cmd                 autopilot / autopilot_caps      worktree span emit
            │                        (marker + 14 call sites)             │
   ai_readiness.run_structural                                    _emit_stage_span
            │
   compute_readiness(session_id=…)
            │
   ┌────────┼────────────────┐
   ▼        ▼                ▼
 None      ""            non-empty
(+env    (truly         (healthy)
 unset)  degraded)
   │        │                │
probe_    live=False      live=True
wired     w=0, HARD        pass
w=0,      GATE
no gate
```

**Design decisions.** The tri-state rides on `str | None` because typer already produces
exactly that shape: omitting the flag yields `None`, and `--session-id "$UNSET"` yields `""`.
No new type is introduced.

**API changes.** `compute_readiness` gains a keyword-only optional parameter — additive, so
the three `ai_readiness` call sites and every test call keep working unchanged. Under
ADR-002's isolation `CLAUDECODE` is deleted, so `_dim_guardrails`'s `if claude_target and
in_session:` gate (`readiness.py:1009`) is false and **no** signal is emitted — a true N-A,
not a suppressed failure.

## 📝 Implementation Plan

> **Execution status (2026-08-02).** Phases 1–5 **DONE**. Phase 6 (release mechanics)
> **NOT STARTED**.
> Changes are uncommitted on `hm/sessionid-env-propagation`; nothing has been landed.
>
> **Carried to Phase 6 (blocked here by design, not skipped):**
> `tests/structural/test_surface_baseline.py` is RED — the shipped Claude surface grew
> 1065 chars (851807 → 852872), the honest cost of `--session-id "$HM_SESSION_ID"` on 14
> `autopilot_caps` call sites + 2 picker lines + `health.md.j2`.
> `_surface_baseline.py:156-178` **refuses to freeze from a task branch** (a squash-land
> deletes the commit the baseline would name), and freezing now would pin it to
> `5da8f995`, which does not contain these template changes. Correct sequence, per
> `[fail:test] snapshot-regen-inside-worktree`: run tests from the worktree → land →
> re-freeze from the base checkout → full suite from the base.

### Phase 1 — readiness tri-state and its full call chain
**Status: DONE** — 30 new/re-derived tests GREEN; `ruff` + `mypy --strict` clean; the
targeted set selected by `test_dep_map` (186 + 81 tests) GREEN. Live probe from inside a
Claude Code session against the base project: `guardrails` 0 → **100**, Production composite
55 → **81**. With the flag, neither tri-state signal fails; without it,
`sessionid_envfile_probe_wired` fails and the structural score is **unchanged at 82** —
confirming ADR-004's weight-0 claim empirically rather than by assertion.
Two pre-existing tests beyond the ones named in scope (`test_readiness_sessionid_live.py`
`:85`, `:139`) asserted the live signal in the now-`probe_wired` state and were re-derived
to `session_id=""`, preserving their original assertions.

- `depends_on`: `[]`
- `parallel_group`: `serial-main`
- `merge_hazards`: `readiness.py` (also edited by Phase 4); `tests/snapshot/*.expected.yaml`
- **Scope in:** `readiness.py`, **`ai_readiness.py` (all three call sites)**, `cli.py`
  (`health_cmd`, both branches), `templates/commands/hm/health.md.j2`,
  `tests/unit/test_readiness*.py`, **`tests/unit/test_fleet_degraded_floor.py`**
- **Scope out:** `autopilot.py`, weight rebalancing, `_CONTEXT_LIMITS`
- **Exit criterion (runnable as written):**
  `uv run pytest tests/unit -q -k 'readiness or fleet_degraded'` green, **and** from inside a
  Claude Code session:
  `uv run hm cli health . --session-id "$HM_SESSION_ID" --json-output /tmp/a.json` then
  `jq -r '.structural.signals_failed[]' /tmp/a.json | grep -c '^guardrails:sessionid_envfile_'`
  → `0`; the same command **without** the flag → exactly `1`, matching
  `guardrails:sessionid_envfile_probe_wired`. (`health_cmd` prints only a composite, so the
  JSON sink is the probe; the key is nested under `.structural`, per `cli.py:1562-1566`.)
  Plus a unit assertion that `probe_wired` reaches `run_ai_readiness(...).actions` at P2 —
  ADR-004's remediation channel is `action`-gated at `improvement.py:102`.
- **Risk:** `medium` — collapsing `None` and `""` silently restores the defect.
- **Rollback:** revert to base HEAD.

### Phase 2 — autopilot explicit-argument plumbing (ATOMIC — see ADR-005)
**Status: DONE** — landed atomically: `autopilot.active_marker`/`status` +
`autopilot_caps.evaluate_boundary` + both CLI subcommands + the `autopilot` CLI itself
(`on` is the writer — arming with an id the readers cannot match is the same split from
the other side) + all 14 rendered `autopilot_caps` sites (one partial × 7 stages) + both
picker lines. 16 new tests and the 193-test existing autopilot suite GREEN; `ruff` +
`mypy --strict` clean; the `test_instruction_preservation` ratchet given an explicit
`_ALLOWED_REMOVALS` entry built from `ATOMIC_COMMANDS` (a hand-typed list could omit one
stage, and an omitted stage IS the forbidden partial landing).

**R3 demonstrated live rather than argued.** Same marker, same environment, one
throwaway project — a wired reader gets `active: true, reason: "armed",
session_scoped: true`; an un-wired reader gets `active: false, reason:
"degraded-idless"`. That second line is autopilot off, and it is what a partial landing
ships. The probe was deliberately NOT run against this repo's own marker: re-arming the
real base with an id, while the base's rendered commands are still the un-wired ones,
would have wedged this very session — R3 reproducing itself during its own verification.

- `depends_on`: `[1]`
- `parallel_group`: `serial-main`
- `merge_hazards`: `tests/snapshot/*.expected.yaml`; rendered stage bodies shared with Phase 4
- **Scope in:** `autopilot.py` (`status`, `active_marker`), `autopilot_caps.py`
  (`evaluate_boundary` + `boundary` / `gate-blocked` CLI), the picker partial, **all 14
  rendered `autopilot_caps` call sites** in `stage_end_summary.md.j2:44,54`,
  `tests/unit/test_autopilot_*.py`
- **Scope out:** ledger vocabulary, cap logic, marker TTL/GC
- **Exit criterion:** (a) a **unit** test builds an id-bearing marker and asserts
  `evaluate_boundary(..., session_id=<id>)` returns `proceed: true` while the id-less resolve
  returns `kill_switch` — this is the real ownership proof and `evaluate_boundary` is pure
  (`autopilot_caps.py:56`); (b) live, from inside a Claude Code session,
  `hm autopilot on --session-id "$HM_SESSION_ID" …` then
  `hm autopilot status --root . --session-id "$HM_SESSION_ID"` reports `session_scoped: true`;
  (c) a render-grep asserts all 14 sites carry the flag.
  > Do **not** use the `autopilot_caps boundary` CLI as the probe. It is not read-only:
  > `:248-249` calls `autopilot.touch()` + `_confirm_entry()`, polluting the smoke denominator
  > and the step-cap numerator, and on the last pipeline stage `:310` calls `autopilot.clear()`,
  > disarming the marker. `:259` also returns `unknown_stage` when `--current` is not in the
  > armed pipeline — a false negative unrelated to this fix.
- **Risk:** `high` — a partial landing turns autopilot fully off (ADR-005).
- **Rollback:** revert to end of Phase 1.

### Phase 3 — root conftest isolation
**Status: DONE** — `tests/conftest.py` owns the pin, `tests/unit/conftest.py`'s copy is
gone, `live_env` is registered in `pyproject.toml`. `test_fresh_install_readiness` now
passes **from inside a Claude Code session**, which is the condition that started this
work. The gate is hostile to its own absence: `test_env_isolation.py` runs an inner pytest
in a subprocess with all three variables set and asserts it comes back green, plus a
meta-check that defeats the pin and asserts the probe goes red. Both weaker forms the
validator rejected were tried and discarded — a vacuous `os.environ is None`, and
composite equality (Phase 1's guarantee, not this phase's).

The probe directory is removed with `rmtree`, not `rmdir`: pytest leaves a `__pycache__`,
and a surviving `tests/_env_isolation_probe/` trips this repo's unclassified-test-directory
gate. That gate caught it — the same "a new test directory inherits nothing" rule
(`[fail:test] snapshot-regen-inside-worktree` instance 13) this phase exists to satisfy.

- `depends_on`: `[1]`
- `parallel_group`: `serial-main`
- `merge_hazards`: `tests/unit/conftest.py`; `pyproject.toml` (marker registration)
- **Scope in:** new `tests/conftest.py` (autouse pin + `live_env` opt-out), `pyproject.toml`
  marker registration, removal of the duplicated `tests/unit/conftest.py` block, new
  `tests/integration/test_env_isolation.py`
- **Scope out:** changing the floors or assertions of `test_fresh_install_readiness`
- **Exit criterion (hostile to its own absence):**
  `tests/integration/test_env_isolation.py` spawns an **inner pytest as a subprocess** with
  `env={**os.environ, "CLAUDECODE": "1", "CLAUDE_ENV_FILE": "/tmp/x", "HM_SESSION_ID": "probe"}`
  running a test that asserts all three resolve to `None`, and asserts the inner run is green.
  It then fails deterministically — in CI too — when `tests/conftest.py` is missing.
  > Two weaker forms were rejected. A bare in-process `assert os.environ.get(k) is None`
  > passes **vacuously** anywhere the vars are not set (CI, `env -u CLAUDECODE`, any non-Claude
  > shell), with no root conftest at all. And composite **equality** under set/unset is
  > guaranteed by Phase 1 alone — both signals are weight-0 (`readiness.py:1016`) and
  > non-gating after Phase 1, so the composites coincide whether or not this phase exists.
  > Both would be green with Phase 3 deleted, which is the defect this criterion replaces.
- **Risk:** `low`
- **Rollback:** delete `tests/conftest.py`, restore the `tests/unit/conftest.py` block.

### Phase 4 — narrative correction, split by context (ADR-003)
**Status: DONE** — Scope A (`readiness.py`, `stage_spans.py`, `metrics.md.j2`, CLAUDE.md)
each names `unexported`; two more `os.environ` sites the plan had not enumerated
(`worktree.py:2448`, `:5033`) were found by the exit-criterion grep and corrected too.
Scope B (`loop.md.j2`, `worktree.py:2398`, CLAUDE.md's fleet paragraph) had only its
attribution changed. **The four `[ -z "$HM_SESSION_ID" ]` predicates in `loop.md.j2` are
byte-identical to base** — extracted and diffed, not eyeballed. That was the whole point
of the context split: the first draft would have "corrected" a guard that is right.

- `depends_on`: `[1, 2]`
- `parallel_group`: `serial-main`
- `merge_hazards`: `readiness.py` (Phase 1), `worktree.py` (Phase 5), rendered surfaces
  (Phase 2), `tests/snapshot/*.expected.yaml`
- **Scope A — mechanism is wrong (`os.environ` readers; must say `unexported`):**
  `readiness.py:991-1030`, `stage_spans.py:181`, `metrics.md.j2:220`, CLAUDE.md loop-marker
  section. **Four sites, not five.**
- **Scope B — mechanism is right, attribution is wrong (edit prose only, conditions frozen):**
  `worktree.py:2398-2399` (a Python comment *about* a shell-context value — the flag arrives
  with a real id on a healthy session, so "empty" is correct there and writing `unexported`
  would re-introduce the very premise this PLAN removes), and `loop.md.j2:496,502,505,514,520,524,531`
  (`:505` carries the WSL2 attribution the first draft never enumerated). In both, replace the
  WSL2 attribution with Cursor/Codex/hook-failure.
- **Frozen — byte-identical to base:** the `[ -z "$HM_SESSION_ID" ]` conditions at
  `loop.md.j2:520,524`. Scope B edits their *surrounding prose*, never the predicates.
- **Exit criterion:** (a) a fixed-file-list grep over Scope A returns zero emptiness claims
  and each of the four contains `unexported`; (b) `loop.md.j2` contains no `WSL2` attribution;
  (c) its two `-z` conditions are byte-identical to base (`git diff` on those lines is empty).
  A bare repo-wide regex is not falsifiable — it legitimately hits the correct shell-context
  sites, turning the gate into a human judgement call.
- **Risk:** `low`
- **Rollback:** revert to end of Phase 2.

### Phase 5 — stage-span consumers (ADR-007)
**Status: DONE, and smaller than planned.** `_cli_task_preflight` already parsed
`--claude-session-id` and already threaded it through `task_preflight` →
`_emit_stage_span` (`worktree.py:4270`); the template was the only missing link. So the
fix is two template lines, not a Python change — and it lands on `task-preflight`, never
`worktree create`, exactly as ADR-007 requires.

**R9 did not fire.** `test_worktree_create_never_gains_claude_session_id` is green, and
`execute.md.j2` carries no such flag. The render guards also gained an `_unescaped()`
normaliser: the Codex branch ships the same instruction with escaped quotes, and the first
version of the guard passed that spelling by accident — a guard that knows one spelling is
half a guard.

**Size ratchet, resolved by compaction rather than by raising a ceiling.** The flags cost
+2283 chars; `plan` (+31) and `wrapup` (+18) went over their per-command ceilings. Per the
bar `test_command_size_budget.py` sets (ADR-011: never raise a ceiling to pass a phase),
two compactions were done first — the `loop.md.j2` degraded-path prose and the
`stage_end_summary` NO-OP paragraph — and they absorbed **both** ceilings entirely
(1617 residual, all of it in the aggregate arm). No ceiling was moved.

The compaction is visible in two more ratchets, both updated with the reason rather than
silently: `test_render_worktree_preflight`'s golden block (the flag is now in the rendered
prose) and `test_render_wrapup_delegation`'s line counts, which went **down** 628→627 /
661→660. That direction is the point — the ratchet is being tightened, not loosened.

- `depends_on`: `[1, 2]`
- `parallel_group`: `serial-main`
- `merge_hazards`: `worktree.py` (Phase 4 edits a comment in the same file)
- **Scope in:** `worktree.py:4262` (`_emit_stage_span`), `worktree.py:5048`
  (`_span_end_session_id`), and — enumerated, per ADR-007's routing constraint —
  `templates/agents/_partials/worktree_preflight.md.j2:23,27` (the `task-preflight` path,
  shared by every stage). `stage_spans.py` tests.
- **Scope out:** the `ambiguous_session_join` metric definition; **and `worktree create` —
  `templates/stages/execute.md.j2:78,82` must NOT gain `--claude-session-id`** (ADR-007).
- **Exit criterion:** a stage span emitted from a stage **other than** loop carries a non-null
  `session_id`, verified by reading the emitted span record; **plus a negative render-grep
  asserting `execute.md.j2` contains no `--claude-session-id`**, and an assertion that a
  standalone `/hm:execute` span is still stamped `hm:execute`, not `hm:loop`;
  `uv run pytest -q -k 'stage_span or span'` green.
- **Risk:** `medium` — touches the metrics path, whose evidence is a record rather than a
  score.
- **Rollback:** revert to end of Phase 4.

### Phase 6 — release mechanics
**Status: PARTIAL.** Done here: five-file bump to 0.46.0 + `uv.lock`, the CHANGELOG entry,
the `tests/snapshot/*.expected.yaml` re-freeze (only `body_sha256` moved — no path or
structural change, and a grep confirms no worktree path leaked, per the 2026-07-26
supersede of `[fail:test] snapshot-regen-inside-worktree`), and both `failures.md` entries
(the unexported-env class, and the over-cap latent defect ADR-004 promised to record).

**Blocked until land — structurally, not by omission:** `test_surface_baseline` and
`test_command_size_budget::test_aggregate_shipped_surface_does_not_grow` (+1617 chars).
`_surface_baseline.py:156-178` refuses to freeze from a task branch because a squash-land
deletes the commit the baseline would name. Re-freeze from the base checkout after landing,
then run the full suite there.

- `depends_on`: `[1, 2, 3, 4, 5]`
- `parallel_group`: `serial-release`
- `merge_hazards`: the five version files must move together (CLAUDE.md 버전업 정책)
- **Scope in:** five-file bump to **0.46.0**, CHANGELOG, snapshot re-freeze, `failures.md`
  entries for (a) the over-cap latent defect and (b) the set-but-unexported class
- **Scope out:** tagging and pushing (user-initiated per CLAUDE.md git policy)
- **Exit criterion:** `uv run ruff check . && uv run mypy --strict src/harness_maker && uv run pytest -q`
  all green, and the five version strings identical.
- **Risk:** `low`
- **Rollback:** revert to end of Phase 5.

## 🧪 Testing Strategy

**Unit.** The tri-state is the core: parametrise `(session_id=None, "", "abc")` ×
`(CLAUDECODE set / unset)` and assert which signal is emitted, its `weight`, and its
`hard_gate`. One regression test asserts `None` and `""` produce **different** signal ids —
the single invariant whose loss restores the bug. `test_fleet_degraded_floor.py:105-113`
must be re-derived: it currently asserts `sessionid_envfile_live` *exists* in the exact state
that ADR-004 reassigns to `probe_wired`. Autopilot gets the mirrored trio on marker
read/write plus a foreign-marker case proving the ADR-005 outage cannot recur.

**Integration.** `tests/integration/test_env_isolation.py` is new and owns the ADR-002
guarantee (equality under both env states). `test_fresh_install_readiness` keeps its floors
and gains the `live_env`-marked parametrisation.

**Render.** Render-grep tests assert `health.md.j2` and all 14 `autopilot_caps` sites emit
`--session-id "$HM_SESSION_ID"`. This is the CI guard against a future template edit silently
un-wiring the probe; ADR-004's signal is the runtime backstop for the same failure.

**Manual (required, not optional).** Phases 1, 2 and 5 all have **live probes from inside a
real Claude Code session** as exit criteria. Per
`[fail:design] runtime-env-gate-dead-on-arrival`, code review cannot substitute for this;
that lesson is why the probes are exit criteria rather than a checklist appendix.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `None`/`""` collapse in a later refactor restores the original defect | medium | high | Dedicated unit test asserting different signal ids; ADR-001 states the invariant |
| R2 | A call site is added later without `--session-id`, silently un-wiring the probe | medium | medium | ADR-004's `probe_wired` at runtime + render-grep at CI |
| R3 | **Phase 2 lands partially and turns autopilot fully off** | **certain** for `autopilot_persistent` harnesses (already dark today); medium otherwise | **critical** | ADR-005 declares the phase atomic; the exit criterion is a pure-function `evaluate_boundary` ownership test plus a foreign-marker unit test |
| R9 | **Phase 5 adds `--claude-session-id` to `worktree create`, hanging standalone `/hm:execute`** | medium (it is the obvious implementation) | **critical** | ADR-007 forbids it in a call-out block; Phase 5 scope-out names the file and lines; negative render-grep + an `hm:execute`-not-`hm:loop` span assertion in the exit criterion |
| R4 | The `guardrails` 145 over-cap makes ADR-004's signal invisible to score-readers | certain | low | Accepted and documented; `signals_failed` still lists it and `/hm:ai-readiness` still raises a P2 item; recorded to `failures.md` |
| R5 | Phase 4 "corrects" a shell-context site that was already right | low | medium | ADR-003's context split names the untouched files explicitly; the exit criterion greps a fixed Python-only file list |
| R6 | Users on a stale render see a new failing item after upgrade | certain | low | Weight 0, no score movement; remedy text reaches `/hm:ai-readiness`, and `/hm:health` shows the id |
| R7 | An existing test needing the live env is not marked `live_env` and silently gets the pinned env | medium | low | Phase 3 greps for `CLAUDECODE`/`HM_SESSION_ID` reads across `tests/` before landing |
| R8 | Snapshot churn across Phases 1/2/4/5 causes merge conflicts | high | low | All phases are `serial-*`; no parallel execution is authorised |

## ✅ Success Criteria

- [x] `guardrails` scores 100 in a healthy Claude Code session (currently 0)
- [x] Production fresh-install composite ≥ 72 with `CLAUDECODE` set (currently 46)
- [x] Fresh-install composite is **identical** with `CLAUDECODE` set and unset
- [x] `hm autopilot status --session-id …` reports `session_scoped: true` **and**
      `autopilot_caps boundary --session-id …` returns `proceed: true`
- [x] All 14 rendered `autopilot_caps` call sites carry `--session-id`
- [x] `sessionid_envfile_live` and `sessionid_envfile_probe_wired` are never both emitted
- [x] A span from a non-loop stage carries a non-null `session_id`
- [x] No Python-context site asserts `$HM_SESSION_ID` is *empty* as the mechanism; the
      shell-context branches are unchanged
- [x] Five version files at 0.46.0; `ruff` + `mypy --strict` + full `pytest` green
      — **partial, land-blocked (not a regression).** `ruff check`, `ruff format --check`
      and `mypy --strict` are all rc=0. `pytest` is rc=1 with exactly two failures,
      `test_surface_baseline.py::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction`
      and `test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow`.
      `_surface_baseline.py:156-178` refuses to freeze a baseline from a task branch
      (a squash-land deletes the commit the baseline would name) and the size arm
      compares against that same baseline, so both can only close after land →
      re-freeze from base → re-run from base. Accepted via `/hm:verify --force`;
      the reason is recorded in `.claude/observability/verify-2026-08-02.jsonl`.

## 🔍 Plan Validation

**Round 1 — `plan-validator`: MAJOR_REVISION** (4 critical, 5 warning, 1 suggestion), with
cross-model second opinion from `codex` and `antigravity` (both `status: invoked`).

| Finding | Source | Resolution |
|---|---|---|
| Phase 1 omits the `ai_readiness` hop; `improvement.py` named as a caller but never calls `compute_readiness` | codex `80f130b3`, escalated by validator | Fixed — all three `ai_readiness` sites in Phase 1 scope; ADR-001 consequence corrected |
| Phase 2 exit criterion proves only `on`→`status`; boundary path stays id-less | codex `93d5e9fe` + antigravity `6a2477fc` (**consensus, 2 models**) | Fixed — ADR-005 rewritten with the total-outage mechanism; phase declared atomic; exit criterion probes `boundary` |
| Phase 3 exit criterion is tautological — satisfied by Phase 1 alone | antigravity `c4267d3e` | Fixed — criterion is now composite **equality** under both env states, plus a dedicated isolation test |
| `test_fleet_degraded_floor.py:105-113` breaks under ADR-004 and is outside Phase 1's scope and command | validator (independent) | Fixed — added to scope; exit command widened to `-k 'readiness or fleet_degraded'` |
| Phase 1 criterion unobservable from `health_cmd` stdout | validator (independent) | Fixed — restated against `--json-output`/`signals_failed` |
| Two more dead fallbacks at `worktree.py:4262,5048`; scope silently widens from WSL2 to universal | validator (independent) | Fixed — new ADR-007 + Phase 5 (Interview #12) |
| ADR-003's blanket premise is wrong; `-z` branches are correct shell-context guards | validator, refuting antigravity `8531c853` and the PLAN's own R4 | Fixed — ADR-003 re-decided as a context split (Interview #11); R4/R5 rewritten |
| ADR-002's opt-out asserted but unspecified | validator (independent) | Fixed — `@pytest.mark.live_env`, registered in `pyproject.toml` |
| ADR-004 credits `/hm:health` with remediation text it does not carry | validator (independent) | Fixed — both channels named precisely; id-only surfacing accepted |
| Phase 4 grep not mechanically falsifiable | validator (suggestion) | Fixed — fixed-file-list grep + positive `unexported` assertion |

**Round 2 — `plan-validator`: MAJOR_REVISION** (2 critical, 7 warning, 2 suggestion). All ten
Round-1 resolutions were **verified as genuinely resolved**, and the DAG was checked clean
(1←[], 2←[1], 3←[1], 4←[1,2], 5←[1,2], 6←[1..5]; acyclic, no parallel groups overlap). The new
findings sit a layer below the first pass and are all folded in above:

| Finding | Resolution |
|---|---|
| **`--claude-session-id` is presence-overloaded** (`worktree.py:2402`, `:2444`) — Phase 5's obvious implementation would mislabel standalone `/hm:execute` spans as `hm:loop` and make the Stop-hook block the stage from ever stopping | ADR-007 gained a forbidding call-out; span id routed via `task-preflight`; `execute.md.j2` moved to scope-out; negative render-grep + span-label assertion added; new risk **R9** |
| Phase 3's criterion still tautological — composite equality is Phase 1's guarantee, and a bare `os.environ is None` assert passes vacuously | Replaced with a subprocess-pytest that injects all three vars and asserts the inner run sees `None` — fails deterministically without `tests/conftest.py` |
| `autopilot_caps boundary` is not a read-only probe (`:248-249` `touch`+`_confirm_entry`, `:310` `clear`, `:259` `unknown_stage`) | Exit criterion moved to the pure `evaluate_boundary`; the CLI caveat is recorded inline |
| Autopilot is **already dark** for `autopilot_persistent` harnesses (`autopilot_autoarm.py:33-43` stamps the id today) | Added as Executive Summary defect #5; ADR-005 Context corrected; R3 re-rated to `certain` for those harnesses |
| `worktree.py:2398-2399` misclassified — it is a Python comment about a *shell* value, so forcing `unexported` there re-introduces the wrong premise | Phase 4 split into Scope A (four `os.environ` sites, must say `unexported`) and Scope B (attribution-only) |
| Phase 4 scope-out was self-contradictory and `loop.md.j2:505,496,531` were unenumerated | Rewritten as Scope B (prose edited) + Frozen (conditions byte-identical), with a `git diff`-empty criterion |
| ADR-004's remedy channel is `action`-gated at `improvement.py:102` | ADR-004 now requires a non-null `action`; Phase 1 asserts the P2 `ActionItem` |
| The tri-state invariant was stated globally but autopilot collapses `""` and `None` (`autopilot.py:242`, `:371`) | ADR-001 scopes the invariant to readiness and states autopilot's `""` rule in one line |
| Phase 5 scope unenumerated; ADR-007 overstated `plan.md.j2` as a span emitter | Both corrected (`worktree_preflight.md.j2:23,27`; `loop-mode-active` emits no span) |
| Phase 1's `signals_failed` path is nested under `.structural` | Criterion restated as a runnable `jq` check |
| Phase 6/Phase 5 renumbering artifacts in ADR-003 and Phase 4 `merge_hazards` | Fixed |

**Validation stops here by design.** The stage permits exactly one validator re-run and it
has been spent. The Round-2 findings above were each verified by the main loop against source
before being folded in, but **this revision itself has not been agent-validated** — recorded
in the frontmatter as `post_pass2_revision_unvalidated: true`. Treat the Round-2 resolutions
as the first thing `/hm:execute` re-checks.

**Second-opinion dispositions (Round 1).** `codex`: 2 agree, 1 partially-agree (the N-A sub-claim was
refuted — emission is gated on `CLAUDECODE` at `readiness.py:1009`, which ADR-002's conftest
deletes, so the isolated case is a true N-A; the `signals_failed` sub-point was kept and
folded into ADR-004). `antigravity`: 1 agree, 1 partially-agree (its "Phase 2 misses the
templates" form was wrong — they were in scope; the underlying exit-criterion gap was kept),
1 **disagree** (the `-z` branches are not dead code — refuted with evidence, and the refutation
corrected the PLAN's own R4).
