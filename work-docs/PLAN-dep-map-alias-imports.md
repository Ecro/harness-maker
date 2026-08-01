---
type: plan
task_slug: dep-map-alias-imports
status: complete
created: 2026-08-01
tags: [harness-maker, plan, python, test-selection, ast, templates]
interview_rounds: 4
adrs: 5
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Replace test_dep_map's substring import matching with qualified module resolution; route review auto-fix verify through it"
---

## 🎯 Executive Summary

**TL;DR** — `test_dep_map.find_importers` never inspects `ast.ImportFrom.names`, so any
module reachable only via `from harness_maker import <mod>` resolves to zero importers,
falls to `source-without-hints`, and forces `mode: full`. The execute stage's "run only
affected tests" optimisation is therefore dead for those modules. The same function's
substring matching is separately unsound. And `review.md.j2:531` runs `uv run pytest -x`
unconditionally on every auto-fix round.

**What** — five changes:
1. Replace substring matching with **qualified module-path resolution** (ADR-001).
2. Add a **1-hop reverse source-dependency** expansion over the package root (ADR-002).
3. Treat **`conftest.py` as a first-class consumer**, mapping to its directory (ADR-003).
4. Route the **review auto-fix verify** step through `hm test_dep_map` (ADR-004).
5. Own the select-then-run recipe in a **new `targeted-test-selection` skill**, because the
   command-size ratchet leaves 584 characters and the recipe does not fit (ADR-005).

**Why** — measured at plan time:

| Symptom | Evidence |
|---|---|
| alias-only modules force FULL | `classify_path("src/harness_maker/autopilot_ledger.py")` → `source-without-hints`, 0 hints, despite 5 test files importing it |
| the style is real | 121 `from harness_maker import X` occurrences under `tests/` |
| substring matching is unsound | `eig` matches `for·eig·n`; `cache` matches `detection_cache`; `verify` matches `plan_verify`; `telemetry` matches `review_telemetry` — none of those modules import the shorter one |
| stem identity is ambiguous | `src/harness_maker/profile.py` **and** `src/harness_maker/memory/profile.py` both exist |
| autouse fixtures are invisible | `tests/unit/conftest.py:108` imports `economics_source` in an autouse fixture; `find_importers` skips every file not named `test_*` |
| the cost was 7 full runs | 1× execute (`execute.md.j2:298` FULL), 3× review auto-fix rounds (`review.md.j2:531`), 3× manual confirmation |

**Estimated impact** — one source file (`test_dep_map.py`), one new skill, one template
(`stages/review.md.j2`), one test file (`tests/unit/test_dep_map.py`), one new structural
test, plus baseline refreshes for the seven rendered artifacts that carry the changed text.

## 📚 Prior Work

- `src/harness_maker/test_dep_map.py:136-143` already records the concern
  ("degenerates to always-FULL in this repo") but attributes it **only** to non-`.py`
  files. The alias case is the second, unrecorded cause of the same symptom.
- `SELECTOR_SOURCE` (`test_dep_map.py:228`) forces FULL whenever the selector's own source
  changes. Phases 1–2 edit that file, so this task's own `/hm:execute` Phase D will
  correctly run the full suite. Designed behaviour, not a regression.
- CLAUDE.md "absent-case = feature black hole" (2026-06-08). Here the absent case (no
  importer found) *was* defined — FULL — but the detector was broken, so the safe branch
  fired always and the optimisation never did: a working fallback masking a dead primary
  path, indistinguishable from "the optimisation is conservative".
- `tests/structural/test_command_size_budget.py:96-125` records ADR-011 (a ceiling must not
  be raised to make a phase pass) and ADR-012, the single override — which required a
  documented −71% compaction first. ADR-005 below follows ADR-012's *other* half: move the
  procedure into a skill instead of spending command budget.
- **Two designs were rejected before this revision.** The interview's first draft
  (segment-set matching, parent-directory scan) was refuted by both second-opinion models;
  its replacement was refuted by `plan-validator` on seven critical points. Both are
  recorded in the transcript and in the ADRs' "Rejected alternatives", because they are
  why the current design is shaped the way it is.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | 1 | Matching semantics | Contract shape | How should `find_importers` match a module name? | **dotted-segment unification** | Superseded at #6 after cross-model review found stem ambiguity | ADR-001 |
| 2 | 1 | review verify scope | Testing depth | What changed-file set feeds dep-map in the auto-fix loop? | **full review diff** | Same source Step 3.5's `high_diff classify` uses; extended at #6 to union untracked paths | ADR-004 |
| 3 | 1 | Regression gate | Testing depth | What shape should the regression gate take? | **synthetic fixture unit tests only** | Live-repo assertions rejected as brittle; render-grep declined — partially reversed at #8 | — |
| 4 | 2 | Lost indirect coverage | Risk tolerance | Dropping substring matching loses 2 real indirect edges. Accept or replace? | **1-hop reverse src dependency** | Curation table rejected as hand-maintained rot | ADR-002 |
| 5 | 2 | Reverse-dep depth | Architecture | How deep should the reverse walk go? | **1-hop, fixed** | Transitive would make any hub edit reach everything | ADR-002 |
| 6 | 3 | Module identity | Contract shape | Segment-bag matching is ambiguous and the parent-directory scan asymmetric. Replace with what? | **qualified module-path resolution** | Raised independently by both models; verified — `profile.py` exists twice | ADR-001, ADR-002 |
| 7 | 3 | conftest consumers | Testing depth | Autouse fixtures importing a module are invisible. Address now? | **include, map to directory** | Autouse genuinely applies tree-wide, so directory granularity is honest | ADR-003 |
| 8 | 4 | Command char budget | Dependencies | `review` has 584 chars of ratchet headroom; the recipe needs ~700+. How to proceed? | **extract the recipe into a skill** | Skills are outside the ratchet; ADR-012 set the precedent. Compact-first and terse-inline both rejected | ADR-005 |
| 9 | 4 | Phase 3 exit form | Testing depth | Hand-enumerate the rendered artifacts, or derive the property? | **derived property test** | Reverses #3's render-grep refusal: the artifact count turned out to be 7, not 5, and a hand list already missed two | — |

### Measurements taken during the interview

Recorded because they are the evidence the ADRs rest on, with the **method** for each so it
can be reproduced. A second-opinion model correctly objected that heuristic-vs-heuristic
deltas are not correctness claims.

- *Selection delta (segment vs substring)*: AST-walked every `tests/**/test_*.py`, computed
  the importer set for all 82 top-level src modules under both rules, diffed. 28 modules
  gain, 6 lose. **This measures the rejected draft rule, not ADR-001's qualified rule** —
  recomputed in Phase 1 (exit criterion).
- *Which losses are real*: for each of the 6, grepped the suspected dependent's source for a
  module-level `^(from|import).*\b<name>\b`. `economics_source`→`economics` and
  `ai_readiness`→`readiness` are real edges; `eig`, `cache`, `verify`, `telemetry` had
  **zero** import statements in their supposed dependents. A directed-edge check, not an
  inference from substring output.
- *Reverse-dependency fan-out*: 1-hop reverse map over `src/harness_maker/*.py` (top-level
  only). Median 1, mean 2.3; worst `io_utils` 32/82 (39%), `models` 26/82 (31%),
  `command_registry` 23/82 (28%); 25 modules have 0 importers. **Global scan** — recomputed
  over the full 128-file package root in Phase 2 (exit criterion).
