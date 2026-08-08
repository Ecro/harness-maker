---
type: review
task_slug: workflow-time-token-savings
status: APPROVED
created: 2026-08-09
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
human_review_needed: false
drift_verdict:
  result: scope_violation
  scope_violations:
    - .gitignore
    - src/harness_maker/worktree.py
    - tests/snapshot/prod-firmware-spec.expected.yaml
    - tests/snapshot/prod-firmware-task.expected.yaml
    - tests/snapshot/prod-tauri-app-spec.expected.yaml
    - tests/snapshot/prod-tauri-app-task.expected.yaml
    - tests/snapshot/side-python-cli-spec.expected.yaml
    - tests/snapshot/side-python-cli-task.expected.yaml
    - tests/snapshot/side-tauri-app-spec.expected.yaml
    - tests/snapshot/side-tauri-app-task.expected.yaml
  scenario_misses: []
  task_slug: workflow-time-token-savings
  computed_at: 2026-08-09T00:15:00Z
---

# REVIEW — workflow-time-token-savings (Track A)

## 🎯 Round summary

| Round | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 (init) | **B** | — | 4 consensus-passed + 9 manual-only | — |
| 2 | **A** | 8 | 0 consensus-passed | 3 P1 + 2 P2 (single-source) |
| 3 | **A** | 6 | 0 | 0 |

**Final grade: A** · Iterations used: 3 / 3 · Exit reason: `converged` ·
Status: **APPROVED** · `human_review_needed: false`

Voter pool N=4 (`code-reviewer`, `security-reviewer`, `codex`, `antigravity`), K=2.
Both second-opinion models `invoked`; neither skipped or failed.

## 🔍 Drift findings (P1)

**`result: scope_violation`** — four file groups changed outside any PLAN phase's declared
scope. All four are explained; none is unplanned work.

| File(s) | Why it changed | Verdict |
|---|---|---|
| `tests/snapshot/*.expected.yaml` (×8) | Re-freeze of `body_sha256` after A3's template edit. A3's scope named `surface_baseline.json` but not `tests/snapshot/` — a scope-declaration miss, not a scope creep. 32 lines, all `body_sha256`, inspected. | accepted |
| `.gitignore` | A4's deliverable was gitignored and would have been dropped by the wrapup commit. Found at execute Step 4. | accepted |
| `src/harness_maker/worktree.py` | `DELIVERABLE_PREFIXES` — forced by `test_deliverable_single_source`, which failed on the `.gitignore` edit above. | accepted |
| `work-docs/*`, `.claude/memory/wiki.md` | Deliverables and the A2 verdict record. | expected |

**Incomplete-phase items (declared, not defects):** `src/harness_maker/hm.py` (A2 scope, not
needed — `command_registry` drives dispatch) and `tests/structural/surface_baseline.json` (A3
scope, deliberately not re-frozen: the ratchet is `now <= was`, and re-freezing would destroy
the pre-PLAN anchor B5 needs).

**Phases B1–B5 and A5 are unstarted** — this review covers Track A only, by scope decision.

## ✅ Consensus findings — round 1 (all resolved)

| # | Sev | Finding | Voices | Resolution |
|---|---|---|---|---|
| 1 | **P1** | `encode_project_dir`'s docstring claimed the widening "cannot admit foreign turns"; `is_own_cwd` returns `True` for `cwd is None`, so a collision plus a legacy `cwd`-less line **does** admit one | code-reviewer, security-reviewer, codex | Docstring states the limit; `test_a_cwd_less_foreign_turn_survives_the_collision_boundary` pins the admitting branch and will fail loudly if `is_own_cwd` is ever made fail-closed. The behaviour is unchanged — fail-closed would drop legacy no-cwd turns in `load_turns` **and** `context_composition`, a larger change than this PLAN owns. |
| 2 | **P1** | `sidechain_turn_groups`'s "one run is one dispatch" is false in **both** directions | code-reviewer, codex (antigravity at P0, independent) | Docstring rewritten to say it is NOT a dispatch count and to name both directions; `test_turn_groups_merges_concurrent_dispatches_into_one_run` pins the undercount. Algorithm unchanged — the transcript does not mark dispatch boundaries, so no key recovers them. |
| 3 | P2 | The `reconcile` reader silently dropped unparseable lines, and every drop moves the verdict **toward** agreement | codex, antigravity (code-reviewer at P1, independent) | Malformed and non-dict lines counted, reported in the summary line and a follow-up line; `RecursionError` caught alongside `ValueError`, matching `economics_source`'s reader. |
| 4 | P2 | Test docstrings cited retracted figures (39/45, 6153/57) as observations | code-reviewer, antigravity | Updated to the shipped 37/616 and 0/1036 and re-labelled illustrative. |

## ✅ Consensus findings — round 2 (single-source, fixed anyway)

Round 2 re-review found that **two of round 1's fixes replaced a false claim with another false
claim**. Both were verified by grep before acting:

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 5 | P1 | The new `sidechain_turn_groups` docstring justified keeping the algorithm with "`code-reviewer` is one of the three agents this ledger records". `rg -o -- '--agent [a-z-]+' src/harness_maker/templates` returns only `plan-validator` ×2 and `test-reviewer` ×2 — **no rendered `code-reviewer` emit site exists**. | Claim replaced with what the code supports: the batch undercount does **not** currently reach the recorded population, and adding a batched emit site later would make it bite. |
| 6 | P1 | The retracted absolute claim survived **verbatim in the test file, 20 lines above the test that refutes it**. | Rewritten with the `cwd`-carrying qualifier and a cross-reference to its twin. |
| 7 | P1 | The whole `reconcile` CLI branch shipped untested — the `--root` guard, the malformed accounting, and the 0/2/1 exit convention had no test; a revert to `except ValueError: continue` would have passed the suite. | Three CLI tests added (`main(["reconcile", …])`), covering all three. |
| 8 | P2 | The wiki entry still said the grouping "over-counts" — the single-direction claim finding 2 retracted. | Both directions stated. |
| 9 | P2 | The spoton test docstring headlined 1036 while asserting 57, with no illustrative label. | Label added. |

