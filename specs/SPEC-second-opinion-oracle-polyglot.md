---
type: spec
task_slug: second-opinion-oracle-polyglot
status: approved
created: 2026-08-10
tier: 2
tags:
  - harness-maker
  - spec
  - python
  - second-opinion
  - oracle
  - polyglot
test_framework: pytest
research_doc: "[[RESEARCH-second-opinion-oracle-polyglot]]"
summary: "Oracle refuses toolchains that cannot parse a file, and sources commands from harness.yaml"
---

## 🎯 Intent

`second_opinion_oracle._run_checks` issues `uv run pytest`, `uv run ruff check` and
`uv run mypy` against every path a cross-model finding names, in every consuming
project, regardless of language. In a TypeScript project this does not degrade the
oracle — it **fabricates** one: three commands that never parsed the finding's
subject, all exiting non-zero, injected into `code-verifier` mode B as evidence.

Measured on a 4-line `.tsx` file: `ruff` emits 3809 bytes of Python syntax errors at
`exit=1` — byte-indistinguishable in meaning from real lint failures — while `pytest`
exits **4** (a code the mode-B rubric does not cover; it teaches only `exit=5`) and
`mypy` exits 2. Two bad outcomes follow, and both are silent: the per-command budget
truncates the wall of noise, and the resulting `[… truncated N chars …]` marker routes
the finding to **`unresolved`** via the rubric's own truncation rule; or a verifier
reading "an oracle block demonstrates the failure" grants a false **`accepted`**, which
carries a Step 4 consensus vote.

## 🌅 Outcomes

After this change:

- A consuming project in **any** language gets either a real oracle or an explicitly
  labelled absent one. It never gets output from a tool that could not parse the file.
- A project declares its own check commands in `harness.yaml`, and
  `/harness-maker:make` pre-fills that declaration from the manifests it already
  detects — so a new TypeScript harness has a working oracle without hand-editing.
- Every Python harness in existence behaves exactly as it does today, byte for byte.
- The four prose surfaces that assert a hardcoded `pytest` / `ruff` / `mypy` triple
  stop asserting it, and a parametrised test prevents the assertion from returning.

## 📋 In-Scope Scenarios

### AC-001: Toolchain that cannot parse a file runs nothing

**Given** a repo whose resolved oracle toolchain has no check registered for the
extension `.tsx`
**And** a cross-model finding naming an in-diff path `src/App.tsx`
**When** `gather()` runs
**Then** zero subprocesses are spawned for that path
**And** the finding's `id` appears in the `### no oracle gathered for:` tail with a
reason naming the toolchain and the extension
**And** no oracle block labelled with that `id` is emitted

### AC-002: Existing Python harnesses are unchanged

**Given** a repo with no `second_opinion.oracle_commands` key
**And** a cross-model finding naming an in-diff path `src/mod.py`
**When** `gather()` runs
**Then** the emitted block is byte-identical to the output of the pre-change
implementation for the same inputs

### AC-003: Commands come from the top-level `toolchains` declaration

**Given** `harness.yaml` declares a root-level `toolchains` list, each entry carrying
`name`, `extensions`, and a `commands` mapping with `test` / `lint` / `types` roles
**When** `gather()` runs for a path an entry's `extensions` covers
**Then** the commands executed are exactly that entry's declared roles, in role order
**And** no `pytest` / `ruff` / `mypy` command is executed unless declared

### AC-009: A path receives only its own group's commands

**Given** a `toolchains` list with a `python` entry and a `node` entry
**And** an in-diff path list containing both `src/mod.py` and `src/App.tsx`
**When** `gather()` runs
**Then** `src/mod.py` receives only the `python` entry's commands
**And** `src/App.tsx` receives only the `node` entry's commands
**And** no command from one entry is ever invoked with a path matched by another entry

### AC-010: Repo-wide commands are unlabelled context, not per-finding evidence

**Given** a declared command without `{path}` (e.g. `pnpm tsc --noEmit`)
**When** `gather()` emits its output
**Then** the block carries no finding `id` label
**And** it is headed as project-wide context that adjudicates no individual finding

### AC-011: Total loss of coverage is visible to the user

**Given** a run that emits **no id-labelled block for any covered finding** — whether
because no path is covered, the command set is empty, the config is unusable, or every
resolved command is repo-wide (a seeded Rust harness), or a run with a non-zero
uncovered fraction
**When** `gather()` finishes
**Then** exactly one warning line naming the uncovered count and the remedy is written
to stderr
**And** the line distinguishes an intentional gap (no toolchain covers these extensions)
from an unusable configuration (malformed or inert entries)
**And** stdout is unaffected

### AC-012: A malformed or inert toolchain declaration degrades, never raises

