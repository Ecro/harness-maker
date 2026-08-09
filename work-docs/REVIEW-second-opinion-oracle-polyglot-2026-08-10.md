---
type: review
task_slug: second-opinion-oracle-polyglot
status: APPROVED
human_review_needed: true
final_grade: A
created: 2026-08-10
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations:
    - commands/make.md
    - tests/structural/test_make_fastpath_contract.py
    - tests/snapshot/prod-firmware-spec.expected.yaml
    - tests/snapshot/prod-firmware-task.expected.yaml
    - tests/snapshot/prod-tauri-app-spec.expected.yaml
    - tests/snapshot/prod-tauri-app-task.expected.yaml
    - tests/snapshot/side-python-cli-spec.expected.yaml
    - tests/snapshot/side-python-cli-task.expected.yaml
    - tests/snapshot/side-tauri-app-spec.expected.yaml
    - tests/snapshot/side-tauri-app-task.expected.yaml
  scenario_misses: []
  task_slug: second-opinion-oracle-polyglot
  computed_at: 2026-08-10T00:00:00Z
---

## 🎯 Round 1 Summary

**Grade: B** (consensus-passed P0 = 0, P1 = 2). Threshold is **A**, so the auto-fix loop ran.
`unverified_severe = true` — three `manual-only` P1s were present.

Voter pool: `code-reviewer` + `security-reviewer` + `codex` = **3**. `antigravity` **skipped**
(`exit 1`, empty CLI output), so this review carries one fewer heterogeneous voice than the
Production matrix intends. K stays 2.

## 🔍 Drift Findings

**P1 — scope drift, 10 files.** Two classes, both defensible but neither in a PLAN phase's
declared scope:

- `commands/make.md` + `tests/structural/test_make_fastpath_contract.py` — required by the repo's
  own `test_every_harness_config_axis_is_classified` gate, which fires on any new `HarnessConfig`
  root field. Recorded in the PLAN's handoff note **after** the fact rather than planned.
- `tests/snapshot/*.expected.yaml` ×8 — mechanical consequence of editing three rendered
  templates. The PLAN never listed snapshot regeneration as an output of Phase 4.

No `scenario_misses`: all twelve ACs have tests.

## ✅ Consensus Findings

### P1 — Python toolchain seeded on `pyproject.toml` presence alone
`code-reviewer` (`profile.py:217`) + `codex af27212f` (`profile.py:216`), both P1, CONCLUDE
aligned. Node roles were gated on `devDependencies` evidence; Python was not, so any repo with a
`pyproject.toml` got `uv run pytest/ruff/mypy` seeded into its config. `_detect_mechanical_checks`'
own docstring records the measured harm of exactly this predicate (psf/requests: `uv run ruff
check .` emitted on a repo that uses neither uv nor configures ruff).

The failure mode is the one this whole change exists to remove, wearing a different hat: on a
poetry/pip repo the seeded commands fail with `FileNotFoundError` or a sync error, the verifier
rubric correctly reads that as an **absent** oracle, every finding degrades to `unresolved` — and
AC-011's coverage warning stays **silent**, because labelled blocks *are* being produced. They
just contain no evidence.

**Fixed** — each Python role is now gated on its own `[tool.*]` block, and the `uv run` prefix
only appears when `uv.lock` or `[tool.uv]` says the project is uv-managed.

