---
type: review
task_slug: playbook-alignment
status: APPROVED
human_review_needed: false
final_grade: A
exit_reason: converged
confirm_pass_ran: true
confirm_pass_new_severe_n: 0
created: 2026-09-16
run_id: 766578d1c2fd
review_base: 8a1f65010f6a96042148d24de4ebe25c56b8d07f
reviewers_invoked: [code-reviewer (design+functionality+robustness+consistency), security-reviewer, concurrency-reviewer, test-reviewer, codex (second opinion)]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: playbook-alignment
  computed_at: 2026-09-16T11:25:00Z
second_opinion_results:
  - model: codex
    status: invoked
    reason: null
    findings_n: 2
---

# REVIEW — playbook-alignment

Diff under review: the worktree diff — 54 changed paths (40 modified, 4 deleted fixture files
moved to `INTENT-OBJ-7.md`, 10 new): `frontmatter.py`, `world.py`, `intent.py`, `second_brain.py`,
`worktree.py`, `wrapup_land.py`, `command_registry.py`, one template line, the skill verb list,
`.gitignore`, both re-frozen baselines, the wrapup ratchet, tests and fixtures.

> `review_base` resolved to `8a1f6501` (the parent of the landed intent-layer commit `3edcca62`
> that this branch was created from), so the confirmation-pass span `review_base..freeze`
> includes that already-reviewed commit; the confirmation briefs name it as out of scope.

## 🎯 Round 1 Summary

- Grade **B** — 2 consensus-passed P1, 0 P0. Coverage: all 7 lenses exercised
  (`blocks_approval: false`).
- Fixes pending: 2 (P1). Manual items: 3 P2 + 1 P3 lens findings, 2 cross-model (P2, P3).
- `human_review_needed: false`.

## 🔍 Drift Findings

None. Every changed path is in a PLAN phase scope or in the PLAN's Phase 4 notes (the four
structural gates found at Phase D and the two baselines re-frozen at main — the one declared
`Do not change` crossing, recorded in the PLAN and the execute summary). Step 2.5: no
`common_ground_marks`. Step 3.3: the PLAN frontmatter carries no `objective:` link
(`[intent] no objective link — skipping`).

## ✅ Consensus Findings

### P1

| id | Lens | File:line | Summary |
|---|---|---|---|
| ec50e469d907399d | consistency | `world.py:1211` | `objective activate` reports `changed: objectives/<id>.yaml`, a path retired by ADR-001; the skill shows this line to the operator. |
| a30ea5608aae9ca2 | consistency | `world.py:1226` | `approve/drop/reopen/close` share the same stale literal — 5 of 7 objective verbs misreport their output location, exit 0. |

### P2

| id | Lens | File:line | Summary |
|---|---|---|---|
| 74d8f031452c2445 | security | `templates/stages/wrapup.md.j2:576` | The new `--claim "<new claim>"` clause inherits the sibling fields' unescaped free-text interpolation into the Bash line the agent executes (pre-existing class, new instance). |
| d64291c704d026e5 | concurrency | `world.py:1027` | `new_objective` is `exists()` then write; two concurrent `new SAME-ID` both succeed and the second silently overwrites, against the docstring's "refusing to overwrite". Downgraded from P1: single-operator verb, one-line `O_CREAT|O_EXCL` fix. |
| 0938d16fbd81b1ed | tests | `tests/unit/test_frontmatter_split.py:88` | No test covers `non_mapping` through `second_brain.parse_frontmatter` or a BOM on any failure path — exactly the two cross-model regressions below pass the suite. |

### P3

| id | Lens | File:line | Summary |
|---|---|---|---|
| 57d5923ff0bf3978 | tests | `tests/structural/test_playbook_alignment_invariance.py:56` | AC-005 skips (loudly) at the next version bump until re-pinned; documented ADR-010 trade-off, no re-pin forcing function. |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | File:line | Summary | Disposition |
|---|---|---|---|---|
| b3663bc91f177d29 | P2 | `second_brain.py:99` | `split_frontmatter` returns the whole input as `body` for `non_mapping`, so `parse_frontmatter` now returns the whole text where HEAD returned the body after the fence; `append_note`/`patch_note` would re-embed the old fence block. **A real regression against ADR-009's "unchanged contract".** | accepted |
| 7ca445f5163285e3 | P3 | `frontmatter.py:37` | The BOM is stripped before any status branch, so every non-ok `body` is the de-BOMed input while the `Split` docstring promises the whole input. | accepted |

## 🤝 Disagreements

- **concurrency P1 → dropped (body replay).** Pass 1: `_write_record` writes back the body
  captured at load, losing prose edits made in between. Pass 2 dropped it: the window is one CLI
  call, the operator is the same human, and the SPEC's accepted-loss row names this class.
  Recorded because the finding is right about the code; a pre-write re-read remains cheap
  hardening.
- **security P2 ×2 → dropped (regex `$` anchor).** `"AB\n"` passes `match()`; the charset still
  excludes `/` and `.`, so no traversal — a correctness nit, folded into the open items.
- **core P3 → duplicate.** The "redundant non_mapping branch" is the codex regression seen from
  the consumer side; not carried separately.
- **tests P2 → raised in Pass 2.** The tests lens added the coverage-hole finding after the two
  cross-model regressions were confirmed.

