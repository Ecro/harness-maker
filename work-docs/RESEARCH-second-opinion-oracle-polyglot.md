---
type: research
task_slug: second-opinion-oracle-polyglot
status: complete
created: 2026-08-10
tags: [harness-maker, research, python, second-opinion, oracle, polyglot, review-gate]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[PLAN-second-opinion-acceptance-gate]]"
  - "[[PLAN-second-opinion-invocation-and-slug-cap]]"
  - "[[REVIEW-second-opinion-acceptance-gate-2026-07-30]]"
summary: "Extension-gate the oracle: emit `no oracle` for files the toolchain cannot consume, and source commands from config"
---

# RESEARCH — Polyglot oracle for the cross-model PIDA gate

## 🎯 Recommended Direction

**Make `second_opinion_oracle` refuse to run a toolchain against a file it cannot
consume, and source the command set from configuration rather than a hardcoded
Python triple.** The extension gate is the load-bearing half; the configurable
command set is the half that makes the gate useful instead of merely silent.

Today `_run_checks` (`src/harness_maker/second_opinion_oracle.py:149-174`)
unconditionally issues `uv run pytest -q <path>`, `uv run ruff check <path>`,
`uv run mypy <path>` for **every** path a cross-model finding names, in **every**
consuming project. In a TypeScript project this is not a degraded oracle — it is a
*fabricated* one: three commands that never inspected the finding's subject, all
exiting non-zero, injected into `code-verifier` mode B as if they were evidence.
The fix has two independent parts and they are not equally urgent. Part one
(refuse to run, say so) removes fabricated evidence and costs nothing to any
existing Python harness. Part two (run the *right* tools) restores the oracle's
value and requires a config contract with a defined absent-case.

## 🔍 Refinement Decisions

`--deep` not set; Phase 0/0.5 skipped.

Discovery lens: **Technical architecture / implementation** (primary) +
**Risk / compliance** (secondary — the failure mode is fabricated evidence
feeding an adjudication gate, not a performance or UX cost). The
user-workflow / product-opportunity lens does not bind: the topic is a specific
defect in a shipped code path with a known consumer, not a roadmap question.

## 📐 Evidence — what actually happens

Measured 2026-08-10 on a 4-line `.tsx` file, running the exact three commands
`_run_checks` issues:

| Command | exit | raw bytes | Output |
|---|---|---|---|
| `uv run pytest -q App.tsx` | **4** | 87 | `ERROR: not found` / `no tests ran` |
| `uv run ruff check App.tsx` | **1** | **3809** | `invalid-syntax: Simple statements must be separated…` with a source snippet per error |
| `uv run mypy App.tsx` | **2** | 107 | `error: Invalid syntax [syntax]` |

Three consequences follow mechanically, and they compound:

1. **The volume claim is credible and it is `ruff`'s doing.** 3.8 KB from four
   lines. `ruff` prints a framed source excerpt per diagnostic and TS/JSX
   cascades a diagnostic per construct, so a real 300–600 line `.tsx` component
   reaching megabytes is a straight-line extrapolation, not a surprise.
2. **The user's `unresolved` prediction is the correct one, and the mechanism is
   the truncation marker.** `_run_checks` caps each command at
   `BUDGET_PER_COMMAND = 1500` (`:172`), so what reaches the subagent is not 2 MB
   — it is ~1.5 KB of Python syntax errors *carrying a `[… truncated N chars …]`
   marker*. `code-verifier_body.md.j2:144` then binds: "Truncation means unknown
   … Prefer `unresolved` over inferring past the cut." The oracle's own budget
   guard converts the garbage into the quiet `unresolved` the user described.
   Note the discrepancy with the reported figure: **2 MB is what the commands
   produce, not what gets injected** — a distinction worth keeping, because it
   means the injected-size guard is working and the defect is purely about
   *content validity*.
3. **The exit codes are worse than useless — they are actively misleading.**
   `code-verifier_body.md.j2:149-152` teaches exactly one mismatch signal:
   pytest's `exit=5` (no tests collected). The observed pytest code here is
   **`exit=4`** (usage error), which that rule does not cover. `ruff`'s `exit=1`
   is byte-identical in meaning to "this file has real lint failures", and
   `mypy`'s `exit=2` likewise. So a verifier reading rubric item 1 — "an oracle
   block associated with its `id` demonstrates the failure" — has a defensible
   path to **`accepted`** on the strength of Python syntax errors about JSX.
   That is a *false-accept* risk on top of the false-`unresolved` one, and
   `accepted` is the disposition that grants a Step 4 consensus vote.

