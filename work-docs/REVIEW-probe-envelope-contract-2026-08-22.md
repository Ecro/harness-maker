---
type: review
task_slug: probe-envelope-contract
status: CHANGES_REQUESTED
created: 2026-08-22
run_id: c488271901e1
review_base: 9d14a5c4e51e54221c01feac24ad29d6842e4998
reviewers_invoked: [design, functionality, robustness, consistency, security, concurrency, tests, codex, antigravity]
consensus_method: cross-check
human_review_needed: true
confirm_pass_ran: false
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/unit/test_lens_coverage.py
    - tests/unit/test_render_lens_axis.py
    - tests/unit/test_review_input_boundaries.py
    - tests/snapshot/prod-firmware-spec.expected.yaml
    - tests/snapshot/prod-firmware-task.expected.yaml
    - tests/snapshot/prod-tauri-app-spec.expected.yaml
    - tests/snapshot/prod-tauri-app-task.expected.yaml
    - tests/snapshot/side-python-cli-spec.expected.yaml
    - tests/snapshot/side-python-cli-task.expected.yaml
    - tests/snapshot/side-tauri-app-spec.expected.yaml
    - tests/snapshot/side-tauri-app-task.expected.yaml
    - uv.lock
    - tests/unit/test_lens_coverage_retired_flags.py
  scenario_misses: []
  task_slug: probe-envelope-contract
  computed_at: 2026-08-22T14:20:00Z
---

# REVIEW — probe-envelope-contract

## 🎯 Round 1 Summary

Grade **D** (P0 1, P1 1). Coverage 7/7, `blocks_approval: false`. Six findings from the seven
lenses plus three from `codex`; `antigravity` skipped.

The headline is not the grade. **Every real defect this review found was introduced by the
change itself** — not by the code it edited — and the most serious one was found by the
cross-model voter alone, after five Claude lenses had read the same file and cleared it.

## 🔍 Drift Findings

**P1 — 13 changed paths sat outside the PLAN's Affected Components table.** All mechanical
consequences of the declared work: 21 `probe=None` call sites in three test files, eight
regenerated snapshots, `uv.lock`, and the new ADR-004 compatibility test. Fixed in round 2 by
amending the table. Recorded because the omission has a shape worth naming: a scope list that
names the edits but not their consequences cannot tell drift from completion.

## ✅ Consensus Findings

| id | Sev | Tag | Where | What | Round 2 |
|---|---|---|---|---|---|
| `cx-dead-root` | P2 | consensus-passed (design + security + codex) | `lens_coverage.py:180` | `--root` parsed, never read — `build_probe_check` was its only consumer | fixed: argument deleted |
| `lens-dispatch-vacuity` | P2 | consensus-passed (tests) | `test_agent_frontmatter_merges.py:311` | both lens-population tests go vacuous if `lens_dispatch("Production")` is empty | fixed: `assert lens_agents` floor |
| `hash-pin-comment-partial` | P2 | consensus-passed (consistency) | `test_agent_body_partials.py:131` | the "these four moved" note sits above only two of the four changed pins | fixed: pointers added at the other two |
| `plan-scope-drift` | P1 | consensus-passed (drift-gate) | PLAN | see above | fixed |
| `receipt-row-missing` | P0 | consensus-passed (consistency) | `test_new_gates_file_a_mutation_receipt.py:59` | claimed the debt entry was removed with no receipt row | **rejected — false positive** |

### The rejected P0, and why it still holds the grade at D

The consistency lens reported that removing `test_agent_frontmatter_merges.py` from
`_UNRECEIPTED_DEBT` without a matching receipt row would break
`test_every_new_structural_gate_has_a_mutation_receipt`. Verified false, twice:

```
$ pytest tests/structural/test_new_gates_file_a_mutation_receipt.py   → rc=0
$ grep -c test_agent_frontmatter_merges <base>/.claude/observability/mutation-receipts.jsonl   → 1
$ grep -c test_agent_frontmatter_merges <worktree>/.claude/observability/mutation-receipts.jsonl → 0
```

The lens read the **worktree's** committed 34-row copy; the gate's `_ledger()` resolves the base
root and reads the 35-row file the writer wrote. That split is documented in `_ledger`'s own
docstring, which records the same mistake being made and fixed once before. Disposition
`rejected`, authority `docstring:…:_ledger`.

It still counts toward the grade, and that is by design rather than by accident: only an
**AC-cited** rejection clears the grade, this harness is task-driven and has no SPEC, so no
rejection can. The documented consequence is that every false positive lands on
`human_review_needed`. That is what happened here, and the flag is the intended output — not a
defect in the change.

## 📝 Manual-Only Findings

Both are `codex` speaking alone, so the vote table tags them `manual-only` and the auto-fix loop
may not touch them. **Both were fixed anyway**, and the distinction matters: they were applied on
a measurement I ran myself, not on the reviewer's word. The rule exists to stop unverified
single-source fixes; a defect reproduced at a shell prompt is not that.

