---
type: review
task_slug: dep-map-alias-imports
status: APPROVED
human_review_needed: true
created: 2026-08-01
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/unit/test_codex_phase7.py
    - tests/unit/test_synthesize_codex.py
    - tests/render/test_render_targeted_test_selection.py
  scenario_misses:
    - "Phase 4 work item 3 — self-harness re-render (deliberately deferred; the CLI refuses to run from inside .worktrees/)"
  task_slug: dep-map-alias-imports
  computed_at: 2026-08-01T00:00:00Z
---

# REVIEW — dep-map-alias-imports

## 🎯 Round 1 Summary

Grade **B** (consensus-passed P0 = 0, P1 = 1). Threshold is A → auto-fix loop entered.
`unverified_severe = true` — four P1 findings landed `weak-consensus` or `manual-only`.

**Voter pool N = 3, K = 2**: `code-reviewer`, `security-reviewer`, `codex`.
`antigravity` returned `status: failed` — *payload unreadable via stdout: ValueError* — so
it cast no vote. Its readable fragment named the same `_reverse_map` / `_package_root`
site the other two did, which is corroboration but not a countable voice.

**What changed the picture:** four findings were confirmed by running the code rather than
by reading it. Those oracles, not the consensus tags, drove which fixes were applied.

## 🔍 Drift Findings

| Severity | Type | Detail |
|---|---|---|
| P1 | scope drift | `tests/unit/test_codex_phase7.py`, `tests/unit/test_synthesize_codex.py`, `tests/render/test_render_targeted_test_selection.py` changed but named in no PLAN phase scope. All three were required; the PLAN's Phase 3 scope simply omitted "the enumeration count tests". `test_synthesize_codex.py` was a *third* such constant, found only after the full suite went red. |
| P1 | incomplete phase | Phase 4 work item 3 (self-harness re-render) not performed. `hm cli make --update` refuses to run from inside `.worktrees/`. Deferred deliberately and recorded in the PLAN's Execution status. |

## ✅ Consensus Findings

### P1 — `targeted-test-selection` SKILL §2 interpolates paths into a shell line with no argv rule
`consensus-passed [2/3]` — `code-reviewer` P1 + `security-reviewer` P1, same file, same
line, same tier. `codex` raised the same defect at P2 (tier split, so it does not bridge,
but it is a third independent voice).

- **file**: `src/harness_maker/templates/skills/targeted-test-selection/SKILL.md.j2:41`
- §1 argues at length that both git commands must be `-z` because paths may contain
  spaces, newlines and non-ASCII. §2 then rendered those same values as
  `--changed-file <f1>` — unquoted, separate-token. The recipe preserved exotic paths
  through §1 and destroyed them at the point of use.
- **Oracle**: `--changed-file -foo.py` → `error: argument --changed-file: expected one
  argument`, **exit 2, no JSON at all**. `--changed-file=-foo.py` → exit 0, JSON.
- Consequence: a `-`-leading or space-bearing path aborts the selection inside the review
  auto-fix loop's *verify* step, and §4 defined only `targeted` and `full` — both of which
  presuppose the process succeeded. The undefined branch reads as a pass.
- **Status: FIXED (round 2)** — `=`-attached + single-quoted form, an explicit rule for
  both hazards, a documented escape when a path contains a quote, and a third §4 arm:
  *non-zero exit / no output / non-JSON → run the whole suite and echo stderr.*

## ⚠️ Weak Consensus

### P1 — `_reverse_map` scans the entire tree for a non-package changed file
`weak-consensus [2/3]` — `security-reviewer` P1 (`:202`) + `codex` P1 (`:197`): surface
match holds (same function, within ±5, same tier) but the CONCLUDE clauses diverge —
resource exhaustion vs. cache staleness. Kept as one finding for the scan half, which is
the one with an oracle.

- `_package_root` returns the file's own directory verbatim when that directory is not a
  package, so a root-level `setup.py` / `noxfile.py` / `conftest.py` makes the **project
  root** the scan root.
- **Oracle**: for a hypothetical root-level `noxfile.py`, `package_root == repo root`, and
  `rglob("*.py")` yields **3137** files — **2609** of them vendored under
  `.venv/site-packages`. A verification run of `--changed-file=-foo.py` emitted
  `SyntaxWarning: invalid escape sequence` from vendored code: it really did AST-parse
  site-packages.
- **Status: FIXED (round 2)** — `_REVERSE_SCAN_EXCLUDED` (VCS / caches / venv /
  site-packages / node_modules / `.worktrees` / build dirs) plus a 2000-file cap that
  abandons the reverse walk rather than paying for it. Re-measured: **3137 → 528**.
