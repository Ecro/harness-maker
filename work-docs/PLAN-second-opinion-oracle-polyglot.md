---
type: plan
task_slug: second-opinion-oracle-polyglot
status: complete
created: 2026-08-10
tags: [harness-maker, plan, python, second-opinion, oracle, polyglot, toolchains]
spec: "[[SPEC-second-opinion-oracle-polyglot]]"
research_doc: "[[RESEARCH-second-opinion-oracle-polyglot]]"
interview_rounds: 5
adrs: 9
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Root-level toolchains declaration; oracle refuses tools that cannot parse a file"
---

## 🎯 Executive Summary

**TL;DR** — Introduce a root-level `toolchains` declaration in `harness.yaml` and make
`second_opinion_oracle` consume it, so the oracle runs a project's real checks on the files
those checks understand, and runs **nothing** on files they do not.

**What / Why.** `second_opinion_oracle._run_checks` hardcodes `uv run pytest` / `ruff` / `mypy`
and issues them against every path a cross-model finding names, in every project. On a `.tsx`
file that is not a degraded oracle but a fabricated one — three commands that never parsed the
subject, all exiting non-zero, injected into `code-verifier` mode B as evidence. Measured:
`ruff` emits 3809 bytes of Python syntax errors at `exit=1` on four lines of JSX.

**Key decisions.** The toolchain declaration lands at the **harness.yaml root**, not under
`second_opinion` (ADR-002) — eight other rendered surfaces hardcode the same Python triple, so
nesting it would make this the third encoding of one project fact and force a key migration when
`verify` / `wrapup` follow. Commands are **grouped per toolchain with role keys** (ADR-003) so a
polyglot repo cannot cross-apply them, and an uncovered extension resolves to **zero
subprocesses** plus a labelled absent oracle (ADR-001) rather than an annotated block.

**Estimated impact.** ~4 source modules, 1 new config model, 4 prose surfaces, ~14 tests. Zero
behavior change for any harness without a `toolchains` key whose findings name `.py` paths —
which is every harness shipped to date.

## 📚 Prior Work

- `[[RESEARCH-second-opinion-oracle-polyglot]]` — the measurement, the two failure paths, and the
  A/B/C approach comparison this plan implements as C+B+A.
- `[[PLAN-second-opinion-invocation-and-slug-cap]]` ADR-001 — "a prose recipe has no execution
  surface"; four silent-skip bugs shipped in prose before the CLI moved into Python. The same
  argument keeps toolchain resolution out of the rendered SKILL and inside the gatherer.
- `[[PLAN-second-opinion-acceptance-gate]]` — created the mode-B ledger vocabulary and the oracle
  gathering step this plan repairs.
- `[fail:test] gate-scoped-to-the-artifact-being-fixed` (count:3) — its 2026-07-30 instance is in
  this exact subsystem: a mode-B vocabulary gate asserted on the SKILL being edited rather than
  the agent that emits the value, leaving four surfaces advertising a retired enum. Phase 4's
  parity gate and its non-vacuity assertion exist because of it.
- `[fail:design] prose-refactor-removal-sweep-gaps` (count:2) — a "zero `rg` hits" exit criterion
  returned green over three surviving sites, one of them split across a line break. Phase 4
  enumerates sites as `file:line` instead.
- CLAUDE.md learned correction 2026-06-08 — the absent-case black hole (count:8, the
  most-recurring class in this repo). ADR-006 exists to answer it explicitly.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | Extension-set source | Contract shape | Where does the covered-extension set come from, given plain command strings? | Sibling key `oracle_extensions` | Superseded in round 3 after the polyglot defect | ADR-003 |
| 2 | Step 3.0 gate | Scope | Proceed to decomposition or lock more first? | Proceed | SPEC was `approved`; remaining gaps had precedent | — |
| 3 | Polyglot grouping | Architecture | Flat sibling lists cross-apply commands in a mixed-language repo — how to resolve? | *(user redirected)* | User asked whether the problem is second-opinion-specific. It is not: 8 further surfaces hardcode the triple | — |
| 4 | Coverage visibility | Observability | Two models independently flagged silent total coverage loss; reinstate? | stderr one-liner | SPEC's Non-Goal excluded a *ledger schema* change, not a warning line — no conflict | ADR-008 |
| 5 | Key location | Architecture | `toolchains` at root, under `second_opinion`, or widen scope to all 9 surfaces? | Root-level `toolchains` | Consumed by the oracle only this round; siblings migrate later with no key move | ADR-002, ADR-009 |
| 6 | Command shape | Contract shape | Role keys (`test`/`lint`/`types`) or a flat list per group? | Role keys | Lets a later consumer take a subset — `targeted-test-selection` needs `test` alone | ADR-003 |
| 7 | Seeding command shape | Dependencies | The detector emits only repo-wide commands, so seeding them verbatim yields zero labelled evidence. Static per-stack table, drop Phase 3, or accept repo-wide? | Static per-stack table | Detection supplies stack identity + package manager only. Rust's `cargo` accepts no path and is a declared limitation | ADR-007 |
| 8 | Validator pass-2 resolution | Risk tolerance | Pass 2 returned MAJOR_REVISION and the re-run cap is spent — fix without a third pass, exceed the cap, accept as risk, or abort? | Fix without a third pass | The nine items are factual corrections with unambiguous fixes, not user judgments; the cap governs validator dispatches, not corrections. `/hm:review` is the next independent gate | — |

Two decisions were made without asking, both on precedent, and are recorded as ADRs rather than
interview rows: the two-root config split (ADR-005 — `second_opinion_invoke.load_config`'s
docstring already states the rule) and the tokenise-then-substitute ordering (ADR-004 — the
module exists to keep model-supplied values off argv).

## 📐 Architecture Decision Records