**Cost, secondary:** three subprocesses at `timeout=300` per distinct path, plus
`redact()` doing `splitlines()` + seven regex substitutions per line over a
multi-megabyte string — all to produce output that is then thrown away by the
budget.

**Config reality check:** this repo's own `.claude/harness.yaml` has **no**
`reviewers.mechanical_checks` key. Any design that treats that key as the command
source must define the absent case explicitly (see Pitfalls).

## 🛠️ Approaches Found

### A. Live manifest probe — reuse `profile._detect_mechanical_checks`

| Field | Content |
|---|---|
| Approach | At gather time, probe the root for `pyproject.toml` / `Cargo.toml` / `package.json` and derive the command set the same way make-time detection already does (`src/harness_maker/profile.py:184-230`). |
| Assumption | The oracle's root is the project root, and manifest presence implies a working toolchain. |
| Evidence | The detection logic exists, is ADR-007-conservative (manifest-explicit `[tool.X]` blocks, Cargo standard whitelist, `package.json` scripts keyed by lockfile runner), and already survived a psf/requests false-positive reality check. |
| Trade-off | Zero new config surface, but the detected commands are **repo-wide** (`uv run ruff check .`, `pnpm test`, `cargo test`) while the oracle needs **path-scoped** ones. Naive path-appending is wrong for `cargo test <path>` (takes a name filter, not a path) and unreliable for `pnpm test <path>`. |
| Compatibility | High — same module, same repo, no schema change. But it makes the oracle shell out to the filesystem on every gather, and `ProjectProfile` is cached (`detection_cache`) with a lifetime the oracle does not control. |
| Risk | **medium** — silently produces a wrong-but-plausible command for Rust and for `package.json` scripts that ignore positional args. |

### B. Explicit config — `second_opinion.oracle_commands` with a `{path}` placeholder

| Field | Content |
|---|---|
| Approach | New `harness.yaml` key under the existing `second_opinion` block: a list of argv templates, e.g. `["pnpm vitest run {path}", "pnpm eslint {path}", "pnpm tsc --noEmit"]`. Commands **without** `{path}` run once repo-wide; commands **with** it run per path. |
| Assumption | The harness author knows their own toolchain and will fill this in. |
| Evidence | Precedent in-repo: `reviewers.mechanical_checks` is exactly this shape (user-maintained, no interview question, preserved across re-render by `interview.py:1184-1187` and `reconcile.py:163`). |
| Trade-off | Deterministic and honest — no guessing — but **the absent case is the whole risk**. An unset key means every existing harness gets nothing unless a default or migration fires. |
| Compatibility | High. `models.py` gains a field; `answers_from_harness_yaml` gains a read; the render path is unchanged. The `{path}` placeholder must be substituted **after** `safe_paths()`, never before, or it reopens the argv-injection hole `PLAN-second-opinion-invocation-and-slug-cap` ADR-001 closed. |
| Risk | **medium** — the absent-case black hole (see Pitfalls) is a documented count:8 failure class in this repo. |

### C. Extension→toolchain gate inside the gatherer, fail-closed to `no oracle`

| Field | Content |
|---|---|
| Approach | The gatherer owns a small map from file extension to toolchain domain (`.py/.pyi` → Python triple; `.ts/.tsx/.js/.jsx` → Node; `.rs` → Cargo; …). A path whose extension is outside the resolved toolchain's domain gets **no commands run at all** and is routed to the existing `no_oracle` list (`second_opinion_oracle.py:189-207`), which already prints *"no usable in-diff path; treat as `unresolved` territory, not refutation"*. |
| Assumption | Extension is a sufficient proxy for "can this tool parse this file". For the failure at hand it plainly is. |
| Evidence | The `no_oracle` channel, its budget reservation, and the matching rubric rule (`code-verifier_body.md.j2:147-148`, "Absent oracle is not refutation") all already exist and are already correct. This approach adds a *producer* for a consumer that is built and tested. |
| Trade-off | Alone, it produces **honest silence** rather than evidence — a TS project gets a correctly-labelled absent oracle and every cross-model finding lands `unresolved`. That is the same outcome the user observed, but *stated* instead of disguised, and with no false-accept path and no wasted 3×300 s. |
| Compatibility | Highest — pure addition inside one module, no schema change, no behavior change for any Python harness. |
| Risk | **low** |

