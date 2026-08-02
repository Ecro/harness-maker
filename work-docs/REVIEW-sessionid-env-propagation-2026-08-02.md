---
type: review
task_slug: sessionid-env-propagation
status: APPROVED
created: 2026-08-02
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
second_opinion_models: [codex, antigravity]
voter_pool_n: 4
consensus_k: 2
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: sessionid-env-propagation
  computed_at: 2026-08-02T00:00:00Z
---

# REVIEW — sessionid-env-propagation

## 🎯 Round 1 Summary

**Grade: D** (1 consensus-passed P0). Auto-fix engaged.

The change wires `HM_SESSION_ID` from the shell into Python entry points as an explicit
argument, because the SessionStart hook writes it **unexported** and `os.environ` therefore
never carries it. Round 1 found the change had done the *writer* half of autopilot and left
five *reader* call sites resolving id-less.

That is not a partial improvement. `autopilot._is_own` is one-directional by design — ids are
compared whenever **either** side has one — so the moment the picker stamps an id, every
un-wired reader computes `env_id is None and marker_id is not None` → foreign → `active_marker`
None. **Wiring the writer without the readers turns autopilot OFF**, which is the exact failure
mode `tests/unit/test_autopilot_session_id_arg.py`'s own module docstring declares fatal.

## 🔍 Drift Findings

**None.** Every changed file maps to a PLAN phase scope. `stage_spans.py` is explicitly
enumerated in Phase 4 Scope A (`stage_spans.py:181`), and `tests/snapshot/*`, the five version
files, CHANGELOG and `failures.md` are Phase 6 Scope in. No PLAN-scoped file was left unchanged.

## ✅ Consensus Findings

### P0 — `evaluate_boundary` never receives the id the caller just validated with

`id: f916fc059b4423af` · `src/harness_maker/autopilot_caps.py:287` ·
**[3/4]** — code-reviewer (P0), codex (P0), corroborated by security-reviewer's reading of the
same chain.

`_cmd_boundary` resolves the marker at `:235` **with** `session_id=args.session_id`, then 50
lines later calls `evaluate_boundary(...)` **without** it. Inside, `active_marker(...,
session_id=None)` → `_is_own(env_id=None, marker_id=<id>)` → False → marker None →
`proceed: false, halt_kind: "kill_switch"`, for a marker this same process accepted moments
earlier. Every healthy Claude Code session that armed via the rendered picker would halt at its
first boundary.

**Fixed** — `session_id=args.session_id` forwarded.

## ⚠️ Weak Consensus

None. No pair matched on surface and diverged on reasoning.

## 📝 Manual-Only Findings

These failed the Step 4a surface match on the **severity-tier** predicate (see §Disagreements),
not on substance — each was independently verified against the source before action.

### P0/P1/P2 — internal marker readers resolve id-less (`touch`, `set_task_slug`, `effective_level`)

`ids: 0203355c44702aa2` (security-reviewer P0, `:194`), `19919b029b813a40` (code-reviewer P1,
`:249`), codex `e0838f876419a34d` (P2, `:249`).

`autopilot.touch`, `set_task_slug` and `effective_level` each call `active_marker(root)` with no
id. Against an id-stamped marker: the heartbeat becomes a permanent silent no-op (a live owner
reports growing idle to the takeover prompt), `set_task_slug` returns False and `_resolve_task_slug`
converts that into `halt_kind: bad_slug` **naming a slug that in fact passed validation**, and
`effective_level` silently downgrades a `full` session to the committed yaml default.

**Fixed** — all three take `session_id` and thread it; `autopilot_caps` passes `args.session_id`
at `:194`, `:249`, `:391`.

### P1/P2 — the Typer `hm cli autopilot` surface had no `--session-id`

`ids: dd0742c2d48bd278` (code-reviewer P1, `cli.py:2274`), `27d40595b8b371b9`
(security-reviewer P2, `cli.py:2253`).

`hm autopilot` (dot-form) gained the flag; the Typer alias — the documented `harness-maker
autopilot on` surface — did not, so arming through it stamps an id-less marker that the rendered
boundary calls then reject. The file's own comment at `:2265` says the two spellings "can never
drift".

**Fixed** — `--session-id` added and forwarded to both `write` and `status`.

*Note: codex's `15f594b423d3e55e` asserted the rendered picker calls this Typer surface. That
premise is false — `hm autopilot` routes through `hm.py` to `autopilot.main`, which had the flag.
Recorded `duplicate`: the real defect is the one above, stated correctly by code-reviewer.*

### P2 — the env-pin gate was `INTEGRATION=1`-only, so it did not run in PR CI

`id: e1954e23cf0490d3` · `tests/integration/test_env_isolation.py:23` · code-reviewer.