### P1 — a malformed user `toolchains` block is overwritten by seeding on re-render
`codex f69cd659` (`interview.py:1215`) + `code-reviewer` #1's TRACE, which reaches the same
mechanism from the renderer side. Same severity tier, same named symbols
(`answers_from_harness_yaml`'s toolchains branch → `seed_toolchains`), same execution risk.

> **Judgment call, stated rather than hidden:** these two findings do not share a `file:line`.
> They were clustered under Step 4a's "same named symbol when line numbers shift" arm because
> `code-reviewer` #1's INFER names `interview.py:1221-1225` and `cli.py:395` explicitly as the
> propagation path, which is `codex f69cd659`'s entire finding. A stricter reading would leave
> both `manual-only` and the grade would be **A** with `unverified_severe` — a worse outcome
> for a defect that reproduces on demand.

**Reproduced empirically before fixing:**
```
malformed toolchains -> answers.toolchains = []
after seed_toolchains -> ['python']
```
`answers_from_harness_yaml` drops an unusable value and returns the field default, so "wrote
something unparseable" and "wrote nothing" arrive identically. Seeding then replaced the user's
text with detected defaults — CLAUDE.md checkpoint 1 user-state destruction, and it defeated the
oracle's fail-closed-on-unusable contract across a single re-render.

My own `test_user_authored_value_is_preserved_verbatim` missed it because it only supplies a
**valid** user value; the three-state split had no round-trip coverage of the middle state.

**Fixed** — `toolchains_key_present()` probes the raw YAML for the key, and `seed_toolchains`
refuses to fill whenever it is present, however malformed.

### P2 — budget accounting: the stated total was not enforced
`code-reviewer` #4 + `codex c6f4f501`, both at `second_opinion_oracle.py:354`. `room` was floored
at 800 while the tail grew one entry per pathless/uncovered finding, so the return could be
`800 + len(tail)` — the in-code comment asserting "≤ BUDGET_TOTAL is actually true of the output"
was false for exactly the inputs that matter. `code-reviewer` additionally found that repo-wide
blocks ran *after* the per-path `break`, spawning a 300 s subprocess per template whose output was
then discarded.

**Fixed** — the tail is capped at `BUDGET_TOTAL - _BLOCKS_FLOOR` before `room` is derived, and
repo-wide blocks are charged against `used` with the same guard.

## ⚠️ Weak Consensus

None. No pair matched on surface with diverging CONCLUDE.

## 📝 Manual-Only Findings

### P1 — `argv[0]` is config-derived, behind a pre-approved Bash rule (`security-reviewer`)
`second_opinion_oracle.py:215`. Before this change argv[0] was one of three hardcoded literals.
The base checkout's `.claude/harness.yaml` is an **explicitly permitted** write target
(`worktree_gate`: "everything else is allowed — the base repo"), no `deny` rule covers it, and the
command that invokes this module matches the shipped `Bash(uv run … hm *)` prefix. So one Write to
that file becomes unprompted execution of an arbitrary program on the next review — no
`shell=True` required, because argv[0] **is** the program.

This is a direct consequence of the config-supplied-commands design. Neither the PLAN nor either
`plan-validator` pass caught it; it took a reviewer reading the permission templates alongside the
diff.

**Fixed despite being `manual-only` — a deliberate protocol deviation.** The auto-fix loop's rule
is `consensus-passed` only, and with `antigravity` skipped this finding had no second voice
available. Shipping a known unprompted-arbitrary-execution path to preserve that rule is not
defensible; the rule exists to stop *silent* application, and this is recorded. `_ALLOWED_RUNNERS`
now gates argv[0] fail-closed, and a rejected template is **reported**, not dropped.

### P1 — inert entries render to unreadable YAML (`code-reviewer` #1)
`harness-yaml/{Production,Side}.yaml.j2:60`. `ToolchainConfig` deliberately permits inert entries
(`is_inert`, with tests asserting both shapes "must be representable"), but an empty collection
rendered as a bare `commands:` / `extensions:` key with no value. On re-read that is `None`, which
`strict=True` rejects — one bad entry raises inside the list comprehension, the broad `except`
returns `None`, and the **entire repo** loses its oracle while the user's other valid entries are
replaced by seeding. **Fixed** — both templates emit `{}` / `[]` explicitly.

### P1 — the absent-key branch had zero coverage (`code-reviewer` #3)
Every test patched `_load_toolchains`, including the AC-002 differential test, which pinned
`gather()` while stubbing the exact function whose absent-key mapping makes AC-002 true. A
one-word regression to `None` in either early return would have cost the entire installed base its
oracle with the suite green. **Fixed** — `test_real_loader_maps_absent_key_to_empty_list`
exercises the real loader across three shapes (no file / no key / empty list).

### P2 — `redact()` misses env-dump shapes its docstring claims (`security-reviewer` #2)
No `KEY=VALUE` rule, so `AWS_SECRET_ACCESS_KEY=…`, `NPM_TOKEN=…`, `github_pat_`, `gh[opsu]_`,
`xox[baprs]-` and `AIza…` survive. Bounded — the text goes to a local subagent, not to an external
model — but the docstring overclaims, and arbitrary configured commands widen the output shapes.
**Not fixed this round**; carried as a follow-up.

### P2 — `Any` on the toolchain plumbing without a justifying comment (`security-reviewer` #3)
`TYPE_CHECKING` import would restore `--strict` on `entry.extensions` / `.commands` / `.name`.
**Not fixed this round.**

### P2 — malformed command templates were silently skipped (`codex 4566f49c`)
`_substitute` returned `None` and the comprehension dropped the role; if a sibling role succeeded
the block looked healthy and `labelled` stayed non-zero, so no warning fired. The PLAN claimed
this "degrades to a labelled failure block" — it did not. **Fixed** alongside the runner allowlist.

### P3 — Node role detection unioned `dependencies` (`codex efcff622`)
Documented policy was `devDependencies`-only; the code unioned production deps, so a runtime
package named `typescript` seeded a `tsc` check. **Fixed.**

### P2 — module-level `_CHANGED` shared across tests (`code-reviewer` #5)
A test omitting `_set_changed` inherits its predecessor's fixture, and
`test_uncovered_extension_spawns_no_subprocess` asserts `rec.calls == []` — precisely the
assertion that passes vacuously on a stale empty set. **Fixed** — the `repo` fixture resets it.

## 🤝 Disagreements

None on severity. `security-reviewer` explicitly **declined** to file three candidate findings
(broad `except` leak, base-vs-worktree read direction, `npx` executing repo-local binaries),
stating the sanitisation guarantee holds rather than inventing findings — recorded because a
reviewer's negative result is evidence too.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | file:line | disposition | note |
|---|---|---|---|---|---|
| `af27212fb475e7ab` | codex | P1 | `profile.py:216` | **accepted** → consensus voter | clustered with code-reviewer #2 |
| `f69cd6598bc6174d` | codex | P1 | `interview.py:1215` | **accepted** → consensus voter | reproduced empirically |
| `c6f4f50163088df2` | codex | P2 | `second_opinion_oracle.py:354` | **accepted** → consensus voter | clustered with code-reviewer #4 |
| `4566f49c629490d6` | codex | P2 | `second_opinion_oracle.py:378` | **accepted** → manual-only | no second voice |
| `efcff6224ef93d35` | codex | P3 | `profile.py:236` | **accepted** → manual-only | doc/impl mismatch |

`antigravity`: **skipped** — `exit 1`, empty CLI output. No findings, no votes this round.

Oracle for the PIDA gate was gathered by direct reproduction in the main loop rather than through
`hm second_opinion_oracle`, because the module under review **is** the gatherer — running it
against its own diff would have been circular evidence. Each disposition above cites what was
actually executed.

---

### Iteration 1 (Grade: B → A)

Fixes applied: 10 (3 consensus-passed, 7 manual-only applied as a stated deviation).

| # | Sev | Summary | File | Status |
|---|---|---|---|---|
| 1 | P1 | Gate Python roles on `[tool.*]` evidence; `uv run` prefix only when uv-managed | `profile.py` | Applied · consensus-passed |
| 2 | P1 | `toolchains_key_present()`; seeding refuses to fill over a present-but-malformed key | `profile.py` | Applied · consensus-passed |
| 3 | P2 | Cap the tail at `BUDGET_TOTAL - _BLOCKS_FLOOR`; charge repo-wide blocks against `used` | `second_opinion_oracle.py` | Applied · consensus-passed |
| 4 | P1 | `_ALLOWED_RUNNERS` gate on `argv[0]`, fail-closed | `second_opinion_oracle.py` | Applied · **manual-only, deliberate deviation** |
| 5 | P1 | Emit `{}` / `[]` for inert entries so re-read does not fail | `harness-yaml/{Production,Side}.yaml.j2` | Applied · manual-only |
| 6 | P1 | Real-loader coverage of the absent-key → `[]` branch (3 shapes) | `test_oracle_toolchain_gate.py` | Applied · manual-only |
| 7 | P2 | Unrunnable template is reported as a `NOT RUN` chunk, not dropped | `second_opinion_oracle.py` | Applied · manual-only |
| 8 | P3 | `devDependencies` only — stop unioning production `dependencies` | `profile.py` | Applied · manual-only |
| 9 | P2 | `repo` fixture resets `_CHANGED` so an omitted `_set_changed` fails | `test_oracle_toolchain_gate.py` | Applied · manual-only |
| 10 | P2 | `redact()` env-dump shapes; `Any` → `TYPE_CHECKING` types | — | **Not applied** — carried forward |

Verification: full suite `rc=0`; `ruff check src/ tests/` clean; `mypy --strict` clean on 130
files; snapshots regenerated (worktree-path leak check clean).

New tests added by the fixes: 13 — the runner allowlist (6 programs), the unrunnable-template
report, the two budget invariants, the real-loader absent-key cases (3 shapes), the
evidence-gated Python seeding, the uv-prefix conditional, the runtime-dependency exclusion, the
malformed-block preservation, and the fresh-install fill.

Two fixes were **caught by tests rather than by reasoning**: the runner allowlist immediately
failed `test_repeated_and_embedded_placeholders_substitute_without_resplit`, whose fixture used
a fake program name `tool` — the allowlist working exactly as intended, on my own test.

Remaining after iteration 1: 2 (both P2, `manual-only`, listed as #10 above). New issues
introduced: 0.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 13        | —   |
| 2         | A     | 10            | 2         | 0   |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged
Status: **APPROVED**
human_review_needed: **true**
Counters: unreviewed 0 · prior-fix 0 · unattributed 0

### Why `human_review_needed` is true at grade A

Two independent reasons, and neither is the grade:

1. **The fixes were not re-reviewed.** Iteration 1 changed `second_opinion_oracle.py`,
   `profile.py`, both harness-yaml templates and two test modules; no reviewer has seen that
   diff. The auto-fix loop's step 6 calls for re-spawning the reviewers whose scope was touched,
   and this run verified by test suite instead. The `_ALLOWED_RUNNERS` set in particular is a
   security control authored in response to a finding and reviewed by nobody.
2. **`antigravity` was skipped**, so the Production matrix's second heterogeneous voice was
   absent for the whole review. Five of the thirteen findings came from `codex` alone; a second
   model might have clustered some of the seven `manual-only` items into consensus, or found
   what neither Claude reviewer nor `codex` did.

Two P2s also remain unfixed by choice (`redact()` env-dump coverage, `Any` typing), both
documented above with their reasoning.

### Autopilot auto-answer record (`auto_full`)

The `human_review_needed` judgment gate was carried to the boundary as `pending`. Autonomy level
`auto_full` **answered it rather than stopping**, and the pipeline advanced to `verify`. Recording
what was passed over, because an unrecorded auto-answer is an unauditable skip of a human
decision:

| Passed-over item | Source | Severity | Why it was not human-reviewed |
|---|---|---|---|
| `argv[0]` runner allowlist (the fix itself) | `security-reviewer` #1 | P1 | Fix applied and unit-tested, but no reviewer has seen the fix diff |
| Inert-entry YAML render fix | `code-reviewer` #1 | P1 | Same — fix unreviewed |
| Absent-key coverage tests | `code-reviewer` #3 | P1 | Same — new tests unreviewed |
| `redact()` env-dump shapes | `security-reviewer` #2 | P2 | Deliberately deferred, unfixed |
| `Any` on toolchain plumbing | `security-reviewer` #3 | P2 | Deliberately deferred, unfixed |
| `4566f49c629490d6` | codex | P2 | Fixed, fix unreviewed |
| `efcff6224ef93d35` | codex | P3 | Fixed, fix unreviewed |
| `af27212fb475e7ab`, `f69cd6598bc6174d`, `c6f4f50163088df2` | codex | P1/P1/P2 | Consensus-passed and fixed; fixes unreviewed |

**The operative gap is not any single finding — it is that iteration 1's ten fixes were verified
by test suite and by nobody's reading.** A human closing this task should read that diff, with
`_ALLOWED_RUNNERS` first: it is a security control written in response to a finding, reviewed by
no one, and its allowlist is a judgement about which programs are legitimate check runners.