## 📝 Manual-only findings (not fixed — recorded)

- **P2 · `reconcile` counts unvalidated JSON objects as dispatches** (codex). Any dict whose
  `verdict` is absent or non-sentinel increments the count; no `StageAgentRow` validation and no
  filter by agent name. Accepted: the ledger is harness-written, and the malformed-line
  accounting added in round 2 surfaces the shape that matters.
- **P2 · `sorted()` stability on equal timestamps** (antigravity). Real but immaterial given
  finding 2's disclosure — the number is already not a dispatch count.
- **P2 · `coherence` and `reconcile` no longer share an exit vocabulary** (code-reviewer, note).
  `coherence` exits 1 on defect; `reconcile` reserves 1 for tool failure. Only `reconcile`'s
  `--help` states its convention.
- **P1 · `is_own_cwd` fail-open on absent `cwd`** — the underlying behaviour behind finding 1.
  Out of scope by decision; pinned by test, and the fix direction is recorded in that test's
  docstring.

## 🤝 Disagreements

- **Grouping severity.** antigravity **P0**, code-reviewer and codex **P1**. Kept as independent
  findings (Step 4c forbids bridging tiers). The substance is identical and was fixed once.
- **Silent-drop severity.** code-reviewer **P1**, codex and antigravity **P2**. Same.
- **Exit-code severity.** antigravity **P1**, code-reviewer **P2**, codex **P3** — three tiers,
  no two agreeing, so all three were `manual-only` under the consensus rule despite unanimous
  substance. Fixed anyway. **This is a real gap in the tier-matching rule**: unanimity across
  four voters produced zero consensus because no two picked the same severity.

## ❌ Refuted

- **antigravity `4d404641` (P1): "`resolve_base_root` is neither defined nor imported → the
  reconcile command crashes unconditionally with `NameError`."** False. The import is at
  `stage_agent_ledger.py:77`, outside the diff hunk the model saw, and the command had already
  been run successfully against four projects. A diff-only reading produced a confident
  crash claim about code that demonstrably runs.
- **security-reviewer declared a coverage gap rather than filling it**: it has no Bash tool, so
  it could not read the two Jinja template hunks and refused to assert they carried no security
  instruction. Verified separately from the diff: the removed prose is two rationale paragraphs;
  no instruction, flag, quoting rule or `{% if %}` branch was touched.

## 🧊 Cross-model findings (frozen @ round 1)

Both models ran exactly once, at round 1, per the one-invocation-per-review contract.

| id | model | severity | disposition | note |
|---|---|---|---|---|
| `582a0caefbe23d61` | codex | P1 | accepted → consensus | `is_own_cwd` fail-open; matched two Claude reviewers |
| `4cf0de8d2bc51d92` | codex | P1 | accepted → consensus | grouping is not a dispatch count |
| `779b3e9b0c6f67b9` | codex | P2 | accepted → consensus | corrupt lines erased from the denominator |
| `4018166b795bc1dd` | codex | P2 | accepted → manual-only | unvalidated rows counted as dispatches |
| `c6011c0be8d290cc` | codex | P2 | accepted → consensus | grouping tests tautological; stale figures |
| `5badccee1b9afd3c` | codex | P3 | accepted → manual-only | exit 1 for a documented-expected state |
| `bc89b2600c986dda` | antigravity | P0 | accepted → manual-only | back-to-back dispatches merge (tier-isolated) |
| `4d404641dd8ffe2b` | antigravity | P1 | **rejected** | `resolve_base_root` NameError — refuted, import at `:77` |
| `1924bef6f6b3345b` | antigravity | P1 | accepted → manual-only | exit code breaks automation |
| `f6be63de32e0fd1d` | antigravity | P1 | accepted → manual-only | 0-vs-N is a valid expected state |
| `0cb10e25e0340539` | antigravity | P2 | accepted → consensus | silent `ValueError` drop masks loss |
| `5f5642d575de787f` | antigravity | P2 | accepted → manual-only | `sorted()` stability on equal ts |
| `4ce3c776bfc923a8` | antigravity | P2 | accepted → consensus | test enforces a retracted premise |

## 📌 What this review says about the harness itself

Recorded because this PLAN's subject **is** the workflow's cost, and the review is evidence:

1. **The cross-model voters earned their cost here.** codex supplied one of the two voices that
   made finding 1 consensus-passed, and both models independently found the grouping defect
   before any Claude reviewer reported it. One antigravity finding was a confident hallucination
   from reading a diff without the file — the refutation cost one grep.
2. **The tier-matching rule loses unanimous findings.** The exit-code issue was reported by three
   of four voters and reached `manual-only` because they picked three different severities. A
   same-issue-different-tier bucket would have caught it; today it relies on the orchestrator
   fixing manual-only items voluntarily.
3. **Two rounds in a row, a fix replaced a false claim with a new false claim** (findings 5 and 6).
   Both were docstring assertions about code behaviour that a single `rg` refuted. The pattern is
   worth a `failures.md` entry: *claims about what the code does, written in the same commit that
   changes it, are unverified by construction.*