The module's own docstring claims "delete `tests/conftest.py` and this goes red, **in CI and
locally**". The `skipif` made that false in the half that matters. The `INTEGRATION` guard exists
for tests that hit an external service; this one only shells out to pytest.

**Fixed** — guard removed, with the reasoning recorded in place of it.

### P2 — ADR-010 takeover guard is bypassable by passing a peer's id (OPEN)

`id: c06dab60ca8738b3` · `src/harness_maker/autopilot.py:742` · security-reviewer, corroborated
by codex `dce214b8a5613a5d` (`duplicate`).

`--session-id <peer-id>` authorizes marker mutation without `--force`. **Not fixed, and judged
not worth fixing:** the marker is a local file the caller can already read and overwrite
directly, so this is not a trust boundary the argument weakens. Recorded so the next reader does
not mistake the check for an authentication boundary.

### P2 — autopilot accepts an unsanitized/unbounded caller id (OPEN, round 2)

`src/harness_maker/autopilot.py:242` · security-reviewer.

Every sibling session-identity surface canonicalizes through `loop_marker.sanitize_session_id`
(`worktree.py`, `hooks/autopilot_autoarm.py`); `autopilot.write` stamps `--session-id` verbatim,
and `AutopilotMarker.claude_session_id` has no `max_length`, unlike its neighbour `task_slug`.
With the shipped wiring both sides are pre-sanitized so they always agree today. A future caller
that skips sanitization (a new hook passing a raw stdin id, a manually exported `HM_SESSION_ID`)
would get a permanent ownership mismatch resolving to `kill_switch` — fail-closed but silent.

**Follow-up, not a blocker.** The reviewer verified the value never reaches a shell, a filesystem
path, or a log sink. Suggested fix: run it through `sanitize_session_id` in `write`/`_is_own`
(idempotent for the tame form already shipped) and add `max_length=64` to the model field.

## 🤝 Disagreements

The `touch` / `set_task_slug` cluster drew **three independent voices at three different
severities** — security-reviewer P0, code-reviewer P1, codex P2 — describing the same defect.
Step 4a admits only same-tier candidates and forbids bridging, so no pair formed a consensus
cluster and all three landed `manual-only` despite unanimous agreement on the facts.

This is a real gap in the filter, recorded rather than papered over: unanimity on *what is broken*
produced zero consensus because the voices disagreed on *how bad it is*. The findings were acted on
after direct verification of the call sites, and the fix is gated by new tests — but a future run
with less orchestrator scrutiny would have shipped this cluster as advisory.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | location | disposition | note |
|---|---|---|---|---|---|
| `a39c3dfdd62ef299` | codex | P0 | `autopilot_caps.py:287` | **accepted** | independently found the round-1 P0; folded into the consensus cluster |
| `15f594b423d3e55e` | codex | P1 | `cli.py:2236` | duplicate | picker premise false; real `cli.py` gap owned by `dd0742c2d48bd278` |
| `dce214b8a5613a5d` | codex | P1 | `autopilot.py:374` | duplicate | same claim as `c06dab60ca8738b3` |
| `b718e1e8e3cf2c94` | codex | P1 | `autopilot.py:612` | rejected | the `or` collapse is deliberate on the autopilot path and is pinned by `test_empty_string_means_idless_on_the_autopilot_path` |
| `e0838f876419a34d` | codex | P2 | `autopilot_caps.py:249` | duplicate | same heartbeat defect as `19919b029b813a40` |
| `41932e0a808a11de` | codex | P3 | `test_instruction_preservation.py:92` | rejected | that ratchet allowlists removals by design; new-flag presence is asserted by `test_render_sessionid_wiring.py` |

`second_opinion_results`:

```yaml
- model: codex
  status: invoked
  findings: 6
- model: antigravity
  status: skipped
  reason: "exit 1: Error: timeout waiting for response"
```

**antigravity did not vote.** The voter pool was N=3, not the configured 4. Graceful degrade per
`failure_policy: warn-and-proceed` — surfaced here rather than silently absorbed.

## Review Iteration Summary

### Iteration 2 (Grade: D → A)

Fixes applied: 5

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P0 | forward `session_id` to `evaluate_boundary` | `autopilot_caps.py:287` | Applied |
| 2 | P0/P1 | `touch` / `set_task_slug` / `effective_level` take and thread `session_id` | `autopilot.py` | Applied |
| 3 | P1 | pass `args.session_id` at the three `autopilot_caps` call sites | `autopilot_caps.py:194,249,391` | Applied |
| 4 | P1 | add `--session-id` to the Typer `autopilot` command, forward to `write` + `status` | `cli.py` | Applied |
| 5 | P2 | drop the `INTEGRATION=1` skipif so the env-pin gate runs in PR CI | `tests/integration/test_env_isolation.py` | Applied |

Remaining: 1 (open P2, `sanitize_session_id` divergence) | New issues introduced: 3 (found by the
round-2 re-review, all in the round-2 test additions — see Iteration 3)

