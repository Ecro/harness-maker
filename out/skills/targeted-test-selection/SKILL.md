---
generated_by: harness-maker
harness_maker_version: 0.52.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/targeted-test-selection/SKILL.md.j2
provenance: official
name: targeted-test-selection
description: Procedure for turning a set of changed files into the tests that actually
  cover them, instead of running the whole suite. Followed by /hm:review's auto-fix
  loop on every fix round; mirrors what /hm:execute Phase D does inline.
content_hash: e8296294d21bce2f3548cc74f0136490bcd5c4f6f6565887c3e691f89c53f208
---

# targeted-test-selection

Select what to run, then run it — and run it with the right amount of the machine.

Three levers, and **which of them exist depends on the runner, not on this skill**. Ask first:

```bash
uv run --with $HOME/harness-maker hm test_runners plan --root .
```

It prints the project's runner (detected from its markers), a `workers` count already capped
for this machine, and — per lever — either the command or `null`:

| Field | Meaning when non-null |
|---|---|
| `parallel` | the flag to add, with the worker count substituted |
| `parallel_is_default` | **`true` = do NOT add it.** `cargo`, `go`, `vitest`, `jest` and `flutter` already parallelise; the flag there caps or nests rather than accelerates |
| `parallel_requires` | an install the flag needs first (`-n` on a pytest without `pytest-xdist` is just `unrecognized arguments`) |
| `select_changed` | the runner's own change-based selection, when it has one |
| `rerun_failed` | re-run only last run's failures — the biggest win while iterating |
| `runner: null` | this table has never heard of the toolchain. **Not an error**: use the project's own test command and skip to §4 |

**`workers` is deliberately about half the cores**, floored at 1 and never above `cores - 1`.
More is not faster: the runner's workers are not the only processes on the box (a suite that
shells out to `git` doubles them), the session waiting for the suite needs a core too, and
several runners are already parallel internally — asking for N there requests N × M. Raise it
with `--fraction`, which refuses anything above 0.7 rather than silently clamping.

§1–§3 below are the **Python** dep-map selector. The selector is `harness_maker.test_dep_map`;
it returns either a bounded node list or an explicit FULL with a reason, and it is **never**
silent. For a non-Python runner use `select_changed` if the recipe named one, and otherwise run
the full suite — a missing dep map is a reason to run more tests, never fewer.

**Why this is a skill and not inline stage prose.** `review.md.j2` is re-read by every loop
commands, and `test_aggregate_shipped_surface_does_not_grow` asserts a STRICT non-increase
over the summed shipped surface against a baseline frozen at HEAD — headroom is zero, and
this recipe is several hundred characters. Every part of it below is a part an inline
character budget would have cut, and each one is a silent skip when missing. Skills are
outside that sum, so the recipe can be explicit here.

## 1. Compute the changed set

Two commands, unioned. Both are **NUL-delimited** — `--name-only` alone octal-escapes and
quotes any path with a space, a newline or a non-ASCII character, and this repo ships
Korean-named assets. A mangled path is not a file: it classifies as `source-without-hints`
(uselessly conservative) or, under a matching prefix, `inert` (unsafe).

```bash
git diff -z --name-only HEAD          # tracked: staged AND unstaged
git ls-files -z --others --exclude-standard   # untracked
```

Split each on NUL and take the union. **The untracked half is not optional**: an auto-fix
that creates a new module or a new test file is invisible without it, and the selection
then verifies a fix it never saw.

## 2. Select

Run this inside **the task worktree** you were given — not the base repo. `git diff`,
`git ls-files` and `--root .` all resolve against the working directory, so a base-repo
invocation returns the base's state and selects tests for changes that are not there.

```bash
cd <the task worktree> && uv run --with $HOME/harness-maker hm test_dep_map --root . --changed-file='<f1>' --changed-file='<f2>' …
```

**Both details of that argument form are load-bearing, and §1's care is wasted without
them.** Use the `=`-attached spelling: a legal git path may begin with `-`, and the
separate-token form makes argparse read it as an option, so the command exits 2 and
prints no JSON at all. Wrap every path in single quotes: the union from §1 can contain
spaces, newlines and shell metacharacters — that is exactly what `-z` preserves — and an
unquoted path splits into several argv entries or, worse, into a second command. If a
path contains a single quote, drop the argv form and re-run the selection with no
`--changed-file` at all, honouring the `mode: full` that comes back.

The `uv run --with` prefix is required — a bare `hm` may not resolve, and the failure mode
of a missing entrypoint inside prose is an LLM quietly skipping the step.

## 3. Empty changed set → still invoke

If the union from §1 is empty, run the command from §2 anyway, with **zero**
`--changed-file` arguments, and honour the `mode: full` it returns.

The selector already refuses to report a targeted selection for an empty input — but that
guard only fires if the CLI is actually called. The natural reading of "compute the set,
then run with it" is to skip the step when the set is empty, which runs no tests at all
and reports success. That is the absent-case failure this project has recorded before: a
feature that activates on an optional input must define what happens when the input is
missing.

## 4. Run

The command prints JSON:

- **`mode: targeted`** → run the test command with `node_ids` appended.
- **`mode: full`** → run the whole suite, and **echo `reason` verbatim** in your output.
  The reason names which changed file had no test mapped to it, or that the selector's own
  source changed (a selection it derives for its own change is circular evidence).
- **Anything else — non-zero exit, no output, or output that is not JSON** → run the
  **whole suite** and echo the command's stderr verbatim. A failed selection is not an
  empty selection. This arm exists because the two above presuppose the process
  succeeded, and a verify step that silently runs nothing reads exactly like a pass.

Whichever mode you are in, run the command the recipe gave you — `parallel` when it is
non-null, `full` otherwise. Two rules about that:

- **While iterating on a failure, run `rerun_failed` first** (when the recipe has one), then the
  targeted set, and only then the full suite. Re-running everything after each edit is where the
  wall-clock actually goes: one full pass per edit dominates any flag you could add.
- **The full suite still runs at least once before the work is called done**, serially or in
  parallel. A suite only ever run in parallel hides order- and isolation-dependent failures,
  which is also why the parallel flag belongs on the command line and **not** in the project's
  persistent config (`addopts` and its equivalents).

Lint and type checks stay **unconditional** — they are repo-wide, cheap, and have no
selection concept. Use the project's own:

```bash
uv run ruff check      # example: this project. Substitute the project's linter.
uv run mypy --strict
```

## 5. What the selection does and does not promise

- It resolves imports by **fully qualified module name**, so `from pkg import a, b` binds
  both names and `cache` never matches `detection_cache`.
- It walks **one hop** of reverse source dependencies: editing a module also selects the
  tests of the modules that import it directly, but not their importers in turn.
- A `conftest.py` that imports the changed module contributes its whole **directory** —
  an autouse fixture really does apply tree-wide.
- **Not covered**: dynamic references (`importlib.import_module("pkg.x")`, string
  monkeypatch targets) are invisible to an AST scan, and two-hop breakage is out of scope
  by design. A file the selector cannot map forces FULL rather than being skipped, so the
  failure direction is extra tests, never missing ones.