- *conftest fan-out*: the 5 `tests/**/conftest.py` files import exactly 4 src modules —
  `synthesize` (3 conftests), `detection_cache`, `foreign_config`, `economics_source`.
  Directory mapping adds `tests/unit` (304 of 364 test files) for those four, plus
  `tests/render` + `tests/structural` for `synthesize` — 324/364 (89%) worst case.
- *Package-root determinism*: all 8 subpackages have `__init__.py`; `src/` does not.
  `package_root` resolves to `src/harness_maker` for every source file. **`tests/` is
  itself a package** (`tests/__init__.py`, `tests/unit/__init__.py` exist), so a test file's
  own package root is `tests` — a different directory from the changed module's. ADR-001
  therefore carries two roots, not one.
- *Char budget*: **the binding gate is the aggregate, not the per-command ceiling.**
  `_ATOMIC_RATCHET["review"] = 29235` with a `×1.02` ceiling leaves 584 chars, and the fused
  entries leave 1,025–1,713 — but `test_aggregate_shipped_surface_does_not_grow`
  (`test_command_size_budget.py:330-361`) asserts `now <= was`, a **strict non-increase**,
  summed over every `.claude/commands/hm/*.md` and every `.agents/skills/hm-*/SKILL.md`
  (`_surface_baseline.py:109-117`). `surface_baseline.json` was re-frozen at HEAD
  (`dfb3caeb`, a test-only commit on top of the `c962e57e` render), so the current render
  equals the frozen sum: **headroom is 0**. The line being replaced is **77 chars**, present
  in 6 of the 7 measured artifacts. Any replacement must be **≤77 chars** or be paid for by
  a compensating cut. Measured candidate:
  `   - Python: follow the \`targeted-test-selection\` skill (§1-§4).` = **64 chars, −13 per
  artifact**, so the aggregate strictly decreases. execute's analogous inline block is 929
  chars including its `{% if is_codex %}` dual branch — inline is impossible at any useful
  length, which is what makes ADR-005 necessary rather than merely convenient.
- *Rendered artifact count*: 7 files carry the auto-fix `uv run pytest -x` from this
  template — `.claude/commands/hm/{review,exec-rev,exec-rev-wrap,exec-rev-wrap-ver,plan-exec-rev}.md`,
  `.agents/skills/hm-review/SKILL.md`, `.claude/stages/review.md`. An earlier count of 5 in
  this PLAN was produced by a `grep … | head -10` that truncated — the exact habit
  CLAUDE.md's context-discipline section warns about, and it caused a wrong disposition.

## 📐 Architecture Decision Records

