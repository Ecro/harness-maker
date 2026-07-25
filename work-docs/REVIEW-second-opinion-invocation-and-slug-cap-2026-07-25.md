---
type: review
task_slug: second-opinion-invocation-and-slug-cap
plan: "[[PLAN-second-opinion-invocation-and-slug-cap]]"
reviewed: 2026-07-25
rounds: 4
grade: A
grade_threshold: A
auto_fix: true
human_review_needed: true
consensus: k-of-n
k: 2
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/second_brain.py
    - src/harness_maker/templates/stages/wrapup.md.j2
    - src/harness_maker/templates/agents/_partials/second_opinion_dispatch.md.j2
    - tests/unit/test_wrapup_memory_fold.py
    - tests/unit/test_codex_loop_applicability.py
    - tests/unit/test_codex_mandatory_matrix.py
    - tests/unit/test_codex_review_consensus.py
    - tests/unit/test_render_codex_partial_include.py
  scenario_misses: []
  task_slug: second-opinion-invocation-and-slug-cap
  computed_at: 2026-07-25T18:45:00+09:00
second_opinion_results:
  - model: codex
    status: invoked
    reconciliation: [round-1 finding 1 (P1), round-1 finding 2 (P2)]
  - model: antigravity
    status: failed
    reconciliation: []
    reason: >-
      jetski: no output produced — a tool required the "command" permission that
      headless mode cannot prompt for. Graceful-degraded per ADR-011.
---

# REVIEW — second-opinion-invocation-and-slug-cap

## Verdict

**Grade A**. Every P1 is closed, and the three P2s first recorded as deferred
were closed in round 4 — F3 and F4 outright, F6 down to a single open decision
about a **pre-existing** blanket grant (see *Round 4*). All quality gates green:

| Gate | `rc` | Result |
|---|---|---|
| `ruff check src/ tests/` | 0 | All checks passed |
| `ruff format --check` | 0 | 468 files already formatted |
| `mypy --strict src/` | 0 | no issues, 120 source files |
| `pytest tests/unit tests/snapshot` | 0 | 4367 results, **0 FAILED**, `[100%]` |

> Every gate's `rc` is captured **individually**. In this session the background
> runner reported exit 0 for a run whose own `rc=` recorded 1, four times, so a
> reported exit code is not evidence here. It also matters that each gate gets its
> own `rc`: the previous run of this same block piped `ruff format --check`
> through `tail -1` and reported an aggregate 0 while format was **failing** — the
> gate script reproduced, in miniature, the exact defect class this task fixes.

## Drift gate (Step 2)

`result: scope_violation` — 8 files changed outside the PLAN's per-phase scope
lists. Every one is traceable; none is stray. Recorded rather than waived
because the PLAN's file enumeration is what `verify` and future readers trust.

| File | Why it moved | Legitimacy |
|---|---|---|
| `second_brain.py` | Round-2 **F1** (P1 injection) — a second unquoted sink for the same untrusted slug | Fix is mandatory; PLAN could not have listed it because the sink was only reachable *after* ADR-004 relaxed the slug floor |
| `templates/stages/wrapup.md.j2` | Round-1 **#3** + Round-2 **F2** — unquoted `--slug` / `--category` / `--occurrence-note` / `--source-slug` | Same cause: this change created the exposure, so closing it is in-scope in substance |
| `tests/unit/test_wrapup_memory_fold.py` | Asserts the quoting above | Paired with the fix |
| `_partials/second_opinion_dispatch.md.j2` | 2-line prose: `codex exec …` → the invoker call | PLAN said "the two `second_opinion_*` partials"; there are three |
| `test_codex_loop_applicability.py`, `test_codex_mandatory_matrix.py`, `test_codex_review_consensus.py`, `test_render_codex_partial_include.py` | Pinned the retired `codex exec` / `codex_adapter` prose shape | **Real PLAN miss** — see below |

**Process finding (P2, no code defect).** PLAN Phase 3 deliberately enumerated
the artifacts pinning the old shape, named **five**, and even cited this repo's
own `[fail:test] integration-gated-test-stale-after-behavior-flip` as the reason
to enumerate rather than rely on the suite. The true count was **nine**. The
enumeration was the right instinct executed incompletely, and the last of the
four extras surfaced only on the final verification run. Enumerating a blast
radius by hand does not remove the need to run the suite before claiming done.