### Iteration 3 (Grade: A → A)

Round 2's re-review found **no new production defect** and confirmed the production fixes
complete. It did find three problems in the tests written *for* those fixes — including a
docstring that claimed coverage the assertions did not have. All three fixed:

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 6 | P1 | the end-to-end boundary test claimed to cover `touch` but asserted nothing about it; stamp a stale `last_seen` first and assert it advanced | `tests/unit/test_autopilot_session_id_arg.py` | Applied |
| 7 | P2 | no test on either arm of the new Typer `--session-id`; added a `CliRunner` round-trip incl. the id-less negative | `tests/unit/test_autopilot_session_id_arg.py` | Applied |
| 8 | P2 | fixed in-repo probe dir made unique per process + per test, and gitignored | `tests/integration/test_env_isolation.py`, `.gitignore` | Applied |

Round 3 then re-reviewed the round-2 test additions with an explicit mutation brief. Again **no
production defect** — but the round-2 pattern had survived on the sibling branch:

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 9 | P1 | `main()`'s `gate-blocked` branch wires `--session-id` at two call sites with **no test that can fail** — the two pre-existing tests are immune (one arms an id-less marker → uuid fallback; the other sets `HM_SESSION_ID` → same id with or without the argument) | `tests/unit/test_autopilot_session_id_arg.py` | Applied · **mutation-verified** |
| 10 | P2 | per-pid probe dir still survives a SIGKILL, and `mkdir`/`write_text` sat above the `try` so a write failure leaked past the `finally`; `.gitignore` cannot hide a leftover from a gate that walks the FS at run time | `tests/integration/test_env_isolation.py`, `.gitignore` | Applied |

Finding 9's fix was verified the way round 3 asked for rather than by assertion-reading: deleting
`session_id=args.session_id` from both `gate-blocked` call sites makes
`test_the_gate_blocked_cli_records_with_a_stamped_marker` fail (marker rejected as foreign, no
ledger row). The production file was restored byte-for-byte afterwards.

**Honest caveat: the round-3 fixes were NOT re-reviewed** — `max_review_rounds: 3` is exhausted.
Their evidence is the mutation check above, which is stronger than the assertion-reading that
rounds 2 and 3 relied on, but it is self-administered.

## Verification

`ruff check` · `ruff format --check` · `mypy --strict` — all green.

`pytest tests/unit tests/render tests/structural tests/integration/test_env_isolation.py` — two
failures, **both pre-existing and structurally land-blocked**, unchanged from the execute stage:

- `test_surface_baseline::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction`
- `test_command_size_budget::test_aggregate_shipped_surface_does_not_grow` (+1617 chars)

`_surface_baseline.py:156-178` refuses to freeze a baseline from a task branch, because a
squash-land deletes the commit the baseline would name. Correct order is land → re-freeze from
base → full suite from base. **No ceiling was raised** (ADR-011); the per-command arms were
absorbed by compaction during execute.

## Final Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 7         | —   |
| 2         | A     | 5             | 1         | 3   |
| 3         | A     | 5             | 1         | 0   |

Final grade: **A**
Iterations used: 3 / 3
Exit reason: cap-exhausted (still progressing — round 3 found and fixed a real P1)
Status: **APPROVED**
human_review_needed: **false**

No open `manual-only` or `weak-consensus` finding is P0 or P1. Every P0/P1 raised across three
rounds is `resolved`; the single remaining item is an open **P2** follow-up
(`sanitize_session_id` divergence), which by definition does not set `unverified_severe`.

`cap-exhausted`, not `converged`: the loop stopped because it ran out of rounds while still
finding things, not because it went quiet. A fourth round had somewhere to look.

### Three caveats the letter does not carry

1. **antigravity did not vote** (`skipped`, timeout). The voter pool was N=3 against a configured
   4. Every consensus judgement here rests on three voices.
2. **Each round found a gap in the previous round's work.** Round 1 → a production P0; round 2 →
   the test written for it asserted nothing; round 3 → the same gap on the sibling `gate-blocked`
   branch. The production code has now been reviewed three times with no new defect since round 1,
   but the *test* work has never survived a review it did not provoke a finding from.
3. **The severity-tier rule cost this review its strongest consensus.** Three voices unanimously
   identified the `touch`/`set_task_slug` cluster and all three landed `manual-only` purely
   because they disagreed on severity (P0/P1/P2). Under a less scrutinising orchestrator that
   cluster ships as advisory. See §Disagreements.

## Follow-ups (not blocking)

- `autopilot.write` / `_is_own`: canonicalize through `loop_marker.sanitize_session_id` and bound
  `AutopilotMarker.claude_session_id` with `max_length=64` (round-2 security P2).
- Land, then re-freeze the surface baseline **from base** and re-run the full suite there to close
  the two structural failures.