### `cx-empty-tools` — P1, and the one that mattered

Deleting `test_every_agent_declares_a_non_empty_tools_list` left this hole:

| `tools:` value | before this change | after, before the fix |
|---|---|---|
| absent | explicit failure naming the security consequence | `AssertionError: unhandled tools: shape NoneType` — caught by accident, useless diagnostic |
| `""` (empty) | explicit failure | **silently passes** |

Measured, not reasoned: `_granted_tools("")` returns `set()`, which intersects `_DANGEROUS` to
nothing and equals the permitted set for any non-privileged agent. In this project `tools:` is the
only *enforced* agent boundary — a `permissions:` block is silently ignored by Claude Code — so an
undeclared boundary is a security regression, which is what that test's own comment said before it
was deleted.

**How it got in**: the Phase 2 edit replaced everything from the `# tools: is the ONLY enforced
agent boundary` comment to end-of-file. The `_READ_ONLY_AGENTS` test that was meant to go sat after
that comment; so did the non-empty test, which was not.

**Fixed** by asserting non-emptiness over the derived population, inside the same test that walks
it. Verified: rendering `code-reviewer` with `tools: ""` turns it RED.

### `cx-allowlist-unchecked` — P2

`dangerous_grant_violations` reads the allowlist as `allowlist.get(name, frozenset())`, so an entry
for an agent that no longer renders is never consulted and never complained about — the one way a
fail-closed exception list rots quietly. **Fixed**: `set(_WRITE_PRIVILEGED) - population` must be
empty. Verified: adding a `ghost-agent` entry turns it RED.

## 🤝 Disagreements

`cx-dead-root` was P2 from two lenses and P3 from codex. Kept at P2 (the higher tier) rather than
bridged; Step 4a admits only same-tier candidates, and the two lens voices already carry it.

## 🧊 Cross-model findings (frozen @ round 1)

| model | status | findings | disposition |
|---|---|---|---|
| `codex` | invoked | 3 | all `accepted` — each verified by a command, evidence in the ledger |
| `antigravity` | skipped | 0 | `agy envelope status 'CANCELED'`, empty payload |

**Codex earned its seat twice in one task.** It caught the deleted non-empty-tools test that five
Claude lenses missed — including the security lens, which reasoned explicitly about
`_WRITE_PRIVILEGED` and concluded "no P0/P1", and the tests lens, which was asked in so many words
whether the new set was a strict superset of the deleted one and answered "by construction, yes".
That construction argument is about the dangerous-grant check, which *is* a superset; the deleted
test asserted a different property. Earlier in the same task it refuted the PLAN's premise that
`_READ_ONLY_AGENTS` held 2 of 11 agents when it held all 11.

**Antigravity has now skipped twice in this task** (plan and review), both `CANCELED` with an empty
payload. Two data points, not a diagnosis — but if it recurs, the `(skipped + failed) / total`
rate per model is the thing to read, not the aggregate.

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|---|---|---|---|---|
| `src/harness_maker/lens_coverage.py` | 206 → 205 | 22 → 22 | 2 → 2 | measured |
| `tests/structural/test_agent_frontmatter_merges.py` | 317 → 341 | 28 → 32 | 2 → 2 | measured |
| `tests/unit/test_agent_body_partials.py` | 248 → 250 | 8 → 8 | 0 → 0 | measured |
| `work-docs/PLAN-probe-envelope-contract.md` | 629 → 637 | null | null | not-python |

Round 2 added complexity to the gate file (+4 cyclomatic, +24 LOC) — three new assertions, each
closing a hole a reviewer found. Reported, not gated.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 6         | —   |
| 2         | D     | 6             | 1         | 0   |

Final grade: **D**
Iterations used: 2 / 3
Exit reason: **no-progress** — the one surviving finding is a rejected false positive with no edit
to make, so a third round could not transition anything. Round 2 itself progressed (6 of 7
resolved); the stop is the absence of remaining work, not a stall.
Churn: 0.070 (max: `tests/structural/test_agent_frontmatter_merges.py`, measured 4, excluded 0) —
below the 0.30 gate, so the re-review was skipped: `churn 0.07 < 0.30`.

Status: **CHANGES_REQUESTED**
human_review_needed: **true**
Counters: unreviewed 6 · prior-fix 0 · unattributed 0

## What a human should look at

1. **The rejected P0.** Confirm the false-positive call. Everything needed is in the code block
   above; it takes one `pytest` run.
2. **Whether Grade D should block wrapup here.** The letter is held entirely by that false
   positive. Every actual defect found was fixed and each fix was verified by mutation.
3. **The base/worktree ledger split.** It produced a P0 false positive from a competent reviewer
   reading the obvious file. The gate handles it correctly; a reader does not. That is a
   documentation or tooling gap, and it is not this task's to fix.