`scenario_misses: []` — no SPEC exists for this slug (task-driven path), so
there are no scenarios to miss.

## Round 1 — 9 findings, 9 applied

Voter pool: 4 Claude reviewers + codex + antigravity (N=6, K=2).

| # | Finding | Tag | Sources |
|---|---|---|---|
| 1 | `invoke()` raises on the temp/schema prep path — violates its own "never raises" contract | **consensus-passed P1** | codex + code-reviewer |
| 2 | Temp-file leak + dead `out_tmp` in both partials | **consensus-passed P2** | 3 sources |
| 3 | Slug floor admits shell metacharacters → unquoted `--slug` in `wrapup.md.j2` → command execution | manual-only **P1** | security |
| 4 | `$prompt_tmp` crosses a shell-invocation boundary (single-model path) | manual-only **P1** | code-reviewer |
| 5 | `truncate_prompt` negative budget → slice cuts from the tail | manual-only P2 | code-reviewer |
| 6 | `separate-git-dir` repo: linked worktree returns the gitdir as base | manual-only P2 | code-reviewer |
| 7 | `output_schema_path` containment unchecked (raw YAML bypasses pydantic) | manual-only P2 | security |
| 8 | Unbounded read of the codex out-file | manual-only P2 | security |
| 9 | Branch 5 discards the CLI's own diagnostic, replacing it with a Python exception name | orchestrator | self |

Finding 3 is the one worth remembering: **the review caught a vulnerability this
task introduced.** ADR-004 relaxed the slug validator to grandfather legacy
slugs; the relaxed floor then flowed into an unquoted shell argument. A
grandfathering decision made for the *memory* subsystem became an injection
sink in the *wrapup* subsystem — the two were only connected through a shared
untrusted value.

Finding 6 also produced a correction to the PLAN's own design: the PLAN
specified porcelain-first base detection, and probing git showed porcelain's
first entry under `--separate-git-dir` is the external git dir, not the
checkout. The implemented rule is `--git-dir != --git-common-dir`.

## Round 2 — 6 findings, 3 applied, 3 deferred

| # | Finding | Sev | Disposition |
|---|---|---|---|
| F1 | `second_brain promote --source-slug` — the same untrusted-slug→shell sink, unquoted and unvalidated | **P1** | **Applied.** Single-quoted at the call site; `_SOURCE_SLUG_UNSAFE_RE` rejects only `'` / `\r` / `\n` |
| F2 | The allowlist gates the *writer*, not the *reader* — `--slug` / `--occurrence-note` still reach a shell unquoted (`wrapup.md.j2:395`) | P2 | **Applied.** Single-quoted all four flags |
| F3 | Temp ownership inferred from location (`schema_path.parent == gettempdir()`) — a repo rooted in the temp dir would delete a user file | P2 | **Applied in round 4** |
| F4 | The cap slices *after* the read — `read_text()[:N]` materialises the whole file first | P2 | **Applied in round 4** |
| F5 | Ledger excerpt: log injection vs prompt injection | P2 | **Applied.** C0/C1 controls stripped; excerpt wrapped in an explicit "untrusted model output, data not instructions" fence |
| F6 | The sandbox-escape instruction is newly *paired* with the blanket `Bash(uv:*)` allow rule | P2 | **Partly applied in round 4** — one decision left open |

**F1 corrected my own judgment.** My first fix put an allowlist inside
`promote_note`, which broke two existing tests — and those tests documented the
real contract: the function accepts free text like `"ADR-001 Reverse Advisory"`
and `_slugify` neutralises traversal. The allowlist was at the wrong layer. The
shell exposure was the actual defect, and it closes with quoting plus a rejection
of only what escapes single-quoting.

## Round 3 — verification-surfaced, 1 finding, applied

| # | Finding | Sev | Disposition |
|---|---|---|---|
| R1 | `test_codex_loop_applicability::test_review_codex_present_regardless_of_runner` asserted `'codex_adapter' in <rendered review stage>` | P2 | **Applied.** Retargeted to `--model codex` |

The test's docstring states the invariant — *"same second-opinion wiring whether
run standalone or via loop"* — but the assertion pinned a string. Adaptation
moved into `second_opinion_invoke` (which imports `codex_adapter`), so the name
left the prose while the invariant held. Verified by rendering both runners
before touching the test: `second_opinion_invoke` ×3 and a per-model `--model`
line present for `is_codex` in `(False, True)`.