**Given** a `toolchains` value that is non-list, has overlapping extension sets across
entries, or contains an entry with empty `commands` or empty `extensions`
**When** `gather()` runs
**Then** it returns normally — no exception escapes to `main()`
**And** every path routes to `no_oracle`
**And** the AC-011 warning names the unusable-configuration cause
**And** no labelled block is emitted carrying a finding `id` and no evidence

### AC-004: `{path}` presence decides per-path versus repo-wide

**Given** a declared command list containing entries with and without `{path}`
**When** `gather()` runs over M distinct in-diff paths
**Then** each `{path}`-bearing command is invoked once per path with the placeholder
substituted
**And** each command without `{path}` is invoked exactly once for the whole run,
with no path appended

### AC-005: Absent-key default is extension-conditional

**Given** no root-level `toolchains` key
**When** `gather()` runs
**Then** paths ending `.py` or `.pyi` receive the historical Python triple
**And** every other path receives no oracle, labelled per AC-001

### AC-006: Substitution never precedes sanitisation

**Given** a cross-model finding whose `file` field is option-shaped, absolute,
`..`-traversing, metacharacter-bearing, or outside `git diff --name-only HEAD`
**When** `gather()` runs with a `{path}`-bearing declared command
**Then** no subprocess receives that value in any argv element
**And** every executed command is passed as an argv list, never a shell string
**And** every invocation's recorded `cwd` equals the `--root` worktree, not the base root
**And** repeated and embedded placeholders (`--file={path}`, `{path}.snap`) substitute in
every occurrence without re-splitting the token

### AC-007: make-time seeding fills only an empty slot

**Given** an existing `harness.yaml`
**When** `/harness-maker:make` runs
**Then** `toolchains` is written from manifest detection only if the key is absent or
an empty list
**And** a user-authored non-empty value is preserved verbatim across re-render
**And** the value survives every config-reconstruction path, including
`--second-opinion-models` and any other flag that rebuilds a config block
**And** when detection yields nothing, the key is not created

### AC-008: No surface asserts a hardcoded Python triple

**Given** the enumerated set of surfaces that describe the oracle's command set
**When** the parity test runs
**Then** no surface in the set asserts that oracle blocks are `pytest` / `ruff` /
`mypy` output, nor teaches a mismatch rule specific to one of them
**And** the enumerated set is non-empty

## 🚫 Non-Goals

- Teaching the mode-B rubric a per-toolchain exit-code vocabulary. Toolchain
  knowledge stays in the gatherer; the rubric keeps its single existing rule,
  "absent oracle is not refutation".
- Re-tuning `BUDGET_TOTAL` / `BUDGET_PER_COMMAND` or the 300 s timeout. Current
  values are retained; changing them is a separate measurement.
- Any change to `safe_paths()`, `redact()` or `truncate()` semantics.
- Reusing `reviewers.mechanical_checks` as the oracle command source. CLAUDE.md
  explicitly forbids reusing the Phase 0 mechanical-check *run*; a separate key
  avoids conflating a repo-wide pre-check with a path-scoped adjudication.
- An interview question for the new key. Like `mechanical_checks`, it is
  user-maintained in `harness.yaml` and preserved on re-render.
- A ledger schema change for observability. A single stderr line (AC-011) is in
  scope; extending `codex_ledger` and its aggregation is not.
- Migrating the **other eight** rendered surfaces that hardcode the Python triple
  (`stages/verify.md.j2`, `stages/wrapup.md.j2`, `commands/hm/loop.md.j2`,
  `skills/verify-before-completion`, `skills/targeted-test-selection`,
  `rubrics/claude_md.yaml.j2`, `settings/Production.json.j2`,
  `settings/Side.json.j2`) onto `toolchains`. The key is placed at the root
  precisely so those migrations need no key move, but they are follow-up work —
  a `verify` / `wrapup` regression would hit every consuming project.
- Deleting the `Bash(uv run pytest:*)` family from the settings templates. Those
  grants gate **Claude's own** Bash calls; the oracle shells out from Python and
  never passes through them, so they are not this defect's taint path.
- Detecting toolchains beyond Python / Rust / Node. `_detect_mechanical_checks`
  has no CMake or Meson probe today and gains none here; a C++ project declares
  `toolchains` by hand.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | This repo's framework; `/hm:execute` Phase A writes against it |
