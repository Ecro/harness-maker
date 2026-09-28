---
type: spec
task_slug: intent-file-inputs
status: approved
created: 2026-09-28
tags: [harness-maker, spec, python, intent-layer, cli, injection]
test_framework: pytest
tier: 2
interview_rounds: 3
summary: "hm intent free-text arguments read from files; rendered recipes stop putting text on the command line"
---
# File inputs for `hm intent` free-text arguments

## 🎯 Intent

Every rendered recipe that writes an intent record puts operator- or agent-composed text inside
a shell command (`--claim '<text>'`, `--note '<text>'`, `--statement "<text>"`). Quoting only
moves the breakout character; three review runs of `sdlc-three-loops-gap` each found the next
site, and the residual P1 `58ef46c950a7b459` was accepted with this task as its structural fix.
The fix is the one `memory_md upsert-wiki --body-file` already uses: the text goes into a file
written with the Write tool, and the command line carries only a path.

## 🌅 Outcomes

- Every free-text argument of the `hm intent` write verbs has a `--<name>-file` twin that reads
  the value from a UTF-8 file.
- No rendered recipe (wrapup Step 5.7, spec Step 4.9, the intent-layer skill) places free text
  on a command line; each tells the agent to write it to a `mktemp` path outside the repo with
  the Write tool and pass that path.
- Existing inline invocations keep working unchanged.

## 📋 In-Scope Scenarios

Covered arguments — `question observe` (`--text`, `--claim`), `question add` (`--claim`,
`--text`), `question resolve` (`--claim`), `metric record` (`--evidence`), `close` (`--note`),
`new` (`--title`, `--statement`, `--scope`, `--out-of-scope`, `--declined`). File twins:
`--text-file`, `--claim-file`, `--evidence-file`, `--note-file`, `--title-file`,
`--statement-file`, `--scope-file`, `--out-of-scope-file`, `--declined-file`. Multi-item:
`--scope`, `--out-of-scope`, `--declined`.

Rendered call sites (the expected set for S5): wrapup Step 5.7 — `question observe`,
`question add`, `close`; spec Step 4.9 — `new`; intent-layer skill — the verb synopsis
(`question add/observe/resolve`, `metric record`, `new`, `close`) and the proposal-path `new`
line. Each exists in the Claude and the Codex render.