- **Not fixed**: the staleness half. `_REVERSE_CACHE` is keyed only by `package_root` with
  no file-set fingerprint. `security-reviewer` refuted the practical impact —
  `hm test_dep_map` is a one-shot process, so every cache dies before the auto-fix loop
  can edit anything — and `code-reviewer` rated it P2. Carried as a follow-up.

## 📝 Manual-Only Findings

### P1 — a top-level `tests/conftest.py` forced FULL for every module it imports
`manual-only` — `code-reviewer` only, but **oracle-confirmed**, and caused by this change.

- `_normalize_hints` maps a conftest hit to its parent, so `tests/conftest.py` → the bare
  node `tests`; `select_tests` then filtered on `startswith("tests/")`, which rejects
  `"tests"`, emptying `kept` and falling through to FULL.
- **Oracle**: shared fixtures at `tests/conftest.py` (the default pytest layout) →
  `mode: full`, reason *"every hint was filtered out for src/pkg/a.py"*.
- This is the PLAN's own Prior Work shape — a working fallback masking a dead primary
  path. Every fixture in the new tests placed conftest at `tests/unit/`, so no test could
  see it.
- **Status: FIXED (round 2)** — the filter now also accepts the bare `tests` / `test`
  roots. Re-measured: `targeted`, `node_ids: ["tests"]`.

### P1 — `import pkg.a` never marked an edge on the ancestor package
`manual-only` — `codex` P1 + `code-reviewer` P2 (tier split, no bridge). Oracle-confirmed.

- Importing `pkg.sub.mod` **executes** `pkg/__init__.py` and `pkg/sub/__init__.py`, but
  `_import_targets` emitted only the leaf. ADR-001's rule table listed only `a.b.c` —
  parent-package edges were never considered there, so this is a gap in the ADR, not a
  deviation from it.
- **Oracle**: changing `pkg/__init__.py` with a consumer doing `import pkg.sub.mod` →
  `hints: []`.
- **Status: FIXED (round 2)** — `_with_ancestors` adds every dotted prefix that resolves
  via `_module_exists` (probed, never assumed). Re-measured:
  `['tests/unit/test_consumer.py']`.

### P1 — namespace packages get the wrong qualified name and search root
`manual-only` — `codex` P1 + `code-reviewer` P2 (tier split).

- With `src/acme/widgets/mod.py` and no `__init__.py` anywhere, `_package_root` returns
  `src/acme/widgets`, so the qualified name is `widgets.mod` rather than
  `acme.widgets.mod`, and import matching is uniformly dead for that project shape.
- **NOT fixed — deferred deliberately.** This repo uses regular packages throughout, so
  there is no oracle here and no in-repo consequence; the fix needs a source-root notion
  derived from project configuration rather than from `__init__.py` presence, which is a
  design decision, not a patch. The failure direction is fail-safe (fewer dependents →
  FULL), and the round-2 scan cap now bounds its cost. Recorded as a follow-up; PLAN R11
  covers the direction but rates likelihood "low", which this finding shows is optimistic
  for a namespace-package consumer.

### P2 — module-scoped caches have no reset API and no eviction
`manual-only` — `code-reviewer`. Follow-up. `execute.md.j2:17` invites agents to call
`build_test_hints()` directly, which is the in-process path where staleness could bite.

### P2 — `tests/structural/test_no_positional_params_in_commands.py` does not scan `templates/skills/**`
`manual-only` — `security-reviewer`. Verified: **no live defect** (the new skill body
contains no `$` at all, and a skill is reference prose, not a slash command). The gate
already treats the plugin's own `skills/` as in scope while the template path is not —
the same "scoped to the artifact you happened to be fixing" asymmetry the module's own
docstring warns about. Follow-up.

### P2 — the render test's empty-set assertions held in the broken world
`manual-only` — `code-reviewer`. Correct, and it was mine: `assert "zero" in body` passed
against a §3 rewritten to say the opposite. **Status: FIXED (round 2)** — now pins the
operative sentences plus the argv form and the failure arm.

## 🤝 Disagreements

| Finding | Position A | Position B | Resolution |
|---|---|---|---|
| `_REVERSE_CACHE` staleness | `codex` P1 — "permanently stale within a process" | `security-reviewer` — not a finding: one-shot process, caches die before any edit | B is right about the shipped CLI path; A is right about in-process callers. Scan half fixed, staleness half carried as P2 follow-up. |
| `_normalize_hints` `.endswith(".py")` directory detection | `codex` P3 — misfires on a directory literally named `suite.py`, and a root conftest maps to `.` | `code-reviewer` — explicitly not a finding: every element originates from `rglob("*.py")` or `source_to_test_candidates`, so the only non-`.py` entries are conftest mappings | Not fixed. B's construction argument holds for real inputs; A's cases are unreachable in any layout this ships against. |