| Command execution | argv list, `shell=False`, `timeout=300` | CLAUDE.md §외부 명령 호출; `shell=True` is banned repo-wide |
| Substitution order | `safe_paths()` → `{path}` substitution → argv | The module exists because `file` is an unconstrained external-model field and settings pre-approve `Bash(uv run pytest:*)` as a **prefix** rule |
| Config preservation | fill-if-empty only | CLAUDE.md checkpoint 1; matches how `reviewers.mechanical_checks` survives re-render |
| Backward compatibility | zero behavior change for absent-key `.py` paths | Every shipped harness is in this state |
| Schema | root-level `toolchains: list[ToolchainConfig]`, default `[]`; each entry `{name, extensions: list[str], commands: {test?, lint?, types?}}` | Empty list = off, same convention as `mechanical_checks`. Root-level because the toolchain identity is a project fact eight other rendered surfaces also hardcode; nesting it under `second_opinion` would make it the third encoding and force a key migration later |
| Command tokenisation | `shlex.split` the declared string first, then substitute `{path}` **within** the resulting tokens; never re-split after substitution | A path may legally contain a space (`_UNSAFE_CHARS` does not reject it), so substituting into the raw string would turn one path into two argv entries |
| Exit code | `main()` always exits 0 | Unchanged — a missing oracle is less evidence, never a failed review |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| AC-001 | unit | `test_non_toolchain_extension_spawns_no_subprocess` |
| AC-002 | unit | `test_python_path_output_unchanged_from_baseline` |
| AC-003 | unit | `test_declared_commands_are_the_only_commands_run` |
| AC-004 | unit | `test_path_placeholder_decides_per_path_vs_repo_wide` |
| AC-005 | unit | `test_absent_key_defaults_by_extension` |
| AC-006 | unit | `test_unsafe_file_value_never_reaches_argv`, `test_recorded_cwd_is_the_worktree_root`, `test_repeated_and_embedded_placeholders_substitute_without_resplit` |
| AC-007 | unit | `test_seeding_fills_only_empty_and_preserves_user_value` |
| AC-008 | unit (structural) | `test_no_surface_asserts_python_triple` |
| AC-009 | unit | `test_path_receives_only_its_own_toolchain_commands` |
| AC-010 | unit | `test_repo_wide_block_is_unlabelled` |
| AC-011 | unit | `test_zero_coverage_emits_one_stderr_warning` |
| AC-012 | unit | `test_malformed_toolchains_degrades_without_raising` |

## ❓ Open Questions

None blocking `/hm:plan`. Two items were resolved as deliberate deferrals and are
recorded here so `plan` does not re-litigate them:

1. **Observability (`oracle_toolchain`).** RESEARCH pitfall 5 argues that
   "every finding `unresolved` because no toolchain matched" should be countable
   rather than inferred, given this subsystem's history of green-looking silence
   (the `skipped/total` denominator that read 10.3% when the truth was 20.7%).
   Excluded from this SPEC by explicit scope decision. If `plan` finds the block
   header carries it for free, that is in scope; a ledger schema change is not.
2. **Budget re-tuning.** With correct toolchains, `tsc` and `eslint` are as
   verbose as `ruff`, so a 1500-char cap can reproduce the reported symptom
   (truncation marker → `unresolved`) with the *right* tools. Out of scope; needs
   its own measurement.

## 🔍 Refinement Decisions

- **Round 1 (Outcomes / Non-Goals / Constraints):** scope locked to RESEARCH
  approaches **C + B + A** in full — extension gate, `harness.yaml` command source,
  and make-time seeding. Absent/unsupported toolchain resolves to **zero commands
  executed** plus a labelled `no_oracle` entry, not an annotated block; this removes
  the false-`accepted` path entirely rather than delegating it to rubric judgment,
  and drops 3×300 s of timeouts and a multi-megabyte `redact()` pass.
- **Round 2 (Constraints / Non-Goals):** `{path}` placeholder presence implicitly
  decides scope — bearing it means per-path, omitting it means one repo-wide
  invocation. Chosen over an explicit `scope:` field because the two can be made
  mutually inconsistent by a user and the placeholder cannot. Prose surfaces are
  **both** corrected and guarded by an enum-parametrised test; the guard was
  initially left out of verification and was reinstated after the
  `[fail:test] gate-scoped-to-the-artifact-being-fixed` precedent (count:3, whose
  2026-07-30 instance is in this same subsystem) was surfaced.
- **§2.5 inequality gate:** four candidates generated, one asked. Skipped —
  argv/`shell=False` handling (common-ground: CLAUDE.md + module docstring),
  budget re-tuning (EIG below ε; retaining current values is the obvious default),
  config key location (common-ground: CLAUDE.md forbids reusing the Phase 0
  mechanical-check run). Asked — make-time seeding versus an existing key, resolved
  to **fill-if-empty**, matching CLAUDE.md checkpoint 1 rather than the
  `content_hash` fingerprint pattern of checkpoint 5, which would introduce
  fingerprint storage into `harness.yaml` for a single field.