### ADR-001: Qualified module-path resolution replaces substring matching
**Status:** Accepted (2026-08-01, via /hm:plan interview #1, revised at #6, corrected after validation)
**Context:** `find_importers` matches `module_name in alias.name` / `in node.module`, never
inspecting `ImportFrom.names`, so the `from harness_maker import a, b, c` style (121
occurrences under `tests/`) resolves to zero importers for `b` and `c`. Substring matching
separately produces false positives. The first repair — matching an unordered set of
dot-delimited segments — was rejected at cross-model review: it flattens `a.x` and `x.a`,
treats every imported symbol as a module, and cannot separate the two `profile.py` files.
**Decision:** Resolve both sides to **fully qualified dotted module names** and compare for
equality. Two distinct roots are involved and must not be conflated:

| Root | Derivation | Used for |
|---|---|---|
| `package_root` | walk up from a file while the containing directory has `__init__.py`; the last such directory | deriving that file's qualified name |
| `search_root` | `package_root.parent` of the **changed** module (`src/` in this repo) | the disk probe below |
| `importer_pkg` | the qualified package of the **importing** file, from *its own* `package_root` (`tests.unit` for `tests/unit/test_x.py`) | resolving `node.level` |

- *Changed file → qualified name*: `src/harness_maker/memory/profile.py` →
  `harness_maker.memory.profile`, `package_root = src/harness_maker`, `search_root = src/`.
- *`import a.b.c`*: target is `a.b.c`. An `as` alias is irrelevant — the target is
  `alias.name`, never `alias.asname`.
- *`from P import n`*: resolve `P` first — level 0 → `P` as written; level ≥ 1 → walk up
  `level - 1` packages from `importer_pkg` and join with `node.module` when present. Then,
  for each alias `n`, emit `P.n` **iff** `search_root/P.replace(".", "/")/n.py` or
  `…/n/__init__.py` exists; otherwise `n` is a symbol and the edge is to `P`.
- *`from P import *`*: `alias.name == "*"`; emit `P` only.
- A file is an importer iff the changed module's qualified name is in the resulting set.

**Consequences:**
- ✅ `from harness_maker import autopilot_ledger` resolves — the alias form is readable.
- ✅ `import harness_maker.autopilot` and `from harness_maker.autopilot import x` keep working.
- ✅ No fragment false positives; `profile.py` vs `memory/profile.py` are distinct.
- ✅ Symbol-vs-module is decided by disk existence, not guessed.
- ⚠️ Three roots to keep straight. The validation pass caught a draft that probed
  `package_root/P/n.py` — expanding to `src/harness_maker/harness_maker/…`, which never
  exists, so **every** `from P import n` would have degraded to a `P` edge and the headline
  alias case would still have failed. The table above exists because that error was silent.
- ⚠️ `search_root` is derived from the **changed** module for every importer, so an importer
  whose own package lives under a different root (e.g. `from tests.helpers import mod` in a
  multi-root consumer project) probes under the wrong tree, misses, and degrades to a `P`
  edge. Over-selection, therefore the same fail-safe direction as R11. Inert in this repo —
  a `tests.*` target can never equal a `harness_maker.*` qualname.
- ⚠️ Dynamic references — `importlib.import_module("harness_maker.x")`, string monkeypatch
  targets — remain invisible. They were invisible under substring matching too (both sides
  read AST identifiers, never string literals), so this is a carried-forward hole (R6), not
  a regression. Independently corroborated by the antigravity second opinion.
**Rejected alternatives:**
- *Dotted-segment set matching* — rejected at cross-model review: loses position, conflates symbols with modules, cannot separate the two `profile.py` files.
- *Keep substring, add alias check* — rejected: fixes the false negatives while preserving every false positive.
- *Qualified resolution with a stem fallback* — rejected: two coexisting rules mean no reader can predict which path a match took.
**Source:** Interview #1, #6

### ADR-002: 1-hop reverse source dependency over the package root, depth fixed at 1
**Status:** Accepted (2026-08-01, via /hm:plan interview #4, #5, revised at #6)
**Context:** Substring matching accidentally covered two real indirect dependencies. ADR-001
removes that accident; silently losing them means a change to `readiness.py` could leave
`ai_readiness` broken while the targeted run reports green. The draft's "scan the changed
file's parent directory" was rejected: it scans 82 files for a top-level module but 6 for
`memory/profile.py`, so cross-subpackage reverse edges are visible in one direction only,
purely by filesystem position.
**Decision:** Scan the **package root** resolved by ADR-001 (`rglob("*.py")`, excluding the
changed file), apply ADR-001's resolution to each file, and collect modules importing the
changed module's qualified name. Union each dependent's `source_to_test_candidates` +
`find_importers` results into the hint set. Exactly **one hop**.

**The cache is module-scoped, not invocation-scoped.** Parsed ASTs are memoized by
`(path, mtime)` and the reverse map by `package_root`, both surviving across
`build_test_hints` calls within one process. A per-invocation cache — the first draft — is
discarded **2N times for an N-file change**, not twice: `select_tests` builds
`{rel: classify_path(rel, …) for rel in changed}` (`test_dep_map.py:278`) and
`classify_path` calls `build_test_hints([src], …)` with a **one-element** list (`:257`), then
`select_tests` calls it again per file (`:314`). Each invocation would rebuild the 128-file
package-root map plus a 364-file `tests/` sweep. At N = 30 — an ordinary review diff, which
is exactly ADR-004's changed set — that is ≈29,500 AST parses **per auto-fix round**, i.e.
slower than the ~6-minute full suite this exists to avoid.

**Consequences:**
- ✅ Indirect coverage becomes a designed property with a stated depth, not a naming coincidence.
- ✅ The scan is symmetric — a top-level module and a subpackage module see the same graph.
- ✅ Fan-out stays bounded: measured median 1, worst 39% (recomputed over the full package in Phase 2, with a numeric gate).
- ⚠️ Hub modules select a large fraction of the suite. Still strictly less than the FULL they trigger today.
- ⚠️ A 2-hop break (A → B → C, edit C, only B's tests run) is out of scope (R7).
- ⚠️ With multiple changed files, per-file expansions are unioned, so changing both B and C *does* reach A — two hops from C. Over-selection, therefore safe; stated so the batch-dependent behaviour is not later read as a bug.
**Rejected alternatives:**
- *Transitive walk* — any edit to `io_utils` or `models` reaches nearly every module; `targeted` becomes a slower spelling of FULL.
- *2-hop* — still explodes on hub modules while adding an indefensible boundary.
- *Parent-directory scan* (the draft) — rejected at cross-model review for the asymmetry above.
- *Hand-curated mapping table* — 2 entries today, unbounded drift tomorrow, no staleness signal. `DOC_CONSUMING_SUITES` is defensible because doc→suite links cannot be derived; import edges can.
**Source:** Interview #4, #5, #6

### ADR-003: `conftest.py` is a first-class consumer, mapped to its directory
**Status:** Accepted (2026-08-01, via /hm:plan interview #7)
**Context:** `find_importers` skips every file whose basename is not `test_*`.
`tests/unit/conftest.py` imports `detection_cache`, `foreign_config`, `synthesize` and (in
an autouse fixture body) `economics_source`; `tests/render` and `tests/structural`
conftests import `synthesize`. An autouse fixture that breaks takes its whole tree with it.
**Decision:** `find_importers` also scans `conftest.py`, and a conftest match contributes
the conftest's **parent directory** as the affected node — pytest accepts a directory node
id, and the directory is the real blast radius of an autouse fixture.

**The scan and the mapping land in the same phase (Phase 2).** Splitting them was the
validator's first critical finding: a `find_importers` that returns `tests/unit/conftest.py`
as a *file* passes `select_tests`' bare `tests/` prefix filter (`:315`), survives the
`empty_hint_sources` backstop (`:317-331`) because nothing was filtered away, and yields a
`targeted` run whose node list collects **zero tests** — a green result that ran nothing.
That is a new false-green class, worse than either the before or after state.

**Consequences:**
- ✅ Closes a real false-green path: an autouse fixture's dependency is no longer invisible.
- ✅ Granularity matches the mechanism — autouse really does apply tree-wide.
- ⚠️ Coarse: exactly 4 src modules are affected; for them selection grows to `tests/unit` (304/364) or, for `synthesize`, 324/364 (89%).
- ⚠️ A conftest match is not distinguished from a test-file match in the returned list; both are strings, and `select_tests`' `tests/` prefix filter accepts a directory.
**Rejected alternatives:**
- *Defer and record as a limitation* — it is a live false-green path, and the premise of this task is that a silently-degraded selector is worse than an honest FULL.
- *A conftest match forces `mode: full`* — that is the disease being cured; `economics_source` would return to always-FULL.
**Source:** Interview #7

### ADR-004: The review auto-fix loop's verify step selects tests via `test_dep_map`
**Status:** Accepted (2026-08-01, via /hm:plan interview #2, revised at #6, corrected after validation)
**Context:** `review.md.j2:531` instructs `uv run pytest -x` unconditionally on every
auto-fix round — several full-suite runs per review, repeating `/hm:execute` Phase D.
**Decision:** The Python branch of the verify step follows the `targeted-test-selection`
skill (ADR-005), whose recipe is:

1. Changed set = **union of tracked and untracked**, NUL-delimited so paths with spaces,
   newlines or non-ASCII survive: `git diff -z --name-only HEAD` ∪
   `git ls-files -z --others --exclude-standard`, split on NUL.
2. `cd <the task worktree> && uv run --with {{ harness_maker_src_path }} hm test_dep_map --root . --changed-file <f1> …`
   — the full literal invocation with the runner prefix, run **inside the worktree the stage
   was given**, as every command in this template is (`review.md.j2:305`,
   `execute.md.j2:307`). A bare `hm` or a base-repo `cd` selects from the wrong tree, and the
   failure mode of a missing entrypoint inside prose is an LLM silently skipping the step.
   **Prose worktree wording, and no leading `!`** — this line lives in a SKILL body, where a
   `!` is inert text rather than an executable-line marker and would misreport the line's
   status to any gate keyed on `^!`; and `<WT>` is a token bound by the *command's* worktree
   preflight, not by the skill, so carrying it out of the command risks an unbound token and
   a base-tree selection. `second-opinion-gate/SKILL.md.j2:28,64,153` sets this precedent.
3. **Empty changed set → still invoke, with zero `--changed-file` arguments**, and honour
   the returned `mode: full`. Stated explicitly because `select_tests`' empty-list guard
   (`test_dep_map.py:270-277`) only fires if the CLI is actually called; the natural reading
   of "compute the set, then run with it" is to skip the step, which would run no tests at
   all and report success.
4. `mode: targeted` → pytest with `node_ids`; `mode: full` → full suite, echoing `reason`
   verbatim.

`ruff check` and `mypy --strict` stay unconditional — repo-wide, cheap, no selection
concept. Rust and Node branches are unchanged (dep-map is Python-only).

**Consequences:**
- ✅ Removes rounds 2..N of full-suite execution; the FULL fallback keeps the safety property.
- ✅ Same tracked-diff source Step 3.5's `high_diff classify` uses, so the two agree about what changed.
- ✅ An auto-fix that creates a new file is seen (the untracked union), and a locale- or space-named path is not mangled (NUL delimiting).
- ⚠️ Deleted paths pass through to `classify_path`, which is path-only and never stats (`:237-243`) — a deleted `.py` with no hint forces FULL, the correct conservative answer.
- ⚠️ Selection quality in review is coupled to the selector's correctness — which Phases 1–2 repair, and why they land first.
**Rejected alternatives:**
- *Only this round's fix files* — a round-3 fix can regress a round-1 area.
- *Per-round narrow + one final full run* — reintroduces a full-suite run per review to buy coverage the FULL fallback already guarantees.
- *`git diff --name-only HEAD` alone* (the draft) — excludes untracked files, so a fix that adds a module or test is invisible.
- *Line-split without `-z`* — `git diff --name-only` octal-escapes and quotes non-ASCII and space-bearing paths; this repo ships Korean-named assets, and a mangled path classifies as `source-without-hints` (uselessly conservative) or, under a matching prefix, `inert` (unsafe).
**Source:** Interview #2, #6

### ADR-005: The select-then-run recipe is owned by a new `targeted-test-selection` skill
**Status:** Accepted (2026-08-01, via /hm:plan interview #8)
**Context:** Two size gates bind, and only the weaker one is obvious. `_ATOMIC_RATCHET["review"]`
(29,235 with a `×1.02` ceiling) leaves 584 characters — but
`test_aggregate_shipped_surface_does_not_grow` (`test_command_size_budget.py:330-361`)
asserts `now <= was`, a **strict non-increase** over the summed
`.claude/commands/hm/*.md` and `.agents/skills/hm-*/SKILL.md` renders, against a baseline
re-frozen at HEAD. **Headroom there is 0.** The line being replaced is 77 chars and appears
in 6 of the 7 artifacts, so the budget is *net ≤ 0 per artifact*, not 584. ADR-004's recipe
in execute Phase D's shape is 929 chars — inline is impossible at any useful length. The
file's comments record ADR-011 (a ceiling must not be raised to make a phase pass) and its
single override ADR-012, which bought room by moving a procedure into the
`second-opinion-gate` skill. **The new skill is outside both gates**: the aggregate's codex
glob is `hm-*/SKILL.md`, which `targeted-test-selection` does not match.
**Decision:** Create a procedural skill `targeted-test-selection` owning the full recipe
(ADR-004 steps 1–4, with the literal commands, the empty-set branch, and the NUL handling).
`review.md.j2`'s verify step becomes a **≤77-character** reference to it — measured
candidate `   - Python: follow the `targeted-test-selection` skill (§1-§4).` at **64 chars,
−13 per artifact**, so the aggregate strictly *decreases*. `ruff check` and `mypy --strict`
move into the skill with the rest of the recipe. Register the skill in `synthesize.py:158`
and `interview.py:152,171`.
**Consequences:**
- ✅ The recipe can be explicit — the parts the validation pass required in writing (untracked union, empty-set branch, worktree scoping) are exactly what any inline budget would have forced out.
- ✅ The aggregate ratchet moves in the correct direction rather than merely holding.
- ✅ Single owner for a procedure `execute.md.j2` also implements; converging execute onto it later is a prose-only change (deferred — see Non-Goals).
- ✅ ADR-011 is respected: no ceiling and no baseline is regenerated.
- ⚠️ One more skill file to keep in sync, subject to the Production 150-line context-lint cap and `tests/unit/test_codex_phase7.py`'s per-skill codex-path assertions.
- ⚠️ A skill referenced by exactly one consumer today.
- ⚠️ The 64-char reference carries no commands at all, so a reader of `review.md.j2` alone cannot see what the verify step runs. Accepted: the alternative is a gate violation, and the skill is loaded by name in the same shape the template already uses for `second-opinion-gate`.
**Rejected alternatives:**
- *Compact `review.md.j2` elsewhere first, then spend the budget* — the sanctioned ADR-012 procedure. Rejected: it attaches an unrelated compaction to this task, leaves the execute/review duplication in place, and is unnecessary once the reference is a net *decrease*.
- *Fit the recipe inline* — impossible against a 0-headroom strict-non-increase gate; even the 584-char reading only bought a version stripped of the untracked union, the empty-set branch and the worktree prefix, each a silent-skip bug the validation pass flagged.
- *Regenerate `surface_baseline.json`* — the aggregate's own docstring reserves regeneration for adding a command or a target, and `test_surface_baseline.py::test_baseline_shape_matches_the_generator` is what forces that act. Regenerating to absorb growth is the ADR-011-forbidden move one layer up.
- *Extend `verify-before-completion`* — that skill is a 5-check wrapup gate; a non-check reference section dilutes its contract.
**Source:** Interview #8

## 🏗️ Technical Design

### Current State

`src/harness_maker/test_dep_map.py:64-92` — `find_importers(module_name, test_dir)`:

```python
if isinstance(node, ast.Import):
    for alias in node.names:
        if module_name in alias.name:      # substring
            ...
if isinstance(node, ast.ImportFrom) and node.module and module_name in node.module:
    ...                                     # node.names never read; node.level never read
```

`build_test_hints` (`:94-131`) calls `source_to_test_candidates` then `find_importers` as
the fallback — **it is `find_importers`' only in-module caller, at `:122`, and it passes a
bare stem**. `classify_path` (`:236-258`) returns `CLASS_SOURCE_WITH_HINTS` iff the hints
are non-empty; `select_tests` (`:261-…`) turns `CLASS_SOURCE_WITHOUT_HINTS` into
`mode: full`. Both `classify_path` and `select_tests` call `build_test_hints` for the same
path, so any per-call cost is paid twice.

`src/harness_maker/templates/stages/review.md.j2:530-534` — verify step, unconditional.

### Affected Components

| Component | Change | Phase |
|---|---|---|
| `test_dep_map` (new private helpers) | package-root walk, qualified-name derivation, import-target resolution | 1 |
| `test_dep_map.find_importers` | qualified matching; `ImportFrom.names` + `node.level` read; new signature | 1 |
| `test_dep_map.build_test_hints` | call-site update for the new signature | 1 |
| `test_dep_map` (new helper) | 1-hop reverse source-dependency scan + per-invocation memoization | 2 |
| `test_dep_map.build_test_hints` | unions reverse dependents; conftest scan + directory mapping | 2 |
| `templates/skills/targeted-test-selection/SKILL.md.j2` | **new** — owns the recipe | 3 |
| `synthesize.py:158`, `interview.py:152,171` | skill registration | 3 |
| `templates/stages/review.md.j2` | verify step references the skill | 4 |
| `tests/unit/test_dep_map.py` | new synthetic-fixture cases | 1, 2 |
| `tests/structural/` | new derived render-property test | 4 |
| 7 rendered artifacts + baselines | refreshed | 4 |

Not touched: `classify_path`, `select_tests`, `source_to_test_candidates`,
`RENDER_AFFECTING_SUITES`, `DOC_CONSUMING_SUITES`, `SELECTOR_SOURCE`, the CLI surface.

### Architecture

```
package_root(src/harness_maker/memory/profile.py) -> src/harness_maker   (walk up while __init__.py)
qualified_name                                    -> harness_maker.memory.profile
search_root                                       -> src/                (package_root.parent)

package_root(tests/unit/test_x.py)                -> tests                (tests/__init__.py exists)
importer_pkg                                      -> tests.unit           (for node.level)

import_targets(tree, importer_pkg, search_root) -> set[str]
    import a.b.c                 -> {"a.b.c"}                (asname ignored)
    from P import n              -> {"P.n"}  if search_root/P/n.py or search_root/P/n/__init__.py
                                    {"P"}    otherwise (n is a symbol)
    from . import n   (level=1)  -> P := importer_pkg, then as above
    from ..pkg import n (level=2)-> P := importer_pkg minus 1 + "pkg", then as above
    from P import *              -> {"P"}

is_importer(file) := qualified_name(changed) in import_targets(file)
```

The reverse walk (ADR-002) applies the same predicate to source files under the changed
module's `package_root`. Consumers scanned by `find_importers` are `test_*.py` (→ the file)
and, from Phase 2, `conftest.py` (→ its parent directory).

### Data Flow

```
changed file ──► source_to_test_candidates ─────────────────┐
             ├─► find_importers(tests/) ──────────────────►┤
             │      ├─ test_*.py   -> file                  │
             │      └─ conftest.py -> parent directory      ├──► hints ──► classify_path
             └─► reverse_dependents(package_root) ──────────┤                    │
                    └─► per dependent: candidates + importers               select_tests
                          (all AST parses memoized per invocation)      targeted / full
```

### API Changes

`find_importers` changes from `(module_name: str, test_dir: Path)` to
`(module_qualname: str, test_dir: Path, search_root: Path)`. It has **two** callers: the
in-module `build_test_hints` at `test_dep_map.py:122` (updated in Phase 1 — an earlier draft
of this PLAN listed `build_test_hints` as out of scope, which would have left an arity
mismatch or, worse, a bare stem flowing into a qualified matcher and every classification
degrading to `source-without-hints`) and `tests/unit/test_dep_map.py`. No template, CLI or
other module references it.

`build_test_hints`, `classify_path`, `select_tests` and the `hm test_dep_map` CLI surface
are unchanged, so `command_registry` and `tests/unit/test_command_surface_gate.py` need no
update.

## 📝 Implementation Plan

### Phase 1 — Qualified module resolution in `find_importers`

- **depends_on:** `[]`
- **parallel_group:** `serial-selector`
- **merge_hazards:** `src/harness_maker/test_dep_map.py` (shared with Phase 2). **Phase 1
  must not be released alone** — it removes two real indirect edges that Phase 2 restores.
  The split is for reviewability, not independent shipping.
- **Scope — in:** `src/harness_maker/test_dep_map.py` — `_package_root`, `_qualified_name`,
  `_import_targets`, `find_importers`, **and the `build_test_hints` call site at `:122`**;
  `tests/unit/test_dep_map.py`
- **Scope — out:** the reverse walk, conftest scanning, `classify_path`, `select_tests`,
  `source_to_test_candidates`, every template
- **Work:**
  1. `_package_root(path) -> Path`, `_qualified_name(path, package_root) -> str`.
  2. `_import_targets(tree, importer_pkg, search_root) -> set[str]` implementing ADR-001's
     five forms, `node.level` resolution, and the `search_root`-anchored disk probe.
  3. Rewrite `find_importers(module_qualname, test_dir, search_root)`; scan `test_*.py`
     only (conftest lands whole in Phase 2).
  4. Update `build_test_hints:122` to derive the qualified name + search root and pass them.
  5. Tests: `from pkg import a, b` selects for `b`; `import pkg.a` selects; `from pkg.a
     import x` selects; `import pkg.a as z` selects for `a` not `z`; `from pkg import
     symbol` where `pkg/symbol.py` is absent selects `pkg` not `pkg.symbol`; `from . import
     b` resolves; `from ..other import c` resolves two levels up; `from pkg import *`
     selects `pkg`; `pkg.cache` is **not** selected by a file importing only
     `pkg.detection_cache`; `pkg.profile` and `pkg.sub.profile` do not select each other;
     an importer whose own package root differs from the target's still resolves.
  6. Update the `:136-143` comment block to name the alias cause alongside the non-`.py` cause.
- **Exit criterion:** `uv run pytest tests/unit/test_dep_map.py -q` green, **and** the
  selection-delta measurement recomputed against the qualified rule with **zero unexplained
  losses** — every module that loses selections relative to today must be shown, by the
  directed-edge grep recorded in the transcript, to have no import edge, or be restored by
  Phase 2. Any loss that fails both arms halts the phase.
- **Risk:** `medium` — changes selection semantics repo-wide.
- **Rollback point:** pre-Phase-1 HEAD.

### Phase 2 — Reverse dependency, conftest consumers, memoization

- **depends_on:** `[1]`
- **parallel_group:** `serial-selector`
- **merge_hazards:** `src/harness_maker/test_dep_map.py` (same file/region as Phase 1)
- **Scope — in:** `src/harness_maker/test_dep_map.py` — reverse-scan helper, conftest
  scanning **and** its directory mapping, per-invocation AST/reverse-map cache,
  `build_test_hints`; `tests/unit/test_dep_map.py`
- **Scope — out:** ADR-001's resolution rules (frozen by Phase 1), `classify_path`,
  `select_tests`, every template
- **Work:**
  1. Reverse-dependency helper: `rglob("*.py")` over the changed module's package root,
     skipping the changed file, reusing Phase 1's predicate.
  2. Memoize parsed ASTs by `(path, mtime)` and the reverse map by `package_root` at
     **module scope**, surviving across `build_test_hints` calls (ADR-002) — required, not an
     optimisation: an N-file change produces **2N** one-element invocations
     (`select_tests:278` → `classify_path:257` → `build_test_hints([src])`, then `:314`), so
     an invocation-scoped cache is discarded 2N times and buys nothing on the multi-file path
     that ADR-004 creates.
  3. Extend `find_importers` to scan `conftest.py`; map a conftest hit to its parent
     directory in `build_test_hints` before de-duplication, so a directory and a file under
     it do not both appear.
  4. Union each dependent's `source_to_test_candidates` + `find_importers` results into
     `affected`, preserving existing de-duplication.
  5. Tests: `b.py` imports `a.py` → changing `a.py` selects `test_b.py`; depth is 1
     (`c`→`b`→`a`; changing `a.py` does not select `test_c.py`); no dependents → unchanged;
     no self-inclusion; a cross-subpackage reverse edge is found; a conftest importing the
     changed module yields its **directory**, not the conftest file; a conftest-only
     consumer yields a node list that is non-empty **and** collects tests; two changed files
     where one imports the other de-duplicate cleanly.
- **Exit criterion:** `uv run pytest tests/unit/test_dep_map.py -q` green; **and**
  `classify_path("src/harness_maker/autopilot_ledger.py")` returns `source-with-hints`;
  **and** the hints for `src/harness_maker/readiness.py` include an `ai_readiness` test;
  **and** the reverse fan-out recomputed over the **full** 128-file package root with **no
  module exceeding 50% of the package** (measured worst today is 39%; a module above 50%
  halts the phase for a design review); **and** two wall-clock arms, because a single-file
  run is exactly the 2-invocation case an invocation-scoped cache already survives and
  certifies nothing about ADR-004's workload: `hm test_dep_map --changed-file
  src/harness_maker/io_utils.py` (the measured worst-case hub) under **15 seconds**, **and**
  a run with **≥20 changed `.py` files** under **30 seconds**.
- **Risk:** `medium` — a bug here inflates every targeted run rather than shrinking coverage.
- **Rollback point:** pre-Phase-1 HEAD (never a Phase-1-only state — see Phase 1's merge hazard).

### Phase 3 — New `targeted-test-selection` skill

- **depends_on:** `[2]`
- **parallel_group:** `serial-template`
- **merge_hazards:** `synthesize.py` / `interview.py` skill lists (any concurrent skill
  addition touches the same lines)
- **Scope — in:** `src/harness_maker/templates/skills/targeted-test-selection/SKILL.md.j2`
  (new), registration in `synthesize.py:158` and `interview.py:152,171`
- **Scope — out:** `review.md.j2` (Phase 4), `execute.md.j2` (Non-Goals), the
  `verify-before-completion` skill
- **Work:**
  1. Author the skill with ADR-004's four numbered steps, the literal
     `cd <the task worktree> && uv run --with {{ harness_maker_src_path }} hm test_dep_map …`
     invocation (prose worktree wording, **no leading `!`**, per the `second-opinion-gate`
     precedent), the `{% if is_codex %}` branch, the NUL-delimited changed-set computation,
     the empty-set instruction, and the `ruff check` / `mypy --strict` lines moved out of
     `review.md.j2`.
  2. Register it in both lists.
- **Exit criterion:** the skill renders to `.claude/skills/targeted-test-selection/SKILL.md`
  and `.agents/skills/targeted-test-selection/SKILL.md`; `uv run pytest tests/render
  tests/snapshot tests/unit/test_codex_phase7.py -q` green (that last suite iterates
  `_ALL_SKILLS` and asserts the codex-path output, and lives outside both render suites);
  the rendered SKILL.md is **≤150 lines** (Production context-lint cap)
- **Risk:** `low` — additive; nothing consumes it until Phase 4.
- **Rollback point:** Phase 2.

### Phase 4 — Point the review verify step at the skill

- **depends_on:** `[3]`
- **parallel_group:** `serial-template`
- **merge_hazards:** the 7 rendered artifacts, `tests/structural/instruction_baseline.json`,
  and the ratchet table — any concurrent template edit re-freezes the same files
- **Scope — in:** `src/harness_maker/templates/stages/review.md.j2` (step 3 of the auto-fix
  loop), a new derived structural test, baseline/snapshot refreshes, re-rendered self-harness
- **Scope — out:** `wrapup.md.j2:170,180` and `verify.md.j2:86,96`; the Rust and Node
  branches of the same step; the second, wrapup-owned `pytest -x` in
  `exec-rev-wrap-ver.md:1407` (a different stage's line that must survive)
- **Work:**
  1. Replace the Python line (77 chars) with a **≤77-char** reference to the skill, in the
     shape `review.md.j2:338` already uses for `second-opinion-gate`. Measured candidate is
     64 chars.
  2. Add a derived structural test (Interview #9) covering **all three output families**, not
     two: (a) the four review-bearing fused commands from `_WORKFLOWS`
     (`tests/structural/test_command_size_budget.py:127-133`), (b) the atomic `review`
     command plus `.claude/stages/review.md` from `synthesize._stage_files()`
     (`synthesize.py:163-171`), and (c) the codex `.agents/skills/hm-review/SKILL.md` — which
     requires rendering with `targets` **including `Target.CODEX`** (the `_render()` helper at
     `test_command_size_budget.py:172-201` passes `[Target.CLAUDE_CODE]` only, so a test built
     on that fixture cannot see family (c) at all). Assert the discovered artifact count is
     **7**, so a derivation that silently narrows fails. For each, assert the auto-fix verify
     step references `targeted-test-selection` and contains no unconditional `pytest -x`
     **within that step's bounds**. Deriving the set is the point: a hand list in an earlier
     draft said five, and omitting family (c) here would repeat that error at 6/7.
  3. Re-render the self-harness. If `tests/structural/test_instruction_preservation.py`
     goes red because a heading or `!` line was removed, the remedy is an
     `_ALLOWED_REMOVALS` entry keyed `<command>@<dev_mode>` **in its own commit** — **not** a
     regeneration of `instruction_baseline.json`, which would disable the gate.
  4. Confirm both size gates. The per-command `_ATOMIC_RATCHET["review"]` is the loose one;
     the binding one is `test_aggregate_shipped_surface_does_not_grow`, a strict
     non-increase with **zero** headroom against a baseline re-frozen at HEAD. Record the
     measured per-artifact delta (expected −13). **Do not raise any ceiling and do not
     regenerate `surface_baseline.json`** (ADR-011; regeneration is reserved for adding a
     command or a target, and is forced by `test_surface_baseline.py`, not by growth).
- **Exit criterion:** `uv run pytest tests/render tests/snapshot tests/structural
  tests/unit/test_command_surface_gate.py -q` green — including the new derived test,
  the unchanged `_ATOMIC_RATCHET["review"]` ceiling, **and
  `test_aggregate_shipped_surface_does_not_grow` passing against the unmodified
  `surface_baseline.json`**
- **Risk:** `medium` — not `low`: the suites named here are **ratchets**, so they block the
  change rather than merely detecting a stale fixture, and the cheapest wrong move (raising
  the constant) is the one ADR-011 prohibits.
- **Rollback point:** Phase 3.

## 🧪 Testing Strategy

**Unit** (`tests/unit/test_dep_map.py`, synthetic `tmp_path` fixtures only — Interview #3):
all cases enumerated in Phases 1 and 2.

**Structural** (Phase 4): one new derived test asserting the recipe reference across every
render that inlines the review stage, with the artifact set computed rather than listed.

**Integration / render**: `tests/render`, `tests/snapshot`, `tests/structural`,
`tests/unit/test_command_surface_gate.py`.

**Repo-level measurement** (a Phase 1 and Phase 2 exit criterion with numeric gates — zero
unexplained losses; no module's fan-out above 50%; the hub case under 15 seconds — not a
committed test, per Interview #3).

**Full suite**: runs once, at `/hm:execute` Phase D, forced by `SELECTOR_SOURCE`.

## 🚫 Non-Goals

- **`wrapup.md.j2` / `verify.md.j2` unconditional full runs** — real, but each fires once
  per task rather than once per fix round. Deferred, not overlooked.
- **Converging `execute.md.j2` Phase D onto the new skill** — desirable de-duplication, but
  it re-freezes the `execute` ratchet entry and every fused render for no correctness gain
  in this task.
- **Dynamic imports and string monkeypatch targets** (R6) — invisible before and after.
- **2-hop dependency breakage** (R7) — out of scope by ADR-002's stated depth.
- **The Rust and Node branches of the review verify step** — dep-map is Python-only.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Qualified resolution drops a real coverage edge the measurement misses | low | high | Phase 1's exit criterion halts on any unexplained loss; unmatched files still fall to `source-without-hints` → FULL |
| R2 | Reverse fan-out makes hub-module edits select most of the suite | high (by design) | low | Depth fixed at 1; Phase 2 gates at 50% of the package |
| R3 | Phase 4 lands while the selector is still mis-selecting | low | medium | `depends_on: [3]` → `[2]` → `[1]` |
| R4 | Phase 1 released without Phase 2 → conftest-shaped false green **and** two lost edges | medium | high | Phase 1 does not scan conftest at all (ADR-003); Phase 2's rollback point is pre-Phase-1 |
| R5 | conftest directory mapping over-selects (89% worst case) | high (by design) | low | Only 4 src modules affected; measured; the alternative (forcing FULL) is worse |
| R6 | Dynamic imports and string monkeypatch targets stay invisible | medium | medium | Pre-existing; recorded in ADR-001 and Non-Goals, corroborated by the antigravity second opinion |
| R7 | 2-hop breakage (A→B→C) remains invisible | medium | low | Recorded in ADR-002 and Non-Goals |
| R8 | The **zero-headroom aggregate** ratchet blocks Phase 4, and the cheapest fix (regenerating `surface_baseline.json`) violates ADR-011 | medium | medium | ADR-005 moves the recipe into a skill outside both gates and makes the reference a net −13 chars; Phase 4's exit criterion names the aggregate test and forbids regeneration |
| R9 | `instruction_baseline.json` regenerated instead of allowlisted, silently disabling the gate | medium | medium | Phase 4 work item 3 names the permitted remedy |
| R10 | Reverse walk is quadratic → `targeted` slower than the full suite | medium | high | Module-scoped memoization is a Phase 2 work item; **two** wall-clock gates — single-file hub <15s and a ≥20-file run <30s, because the single-file arm alone cannot see the multi-file path ADR-004 creates |
| R12 | The derived Phase 4 test is built on a claude-only render and silently covers 6 of 7 artifacts | medium | medium | Phase 4 work item 2 names all three output families, requires `Target.CODEX` in the render, and asserts the count is 7 |
| R11 | Package-root walk misbehaves in a consumer project with an unusual layout | low | low | The walk stops at the first directory without `__init__.py`; a wrong root yields *fewer* dependents — degrading toward today's behaviour, never toward a missed FULL |

## ✅ Success Criteria

- [x] `find_importers` matches `from harness_maker import <mod>` for every alias in the statement.
- [x] `find_importers` no longer matches on bare substrings (`cache` ↛ `detection_cache`).
- [x] `harness_maker.profile` and `harness_maker.memory.profile` do not select each other's tests.
- [x] `import x as y` matches `x`, never `y`; `from P import *` matches `P`.
- [x] `from P import n` matches `P.n` when `search_root/P/n.py` exists, and `P` otherwise.
- [x] Relative imports (`from . import x`, `from ..pkg import y`) resolve via `node.level` against the **importer's** package.
- [x] `build_test_hints`'s call site passes a qualified name and search root — no bare stem reaches the matcher.
- [x] `classify_path("src/harness_maker/autopilot_ledger.py")` returns `source-with-hints`.
- [x] Changing `readiness.py` selects `ai_readiness`'s tests via the 1-hop reverse walk.
- [x] The reverse walk is depth-1 and scans the whole package root, including subpackages.
- [x] A `conftest.py` importing the changed module contributes its **directory**, and the resulting node list collects a non-zero number of tests.
- [x] No module's reverse fan-out exceeds 50% of the package; the `io_utils` case runs in under 15 seconds **and** a ≥20-file invocation under 30 seconds.
- [x] AST and reverse-map caches survive across `build_test_hints` calls (module scope), not just within one.
- [x] The `targeted-test-selection` skill renders to both `.claude/` and `.agents/`, under 150 lines, is registered in `synthesize.py` and `interview.py`, and passes `tests/unit/test_codex_phase7.py`.
- [x] Every render that inlines the review stage references the skill and carries no unconditional `pytest -x` in the auto-fix verify step — asserted by a **derived** test covering all three output families (fused, atomic + `.claude/stages/`, codex `hm-review`) with the count asserted as 7.
- [x] The replacement reference is ≤77 chars; `_ATOMIC_RATCHET["review"]` is unchanged and green; `test_aggregate_shipped_surface_does_not_grow` passes against an **unmodified** `surface_baseline.json`; `instruction_baseline.json` is not regenerated.
- [x] `ruff check`, `mypy --strict`, and the full suite are green.

## 📌 Execution status (updated by /hm:execute, 2026-08-01)

| Phase | Status | Evidence |
|---|---|---|
| 1 — qualified module resolution | **DONE** | 26 unit tests; selection delta recomputed against the qualified rule — 33 modules gain, 36 (module, lost-test) pairs lose, and **zero** unexplained: a boundary-aware regex for each module's qualified name found no reference in any lost file |
| 2 — reverse dependency + conftest + memoization | **DONE** | 36 unit tests; `autopilot_ledger` now `source-with-hints`; `readiness` hints include an `ai_readiness` test; max reverse fan-out **33%** (`io_utils`, 43/129, gate 50%); single-file hub **6.68s** (gate 15s); 22-file run **6.95s** (gate 30s) — the near-equality is the cache surviving across the 2N invocations |
| 3 — `targeted-test-selection` skill | **DONE** | renders to `.claude/` and `.agents/`, **99 lines** (cap 150); registered in `synthesize._ALL_SKILLS`, `interview._ALL_SKILLS`, `_SIDE_ENABLED_SKILLS`; `test_codex_phase7` count 20→21; 8 snapshot fixtures regenerated |
| 4 — review verify wiring | **DONE** | 5 new structural tests; aggregate surface **decreased** (claude −65, codex −13) with `surface_baseline.json` and `instruction_baseline.json` untouched; `_ATOMIC_RATCHET["review"]` unchanged |

### Deviations from the plan as written

1. **The skill carries no `{% if is_codex %}` branch** (Phase 3 work item 1 asked for one).
   `synthesize._skill_files()` passes only `{"name": n}` as template context, and no
   existing skill references `is_codex` — skills are single-source and dual-rendered with
   identical content. Using the variable would have raised at render time. The recipe is
   written as prose plus fenced bash, which both IDEs read as reference.
2. **The derived test asserts four artifact FAMILIES, not `count == 7`** (Phase 4 work
   item 2 specified 7). Discovery found **8** for the default Production profile: the
   count is config-dependent, because this repo's own harness.yaml lacks the
   `exec-rev-ver-wrap` workflow that the default profile renders. Two further facts made
   the planned derivation wrong in the same place: `exec-rev-ver-wrap` is **absent from
   `_WORKFLOWS`**, so the `_WORKFLOWS`-based formula would have missed it; and `render()`
   writes codex artifacts to `root/.agents`, **outside** the directory it is handed, so a
   scan of the render root finds the codex skill only if the render target is its parent.
   The test discovers artifacts by content and asserts atomic + stage-body + codex +
   ≥2 fused are all represented, plus a scoping guard proving wrapup's own `pytest -x`
   survives.
3. **Self-harness re-render deferred** (Phase 4 work item 3). `hm cli make --update`
   refuses to run from inside `.worktrees/` — a deliberate rail against
   `[fail:test] snapshot-regen-inside-worktree`. It was NOT bypassed. This repo's own
   `.claude/commands/hm/review.md` therefore still carries the old line until a re-render
   runs from the base checkout, which is how this repo already handles template changes
   (HEAD's `chore(harness): re-render self-harness at 0.44.0` is the precedent).
4. **Phase 3's exit criterion named the wrong suite.** It listed `tests/snapshot`, but
   that directory holds only `regenerate.py` and two doc tests — the snapshot COMPARISON
   lives in `tests/unit/test_synthesize_snapshot.py`, which the stated criterion never
   ran. It was red (8 failures, file count +1) and was caught only by checking whether a
   passing snapshot suite was plausible after adding a rendered artifact. Exactly
   `[fail:test] enumeration-tests-not-updated-with-new-rendered-artifact`.

### Follow-ups this task deliberately did not take

- Re-render the self-harness from the base checkout (deviation 3).
- `tests/snapshot/` contains `.expected.yaml` fixtures whose only consumer lives in
  `tests/unit/` — a directory-name/owner mismatch that made deviation 4 easy to make.

## 🔍 Plan Validation

### Cross-model second opinion (Step 4 pre — codex and antigravity, both `status: invoked`)

| Model | Finding | Disposition |
|---|---|---|
| codex + antigravity | Stem/segment identity ambiguous across subpackages | **Accepted** — verified (`profile.py` ×2); ADR-001 rewritten |
| codex + antigravity | Parent-directory source root asymmetric | **Accepted** — verified; ADR-002 scans the package root |
| codex | `from P import n` conflates symbols with modules | **Accepted** — ADR-001 decides by disk probe (root corrected during validation) |
| codex | Relative imports (`node.level`) unmodelled | **Accepted** — ADR-001 resolves by level against the importer's package |
| codex + antigravity | `git diff --name-only HEAD` misses untracked files | **Accepted** — ADR-004 unions `git ls-files --others --exclude-standard` |
| codex | NUL-safe quoting / rename / deletion | **Accepted** (was overstated) — ADR-004 now specifies `-z` splitting; deletion covered by `classify_path`'s path-only design |
| antigravity | Empty diff → tests skipped → false pass | **Split** — the guard exists (`test_dep_map.py:270-277`), so the original claim is refuted; but it only fires if the CLI is invoked, which ADR-004 step 3 now states explicitly |
| antigravity | Fan-out metric contradicts the local-scan rule | **Accepted** — the metric was a global scan; recorded, and the parent-dir rule is gone |
| antigravity | 1-hop is accidentally transitive across multi-file changes | **Accepted** — stated in ADR-002; over-selection, therefore safe |
| antigravity | Dotted-segment adds no *new* dynamic-import false negatives (informational) | **Accepted** — corroborates R6; both sides read AST identifiers, never string literals |
| codex | `conftest.py` and dynamic imports invisible | **Accepted (conftest)** via ADR-003; **recorded limitation (dynamic)** as R6 |
| codex | Phase 3 omits generated skill outputs | **Accepted — disposition reversed.** The earlier "partly rejected" rested on a `grep … \| head -10` that truncated at 5 of 7 artifacts |
| codex | Measurements overstated; publish the method | **Accepted** — method recorded per measurement; both recomputations are gated exit criteria |
| codex | Multi-file batch semantics unspecified | **Accepted** — ADR-002 states the union; Phase 2 adds the batch test |
| codex | Phase 1 alone unsafe; no quantitative exit gates | **Accepted on both halves** — R4 + merge hazard for the first; numeric gates added to Phases 1 and 2 for the second |

### `plan-validator` — MAJOR_REVISION, resolved

| # | Critical critique | Resolution |
|---|---|---|
| 1 | Phase 1 scans conftest while Phase 2 owns the mapping → a **new** false-green class (a `targeted` run collecting zero tests) | Both moved wholly into Phase 2; ADR-003 records why the split is forbidden |
| 2 | ADR-001's disk probe rooted at `package_root` expands to `src/harness_maker/harness_maker/…` and never succeeds → the headline alias case still fails | ADR-001 now carries a three-root table; the probe is anchored at `search_root = package_root.parent`, and `importer_pkg` is separate |
| 3 | Phase 1 changes `find_importers`' signature while declaring its only caller out of scope | `build_test_hints:122` moved into Phase 1's in-scope list; the API-Changes text corrected |
| 4 | Rendered artifact set wrong (claimed six, listed five, actual seven) | Verified — 7. Replaced by a derived structural test (Interview #9); the out-of-scope wrapup occurrence at `exec-rev-wrap-ver.md:1407` is named explicitly |
| 5 | Phase 3's `low` risk inverted — 584-char ratchet blocks the change and ADR-011 forbids raising it | ADR-005 (new): recipe moves to a skill, outside the ratchet. Split into Phases 3 and 4; Phase 4 risk raised to `medium` |
| 6 | ADR-004's recipe omits `cd <WT>` and the `uv run --with` prefix → selection computed in the wrong tree | The literal invocation is written into ADR-004 step 2 and owned by the skill |
| 7 | Reverse scan is quadratic across two `build_test_hints` calls, no runtime budget | Memoization is a Phase 2 work item; 15-second wall-clock exit criterion on the `io_utils` hub |

| # | Warning / suggestion | Resolution |
|---|---|---|
| 8 | NUL/quoted-path half recorded as Accepted but unaddressed | ADR-004 step 1 specifies `-z` splitting for both git commands |
| 9 | Measurement exit criteria are narrative, not gates | Numeric gates added: zero unexplained losses (Phase 1); ≤50% fan-out and <15s (Phase 2) |
| 10 | Empty-changed-set branch unspecified in the prose an LLM executes | ADR-004 step 3, citing the PLAN's own "absent-case" learned correction |
| 11 | `instruction_baseline.json` allowlist discipline unaccounted for | Phase 4 work item 3 names `_ALLOWED_REMOVALS` and forbids regeneration |
| 12 | Line citation off by four | Corrected to `test_dep_map.py:270-277` |
| 13 | One antigravity finding had no recorded disposition | Added to the table above |
| 14 | No document-level Non-Goals section | Added |

### `plan-validator` — second pass, MAJOR_REVISION, resolved

The validator's re-run budget is now spent (one re-run, per this stage's resolution rule).
All six findings were verified against the repo before being applied; none required a new
architectural choice.

| # | Critique | Severity | Resolution |
|---|---|---|---|
| 15 | ADR-005 escapes `_ATOMIC_RATCHET` but walks into `test_aggregate_shipped_surface_does_not_grow` — a **strict non-increase** with **zero** headroom, not 584 | critical | Verified (`test_command_size_budget.py:330-361`, `_surface_baseline.py:109-117`, baseline re-frozen at HEAD `dfb3caeb`). ADR-005's Context, Decision and Rejected-alternatives rewritten against the real gate; budget is now *net ≤ 0*, with a measured 64-char reference (**−13/artifact**). The finding **strengthens** ADR-005 — inline is impossible at any length — but its stated number was wrong |
| 16 | Per-invocation memoization is discarded **2N** times, not twice; the 15s single-file gate cannot see ADR-004's multi-file workload | critical | Verified (`select_tests:278` → `classify_path:257` → one-element `build_test_hints`, then `:314`). Cache moved to **module scope**, keyed `(path, mtime)` / `package_root`; Phase 2 gains a **≥20-file / <30s** exit arm |
| 17 | The derived Phase 4 test's stated derivation names 6 of 7 artifacts and omits the codex family, which a claude-only render fixture cannot see | warning | Work item 2 now names all three families, requires `Target.CODEX`, and asserts the count is **7**. Recorded as R12 |
| 18 | ADR-004 step 2's `!cd <WT>` diverges from the `second-opinion-gate` precedent — `!` is inert in a SKILL body and `<WT>` is bound by the command, not the skill | warning | Changed to prose worktree wording with no leading `!`, matching `second-opinion-gate/SKILL.md.j2:28,64,153`; the reasoning is recorded inline so the relocation does not silently undo critique 6 |
| 19 | Phase 3's exit criterion omits `tests/unit/test_codex_phase7.py`, which iterates `_ALL_SKILLS` | suggestion | Added to Phase 3's exit criterion |
| 20 | `search_root` is the changed module's root for **all** importers — worth stating | suggestion | Added as an ADR-001 consequence with its fail-safe direction (over-selection, as R11) |

Confirmed clean on the second pass: critiques 1, 3, 6, 8–14; ADR-001's three-root table and
its `level - 1` arithmetic; rollback strategy; scope drift; SPEC alignment; test-strategy
depth. The cross-model dispositions were re-checked and remain accurate, with one
qualification the validator raised and this revision absorbed: codex's "multi-file batch
semantics" was accurate for *semantics* but not for *cost* — that gap is finding 16.