## Cross-model second opinion

| Model | Status | Detail |
|---|---|---|
| `codex` | `invoked` | 5 findings (3× P1, 1× P2, 1× P3). Three were oracle-confirmed and two of those are now fixed. |
| `antigravity` | **`failed`** | *payload unreadable via stdout: ValueError.* No vote. The readable fragment pointed at `_reverse_map`/`package_root`, corroborating the finding the other two raised. |

---

### Iteration 2 (Grade: B → B)
Fixes applied: 5 · Verification: full suite `pytest_rc=0`, ruff + `mypy --strict` clean · Reverted: 0

| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| F1 | P1 | SKILL §2 argv quoting + `=` form + §4 failure arm | `skills/targeted-test-selection/SKILL.md.j2` | Applied |
| F2 | P1 | Bound the reverse scan (exclusions + 2000 cap) | `test_dep_map.py` | Applied |
| F3 | P1 | Accept the bare `tests`/`test` roots in `select_tests` | `test_dep_map.py` | Applied |
| F4 | P1 | `_with_ancestors` — ancestor package edges | `test_dep_map.py` | Applied |
| F7 | P2 | Render-test assertions that held in the broken world | `tests/render/...` | Applied |

Re-review re-spawned both reviewers (scopes touched). Cross-model NOT re-invoked — each model is
called exactly once per `/hm:review`; round-1 findings are carried forward.

**Round-2 outcome:** `security-reviewer` closed both of its round-1 P1s. `code-reviewer` passed
4 of 5 fixes. Every remaining finding was introduced BY the round-2 fixes.

### Iteration 3 (Grade: B → A)
Fixes applied: 3 · Verification: full suite `pytest_rc=0`, ruff + `mypy --strict` clean · Reverted: 0

| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| G1 | P1 (CR) / P2 (SR) | Cap trips silently → stderr warning + first test of the cap branch | `test_dep_map.py` | Applied |
| G2 | P2 (SR) | `build`/`dist` excluded at any depth dropped first-party `pkg/build/` | `test_dep_map.py` | Applied (see below) |
| G3 | P2 (CR) | Directory↔file subsumption missing across the aggregate | `test_dep_map.py` | Applied |

**G2's first attempt was wrong and my own new test caught it.** Anchoring on the string position
made `pkg/build/` look top-level, because `_package_root` for a module in `src/pkg` IS `src/pkg`.
The exclusion is now conditioned on the scan root not itself being a package — the project-root
case the cap exists for — with tests for both directions.

**One `code-reviewer` P1 recommendation was declined, deliberately.** It asked that an over-cap
root degrade to `CLASS_SOURCE_WITHOUT_HINTS` → FULL. Refused: the reverse map is an *enhancement*
over the direct-importer scan, not its base. Above the cap the selection falls back to exactly
what this branch's predecessor did for every repo — convention candidates plus direct importers —
so degrading to FULL would make large monorepos strictly worse than before this change. The
finding's real content was the *silence*, and that is fixed (stderr line + regression test).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 9         | —   |
| 2         | B     | 5             | 4         | 3   |
| 3         | A     | 3             | 2         | 0   |

Final grade: **A**
Iterations used: 3 / 3
Status: **APPROVED**
human_review_needed: **true**

⚠️ Grade A but 2 unverified severe finding(s) remain (manual-only / weak-consensus P1) —
human review required before wrapup:

1. **Namespace packages get the wrong qualified name** (`codex` P1, manual-only). No in-repo
   oracle — this repo uses regular packages throughout. The fix needs a source-root notion
   derived from project configuration rather than from `__init__.py` presence, which is a design
   decision rather than a patch. Failure direction is fail-safe (fewer dependents → FULL) and the
   round-2 cap now bounds its cost. Affects consumer harnesses only.
2. **`_REVERSE_CACHE` staleness** (`codex` P1 / `code-reviewer` P2, weak-consensus). Keyed only by
   `package_root`, no file-set fingerprint. `security-reviewer` refuted the shipped-path impact —
   `hm test_dep_map` is one-shot, so caches die before the auto-fix loop can edit anything — but
   `execute.md.j2:17` invites agents to call `build_test_hints()` in-process, which is the path
   where it could bite.

---

## Post-review work (user-directed, after the loop closed)