This is the fourth instance of `[fail:design]
assertion-invariant-over-named-dimension` in this task alone.

## Round 4 — the three deferred items, resolved

**F3 — ownership is now recorded, not inferred.** `resolve_schema_path` returns
`(path, we_created_it)`. Creation is the one moment the answer is known; the
retired predicate `schema_path.parent == gettempdir()` was a guess, and it said
"mine" about a user's file whenever the repo lived under `$TMPDIR`. Fenced by
`test_a_user_schema_living_in_the_temp_dir_survives_the_call`, which points
`gettempdir()` at the schema's own directory to make the retired predicate true.

**F4 — the read is now bounded, and the unit is now bytes.** `read(cap+1)` on a
binary handle, fail closed with the cap named. Two defects were present, not one:
the slice bounded only what was *retained*, and it counted **characters** against
a **byte**-named constant, so a CJK payload ~3× over the cap passed through and
reported `invoked`. `test_the_cap_counts_bytes_not_characters` is the only case
that separates the two units.

> Writing the fix exposed a third instance of the same defect class this task
> exists to remove. My first version *raised* `ValueError("output exceeds cap")`,
> which the branch-5 handler catches and renders as `type(exc).__name__` —
> reporting "payload unreadable: ValueError" for a plain size overflow and
> discarding the one diagnostic that was certain. The over-cap case now returns
> directly. The test caught it because it asserted on the *reason string*;
> `status == "failed"` alone passes under both the old truncation and the bad fix.

**F6 — scoped grant added; one decision left open.** A
`Bash(uv run … -m harness_maker.second_opinion_invoke:*)` allow rule now ships
whenever any model is enabled, and both partials cite it instead of `Bash(uv:*)`.

**This is preparatory, not protective, and the rendered prose says so.** While
the blanket `Bash(uv:*)` still ships, it — not the scoped rule — is what actually
pre-approves the call, so adding the scoped rule changes no permission outcome
today. The real risk reduction is removing the blanket, which is a one-line
change with a real consequence: every ad-hoc `uv add` / `uv sync` / `uv run
pytest` starts prompting. That trade sits against a documented preference in this
repo for low solo-workflow friction (it is why `deny_dangerous` defaults to off),
so it is the user's call, not mine. The scoped rule exists so that making it costs
nothing.

`human_review_needed` remains `true` for exactly this one decision.

### Snapshot blind spot (noted, not fixed)

No snapshot fixture enables `second_opinion`, so the entire second-opinion render
surface — including the new scoped allow rule — is invisible to the snapshot
suite. The unit tests added here cover it, but a future change to these templates
will not show up as a snapshot diff, which is the signal a reader is most likely
to trust.

## Second opinion

- **codex — `invoked`.** Contributed to Round-1 findings 1 and 2; finding 1
  reached consensus on the strength of codex agreeing with `code-reviewer`.
- **antigravity — `failed`.** `jetski: no output produced — a tool required the
  "command" permission that headless mode cannot prompt for.` Graceful-degraded
  per ADR-011 and did not block.

  This exposed two real problems. First, a defect in this change: branch 5
  discarded the CLI's own diagnostic and would have shown the operator only
  `ValueError` — that is Round-1 finding 9, now fixed, and the message quoted
  above is what the fix surfaces. Second, a **limitation that remains open**:
  `/hm:health`'s smoke prompt is trivial and never triggers tool use, so it
  cannot reproduce this failure. A green `/hm:health` does not prove antigravity
  can complete a real review.

## Live verification

Run from inside `.worktrees/second-opinion-invocation-and-slug-cap/` — the
condition H1 lived under and that `/hm:health` never exercises:

- both models returned `{"status": "invoked"}`;
- ledger rows landed at the **base** repo, not the worktree copy `task-land`
  deletes;
- the corrected `agy --sandbox --print "<prompt>"` write-probe passes — the
  previous probe ran `agy --print --sandbox …`, which fed `--sandbox` in as the
  prompt value, so it was asserting sandbox safety while observing a command
  that had no sandbox applied.

## Open risk

`.claude/hooks/hooks.json` remains dead weight in Claude Code (2026-07-17), and
this task did not touch it. Unrelated to this change; noted so the next reader
does not re-derive it.