### ADR-001: An unusable toolchain emits no oracle, never an annotated block
**Status:** Accepted (2026-08-10, via /hm:spec + /hm:plan interview)
**Context:** Running Python tools on a `.tsx` file produces output that is indistinguishable from
real failures (`ruff` `exit=1`) and, once truncated, trips the mode-B rubric's "truncation means
unknown" rule. Both a false `accepted` and a false `unresolved` are reachable.
**Decision:** When no toolchain entry covers a path's extension, run zero subprocesses and route
the finding to the existing `no_oracle` list with a reason naming the extension.
**Consequences:**
- ✅ Removes the false-`accepted` path entirely rather than delegating it to rubric judgment.
- ✅ Reuses a consumer rule that already exists and is already correct ("Absent oracle is not
  refutation"), so the mode-B rubric needs no new toolchain vocabulary.
- ✅ Drops 3×300 s of timeouts and a multi-megabyte `redact()` pass per uncovered path.
- ⚠️ A project with no `toolchains` key gets zero oracle coverage for non-Python files. Honest,
  but weaker than the status quo's illusion of coverage. ADR-008 makes it visible.
**Rejected alternatives:**
- Run anyway and prepend a "toolchain mismatch" warning to the block — rejected: it keeps the
  false-`accepted` path alive and depends on the verifier reading a header it is not required to
  weigh, at unchanged cost.
- Teach the rubric per-toolchain exit codes — rejected: pushes toolchain knowledge into prose no
  test can hold, and the observed pytest code was `exit=4`, which the one existing rule already
  fails to cover.
**Source:** SPEC interview round 1

### ADR-002: The toolchain declaration lives at the harness.yaml root
**Status:** Accepted (2026-08-10)
**Context:** The obvious home was `second_opinion.oracle_commands`. But `rg` over the templates
finds the Python triple hardcoded in **nine** rendered surfaces, of which the oracle is one:
`stages/verify.md.j2`, `stages/wrapup.md.j2`, `commands/hm/loop.md.j2`,
`skills/verify-before-completion`, `skills/targeted-test-selection`, `skills/second-opinion-gate`,
`rubrics/claude_md.yaml.j2`, and both `settings/*.json.j2`. `reviewers.mechanical_checks` already
encodes an overlapping fact.
**Decision:** Declare `toolchains` at the root of `harness.yaml`. This round wires exactly one
consumer — `second_opinion_oracle`.
**Consequences:**
- ✅ The eight sibling surfaces migrate later by reading an existing key; no key move, no
  migration shim for us to own.
- ✅ Avoids making this the third encoding of "what toolchain is this project".
- ⚠️ A root-level key with one consumer looks over-general until the second consumer lands.
  ADR-009 records the deferral so the gap is intentional and legible.
**Rejected alternatives:**
- `second_opinion.oracle_commands` — rejected: this repo already paid the cost of moving
  `codex_second_opinion` → `second_opinion`, including a one-shot silent migration and a
  both-keys-present advisory. Choosing the same shape again buys a second one.
- Migrate all nine surfaces now — rejected: a `verify` / `wrapup` regression reaches every
  consuming project, and it would require rewriting the SPEC.
**Source:** Interview #5

### ADR-003: Commands are grouped per toolchain and keyed by role
**Status:** Accepted (2026-08-10)
**Context:** Flat sibling lists (`oracle_commands` + `oracle_extensions`) were the round-1 choice.
Both second-opinion models independently found the same defect: in a repo with a Python backend
and a TypeScript frontend, every covered path receives **every** command, so `pytest` runs on
`.tsx` — the exact bug under repair. A single-language repo never reveals it.
**Decision:**
```yaml
toolchains:
  - name: python
    extensions: [".py", ".pyi"]
    commands: {test: "uv run pytest -q {path}", lint: "uv run ruff check {path}", types: "uv run mypy {path}"}
```
A path receives only the commands of the entry whose `extensions` matched it.

**Validity rules, and where each is enforced.** The grouped shape removes the *cross-group*
inconsistency but admits two *per-entry* ones, so both are pinned:
- An entry with empty `extensions` **or** empty `commands` is **inert**: it matches nothing, and
  any path that would have matched it routes to `no_oracle`. It never yields a labelled block with
  no evidence — that is the false-`accepted` shape.
- Extension sets must be disjoint across entries. Overlap and type errors are rejected by
  **pydantic at config-load time**, which covers `/harness-maker:make`.
- The oracle's **runtime** read of the base-root `harness.yaml` is a separate trust boundary: a
  hand-edited file can be malformed after render. The contract is **no exception of any type
  escapes `resolve_toolchains()`** — not "validation errors are caught". The likeliest hand-edit
  failures are not `toolchains`-value errors at all: a `harness.yaml` that no longer parses
  (`yaml.YAMLError`) and a failed base-root resolution (`subprocess` error) both raise from the
  config *read*, outside any `ValidationError` handler, and `main()` guards only the
  findings-file parse. The run degrades to `no_oracle` plus the ADR-008 warning in every case.
**Consequences:**
- ✅ The inconsistent state that flat siblings admitted is structurally unrepresentable across
  groups, and explicitly inert (not silently covered) within one.
- ✅ Role keys let a later consumer take a subset — `targeted-test-selection` needs `test` alone,
  `verify` needs all three.
- ⚠️ One more level of YAML nesting, and make-time seeding must emit groups rather than a list.
**Rejected alternatives:**
- Flat lists plus a documented "one toolchain per repo" constraint — rejected: the constraint has
  no enforcement point, and violating it silently reproduces the original bug.
- Flat lists with a package-manager-mismatch heuristic — rejected: a heuristic here yields both
  false positives and false negatives on a safety gate.
- A `*.ts,*.tsx: <cmd>` prefix DSL — rejected: introduces a parser for a problem structured YAML
  already solves.
**Source:** Interview #3, #6; codex `fb0bdf4d`/`700c5117`, antigravity `fb0bdf4d`

### ADR-004: `{path}` presence decides scope; tokenise before substituting
**Status:** Accepted (2026-08-10)
**Context:** `cargo test <path>` takes a name filter, not a path, so a per-command scope contract
is unavoidable. Separately, `safe_paths`'s `_UNSAFE_CHARS` does not reject the space character, so
a legal path may contain one.
**Decision:** A command template containing `{path}` runs once per covered path; one without it
runs exactly once per `gather()`. Templates are `shlex.split` **first**, then `{path}` is
substituted **within** the resulting tokens, with no re-split. Substitution consumes only
`safe_paths()` output. `subprocess.run` receives a list; `shell=True` never appears. Every
occurrence of `{path}` in every token is substituted (repeated and embedded forms included:
`--file={path}`, `{path}.snap`), and a template whose `shlex.split` raises degrades to a labelled
failure block rather than propagating.
**Consequences:**
- ✅ A path containing a space stays one argv element.
- ✅ `--file={path}` style embedding works without a second rule.
- ✅ The sanitise→substitute ordering is asserted at the argv boundary (AC-006), so a future
  refactor that reverses it fails observably.
- ⚠️ A template with no `{path}` and no repo-wide meaning is silently repo-wide. Accepted: the
  alternative (`scope:` field) can be set inconsistently with the placeholder.
**Rejected alternatives:**
- Explicit `scope: path | repo` per entry — rejected in interview: user-settable inconsistency.
- Substitute into the raw string then `shlex.split` — rejected: splits paths containing spaces
  into two arguments, and re-opens the option-shaped-value hole this module exists to close.
**Source:** SPEC interview round 2; codex `68d125c8`, antigravity `7be6345f`

### ADR-005: Config resolves from the base repo root; the diff stays at `--root`
**Status:** Accepted (2026-08-10)
**Context:** `gather()` must run `git diff --name-only HEAD` in the task worktree — the SKILL's
`cd <worktree>` is load-bearing, and rooting at base yields an empty changed-set and an
all-`unresolved` degradation that looks like a working run. But `second_opinion_invoke.load_config`
already documents the opposite requirement for config: *"a worktree has no `.claude/` at all when
the project gitignores it, so a cwd-relative read would silently substitute defaults for the
user's configured model while still reporting `invoked`."*
**Decision:** Keep `--root` as the diff root. Resolve config separately via
`second_opinion_invoke.resolve_base_root(root)` — always from the supplied `root`, never
`Path.cwd()` — and read `harness.yaml` from there.

**The executed commands' `cwd` stays `--root` (the worktree), unchanged from today**
(`_run_checks` already passes `cwd=str(root)`). This is stated because the config split makes
either root a plausible reading, and the wrong one runs the checks against *unmodified* base files
— output that looks like a clean run. AC-006 asserts the recorded `cwd` against this value, so it
is a pinned target rather than whatever the implementer picks.
**Consequences:**
- ✅ A project that gitignores `.claude/` keeps its configured toolchains instead of silently
  falling back to ADR-006's Python default.
- ✅ Reuses a tested helper rather than adding a second base-root reader (the repo has a
  structural test forbidding a second worktree-enabled reader for the same reason).
- ⚠️ A `toolchains` edit made **inside** an unmerged worktree is invisible to that worktree's own
  review until it lands on base. Accepted and documented; the reverse (worktree-local config) is
  the silent-default failure the docstring already rules out.
**Rejected alternatives:**
- Read config from `--root` — rejected: the documented silent-default failure.
- Read from `Path.cwd()` — rejected: `codex_ledger.main()` did exactly this and wrote into a
  gitignored worktree path, losing rows at `task-land`.
**Source:** precedent (`second_opinion_invoke.load_config` docstring); codex `13336716`

### ADR-006: The absent-key default is extension-conditional
**Status:** Accepted (2026-08-10)
**Context:** Every harness shipped to date has no `toolchains` key. "Feature activates on an
optional field" is this repo's most-recurring design failure (count:8) precisely because the
absent case is left undefined and the feature never fires for anything predating the field.
**Decision:** With no `toolchains` key: `.py` and `.pyi` paths receive the historical Python
triple; every other extension receives no oracle per ADR-001.
**Consequences:**
- ✅ Zero behavior change for existing Python harnesses — the property AC-002 asserts against the
  parent commit's output.
- ✅ TypeScript projects stop receiving fabricated evidence immediately, before they configure
  anything.
- ⚠️ No consuming project gains a *working* oracle until it re-renders (ADR-007 seeds it) or edits
  `harness.yaml`. ADR-008 makes that state visible rather than silent.
**Rejected alternatives:**
- Default to running nothing at all — rejected: silently removes working coverage from every
  Python harness.
- Default to the Python triple unconditionally — rejected: that is the bug.
**Source:** SPEC interview round 1; CLAUDE.md learned correction 2026-06-08

### ADR-007: make-time seeding fills only an empty slot
**Status:** Accepted (2026-08-10)
**Context:** `profile._detect_mechanical_checks` already probes manifests conservatively
(ADR-007-style `[tool.X]` block matching, Cargo whitelist, `package.json` scripts keyed by
lockfile). Reusing it at make time turns a runtime inference into a reviewable config value.
**Decision:** `/harness-maker:make` writes `toolchains` only when the key is absent or an empty
list. A user-authored value is preserved verbatim, and the value must survive **every** config
reconstruction path.

**Detection supplies stack identity, not command strings.** Every command
`_detect_mechanical_checks` emits is repo-wide with no path argument — `uv run ruff check .`
(profile.py:206), `uv run pytest --tb=short -q` (:210), `cargo test` (:214),
`{runner} run {key}` (:232). Under ADR-004 a template without `{path}` runs once per `gather()`,
and under ADR-008 its output is **unlabelled**. Seeding those strings verbatim would therefore
produce a harness whose oracle yields **zero per-finding evidence — for Python too** — while
AC-011's warning stays silent, because the command set is non-empty and the paths are covered.
That is the silent-degradation class this whole PLAN exists to close, reintroduced through its own
seeder.

So seeding uses detection only for **stack identity and package-manager choice**, and takes the
role templates from a **static per-stack table in code**:

| detected | test | lint | types |
|---|---|---|---|
| python | `uv run pytest -q {path}` | `uv run ruff check {path}` | `uv run mypy {path}` |
| node | `npx --no-install vitest run {path}` | `npx --no-install eslint {path}` | `npx --no-install tsc --noEmit` |
| rust | `cargo test` | `cargo clippy` | — |

**The Node row uses `npx --no-install`, not `<runner> <bin>`.** `_detect_mechanical_checks`
falls back to `runner = "npm"` when neither a pnpm nor a yarn lockfile is present
(profile.py:224-229) — the most common Node repo. `npm vitest run src/App.tsx` is not a valid
command: npm exposes no such subcommand, binaries need `npx` / `npm exec --`. Such a command
exits non-zero **without ever parsing the subject**, and because it *does* carry `{path}` it is
emitted as an **id-labelled** block — the exact false-`accepted` shape ADR-001 exists to remove,
reproduced by this PLAN's own seeder. `--no-install` keeps it from silently fetching a package
from the network mid-review.

**Each Node role is additionally gated on the tool being present in `devDependencies`.** Seeding
already parses `package.json`, so this is nearly free, and it converts a guess into a fact: a repo
using `jest` rather than `vitest`, or `biome` rather than `eslint`, gets **no entry for that
role** rather than a wrong command. An absent entry routes to `no_oracle` with a visible reason —
honest degradation. A wrong command is fabricated evidence.

**Consequences:**
- ✅ Matches CLAUDE.md checkpoint 1 (default = preserve user state) and how
  `reviewers.mechanical_checks` already survives re-render.
- ✅ New projects get a working, *labelled* oracle with no hand-editing.
- ⚠️ **Rust gets no labelled evidence.** `cargo test` takes a name filter and `cargo clippy` a
  crate, so neither accepts `{path}`; a Rust project's oracle is unlabelled project-wide context
  only. Recorded as a stated limitation, not a defect — the alternative is a fabricated per-path
  `cargo` invocation, which is the bug under repair.
- ⚠️ The table is static, so a project using `jest` rather than `vitest` must edit
  `harness.yaml`. Acceptable: the value is visible and editable, and fill-if-empty never
  overwrites it.
- ⚠️ Only Python / Rust / Node are detectable. C++ and everything else is declared by hand;
  unknown stack emits nothing rather than guessing.
**Rejected alternatives:**
- Seed the detected strings verbatim — rejected: proven above to yield zero labelled evidence.
- Drop seeding from this round — rejected in interview: new installs, the case that benefits most,
  would then need hand-editing before the oracle works at all.
- `content_hash` fingerprint arbitration (CLAUDE.md checkpoint 5) — rejected: introduces
  per-field fingerprint storage into `harness.yaml` for one key.
**Source:** Interview #5, #7; codex `700c5117` (not-addressed in draft 1), `493fdd78`

### ADR-008: Repo-wide output is unlabelled context; total coverage loss warns once
**Status:** Accepted (2026-08-10)
**Context:** A repo-wide command (`pnpm tsc --noEmit`) fails for reasons unrelated to any single
finding — a pre-existing error elsewhere in the tree. Labelling that block with every covered
finding's `id` re-creates the false-`accepted` path this work exists to close. Separately, both
models flagged that a project with zero coverage sees nothing: the `no_oracle` tail lives inside
the verifier prompt, which the user never reads.
**Decision:** Repo-wide command output is emitted as a block carrying **no** `id` label, headed as
project-wide context. When no in-diff path is covered, or the resolved command set is empty,
`gather()` writes exactly one warning line to stderr naming the uncovered count and the remedy.

**The trigger is an output property, not a config property.** Warn when the run emitted **no
id-labelled block for any covered finding** — whatever the cause. A config-shaped trigger
("command set empty OR nothing covered") is defeated by a `toolchains` entry that is technically
non-empty but wholly repo-wide: a seeded Rust harness has covered paths and a non-empty command
set, yet `cargo test` / `cargo clippy` accept no path, so every block is unlabelled and the
warning never fires. That is the silent degradation this ADR exists to remove, surviving inside
the fix for it. One output-shaped predicate covers the Rust case, any future all-repo-wide
config, and both original causes. The line also reports a **non-zero uncovered fraction** with
its count, so partial loss (a `python`-only declaration receiving `.tsx` findings) is visible
too — still exactly one line, so ADR-008's flooding objection does not apply.

The line **distinguishes its cause**: `no toolchain covers these extensions` (an intentional gap —
ADR-006's default, or a declared set that omits this language) versus
`toolchains config unusable` (malformed / inert entries — ADR-003's runtime degrade). Those have
opposite remedies, and one undifferentiated message sends a user with a typo hunting for a
missing feature.

**Each labelled block header names the resolved toolchain** — `### oracle for id(s)=… (path: …,
toolchain: node)`. This answers the SPEC's deferred Open Question 1: it is one interpolated field
on a line the emitter already writes, so the "if it is free, it is in scope" condition holds. The
ledger-schema half stays deferred.
**Consequences:**
- ✅ Reuses the consumer's existing rule verbatim — "An unlabelled block is not evidence for
  anything" — so no rubric change is needed to neutralise the attribution.
- ✅ The silent-degradation class that produced this subsystem's 10.3%-vs-20.7% miscount gets a
  positive signal at near-zero cost.
- ⚠️ Repo-wide output still consumes budget while adjudicating nothing. Accepted: it is context
  the verifier may legitimately weigh, and the budget already truncates visibly.
- ⚠️ One line, not per path: a per-path warning would flood a large diff. AC-011 asserts exactly
  one, in both directions.
**Rejected alternatives:**
- Drop repo-wide command support entirely — rejected: it would make `cargo test` and
  `tsc --noEmit` unexpressible, and the `{path}` contract already implies the scope.
- Extend the `codex_ledger` schema with `oracle_toolchain` — rejected this round: schema plus
  aggregation changes, and the aggregation side of that ledger has its own history of denominator
  bugs.
**Source:** Interview #4; codex `92154ab5`, `57c8f573`; antigravity independent concurrence

### ADR-009: The eight sibling surfaces are deferred, not forgotten
**Status:** Accepted (2026-08-10)
**Context:** ADR-002 places the key at the root specifically so `verify`, `wrapup`, `loop`,
`verify-before-completion`, `targeted-test-selection`, the CLAUDE.md rubric and both settings
templates can read it later. Doing them now triples the phase count and puts a `verify` /
`wrapup` regression in front of every consuming project.
**The general principle that replaces the pytest-specific rule**, written here verbatim so Phase 4
has something to copy and AC-008 can assert its *presence*, not merely the triple's absence:

> A non-zero exit is evidence only when the tool actually parsed and exercised the subject. A tool
> that collected nothing, could not parse the file, or was never given the file is an **absent**
> oracle, not a failing one. `pytest` printing "no tests ran" is the worked example; the rule is
> not specific to it. The gatherer no longer emits blocks from tools that cannot consume the
> file, so this rule now covers only the residual in-toolchain cases.

This is a single principle, not a per-toolchain vocabulary, so it does not cross the SPEC's
Non-Goal.

**Decision:** This round wires one consumer. Phase 4 **corrects** the prose in the two surfaces
that describe the *oracle's* output (`code-verifier_body.md.j2`, `second-opinion-gate/SKILL.md.j2`)
plus the oracle module's own docstring, and leaves `targeted-test-selection`'s Python-only note
accurate as written. The remaining surfaces keep their hardcoded commands and are listed in the
SPEC's Non-Goals with file paths.
**Consequences:**
- ✅ Bounded blast radius; no consuming project's completion gate changes.
- ✅ The follow-up needs no key migration.
- ⚠️ For an interval, `toolchains` describes the project while `verify` still runs `uv run pytest`
  regardless. The two can disagree, and nothing detects it. The SPEC records this explicitly so it
  cannot be mistaken for an oversight.
**Rejected alternatives:**
- Widen scope now — rejected in interview #5.
- Delete the settings `Bash(uv run pytest:*)` grants as part of the sweep — rejected: those gate
  Claude's own Bash calls, not the oracle's `subprocess.run`, so they are not this defect's taint
  path. Recorded in Non-Goals so the parity inventory does not silently omit them.
**Source:** Interview #5; codex `df482d16`, `bc6d9ffd`; antigravity `b480cd4a`

## 🏗️ Technical Design

**Current state.** `second_opinion_oracle.gather(findings, root)` calls `_changed_files(root)`,
groups findings by path via `safe_paths`, and calls `_run_checks([path], root)` per distinct path.
`_run_checks` iterates a hardcoded 3-tuple of argv lists, runs each with `cwd=root`,
`timeout=300`, `check=False`, and appends `f"$ {' '.join(cmd[:3])} [{status}]\n{truncate(redact(body), 1500)}"`.

**Affected components.**

| Component | Change |
|---|---|
| `models.py` | New `ToolchainConfig` (`name`, `extensions`, `commands: ToolchainCommands`); new root field `toolchains: list[ToolchainConfig] = []` on the answers model |
| `interview.py` | `answers_from_harness_yaml` reads `toolchains`; preserved on re-render like `mechanical_checks` |
| `cli.py` | `_build_second_opinion_override` and any sibling reconstruction path must not drop the new field |
| `synthesize.py` | Propagate `toolchains` into the rendered `harness.yaml` |
| `profile.py` | Emit toolchain **groups** (stack → extensions + role-keyed commands), not a flat command list |
| `second_opinion_oracle.py` | Resolve toolchains from base root; partition paths; tokenise + substitute; unlabelled repo-wide block; stderr warning |
| `templates/agents/code-verifier_body.md.j2` | `:108` command-set description; `:149` exit-code rule generalised while keeping the pytest example |
| `templates/skills/second-opinion-gate/SKILL.md.j2` | §2 guarantee list gains the extension gate |

**Data flow.**

```
harness.yaml (BASE root, via resolve_base_root)
        │  toolchains: [{name, extensions, commands{test,lint,types}}]
        ▼
  resolve_toolchains()  ──► absent? ─► synthetic python group (ADR-006)
        │
        ▼
gather(findings, root=WORKTREE)
        │
        ├─ _changed_files(root)          ← git diff, worktree
        ├─ safe_paths(finding.file, allowed)
        │
        ├─ partition by extension
        │      covered   ─► group's role commands
        │      uncovered ─► no_oracle tail  (0 subprocesses)
        │
        ├─ per-path commands ({path} present)  ─► labelled block per path
        ├─ repo-wide commands ({path} absent)  ─► ONE unlabelled context block
        │
        └─ zero covered OR empty command set   ─► one stderr warning line
```

**Design decisions** — every architectural choice above is bound to an ADR: gate semantics
ADR-001, key placement ADR-002, grouping + roles ADR-003, `{path}` + tokenisation ADR-004, root
split ADR-005, absent-key ADR-006, seeding ADR-007, attribution + visibility ADR-008, deferral
ADR-009.

**No API changes** to `safe_paths`, `redact`, `truncate`, or `main`'s CLI surface. `main` keeps
`--findings-file` / `--root` and keeps exiting 0 unconditionally.

## 📝 Implementation Plan

### Phase 1 — Config model, reader, and every reconstruction path
- **Status:** DONE — `tests/unit/test_toolchains_config.py`, 11 passing. The `--preset` drop
  reproduced live before the fix (`assert [] == ['python']`), confirming validator C3.
- **depends_on:** `[]`
- **parallel_group:** `serial-foundation`
- **merge_hazards:** `models.py`, `cli.py`, `synthesize.py` — Phase 3 also edits all three. The
  `depends_on` ordering serialises them; do not run these two concurrently.
- **Scope (in):** `models.py`, `interview.py` (`answers_from_harness_yaml`), `cli.py`
  (`_build_answers` + the preset-switch rebuild at `:1402-1411`), `synthesize.py`, **both**
  `templates/harness-yaml/Production.yaml.j2` and `templates/harness-yaml/Side.yaml.j2`.
- **Scope (out):** `second_opinion_oracle.py`, `profile.py`, all agent/skill templates.
- **Exit criterion:** `uv run pytest tests/unit/test_toolchains_config.py -q` passes, asserting:
  - (a) an entry with empty `extensions` or empty `commands` is inert (`ToolchainConfig`, the
    per-entry model), and overlapping extension sets across entries are rejected by a
    **model-level validator on the containing `toolchains` list** — a per-entry model
    structurally cannot see its siblings;
  - (b) a `toolchains` value round-trips `synthesize` → `harness.yaml` → `answers_from_harness_yaml`
    unchanged, **under both the `Production` and the `Side` preset** — a single-template
    assertion can pass while the other preset never emits the key at all, which silently returns
    ADR-006's Python default for half the install base;
  - (c) the value survives `--preset` (the `_build_answers` seven-field rebuild at `cli.py:1402`
    is the live drop path for a **root-level** field; the comment above it already records this
    loss class for `autonomy`), and every other flag that reconstructs answers;
  - (d) a **structural** test — modelled on `tests/structural/test_autopilot_marker_api_session_key.py`
    — walks the AST for every `InterviewAnswers(...)` construction site and fails when one omits a
    field, so (c) cannot go stale as new flags are added. "Discover reconstruction functions" is
    this test; without a named mechanism the criterion has no predicate and is unprovable.
- **Risk:** `low`
- **Rollback point:** parent commit.

### Phase 2 — Extension gate and config-driven dispatch
- **Status:** DONE — `tests/unit/test_oracle_toolchain_gate.py`, 31 passing.
  Two implementation decisions were corrected by the tests rather than by review:
  (i) unusable config initially fell back to the Python default; the AC-012 assertion forced
  the absent/unusable split to be **fail-closed**; (ii) the `toolchain:` header annotation
  broke AC-002's byte-identity, so it is emitted only when the toolchain came from config —
  lowering AC-002 to accommodate it would have been meeting the threshold by moving it.
  The dead `_run_checks` was **removed**, not left behind: two tests patched it, and a test
  that patches a function nothing calls is green over any behaviour.
- **depends_on:** `[1]`
- **parallel_group:** `post-foundation` (same group as Phase 3 — disjoint files, co-schedulable)
- **merge_hazards:** `second_opinion_oracle.py` is touched by Phase 4's docstring correction —
  Phase 4 depends on this phase, so no concurrent edit.
- **Scope (in):** `second_opinion_oracle.py` only.
- **Scope (out):** config schema (Phase 1), seeding (Phase 3), prose (Phase 4).
- **Exit criterion:** `uv run pytest tests/unit/test_second_opinion_oracle.py -q` passes with the
  new cases, each asserting an observable rather than a summary:
  - AC-001 — patched `subprocess.run` records **zero** calls for an uncovered extension, and the
    finding id appears in the no-oracle tail;
  - AC-002 — output for a `.py` path with no `toolchains` key is byte-equal to the parent
    commit's output for identical inputs;
  - AC-003 — recorded argv equals the declared role commands, in role order;
  - AC-004 — a `{path}`-bearing command records one call per path; a bare one records exactly one
    call per `gather()` regardless of path count;
  - AC-005 — the five-row extension table;
  - AC-006 — for adversarial `file` values (leading `-`, absolute, `..`, metacharacters,
    off-diff, and a path containing a space) every recorded argv element is either a literal
    token from the template or a `safe_paths` member, and `shell` is never true;
  - AC-009 — with disjoint `python` and `node` entries and a mixed path set, no `(template, path)`
    pair crosses groups;
  - AC-010 — the repo-wide block carries no id label;
  - AC-011 — a zero-coverage run writes exactly one stderr line and leaves stdout equal to the
    no-warning run's stdout.
  Also assert degradation, each of which must leave `gather()` returning normally:
  - a malformed command template (`shlex` error) and a `TimeoutExpired` each produce a labelled
    failure block;
  - a **malformed or inert `toolchains` block** at runtime (non-list, non-mapping entry,
    overlapping extensions, entry with empty `commands`, entry with empty `extensions`, unknown
    role key) **plus the two config-read failures** (`harness.yaml` unparseable as YAML;
    base-root resolution raising) each degrade every path to `no_oracle` plus the ADR-008
    `config unusable` warning, and never raise out of `gather()`;
  - repeated and embedded placeholders (`--file={path}`, `{path}.snap`) substitute in every
    occurrence without re-splitting the token;
  - the recorded `cwd` equals `--root` (the worktree) for every invocation.

  **Tail format and budget.** The `no_oracle` tail becomes grouped by cause — the existing
  unsafe/off-diff group and a new uncovered-extension group naming the extension — so the mode-B
  consumer can tell them apart. Assert that a large uncovered set does not starve the blocks
  section below the existing 800-character floor (`room = max(BUDGET_TOTAL - len(tail), 800)`);
  `BUDGET_TOTAL` itself is unchanged, per SPEC Non-Goals.
- **Risk:** `medium` — this is the module the review gate depends on.
- **Rollback point:** Phase 1.

### Phase 3 — make-time seeding
- **Status:** DONE — `tests/unit/test_toolchain_seeding.py`, 13 passing.
  `detect_toolchains` is a new function beside `_detect_mechanical_checks`, whose contract is
  unchanged; seeding is wired in `cli.make` **after** the override pass so a `--preset` rebuild
  cannot discard it.
- **depends_on:** `[1]`
- **parallel_group:** `post-foundation` (with Phase 2 — disjoint files)
- **merge_hazards:** `cli.py`, `synthesize.py`, `models.py` — all three shared with Phase 1, which
  this phase depends on. None with Phase 2 (disjoint files).
- **Scope (in):** `profile.py` (a new group emitter beside `_detect_mechanical_checks`, which
  keeps its current contract unchanged), the static per-stack role table (ADR-007), `cli.py` /
  `synthesize.py` fill-if-empty wiring.
- **Scope (out):** `second_opinion_oracle.py`, prose surfaces.
- **Exit criterion:** `uv run pytest tests/unit/test_toolchain_seeding.py -q` passes, asserting
  key-absent → written, key-empty → written, key-user-authored (arbitrary sentinel string no
  detector could emit) → preserved verbatim, detection-empty → key not created, and a mixed
  Python+Node fixture → two disjoint groups rather than one merged list. Plus the two assertions
  that make the seeded value *useful* rather than merely present:
  - **every seeded `test` and `lint` value contains `{path}`** (`types` may be repo-wide; `rust`
    is the declared exception per ADR-007) — without this, seeding silently reproduces the
    all-unlabelled degradation while every other assertion here still passes;
  - **every seeded command's invocation form is valid for the detected runner** — a fixture with
    no lockfile (so `runner == "npm"`) must not produce `npm vitest …`; and each Node role is
    emitted only when its tool is in `devDependencies`, with a `jest`-not-`vitest` fixture
    asserting the `test` role is **absent** rather than wrong;
  - one end-to-end case: a fixture seeded by this phase, run through `gather()`, yields a
    **labelled per-path block**, not only an unlabelled repo-wide one.
- **Risk:** `low`
- **Rollback point:** Phase 1.

### Phase 4 — Prose surfaces and the parity gate
- **Status:** DONE — `tests/structural/test_no_hardcoded_toolchain_claim.py`, 7 passing.
  The gate was verified to actually **fail** on a reintroduced claim, and the reintroduction
  used to verify it was deliberately **split across a line break** — the shape a line-oriented
  matcher cannot catch by construction, and the shape that historically escaped. The complement
  scan's predicate was narrowed from "names the module" to "describes the command set" after it
  flagged `command_registry.py` / `hm.py`, which carry the module name only as a dispatch string.
- **depends_on:** `[2, 3]` — both. Phase 4's prose describes the runtime behavior Phase 2 lands
  **and** the configuration Phase 3 seeds; depending on Phase 2 alone lets the prose and the
  seeder encode different command shapes.
- **parallel_group:** `serial-closeout`
- **merge_hazards:** `second_opinion_oracle.py` docstring (Phase 2 owns the body).
- **Rollback point:** Phase 3 — this phase depends on `[2, 3]`, so reverting to Phase 2 would
  also discard Phase 3.
- **Scope (in):** `second_opinion_oracle.py` module docstring and the `exit=5` comment;
  `templates/agents/code-verifier_body.md.j2` `:108` and `:149`;
  `templates/skills/second-opinion-gate/SKILL.md.j2` §2 guarantee list; new
  `tests/structural/test_no_hardcoded_toolchain_claim.py`.
- **Scope (out):** the eight deferred surfaces (ADR-009). `targeted-test-selection`'s Python-only
  note stays — it remains accurate.
- **Exit criterion:** the new structural test passes and **fails** when any surface is reverted.
  - **Discovery predicate — and it must not key on the string being removed.** Keying discovery
    on the hardcoded triple is self-defeating: the moment Phase 4 succeeds the population is
    empty and the non-vacuity guard fails the suite. Instead each oracle-describing surface
    carries an explicit anchor comment `<!-- @hm:oracle-command-surface -->` (or `# @hm:` in
    Python), the test collects surfaces by that anchor, and the predicate asserted is "does not
    assert a fixed command set". The anchor is independent of the property, so the population
    stays stable across the fix.
  - **Pair it with a complement scan**, because an anchor set is *self-declared by the artifacts
    being fixed* — the `[fail:test] gate-scoped-to-the-artifact-being-fixed` shape this PLAN
    cites in Prior Work. A dropped anchor fails on the size assertion, but a **newly added**
    surface that asserts a fixed command set and carries no anchor is invisible by construction.
    So: every file referencing `second_opinion_oracle` or describing oracle blocks must either
    carry the anchor **or** appear in a `DEFERRED_SURFACES` constant listing ADR-009's eight
    paths. New unanchored, unlisted surfaces fail. Keep that constant in this test file so the
    deferral list has exactly one machine-readable home.
  - Assert the collected population is **non-empty** before asserting the predicate, and that it
    equals the expected surface count — a dropped anchor must fail loudly, not shrink the
    population silently.
  - Scan **multiline** — one historical instance of this claim spanned a line break, which a
    line-oriented matcher cannot catch by construction.
  - Assert the **presence** of ADR-009's general principle at `:149`, not only the triple's
    absence. A rule generalised into a sentence that adjudicates nothing would otherwise pass.
- **Risk:** `low`

## 🧪 Testing Strategy

- **Unit (primary).** All eleven ACs. `subprocess.run` is patched throughout and assertions are on
  **recorded argv, cwd, and call count** — never on a prose summary. Call-count assertions are the
  only thing that proves ADR-001's "runs nothing", and exact-argv assertions are the only thing
  that proves ADR-004's ordering.
- **Differential.** AC-002 compares against the parent commit's `gather()` output for identical
  inputs. **The mechanism is named, because two of the three plausible ones void the independence
  claim**: the test loads the pre-change module text into a temp module and calls its `gather()`.
  A vendored copy degrades to a snapshot the author can edit into agreement, and a hand-written
  expected string is not differential at all — either would leave the machine companion's
  `oracle_source: differential` claim false.
  **The baseline is pinned to an immutable blob SHA, never `HEAD~`.** `HEAD~` is a moving
  reference: it points at the pre-change module only until the next commit, after which the test
  compares the new `gather()` against itself and passes vacuously — forever, silently, on the one
  assertion protecting every shipped Python harness. Capture
  `git rev-parse HEAD:src/harness_maker/second_opinion_oracle.py` before Phase 2 and embed that
  SHA as a module constant, read back with `git cat-file -p <sha>`. An unresolvable blob is a
  **hard failure, not a skip** — a rewritten history must surface red.
- **Structural.** Phase 4's parity test, with the non-vacuity assertion.
- **Integration.** One end-to-end pass with real `subprocess` on this repo's own `.py` files,
  guarded by `INTEGRATION=1`, confirming the historical triple still runs and exits 0.
- **Not covered.** No live TypeScript project is exercised in CI — no Node toolchain in the test
  environment. The `.tsx` path is covered by the extension gate's zero-call assertion, which does
  not need Node installed. This is a deliberate gap, not an oversight.

## 🪟 Phase D.5 — Newly-reachable window

This is a repair, so the window question is mandatory. Green gates measure the coverage that
existed *before* the fix; `[fail:code] fix-introduced-defect-passes-all-gates` is at count:4 in
this repo, every instance on an entirely-green four-gate run.

**1. What input window does this repair newly make reachable?**
Three, and they are distinct:
- **(a) Config-driven argv.** Before, argv was three fixed literals plus a sanitised path.
  Now the *command itself* comes from `harness.yaml`, so an attacker-or-typo-controlled string
  reaches `shlex.split` and then `subprocess.run`. Newly reachable: arbitrary argv[0], embedded
  and repeated `{path}`, unbalanced quotes, empty templates, and paths containing a space.
- **(b) The `None` config state.** `_load_toolchains` now returns three states where there was
  no state at all. Newly reachable: `toolchains` present-but-unusable, which must fail closed —
  falling back to the Python default there re-runs `pytest` on `.tsx` and is the original bug.
- **(c) Zero-labelled-block runs.** The gate can now legitimately produce a run with no
  per-finding evidence (uncovered extensions, all-repo-wide config). Newly reachable: a review
  where every cross-model finding lands `unresolved` with no code defect at all.

**2. Which test enters each window, and is it in this commit?** Yes, all three:
- (a) `test_oracle_toolchain_gate.py::test_unsafe_file_value_never_reaches_argv` (5 adversarial
  values), `::test_space_containing_path_stays_one_argv_element`,
  `::test_repeated_and_embedded_placeholders_substitute_without_resplit`, and the malformed-
  template arm of `::test_malformed_toolchains_degrades_without_raising`.
- (b) `::test_malformed_toolchains_degrades_without_raising` (6 shapes, incl. unparseable YAML)
  and `::test_base_root_resolution_failure_degrades`. These assert **no labelled block**, which
  is the fail-closed half — an earlier implementation of mine passed the "does not raise" half
  while silently falling back to the Python default, and only this assertion caught it.
- (c) `::test_zero_labelled_block_emits_exactly_one_stderr_warning`,
  `::test_all_repo_wide_config_still_warns`, `::test_full_coverage_emits_no_warning`.

**Absent-case (count:8, the repo's most-recurring class).** This feature activates on an
optional field, so the absent case is the majority of the install base. Covered explicitly and
in both directions: `test_absent_key_defaults_by_extension` (4 rows) pins that `.py`/`.pyi`
keep the historical triple and everything else gets nothing, and
`test_python_path_output_unchanged_from_baseline` pins byte-equality against the pinned
baseline blob. Absent (`[]`) and unusable (`None`) are deliberately different states, and
`test_detection_empty_leaves_the_key_absent` stops seeding from collapsing them by writing an
empty list.

## 📌 Handoff note for `/hm:wrapup` — the mutation receipts are in the BASE repo

`hm mutation_receipt record` writes to the **base** repo root
(`/home/noel/harness-maker/.claude/observability/mutation-receipts.jsonl`), not to this task
worktree — the same base-root seam recorded in `wrapup-memory-base-seam`. Two receipts for
`test_no_hardcoded_toolchain_claim.py` are sitting there as an unstaged `M`, and
`test_new_gates_file_a_mutation_receipt` is red without them. They are therefore **part of this
change** but outside the branch that carries it: `task-land` aborts on a dirty base, and a
naive `git add` in the worktree stages nothing.

Two repo gates fired during Phase 4's regression and are worth naming, because both were
correct and neither was in the PLAN:
- `test_every_harness_config_axis_is_classified` — a new `HarnessConfig` root field must be
  classified. `toolchains` is **disclosed**, not internal: it decides which file types the
  oracle checks at all, so a user who never learns it exists cannot tell an honestly-empty
  oracle from a broken one. `commands/make.md` §4.3 gained the row.
- `test_new_gates_file_a_mutation_receipt` — a new structural gate must record which source
  line, when deleted, turns it red. Both were measured, not asserted: deleting
  `code-verifier_body.md.j2:159` reddens the general-principle test, and deleting the anchor at
  `:116` reddens three.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | A config-reconstruction path is missed and `toolchains` silently resets | medium | high — the seeded value vanishes and ADR-006's default silently returns | The live path for a **root-level** field is `_build_answers`'s seven-field rebuild on `--preset` (`cli.py:1402`), whose own comment records this loss class for `autonomy`. ADR-002's root placement made `_build_second_opinion_override` structurally incapable of dropping it, so aiming the mitigation there was wrong. Phase 1(c) covers `--preset` explicitly; Phase 1(d) is an AST test over every `InterviewAnswers` construction site so the coverage cannot go stale |
| R8 | Seeding emits repo-wide templates and the oracle produces only unlabelled blocks | was **certain** in draft 1 | high — zero per-finding evidence, and AC-011's warning does not fire because coverage is non-zero | ADR-007 takes commands from a static per-stack table, not from the detector's strings; Phase 3 asserts `{path}` presence in every seeded `test`/`lint` and adds an end-to-end labelled-block case |
| R9 | The parity gate's population empties itself on success | was **certain** in draft 1 | medium — the suite fails on a correct fix, or the guard is dropped and the class returns | Discovery keys on an `@hm:oracle-command-surface` anchor, independent of the string under removal; population size is asserted, not just non-emptiness |
| R2 | Prose and runtime diverge because Phase 4 lands before Phase 3 | medium | medium | `depends_on: [2, 3]`, raised from `[2]` after both models flagged it |
| R3 | The parity gate passes vacuously | medium | medium — the count:2 failure class | Non-vacuity assertion on population size; multiline scan; sites enumerated as `file:line` in Phase 4 scope |
| R4 | A worktree-local `toolchains` edit is invisible to its own review (ADR-005) | low | low | Documented in ADR-005 consequences; the inverse failure is silent and worse |
| R5 | `verify` / `wrapup` keep running the hardcoded triple while `toolchains` says otherwise (ADR-009) | certain | low for this round | Listed in SPEC Non-Goals with file paths; ADR-009 makes the interval explicit |
| R6 | A repo-wide command's unrelated failure still sways the verifier despite being unlabelled | low | medium | AC-010 pins the absence of labels; the consumer rule that neutralises it already exists and is quoted in the oracle evidence |
| R7 | Seeding emits a command the project's package manager rejects (`npm run test {path}` needs `--`) | medium | low | ADR-007: seeding maps by stack identity and emits nothing for an unknown stack; a wrong command degrades to a labelled failing block, never to fabricated cross-language output |

## ✅ Success Criteria

- [x] AC-001 — uncovered extension: zero subprocess calls, finding in the no-oracle tail
- [x] AC-002 — `.py` path with no key: byte-identical to the parent commit
- [x] AC-003 — only declared role commands run, in role order
- [x] AC-004 — `{path}` present ⇒ per path; absent ⇒ exactly once per gather
- [x] AC-005 — five-row extension default table
- [x] AC-006 — no adversarial `file` value reaches any argv element; `shell` never true
- [x] AC-007 — fill-if-empty; user value preserved through every reconstruction path
- [x] AC-008 — no surface asserts the hardcoded triple; population non-empty
- [x] AC-009 — no `(template, path)` pair crosses toolchain groups
- [x] AC-010 — repo-wide block carries no id label
- [x] AC-011 — a run emitting no id-labelled block writes exactly one cause-differentiated stderr line; stdout unchanged
- [x] AC-012 — malformed / inert `toolchains` degrades to `no_oracle`, never raises
- [x] `uv run ruff check` and `uv run mypy --strict` clean on all touched modules

## 🔍 Plan Validation

**Pass 1 — `plan-validator`: MAJOR_REVISION** (4 critical, 5 warning, 2 suggestion), run with
cross-model findings from both enabled models injected. Every critical was fact-checked against
the source before revising; all four held.

| Critique | Verified | Resolution |
|---|---|---|
| **C1** Phase 3 seeds repo-wide commands → zero labelled evidence for **every** stack, and AC-011 does not fire because coverage is non-zero | `profile.py:206-232` emits `uv run ruff check .`, `cargo test`, `{runner} run {key}` — none carry a path | Interview #7. ADR-007 rewritten: detection supplies stack identity only; commands come from a static per-stack table. Phase 3 asserts `{path}` in every seeded `test`/`lint` plus one end-to-end labelled-block case |
| **C2** Phase 1 scope names `templates/harness.yaml.j2`, which does not exist | Confirmed — real files are `templates/harness-yaml/{Production,Side}.yaml.j2`. CLAUDE.md records this exact class (corrected 2026-07-29) | Both real paths named; Phase 1 exit now asserts emission under **both** presets, since a single-template pass leaves half the install base on ADR-006's default |
| **C3** R1 aims at `_build_second_opinion_override`, which ADR-002's root placement already made safe; the live drop path is `_build_answers`'s seven-field rebuild on `--preset` | `cli.py:1402-1411` confirmed — the comment directly above it records this same loss class for `autonomy` | R1 rewritten; Phase 1(c) covers `--preset`; Phase 1(d) defines the discovery mechanism as an AST test over `InterviewAnswers` construction sites, modelled on `test_autopilot_marker_api_session_key.py` |
| **C4** ADR-003's "structurally unrepresentable" claim does not cover per-entry `commands: {}` / `extensions: []`, and does not say where overlap is rejected | Confirmed by inspection — `main()` guards only the findings-file parse | ADR-003 gained explicit validity rules and two enforcement points (pydantic at load, `resolve_toolchains` at runtime with a never-raise contract); new **AC-012** and a Phase 2 malformed-config assertion |
| **W1** command `cwd` unpinned | ADR-005 now states worktree `--root` explicitly; AC-006 asserts it |
| **W2** Phase 4's discovery predicate is self-defeating if keyed on the string being removed | Discovery keys on an `@hm:oracle-command-surface` anchor; population size asserted, not just non-emptiness |
| **W3** AC-002's differential mechanism unnamed | Testing Strategy names `git show HEAD~:` into a temp module, and rejects the two variants that void the independence claim |
| **W4** `no_oracle` tail format and budget displacement unspecified | Phase 2 specifies a cause-grouped tail and asserts the 800-char block floor is not starved |
| **W5** ADR-009's "general principle" never written | Written verbatim in ADR-009; AC-008 asserts its **presence**, not only the triple's absence |
| **S1** SPEC Open Question 1 left unanswered | ADR-008: the block header names the resolved toolchain (one interpolated field — the "if free" condition holds) |
| **S2** Phase 3 merge_hazards inaccurate | `cli.py` / `synthesize.py` / `models.py` listed against Phase 1 |

**Cross-model reconciliation (validator pass 1).** codex: 3 addressed, 6 partially-addressed,
1 not-addressed (`700c5117` — the seeding shape, now C1). antigravity: 2 addressed,
3 partially-addressed, 1 not-addressed (`5888f3df` — the `cwd`, now W1). Every
partially-addressed item is closed by the revisions above; the two not-addressed items were the
two the revision cycle existed to catch.

**Pass 2 — `plan-validator`: MAJOR_REVISION** (1 critical, 5 warning, 3 suggestion). It confirmed
C2, C3 and C4 as genuinely resolved by fact-check, and found that **C1's replacement artifact was
itself wrong**.

| Critique | Verified | Resolution |
|---|---|---|
| **C5 (critical)** ADR-007's static Node row renders `<r> vitest run {path}`, but `runner` falls back to **npm** when no pnpm/yarn lockfile exists — the most common Node repo — and `npm vitest …` is not a valid command. It exits non-zero without parsing the subject, and because it *does* carry `{path}` it is emitted **id-labelled**: the false-`accepted` shape ADR-001 removes, reproduced by the seeder. Phase 3's exit asserted only `{path}` presence and group disjointness, both of which the broken table satisfies | `profile.py:224-229` confirmed — `else: runner = "npm"` | Node row uses `npx --no-install`; each Node role is gated on the tool appearing in `devDependencies` (absent tool ⇒ **no entry** ⇒ `no_oracle`, never a wrong command); Phase 3 asserts invocation-form validity for the detected runner and a `jest`-not-`vitest` fixture asserting the `test` role is absent |
| **W6** The Rust limitation suppresses its own detector: a seeded Rust harness has covered paths and a non-empty command set, so AC-011 never fires while every block is unlabelled | Follows from ADR-004 + the AC-011 trigger as written | **AC-011's trigger is now an output property** — warn when no id-labelled block was emitted for any covered finding, whatever the cause. One predicate covers Rust, any future all-repo-wide config, and both original causes. Partial-coverage counts are reported on the same single line (absorbs S3) |
| **W7** `HEAD~` is a moving reference; after any later commit AC-002 compares the new `gather()` against itself and passes vacuously forever | Correct by construction | Baseline pinned to an immutable blob SHA embedded as a test constant; an unresolvable blob is a hard failure, never a skip |
| **W8** Prose AC-006 was amended but the `.machine.yaml` AC-006 was not — the artifact `/hm:execute` binds tests to disagreed with the prose | Confirmed by inspection | machine AC-006 `input_domain` / `expected_relation` / `preconditions` amended; Verification Criteria row now lists three test names |
| **W9** An anchor set is self-declared by the artifacts being fixed — a **newly added** unanchored surface is invisible by construction | The `gate-scoped-to-the-artifact-being-fixed` shape this PLAN cites in Prior Work | Anchor scan paired with a complement scan: any file referencing the oracle must carry the anchor or appear in a `DEFERRED_SURFACES` constant holding ADR-009's eight paths |
| **W10** AC-012's domain is entirely about the *value* of `toolchains`; an unparseable `harness.yaml` or a failed base-root resolution raises from the config **read**, outside any `ValidationError` handler | Confirmed — `main()` guards only the findings-file parse | Contract restated as "no exception of **any type** escapes `resolve_toolchains()`"; both read failures added to AC-012's domain and the Phase 2 assertion |
| **S4** Phase 2 `serial-core` vs Phase 3 `post-foundation` contradicted the prose calling them co-schedulable; Phase 4's rollback pointed at Phase 2 despite depending on `[2, 3]` | Both correct | Phase 2 moved to `post-foundation`; Phase 4 rollback set to Phase 3 |
| **S5** Cross-entry disjointness attributed to `ToolchainConfig`, which structurally cannot see siblings | Wording defect, not an enforcement gap | Phase 1(a) assigns disjointness to a model-level validator on the containing list |

**Outcome: `MAJOR_REVISION_RESOLVED`.** The re-run cap (one) is spent, so all nine items were
applied without a third validator dispatch — an explicit user decision, recorded here. The cap
governs validator dispatches, not corrections. Residual exposure: the pass-2 revisions themselves
are unvalidated by an independent reviewer; `/hm:review` is the next gate that sees them.

**Cross-model reconciliation (validator pass 2).** Both pass-1 not-addressed items are now
`accepted`: codex `700c5117` (the seeding shape — its underlying claim stayed live through C5 and
is closed by the `npx` + `devDependencies` gate) and antigravity `5888f3df` (the command `cwd` —
pinned in ADR-005, asserted in Phase 2, and now mirrored in machine AC-006).