The user asked for both deferred findings to be fixed rather than carried. This is new
work landed after the 3-round loop closed, so it is recorded separately and re-reviewed
on its own rather than counted as a fourth auto-fix iteration.

### 1. Source-root derivation replaces `_package_root` — resolves the namespace-package P1

The user's steer ("some code breaks when there is no `src/`") pointed at the real root
cause, which is neither `src/` nor namespace packages specifically: **the import root was
derived from `__init__.py` presence**. Measured across all four layouts before touching
anything:

| Layout | before | after |
|---|---|---|
| `src/acme/mod.py` (regular) | `acme.mod` ✓ | `acme.mod` ✓ |
| `acme/mod.py` (flat, regular) | `acme.mod` ✓ | `acme.mod` ✓ |
| `src/acme/widgets/mod.py` (namespace) | **`widgets.mod`** ✗ | `acme.widgets.mod` ✓ |
| `acme/widgets/mod.py` (flat namespace) | **`widgets.mod`** ✗ | `acme.widgets.mod` ✓ |

So the defect was layout-independent, and the two regular-package rows are the regression
guard — they were already correct and had to stay correct.

`_SOURCE_ROOT_DIRS = ("src", "lib")` + `_source_root(path, project_root)` now derive the
root from the project; `_qualified_name` relativizes to it directly; `project_root` is
threaded through `_targets_cached`, `_reverse_map`, `_reverse_dependents` and
`find_importers`. `_package_root` is deleted. Pinned by 8 parametrized tests (4 layouts ×
{qualified name, end-to-end importer resolution}).

**Stated limitation:** configuration-declared roots (`[tool.setuptools] package-dir` and
the Poetry/Hatch equivalents) are still not read. Such a project names modules relative to
the project root instead — fewer matches, therefore FULL, never a wrong match.

### 2. `_REVERSE_CACHE` fingerprint — resolves the staleness P1

The key is now `(source_root, len(candidates), newest_mtime_ns)`, computed before the
lookup: one `rglob` + `stat` per lookup buys back the AST walk, which is the expensive
half. `clear_caches()` added for in-process callers. Pinned by a test that creates a file
between two `build_test_hints` calls and requires the second to see it.

### Side effect: the selection got faster, not slower

The reverse-scan root moved from the topmost package (`src/harness_maker`) to the source
root (`src`), which removed duplicated scanning:

| Gate | round 3 | now |
|---|---|---|
| hub `io_utils.py` (limit 15s) | 6.68s | **3.48s** |
| 22-file run (limit 30s) | 6.95s | **4.50s** |

### 3. Delta re-review — it found two P1s, both introduced by §1

The refactor was re-reviewed on its own rather than counted as a fourth auto-fix round.
Both P1s were mine, and one was a **regression**:

| # | Sev | Finding | Oracle |
|---|---|---|---|
| H1 | P1 | `lib` in `_SOURCE_ROOT_DIRS` mis-roots a project whose `lib/` is a real package | `lib/foo.py` → qualname `foo` (want `lib.foo`), `hints: []` |
| H2 | P1 | The `build`/`dist` gate asked whether the scan root was a package — permanently False once the root became `src/`, so first-party `src/build/` was dropped | scan returned only `['src/pkg/__init__.py']` |
| H3 | P2 | `find_importers`' `project_root` default was correct only via the degenerate out-of-project fallback arm | — |
| H4 | P2 | Reverse-cache key omitted `project_root` and the free `size` dimension | — |

**H1 is the one worth remembering.** Fixing namespace packages broke a shape the *previous*
`__init__.py` walk handled correctly, while the docstring I wrote next to it claimed the
heuristic could only cost "fewer matches … never a wrong match" — it could also
cross-select `lib/foo.py` with a top-level `foo.py`. A candidate directory that is itself
importable is a package, never an import root; that guard is now explicit and tested.

**H3 confirmed a suspicion I had raised in the review brief.** I asked whether the
`project_root` default was right or merely accidental; the answer was accidental — it only
worked because those call sites use level-0 imports where `importer_pkg` is never read.
The parameter is now required.

Verification after H1–H4: full suite `pytest_rc=0`, ruff + `ruff format --check` +
`mypy --strict` clean, repo invariants hold (`autopilot_ledger` → `source-with-hints`,
`readiness` → `ai_readiness` test, `_source_root` of a repo module → `src`), perf gates
4.17s / 4.40s against 15s / 30s.

---

Also carried, below the severe threshold: `test_no_positional_params_in_commands.py` does not scan
`templates/skills/**` (no live defect — the skill body contains no `$`); the three module-scoped
caches have no reset API; `__pypackages__` (PEP 582) is not in the scan exclusions.