### S1: A file value equals the same inline value
**Given** a single-valued text `x` that does not end in a newline
**When** one call passes `--<name> x` and another passes `--<name>-file` pointing at a file
holding `x` followed by zero or more `\n`
**Then** each covered field stored by either call equals `x` itself (compared to the original
`x`, not to the other call's output; timestamp fields excluded; each call on a fresh root)
**And** one call may mix forms across arguments (`--title x --statement-file f`)

### S2: Shell metacharacters survive untouched
**Given** a file whose text contains `'`, `"`, a backtick, `$(...)`, and an embedded newline
**When** it is passed through the matching `--<name>-file`
**Then** the stored value is that text exactly, with only trailing `\n` removed

### S3: Ambiguous or empty input is refused
**Given** a verb call
**When** both `--<name>` and `--<name>-file` are given, or a required argument is given in
neither form, or the file is missing, not UTF-8, or empty after trailing-newline removal
**Then** the command exits non-zero with a message naming the argument
**And** nothing is written: `.claude/intent.yaml`, `intent/*.md`, `.claude/intent/metrics.yaml`
and the intent ledger are byte-identical to before

### S4: Multi-item files
**Given** a `--scope-file`, `--out-of-scope-file` or `--declined-file` holding one item per line
**When** `hm intent new` reads it
**Then** each non-empty line (surrounding whitespace stripped) is one item, in order, equal to
passing each as the repeated inline flag
**And** a file with zero non-empty lines is refused, for each of the three

### S5: Rendered recipes carry paths, not text
**Given** a freshly rendered harness (Claude and Codex targets)
**When** wrapup Step 5.7, spec Step 4.9 and the intent-layer skill are read
**Then** every call site in the expected set is present
**And** none carries a covered argument in inline form; each uses the `-file` twin
**And** each surface instructs writing the file with the Write tool to a `mktemp` path outside
the repo

## 🚫 Non-Goals

- Removing the inline flags (kept for hand use; templates stop using them).
- `--locator`, `--observed-at`, `--status`, `--relation`, ids and metric values — not free text.
- Other CLIs (`memory_md`, `second_brain promote` already take `--body-file`).
- A PreToolUse hook that inspects `hm intent` command lines.
- Re-rendering this repo's dogfood harness (happens with the next release).
- Editing `src/harness_maker/templates/skills/intent-layer/references/workflow-feedback.md.j2`
  (hash-bound WORLD-INTENT-CLOSED-LOOP trial evidence).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo standard |
| Type / lint | `mypy --strict src tests`, `ruff` | CI runs `tests` too (last task's miss) |
| Compatibility | Inline flags unchanged. Per argument: a required one takes exactly one form; an optional one at most one, and neither keeps today's default. Forms may differ between arguments of one call | Released harnesses (0.60.4 cache) still pass inline values |
| File decoding | UTF-8 only; value = content with trailing `\n` removed | S1 equivalence with inline values |
| Protected file | `workflow-feedback.md.j2` untouched | `tests/unit/test_world_intent_protocol_evidence.py` binds captured evidence to its hash |
| Skill size | Rendered intent-layer SKILL.md ≤ 120 newlines | `test_render_intent_layer_assume_add` cap |
| Surface budget | Declare `surface_allowance` in the PLAN; a terminal phase re-freezes the baseline and removes the allowance | Otherwise main goes red after land (memory: surface_allowance expires at wrapup) |
| Instruction baseline | Changed `!` lines are listed in `_ALLOWED_REMOVALS` per the test's documented procedure | `test_instruction_preservation` |
| Dogfood | Recipes calling `*-file` flags fail against the 0.60.4 plugin cache until release | Rendered harness pins the released plugin |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add `--text-file`, `--claim-file`, `--evidence-file`, `--note-file`, `--title-file`, `--statement-file`, `--scope-file`, `--out-of-scope-file`, `--declined-file` to the public `hm intent` CLI, with fixed value semantics: UTF-8; single values = content minus trailing `\n`, empty refused; multi-item = one item per non-empty stripped line, zero items refused | public API/CLI contract | Rendered harnesses will write files to these semantics; removing a flag or changing the semantics later breaks them |

## Acceptance Criteria

### AC-001: File value equals inline value
For every covered single-valued argument, the field stored from a file holding `x` plus trailing
newlines, and from inline `x`, each equal `x`.

### AC-002: Metacharacters stored verbatim
Text containing quotes, a backtick, `$(...)` and newlines passed by file is stored exactly.

### AC-003: Ambiguous or empty input refused
Both forms (single and multi-item), neither form for a required argument, missing file, non-UTF-8
file, or empty value exit non-zero, name the argument, and leave every intent artefact unchanged.

### AC-004: Multi-item file parsing
`--scope-file`, `--out-of-scope-file` and `--declined-file` yield one item per non-empty stripped
line, equal to the repeated inline flags; zero items is refused for each.

### AC-005: Rendered recipes carry no inline free text
Every expected call site is present in both renders, none carries a covered argument inline, and
each surface carries the Write-tool `mktemp` instruction.

### AC-006: Inline invocations unchanged
Existing intent CLI behaviour tests keep passing without modification. Render tests that pin the
old inline recipe text (e.g. `tests/unit/test_render_intent_layer.py`) may be updated to the
`-file` form.

### AC-007: Mixed forms in one call
`hm intent new` with `--title` inline and `--statement-file` stores both values.

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (property) | `tests/unit/test_intent_file_inputs.py::test_file_equals_inline`, `::test_mixed_forms` |
| S2 | unit | `tests/unit/test_intent_file_inputs.py::test_metacharacters_verbatim` |
| S3 | unit (parametric) | `tests/unit/test_intent_file_inputs.py::test_refused_inputs` |
| S4 | unit | `tests/unit/test_intent_file_inputs.py::test_scope_file_lines` |
| S5 | unit (render) | `tests/unit/test_intent_file_inputs.py::test_recipes_carry_no_inline_text` |
| — (AC-006) | unit | `tests/unit/test_intent_doc_new.py`, `test_intent_doc_record.py`, `test_intent_vocabulary.py` unchanged and green |

## ❓ Open Questions

(none)

## 🔍 Refinement Decisions

- Round 1: all free-text arguments of the write verbs; keep inline flags with mutual exclusion;
  intent link none; autopilot on.
- Round 2: file value = UTF-8 content minus trailing `\n`, empty refused; multi-item files are
  one item per non-empty stripped line; IRR-001 recorded; DRI approved.
- Round 3 (spec-validator MAJOR_REVISION + Codex, 7 findings accepted): `--declined` added (it
  was inside the approved "all free-text arguments" scope and rendered double-quoted); AC-001
  compares each field to the original; AC-003/004 strengthened; AC-005 pins the call-site set;
  AC-006 scoped to CLI behaviour tests; AC-007 mixed forms; IRR-001 carries the value semantics.