## 🧊 Cross-model findings (frozen @ round 1)

Model `codex` invoked once (`status: invoked`), 2 findings; PIDA (code-verifier mode B, oracle =
probes executed against the worktree and against `git show HEAD:` for the pre-change parser)
dispositions ledgered (2 rows).

| id | Sev | disposition | lifecycle | oracle |
|---|---|---|---|---|
| b3663bc91f177d29 | P2 | accepted | pending | now `({}, whole text)`; HEAD `({}, 'hello\n')` |
| 7ca445f5163285e3 | P3 | accepted | pending | `split.body == b"# prose\r\n"` for the BOM'd input |

## Auto-fix loop

### Iteration 2 (Grade: B → A)
Fixes applied: 2

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `objective activate` `changed:` now comes from a shared `_changed_path(root, id)` (`work-docs/INTENT-<id>.md`). | `src/harness_maker/world.py` | Applied · caused_by=none |
| 2 | P1 | `approve/drop/reopen/close` emit uses the same helper; `new`'s inline `rel` folded into it (one source for the operator-facing line). | `src/harness_maker/world.py` | Applied · caused_by=none |

Verification: ruff/format/mypy strict clean on `world.py`; `test_intent_doc_new.py`,
`test_world_objectives.py`, `test_world_status_and_revisit.py`, `test_intent_doc_record.py`,
`test_intent_layer_lifecycle.py` green; a live `hm world objective approve --json` reports
`changed: work-docs/INTENT-OBJ-1.md`.

Re-review: churn 1.0 (max: the REVIEW document itself, new; `world.py` 0.004) ≥ 0.30 →
`review_consensus plan` named one `code-reviewer` functionality dispatch; it returned no
findings (`relative_to(root)` cannot raise — the path is built under `root`; no retired literal
survives as an emit value; AC-006's substring still holds).

Remaining: 4 lens (3 P2 + 1 P3) + 2 cross-model (P2, P3), all `accepted`, none grade-bearing | New issues introduced: 0
Churn: 1.0 (max: work-docs/REVIEW-playbook-alignment-2026-09-16.md, measured 2, excluded 0)

## Confirmation pass

### confirm-1 — `review_base..e485609a` (frozen working tree), 4 dispatches

All 7 lenses exercised (`blocks_approval: false`). The span includes the already-reviewed
intent-layer commit `3edcca62`; briefs named it out of scope. Cross-model voters re-read from
section 7. New findings: **zero at P0/P1**; one P2:

| id | Lens | Sev | File:line | Summary | Disposition |
|---|---|---|---|---|---|
| 1754f3e1489470b8 | tests | P2 | `world.py:1086` | No test pins the CLI `changed:` value for `approve/activate/drop/reopen/close` — the exact P1 just fixed would return unnoticed. | accepted, not fixed (P2) |

core, security and concurrency returned no findings (`_changed_path` cannot raise; no retired
literal survives as an emit value; `activate`'s second `load_world` feeds only the never-locking
cap warning).

Outcome: **APPROVED** — every mandatory lens exercised and no new severe finding. Ledger:
`confirmation-pass --pass 1 PASS --terminal`. Freeze refs reaped.

## 🔁 Oscillation

`review_churn oscillation --rounds 2` → `[]`.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 8 (2 P1 · 3 P2 · 1 P3 · 2 cross-model) | — |
| 2         | A     | 2             | 6 (none grade-bearing) | 0 |
| confirm-1 | A     | —             | 7 | 1 (P2) |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `src/harness_maker/world.py` (round 2) | 1238 → 1243 | 245 → 245 | null | measured |
| `work-docs/REVIEW-playbook-alignment-2026-09-16.md` | null → 106 | null | null | not-python |

Status: **APPROVED**
human_review_needed: **false**
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0

## Open items for wrapup / follow-up (not grade-bearing)

- ~~P2 `b3663bc91f177d29` / P3 `7ca445f5163285e3` / P2 `0938d16fbd81b1ed`~~ — **fixed after
  the review at the user's direction (post-verify, before wrapup):** `split_frontmatter` now
  returns the post-fence body for `non_mapping` and the ORIGINAL bytes (BOM included) for
  `missing`/`unterminated`/`invalid_yaml`; `test_frontmatter_split.py` gained the non-mapping
  body case, three BOM-on-failure cases and the `parse_frontmatter` non-mapping contract case.
  Verified: `parse_frontmatter("---\n- a\n---\nhello\n") == ({}, "hello\n")` (HEAD
  behaviour restored); targeted suites green; the full CI plan re-runs at wrapup Step 2.
- P2 `d64291c704d026e5` — `new_objective`: exclusive create (`O_CREAT|O_EXCL`) before the atomic write.
- P2 `74d8f031452c2445` — wrapup 5.7 `--claim` text quoting guidance (pre-existing class).
- P2 `1754f3e1489470b8` — a CLI-level test for the `changed:` line of the five mutating verbs.
- P3 `57d5923ff0bf3978` — AC-005 pin skip on version bump: consider a "pin stale" advisory.
- Nit: `_OBJECTIVE_ID_RE` `match` → `fullmatch` (trailing newline).
- Previous SPEC's AC-017 judgment subject moved (fixtures renamed); its next wrapup re-judges.