**Recommended composition: C as the floor, B as the source of truth, A as the seed.**
C is not optional under any of the three — it is what removes fabricated evidence,
and it is the only part that is safe to ship on its own. B supplies the commands
when the author has declared them. A runs once at `/harness-maker:make` to
*pre-fill* B's key (visible in `harness.yaml`, editable, no runtime guessing), which
sidesteps A's cache-lifetime and repo-wide-vs-path-scoped problems by turning a
runtime inference into a reviewable config value.

## ⚠️ Pitfalls

1. **Absent-case black hole.** `CLAUDE.md` records this as the most-recurring
   design failure in the repo (`count:8`, 2026-06-08): *a feature that activates
   on an optional field never fires for anything predating the field*. If
   `second_opinion.oracle_commands` is unset, the behavior must be written down
   and tested — default to the Python triple **gated by C's extension check**
   (safe: Python harnesses keep today's behavior, TS harnesses get honest
   silence), not to "run nothing" and not to "run the triple unconditionally".

2. **Fixing only the artifact you were looking at.** `[fail:test]
   gate-scoped-to-the-artifact-being-fixed` (count:3) — and its 2026-07-30
   instance is *this exact subsystem*: a mode-B vocabulary gate asserted on the
   SKILL being edited rather than the agent that emits the value, leaving four
   surfaces advertising a retired enum. The Python-triple claim lives in **at
   least four places**, and patching `_run_checks` alone leaves three lying:
   - `src/harness_maker/second_opinion_oracle.py:153-155` — the commands
   - `src/harness_maker/second_opinion_oracle.py:166-170` — the `exit=5` comment
   - `templates/agents/code-verifier_body.md.j2:108` — "blocks of real command
     output (`pytest` / `ruff` / `mypy`)"
   - `templates/agents/code-verifier_body.md.j2:149-152` — the pytest-specific
     exit-code rule (which, per the measurement above, names the wrong code)
   - `templates/skills/targeted-test-selection/SKILL.md.j2:88-91` — the sibling
     "this selector is Python-only" note, whose polyglot advice is *correct* and
     should be the model for the oracle's
   Enumerate sites **before** writing the exit criterion, and state them as
   `file:line` — `[fail:design] prose-refactor-removal-sweep-gaps` (count:2)
   records a criterion of the form "zero `rg` hits" returning green over three
   surviving sites, one of them split across a line break where a line-oriented
   `rg` could not match it by construction.

3. **Substituting `{path}` before sanitising it.** The entire reason this module
   exists (module docstring, `:11-21`) is that paths arrive from an external
   model's unconstrained `file` field, and the shipped settings pre-approve
   `Bash(uv run pytest:*)` as a **prefix** rule. A config-supplied template
   makes it tempting to build the string first. `safe_paths()` must run first,
   always, and the result must reach `subprocess.run` as argv elements — never a
   shell string, never `shell=True`.

4. **A new exit-code vocabulary per toolchain is a trap.** Teaching the mode-B
   rubric that "`tsc` exit 2 means X, `eslint` exit 2 means Y" pushes toolchain
   knowledge into a prose rubric that no test can hold. Prefer keeping the
   knowledge in the *gatherer*: if the toolchain cannot consume the file, emit no
   block. Then the rubric needs exactly one rule — the "absent oracle is not
   refutation" one it already has.

5. **Silent degradation is invisible without a positive signal.** This subsystem
   has been bitten repeatedly by green-looking silence (`/hm:health`'s
   base-only smoke; the `skipped/total` denominator that read 10.3% when the
   truth was 20.7%). Whatever ships should emit a machine-readable
   `oracle_toolchain: <name>|none` — in the block header and, ideally, on the
   `.claude/observability/second-opinion.jsonl` disposition row — so
   "every finding `unresolved` because we have no toolchain" is countable rather
   than inferred.

## ❓ Open Questions

