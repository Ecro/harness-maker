---
type: review
task_slug: workflow-step-audit
status: APPROVED
created: 2026-07-29
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
grade: B
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations: [".gitignore"]
  scenario_misses: []
  task_slug: workflow-step-audit
  computed_at: 2026-07-29T00:00:00Z
---

# REVIEW — workflow-step-audit (round 1)

## 🎯 Round 1 Summary

**Grade B** — 1 consensus-passed P1, fixed in-round. 0 consensus-passed P0.
Full suite `rc=0`, `ruff check .`, `ruff format --check`, `mypy --strict src` (127 files) all green.

**`human_review_needed: true`** — ~~three `manual-only` P1 findings remain unfixed~~. **All three are now CLOSED (2026-07-29); see each finding below.** The
letter cleared; the flag is what carries them.

Scope reviewed: 57 tracked files + 12 untracked, +757/−470. Phases 0, 0.5, 0.75
(entrypoint only) and 4 (classifier only) of `PLAN-workflow-step-audit`.

## 🔍 Drift Findings

**P1 — scope drift: `.gitignore`.** Not in any PLAN phase's `Scope (in)`. Justified —
`work-docs/*` is gitignored, so the Phase 0 BASELINE document (which
[ADR-011](PLAN-workflow-step-audit.md#adr-011) requires to be durable and never
recomputed) was not committable without a `!work-docs/BASELINE-*.md` negation. Recorded
rather than waived: the change is right, its absence from the PLAN is the finding.

**Incomplete phases** (all recorded in the PLAN's progress table, none silent):
Phase 4's `Scope (in)` names the classifier **and** `execute.md.j2`'s Phase C/D prose;
only the classifier landed. Phases 1, 2, 3, 5, 6, 7, 8 not started.

## ✅ Consensus Findings

### P1 — the `hm` rewrite silently disabled a validation gate `[2/2 strong]`

**Sources:** security-reviewer (`test_command_surface_gate.py:31`), code-reviewer
(`test_command_size_budget.py:114`, same class at a second site).

Both reached the same CONCLUDE from different entry points: the rewrite moved call sites
out from under checks that were keyed to the old spelling, and the checks then passed
**vacuously** rather than failing.

- `_INVOKE` extracted only `python -m harness_maker…`. After the rewrite ~230
  invocations produced no matches, `offenders` stayed empty, and
  `assert not offenders` succeeded having examined nothing. This is the exact bug class
  `command_registry` exists for — its own docstring cites `autopilot_caps on`, a
  subcommand that does not exist.
- Registering the newly-visible modules surfaced a **pre-existing** gap underneath:
  `delegation_ledger` — shipped in `wrapup.md.j2` as `hm delegation_ledger record` — had
  no `misroute_guard`, so a verb routed to the wrong module would have died with
  argparse's "invalid choice" (reads as a template typo) instead of being redirected.

**Fixes applied this round:**

| # | Change | File |
|---|---|---|
| 1 | `_INVOKE_HM` + dual-spelling `_iter_invocations` | `tests/unit/test_command_surface_gate.py` |
| 2 | `assert seen > 100` non-empty guard | `tests/unit/test_command_surface_gate.py` |
| 3 | Registered `delegation_ledger` (subparser/`record`) + `test_dep_map` (flagonly) | `src/harness_maker/command_registry.py` |
| 4 | Wired `guard_or_none("delegation_ledger", argv)` | `src/harness_maker/delegation_ledger.py` |
| 5 | Restored the sed-corrupted `_EXEMPT_EXEC` comment | `tests/structural/test_command_size_budget.py` |

The non-empty guard is the load-bearing half. `assert not offenders` is satisfied by an
extraction that finds nothing, which is precisely how this gate went quiet. A green gate
must mean "checked and clean", never "looked and saw nothing".

This is CLAUDE.md's own recorded anti-pattern, verbatim: *게이트를 만들 때는 자기가
고치던 산출물에만 범위를 맞추지 말 것.* Note the contrast the security reviewer drew —
`test_permission_syntax.py` and `test_hm_entrypoint.py` **did** get dual-spelling
extraction plus non-empty guards during this work. T-C1 was missed.

## 📝 Manual-Only Findings

Single-source; not auto-applied. All three are code-reviewer findings on Phase 4's
classifier and on the rewrite's integration boundary.

### P1-1 — `select_tests` returns zero tests for a real source module  
**CLOSED 2026-07-29.** Two guards, because the specific case was an instance of a general one: `SELECTOR_SOURCE` forces FULL outright (a selection this file derives for a change to this file is circular), and any `source-with-hints` file whose hints are ALL filtered out also forces FULL. A third backstop rejects an empty `targeted` selection except when every path is inert — the one honest empty answer.
`test_dep_map.py:252`. `source_to_test_candidates` short-circuits to `[source_path]` for
any stem starting with `test_`/`conftest`; `select_tests` then filters hints to `tests/`,
emptying the list — but the `SOURCE_WITH_HINTS` classification already bypassed the FULL
arm. So `src/harness_maker/test_dep_map.py` (a real module, covered by two suites)
selects **nothing** and reports `mode: targeted`. Violates
[ADR-008](PLAN-workflow-step-audit.md#adr-008)'s protected invariant. **Fix:** when the
filtered list is empty, fall through to FULL naming the file.

### P1-2 — `docs/` and `README.md` are classified inert, but suites assert their contents  
**CLOSED 2026-07-29.** Both left the inert set. `DOC_CONSUMING_SUITES` maps the known docs (both READMEs, both HOW-IT-WORKS, BOOTSTRAP, showcase-diff) to their real suites with **exact** keys — a `docs/` prefix would make the same over-broad promise in the other direction. Anything unlisted falls to the default arm and forces FULL, so the map is an OPTIMISATION: incompleteness costs a full run, never a missed test. A source-scanning detector was tried and discarded — it flagged 24 suites, nearly all of which merely WRITE a fixture `README.md`, and a heuristic that noisy gets weakened until it is vacuous.
`test_dep_map.py:187`. `test_bootstrap_doc.py` asserts tokens in `docs/BOOTSTRAP.md`;
`test_readme_one_prompt.py` / `test_readme_install_commands.py` read the real READMEs.
`README.ko.md` is **not** in the tuple and correctly falls to FULL — that asymmetry is
itself evidence the list was assembled by hand. The same reasoning that correctly
excluded `CLAUDE.md` was not carried to its two siblings.

### P1-3 — no test executes the invocation form the rewrite ships  
**CLOSED 2026-07-29** by `tests/integration/test_hm_console_script_resolves.py` (`INTEGRATION=1`, runs `uv run --with <repo> hm …` from `/tmp`).
`test_hm_entrypoint.py:45` runs `python -m harness_maker.hm …`;
`test_wrapup_brief_rendered_argv.py:101` explicitly avoids the console script to dodge a
PATH dependency. Nothing anywhere runs `uv run --with <ref> hm <mod>` — the form every
rendered `!` line now carries. If that resolution ever fails (e.g. a `--with` ref
resolving to a release predating the entry point), every mandated call in every stage
dies with `hm: command not found` and no test observes it. CLAUDE.md checkpoint #8 asks
for exactly one `INTEGRATION=1` subprocess case here.

### P2 (manual-only, condensed)
- `render.py:356` — the prune pattern's comment claims a fork user's rule "is never
  pruned"; `[^ ]*harness[-_]maker[^ ]*` matches `/home/u/forks/harness-maker`. Direction
  is still safe (a prompt, never lost protection) but the stated guard is weaker than
  claimed.
- `settings/*.json.j2` — the grant now flows through a PATH-resolved program name rather
  than an interpreter-resolved module. A narrowing of the trust chain, not a hole.
- `test_dep_map.py:84` — `find_importers` matches module names by **substring**; that was
  advisory when it produced hints and is now a gate deciding targeted-vs-FULL.
- `test_dep_map.py:254` — `mode: "targeted"` with `node_ids: []` is ambiguous: a consumer
  doing `pytest ${node_ids}` runs *everything*. No consumer exists yet, so a third mode
  `"none"` is free to add now.
- `command_registry.py:229` and ~15 `ArgumentParser(prog=…)` strings still teach the
  retired long form.
- `hm.py:85` — the comment claims `argv[0]` stays `hm <module>`; `alter_sys=True`
  overwrites it. The code is *more* faithful to `python -m` than the comment says.

## 🤝 Disagreements

None on severity. The two reviewers' scopes overlapped only on the gate-vacuity class,
where they agreed.

## Refuted after investigation — recorded because the question was asked hardest

The security reviewer could not construct a permission widening, and verified each leg
against `permission_syntax.py` rather than assuming:

- **`Bash(uv run --with <ref> hm *)` is strictly narrower than the
  `python -m harness_maker.*` rule beside it.** The long form reaches every module in the
  package (`cli`, `gates.*`, `hooks.*`); `hm` reaches 25. Net grant unchanged.
- **Not a `Bash(uv:*)` rerun.** The `--with` slot is a rendered literal, escaped by
  `_wildcard_body` — the sdist-build-backend execution vector is unreachable. The
  trailing `` *`` compiles to `^…hm(?: .*)?$`, a word boundary, so `hmX` does not match.
  `split_subcommands` splits on `;`/`&&`/`|` before matching, so chaining is dead.
- **`hm` cannot be induced outside `_DISPATCHABLE`** — membership is checked before any
  import; the target string is built from a frozenset of 25 literals.
- **Shadowing gets *better*.** `python -m pkg.mod` prepends CWD to `sys.path`; a console
  script does not. A `harness_maker/` directory dropped in the working tree can no longer
  shadow the real package for any rewritten call site.
- **`canonicalize` does not mask a deletion** — `_EXEC_LINE` captures only `^\s*!` lines,
  the fold is restricted to `_DISPATCHABLE` names, and no two frozen long-form lines
  collapse to the same string under it.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | 5             | 3 P1 manual-only + 6 P2 | 0 |

Final grade: **B**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: **true** — three unverified P1 (`manual-only`), all on Phase 4's
classifier and the rewrite's untested integration boundary. The classifier has no
consumer yet (`execute.md.j2` still calls `build_test_hints()`), so P1-1 and P1-2 are
latent rather than live; P1-3 is live the moment a user re-renders.
