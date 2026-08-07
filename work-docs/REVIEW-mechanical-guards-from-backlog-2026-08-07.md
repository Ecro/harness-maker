---
type: review
task_slug: mechanical-guards-from-backlog
status: CHANGES_REQUESTED
created: 2026-08-07
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: mechanical-guards-from-backlog
  computed_at: 2026-08-07T02:10:00Z
---

# REVIEW — mechanical-guards-from-backlog

## 🎯 Summary

**Final grade: C** (`P0_count = 0`, `P1_count = 4` at round 2). Three rounds, **12 findings**,
and the headline is uncomfortable and worth stating first:

> **The guards built to stop a failure class were themselves riddled with that class, in
> three consecutive rounds, every time on a fully green suite.**

Building a guard confers no immunity. If anything it does the reverse: "this one *is* the
check, so it must be right" is what skips the verification. In every round the defect was
found by a reviewer or by an executable probe — **never by the suite**, which was green
throughout.

Voter pool **N = 4** at round 1 — the first time all four voices voted in this session.
`antigravity` returned `invoked` on a ~40 KB prompt, against a `skipped` (240 s timeout) on
the ~190 KB prompt of the previous task. That is a usable operational signal: prompt size,
not availability, is what has been costing that vote.

## 🔍 Drift findings

`result: clean`. Two divergences, recorded rather than absorbed:

- **`command_registry.py` / `hm.py` are not in any PLAN phase's stated scope.** Phase 4
  listed the CLI, the review-stage prose and the receipts, and omitted *registering* the
  subcommand — without which Phase 4 cannot satisfy its own exit criterion. A PLAN omission,
  not a scope violation.
- **Phase 4's review-stage prose line was never written.** Genuinely unfinished; see the
  open items below.

## ✅ Consensus findings — round 1 (N=4, K=2)

| # | Finding | Votes | Tag |
|---|---|---|---|
| 1 | `_is_driven` counts non-executing mentions as coverage | code P1 · sec P1 · agy P1 · codex P2 | **consensus-passed P1 [3/4]** |
| 2 | Nothing demands a receipt; the docstring over-claimed | code P1 · codex P1 | **consensus-passed P1 [2/4]** |
| 3 | Ledger read-then-rewrite loses concurrent rows | code P1 · sec P0 | weak-consensus (tiers diverge) |
| 4 | Misroute guard not wired on a registered module | sec P0 | manual-only — **turned the suite red**, fixed immediately |

Verified by executable probe before any fix, so these are not review opinion:

| Probe | Result |
|---|---|
| G1 population vs instance-13 artifacts | 10 goldens, **zero** `*_pre_change.md` — the guard omitted the artifact class it was written for |
| `/mnt/c/Users/…` (WSL2, this repo's own platform) | **not detected** |
| `C:\Users\…` | **not detected** |

## ✅ Consensus findings — round 2 (N=2, models frozen at round 1)

Every round-2 fix that I reported as done came back as a P1:

| Finding | Votes | What I had claimed |
|---|---|---|
| `_is_driven` still counts prose/docstring/stderr AND now rejects the canonical `hm <name>` form | code P1 · sec P1 | "restricted to executing shapes" |
| Allowlist's shared reason is **factually false** for ≥2 of 9 | code P1 · sec P1 | "an accurate reason" |
| Atomic-append fix has **no test that fails on revert** | code P1 · sec P1 | "used the existing helper" |
| `mutation_receipt` registered but inert; ledger **gitignored** | code P1 · sec P1 | "receipts recorded at the base repo" |

`test_dep_map` is driven by `_uv_run("hm", "test_dep_map", …)` — a real console-script
subprocess, the exact spelling the guard's own docstring calls the contract with the user —
and my "honest" detector rejected it, then my allowlist asserted it was undriven. The
reviewer's phrase is the right one: the allowlist **laundered detector false-negatives into a
documented-looking backlog**.

## 🔧 Round 3 — what changed

- **Detector rewritten from regex to AST.** A string constant is not a call in a syntax tree,
  which removes the whole failure mode rather than patching its current direction. Alias
  resolution added (`from harness_maker import x as mod` → `mod.main()`), which two regex
  versions both missed. Result: **23 driven / 8 undriven**, re-derived.
- **Allowlist: per-entry reasons**, not `dict.fromkeys`. A shared string has nowhere to record
  a difference, which is exactly how the false claim survived.
- **Concurrency proven.** Reverted to read-then-rewrite and measured **12 writers → 5 rows,
  7 lost**; restored. ADR-002 satisfied by observation, not by inspection.
- **Receipt ledger made trackable** — a three-line `.gitignore` change that descends into the
  directory, re-excludes its churn, and re-includes only the receipts. Verified both ways.
- ADR-002 demonstrations rewritten: 5 executing shapes must be detected, **6 non-executing
  mention shapes must not** — every one of those six was accepted by a previous detector.

## 📝 Open — not fixed, for a human decision

1. **`mutation_receipt` is a registered CLI with no caller** (consensus-passed P1, partially
   addressed). The docstring now states plainly that it is opt-in, unenforced, and
   syntactically validated only. The ledger is now inspectable. **But nothing files a
   receipt**, so the obligation is still unenforced and `hm --help` advertises a verb no
   template calls. Two honest exits: build the consumer (a `/hm:review` step, or a structural
   test), or **unregister it** until one exists. I did not choose unilaterally — dropping
   scope is the user's call.
2. **Eight subcommands remain undriven**, allowlisted with per-entry reasons. PLAN Phase 3
   decided in advance that surfaced gaps are findings, not blockers — but that decision was
   made expecting a small number. Eight of thirty is worth a deliberate look.
3. **P2s left open**: `tests/fixtures/pretooluse_payload_write.json` legitimately contains
   `/home/user` placeholders and sits outside G1's population (no exemption mechanism exists
   yet); `\Z` vs `$` in the locator regexes; three failure messages still say "numbered steps"
   where the assertion now checks order only.

## Review Iteration Summary

| Iteration | Grade | Fixes | Remaining | New |
|-----------|-------|-------|-----------|-----|
| 1 (init)  | B     | —     | 12        | —   |
| 2         | C     | 8     | 4         | **4** |
| 3         | C     | 6     | 3         | 0   |

Final grade: **C** · Iterations: 3 / 3 · Exit reason: **cap-exhausted**
Status: **CHANGES_REQUESTED** · human_review_needed: **true**

Round 3's fixes were **not** re-reviewed — the cap was reached. Given that rounds 1 and 2
each certified fixes that the next round overturned, that is the single most likely place
for another defect to be sitting right now.

## 🧊 Cross-model findings (frozen @ round 1)

### `codex` — `invoked`

| id | sev | file | finding | outcome |
|---|---|---|---|---|
| `32480117fec458b8` | P1 | `mutation_receipt.py` | G2 does not mechanize the obligation; it is an optional recorder | consensus-passed with code-reviewer; **partially open** |
| `df08c2d76cc6d082` | P2 | `mutation_receipt.py` | receipts may name nonexistent files/lines/nodes | manual-only; docstring now states validation is syntactic only |
| `fe6be5f7329c9163` | P2 | `test_cli_surfaces_are_driven.py` | detector accepts imports as coverage | joined the [3/4] P1 cluster |

### `antigravity` — `invoked`

| id | sev | file | finding | outcome |
|---|---|---|---|---|
| `3b1e682516ef081c` | P1 | `test_cli_surfaces_are_driven.py` | regex matches imports and mocks, defeating the guard's purpose | consensus-passed P1 |
| `2fdbc47a4525aae7` | P2 | `test_cli_surfaces_are_driven.py` | `_DISPATCHABLE` is not the true registry; `MODULES` has more | manual-only — **verified**: `MODULES` carries 17 surfaces `_DISPATCHABLE` does not, and no test binds them |

Both models independently raised the `_is_driven` defect, and antigravity's registry finding
was confirmed by direct comparison. The two-model configuration paid for itself this round.