1. **Unknown extension → silence or best effort?** Recommendation is silence
   (C). Confirm, because it means a TS harness with no `oracle_commands` set
   gets *zero* oracle coverage and every cross-model finding becomes a manual
   item. That is honest, but it is a real reduction in gate strength versus the
   status quo's illusion of coverage.
2. **Where does the config key live** — `second_opinion.oracle_commands` (shared
   across models, alongside `failure_policy`/`agents`) or reuse/extend
   `reviewers.mechanical_checks`? The two have different semantics (repo-wide
   pre-check vs. path-scoped adjudication) and CLAUDE.md explicitly warns
   against reusing Phase 0 mechanical checks as an oracle — but that warning is
   about *reusing the run*, not the *command list*.
3. **Placeholder contract.** `{path}` per-command with "no placeholder ⇒ run
   once repo-wide"? Or an explicit `scope: path|repo` field per entry? The
   former is terser; the latter is unambiguous for `cargo test`, where a path
   is neither appendable nor omittable in a useful way.
4. **Does the make-time seeding (A) belong in this unit of work,** or is
   config-only (B+C) the right first cut with seeding as a follow-up? Seeding
   touches `profile.py`, `synthesize.py` and the migration path; B+C touch one
   module and two templates.
5. **Absent-case default, stated as a rule:** unset key + `.py` file ⇒ Python
   triple; unset key + non-`.py` ⇒ no oracle. Confirm this is the intended
   behavior for *existing* harnesses, since it silently changes nothing for them
   (the desired property) but also means no consuming project benefits until it
   edits `harness.yaml`.
6. **Budget re-tuning.** With the right toolchain, is 1500 chars/command still
   right? `tsc` and `eslint` are as verbose as `ruff`; the truncation marker
   still routes a truncated block to `unresolved`, so a too-tight budget
   reproduces the reported symptom with correct tools.

## 📚 Sources

No external sources. All findings are from this repository plus one local
measurement:

- **Measurement (2026-08-10):** `uv run {pytest,ruff check,mypy}` against a
  4-line `.tsx` file — exit codes 4 / 1 / 2 and 87 / 3809 / 107 raw bytes.
  Reproduce by writing any JSX file and running the three commands from
  `_run_checks`.
- `src/harness_maker/second_opinion_oracle.py` — `_run_checks:149-174`,
  `gather:177-229`, `safe_paths:69-96`, budgets `:45-46`.
- `src/harness_maker/templates/agents/code-verifier_body.md.j2:100-152` — mode-B
  input contract, decision rubric, four binding oracle rules.
- `src/harness_maker/templates/skills/second-opinion-gate/SKILL.md.j2:52-96` —
  §2 oracle gathering, the `cd <worktree>` requirement, the five guarantees.
- `src/harness_maker/templates/skills/targeted-test-selection/SKILL.md.j2:82-92`
  — the sibling module's explicit polyglot stance.
- `src/harness_maker/profile.py:184-230` — `_detect_mechanical_checks`, ADR-007
  manifest-explicit detection for Python / Rust / Node.
- `src/harness_maker/models.py:1272-1274` — `reviewers.mechanical_checks`
  (user-maintained, empty = off).
- `CLAUDE.md` — second-opinion PIDA gate contract; the 2026-06-08 absent-case
  learned correction.

## 🔗 Related Internal Docs

- [[PLAN-second-opinion-acceptance-gate]] — introduced Step 3.6 oracle gathering
  and mode-B ledger vocabulary; the direct parent of this defect.
- [[PLAN-second-opinion-invocation-and-slug-cap]] — ADR-001, "prose recipes have
  no execution surface"; the precedent for keeping toolchain logic in Python.
- [[REVIEW-second-opinion-acceptance-gate-2026-07-30]] — the M1/M4 findings that
  produced `safe_paths`, the budget and the value-shaped redactor.
- [[PLAN-second-opinion-multi-model]], [[PLAN-antigravity-second-opinion-timeout]]
  — the `file`-field-is-unconstrained property this module defends against.
- `[fail:test] gate-scoped-to-the-artifact-being-fixed` (count:3) — including its
  2026-07-30 instance inside this same subsystem.
- `[fail:design] prose-refactor-removal-sweep-gaps` (count:2) — why the exit
  criterion must enumerate sites, not grep for a phrase.
