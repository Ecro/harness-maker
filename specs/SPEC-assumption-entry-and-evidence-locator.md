---
type: spec
task_slug: assumption-entry-and-evidence-locator
status: approved
created: 2026-09-18
tags: [harness-maker, spec, python, jinja2, intent-layer, assumptions, staleness]
tier: 1
test_framework: pytest
research_doc: "[[RESEARCH-assumption-entry-and-evidence-locator]]"
summary: "`hm world assume add` + optional content-fingerprint `locator` on evidence; `gap` derives staleness"
---

> Vocabulary and storage layout are superseded by [[SPEC-intent-vocabulary-rename]];
> owners shape and advisory approval guidance by [[SPEC-intent-owners-role-map]].
> This historical SPEC and its machine companion retain their original ACs and test bindings
> as compatibility evidence. Unchanged behavioral guarantees still apply.


# SPEC — Assumption entry point + evidence locator

## 🎯 Intent

The assumption tri-state (`known / assumed / unknown / conflict`) is the one mechanism the first
intent RESEARCH called genuinely novel, and it cannot be entered. `hm world assume` has only
`observe` and `resolve`, both of which require an existing record, and the dogfood repo has no
`assumptions.yaml`. As a result, `depends_on` and `revisit_when: {assumption, status}` have nothing
to point at.

A recorded assumption also cannot say when the code it rests on has moved, which is how knowledge
in this repo has repeatedly gone stale. This SPEC adds an entry verb and an optional content
fingerprint on evidence, so the harness can report, deterministically and without an LLM, that a
cited span changed.

## 🌅 Outcomes

- An operator (or the model, on the operator's yes) can create an assumption with one CLI call, and
  wrapup 5.7 offers that call.
- An evidence entry can cite `path:A-B`. A citation of a path or span that does not exist is refused
  when it is recorded.
- `hm world gap --json` lists every assumption with its status and reports, per assumption,
  whether its most recent cited span is still present; a dependent non-terminal objective is listed
  under `needs_revalidation` when it is not. `hm world status` is unchanged (its payload is frozen).
- Re-confirming with a fresh locator clears the stale report. No record is ever rewritten to do so.

## 📋 In-Scope Scenarios

### S1: add creates a record
**Given** a world with no assumption `x`
**When** `hm world assume add x --claim "C" --status assumed` runs
**Then** `assumptions.yaml` holds `{id: x, claim: C, status: assumed, evidence: [], history: []}`
(the file and envelope are created when absent), and the CLI prints `changed: assumptions.yaml`, the
same form `observe` and `resolve` print
**And** with `--text T --observed-at TS [--locator L]` the record carries exactly one evidence entry
`{text: T, observed_at: TS(UTC), relation: confirms[, locator: …]}`

### S2: add refuses and writes nothing
**Given** a world where assumption `x` exists
**When** `add` is called with an existing id, `--status conflict`, an empty claim, an id outside
`[a-z0-9_]+`, a naive timestamp, or `--locator` without `--text`
**Then** the command exits non-zero, names the offending field, and `assumptions.yaml` is
byte-identical (or still absent)

### S3: a locator is validated and fingerprinted when recorded
**Given** a checkout containing `src/m.py` with 30 lines
**When** `add` or `observe` is given `--locator src/m.py:10-12`
**Then** the stored locator is `{path: src/m.py, lines: [10, 12], fingerprint: <sha256 of the
normalized lines 10–12>, k: <count of non-empty normalized lines in 10–12>}`
**And** `--locator` naming a missing path, an absolute path, a path containing `..`, `A > B`,
`A < 1`, `B` past the file's last line, a span longer than 40 lines, a span with no non-empty line after normalization, or a file that is
not UTF-8 or cannot be read is refused and nothing is written

### S4: gap derives freshness from the latest locator
**Given** an assumption whose most recent locator-bearing evidence cites `src/m.py:10-12`
**When** `hm world gap --json` runs
**Then** `assumptions` maps every assumption id to its status, and the assumption appears in
`stale_evidence` with `changed` when the normalized text is found
nowhere in the file, or with `missing` when the path is gone or unreadable
**And** it is absent from `stale_evidence` when the span is unchanged, or when the span changed only
in whitespace — including a blank line inserted inside it (`fresh`: the first `k` non-empty
normalized lines at or after line A hash equal)
**And** it is absent from `stale_evidence` when the normalized text now occurs at other lines
(`moved`), in which case `gap` reports the current line of that occurrence under
`moved_evidence`
**And** running `gap` writes no file, and `hm world status --json` returns the same key set as
before this change

### S5: re-confirmation clears the report
**Given** an assumption reported `changed` in S4
**When** `observe <id> --relation confirms --text … --observed-at … --locator src/m.py:14-16` runs
against the current file
**Then** the next `gap` no longer lists it, and the older evidence entry is still present,
unmodified

### S6: staleness propagates to objectives, reported not enforced
**Given** a `proposed` or `active` objective with `depends_on: [x]`
**When** `x` is in `stale_evidence` and `hm world gap --json` runs
**Then** that objective id is listed in `gap`'s `needs_revalidation` (as it would be for `conflict`),
and `derive(world, oid, staleness=…)` returns `needs_revalidation: true`
**And** a `closed` or `dropped` objective is never listed
**And** `derive` called without `staleness` (status, the autopilot gate, transitions) reads no cited
file and returns exactly what it returned before this change

### S7: writers do not lose each other's rows
**Given** two processes writing `assumptions.yaml` at the same time (`add` + `add`, or `add` +
`observe`)
**When** both complete
**Then** both writes are present in the file, and a writer that meets a held lock does not write
until the lock is released

### S8: wrapup and the skill offer the verb
**Given** a harness rendered with the intent layer present
**When** wrapup 5.7's assumption question renders (Claude and Codex variants)
**Then** its options are at most two assumption ids (stale ones first, labelled
**"(cited code changed)"**), then **"new — record an assumption"**, then **"no"** — four at most; any
remaining ids are named in the question text for the operator to type via Other; the ids come from
`hm world gap --json`'s `assumptions` / `stale_evidence`
**And** on "new" the block runs `hm world assume add …` exactly once with the arguments the operator
confirmed, keeping the `If the answer is "yes":` / `Otherwise: write nothing` contract
**And** the `intent-layer` skill lists the `add` argument form and the `--locator` flag on `observe`

## 🚫 Non-Goals

- **Probe-backed checks of external claims** (`check: {cmd}`, `hm world assume check`). Claims
  about Claude Code, Codex or `agy` behaviour cannot be caught by a repo locator; that limitation is
  accepted here and handled as a follow-up task.
- `path:line@sha`, `git diff`, or any VCS read in the staleness path.
- Symbol / AST anchors, whole-file hashes, and multi-span locators.
- Automatic change of an assumption's `status`, and automatic removal or rewriting of evidence.
- Gating on staleness: `needs_revalidation` stays a report; no autopilot, review or wrapup gate
  reads it.
- Locators on `CLAUDE.md`, `wiki.md`, or any file outside `.claude/world/`'s evidence records.
- A delete or rename verb for assumptions.
- Any change to `hm world status`'s payload (frozen by PLAN-objective-gap-proposal ADR-001).
- A schema major bump. `locator` is an optional evidence key, and a v1 reader without it keeps
  working.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` (+ `mypy --strict`, `ruff`) | CLAUDE.md fixed toolchain |
| Normalization | per line `" ".join(line.split())`; lines empty after that are dropped; the remainder joined by `"\n"`; fingerprint = lowercase hex sha256 of the UTF-8 bytes | persisted format; must be stable across releases; whitespace-only reflow is not a change |
| Locator path | repo-relative POSIX, resolved against the **current checkout root**, must not be absolute, contain `..`, or resolve outside the root | two-roots rule (versioned state reads the current tree); path traversal |
| Span | `1 ≤ A ≤ B ≤ last line`, `B − A + 1 ≤ 40`, and at least one line non-empty after normalization (an all-blank span has no fingerprint worth checking — refused with the other S3 cases) | a whole-file span is the noisy approach the RESEARCH rejected |
| Freshness | `fresh` = the first `k` non-empty normalized lines at or after line `A` hash to `fingerprint` | a blank line inserted inside the span is whitespace, not a change |
| Relocation | `moved` = the normalized span text equals the normalized text of some other contiguous run of the same number of non-empty lines in the file; the first such run's start line is reported | deterministic; there is no fuzzy match |
| Authoritative evidence | the entry with the greatest `observed_at` among those carrying `locator` (ties → later in file) | a re-confirmation is the re-stamp; history stays immutable |
| Derived, not stored | `fresh/moved/changed/missing`, `stale_evidence`, `moved_evidence` are computed at read time | existing `derive` principle; every mutation touches one file |
| Read cost | staleness is computed only by `gap` (and `derive` when handed a staleness map); it adds only file reads — no subprocess, no git, no LLM; `status`, the autopilot gate and transitions do no cited-file I/O | `status` is the free, frozen read path |
| Malformed stored data | a stored `locator` that fails its shape check, or a locator-bearing entry whose `observed_at` is not an aware ISO-8601 string, leaves the record loaded; the entry is treated as having no locator and the problem is listed in `broken_references` as `assumptions.yaml:assumptions[i].evidence[j].<field>` | locator data must never make a dependent objective `broken` (which would gate autopilot) |
| Locking | `add`, `observe`, `resolve` read-modify-write `assumptions.yaml` under the same flock mechanism `record_value` uses | review 40a36af2 finding repeated for a third writer |
| Schema | `schema_version` stays 1; `locator` = `{path, lines, fingerprint, k}` is optional | additive; old files load unchanged |
| Surface | wrapup 5.7 and the `intent-layer` skill only; ≤ 8 added lines per wrapup variant; skill stays ≤ 120 lines; growth declared via `BASELINE-DELTA-*.md` + `surface_allowance` and retired by a terminal phase | four normative size sites move together; allowance expires at wrapup |
| Writes | every write is answer-gated in rendered prose; the verbs themselves are ordinary CLI | SPEC-intent-world-model-objective-layer contract |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_ac_001_add_creates_record`, `test_ac_013_add_prints_changed_line` |
| S2 | unit | `test_ac_002_add_refusals_write_nothing` |
| S3 | unit | `test_ac_003_locator_validated_and_fingerprinted` |
| S3 | unit (property) | `test_ac_004_fingerprint_whitespace_invariant` |
| S4 | unit | `test_ac_005_gap_derives_freshness` |
| S5 | unit | `test_ac_006_latest_locator_is_authoritative` |
| S6 | unit | `test_ac_007_staleness_propagates_to_objectives` |
| S7 | integration | `test_ac_008_concurrent_writers_keep_both_rows` |
| S1–S4 | unit | `test_ac_009_v1_file_without_locator_loads` |
| S8 | unit (render) | `test_ac_010_wrapup_offers_add_and_lists_stale_first` |
| S8 | unit (render) | `test_ac_011_skill_lists_add_and_locator` |
| S8 | structural + manual | `tests/structural/test_assumption_entry_invariance.py::test_ac_012_surface_pinned_and_allowance_retired`; manual: `git diff` of the baseline files at the terminal phase |

### Acceptance criteria

### AC-001: add creates the assumption record
S1. The file, envelope and record equal the hand-written expected YAML for the no-evidence case
and for the with-evidence case.

### AC-002: add refusals write nothing and name the field
S2. For each of the six refused inputs: non-zero exit, the field named, the file byte-identical or
absent.

### AC-003: locator is validated and fingerprinted at record time
S3. A valid locator stores path, lines and the fingerprint of a hand-computed literal. Each of the
eight refused locators writes nothing, for both `add` and `observe`.

### AC-004: fingerprint is whitespace-invariant and token-sensitive
S3 / Normalization. Re-indenting, trailing spaces, CRLF line endings and inserted blank lines leave
the fingerprint unchanged; changing, adding or removing any non-whitespace character changes it.

### AC-005: gap derives fresh, moved, changed and missing without writing
S4. Four fixtures give four outcomes, plus a blank-line-inside-span fixture that stays fresh;
`moved_evidence` reports the relocated start line; `assumptions` lists a locator-less record; the
bytes of `.claude/world/` are unchanged after `gap`; `status`'s key set is unchanged.

### AC-006: only the latest locator-bearing evidence decides staleness
S5. After re-confirmation the assumption leaves `stale_evidence`, and the older entry is unchanged.
An evidence entry without a locator that is newer than the latest locator does not clear or cause
staleness.

### AC-007: staleness propagates to dependent objectives only while non-terminal
S6. Proposed and active dependents are listed in `gap`'s `needs_revalidation`; closed and dropped
are not; `derive` without `staleness` reads no cited file and is unchanged.

### AC-008: concurrent writers keep both rows
S7. A writer that meets a held lock does not write until release (positive contention signal), for
`add`, `observe` and `resolve`; racing `add`/`add` keeps both ids and `add`/`observe` keeps the new
evidence row.

### AC-009: a v1 file without locators loads unchanged
Schema. A pre-change `assumptions.yaml` fixture validates and `gap` has empty `stale_evidence`; a
malformed `locator` is listed in `broken_references` naming `evidence[j].locator` while the record
stays loaded and a dependent objective is not `broken`.

### AC-010: wrapup 5.7 offers add and lists stale assumptions first
S8. In both rendered variants, the assumption answer-gated block contains the literals
`(cited code changed)`, `new — record an assumption` and `hm world assume add <id> --claim`, a
four-option cap, the gap source, and the yes / otherwise-write-nothing lines in order.

### AC-011: the skill lists the add and locator argument forms
S8. The rendered `intent-layer` SKILL.md (both paths) contains the `assume add` argument form and
`--locator` on `observe`, and stays ≤ 120 lines.

### AC-012: surface growth declared and retired
Surface. The wrapup and skill growth is covered by a `BASELINE-DELTA` doc plus `surface_allowance`
during the task; at the terminal phase the baselines are refrozen, and no allowance remains.

### AC-013: add prints a changed line
S1. The `add` CLI prints `changed: assumptions.yaml` (the form `observe` / `resolve` already print) on
success and no `changed:` line on refusal.

### Test files (spec gate)

- `tests/unit/test_world_assume_add.py` — AC-001, AC-002, AC-013
- `tests/unit/test_world_evidence_locator.py` — AC-003 … AC-007, AC-009
- `tests/integration/test_world_assume_concurrency.py` — AC-008
- `tests/unit/test_render_intent_layer_assume_add.py` — AC-010, AC-011
- `tests/structural/test_assumption_entry_invariance.py` — AC-012

## ❓ Open Questions

(none — plan-level choices: whether the lock file keeps the name `.hm-world-outcomes.lock` or
becomes a directory-wide name, and the exact prose wording of the 5.7 option labels)

## 🔍 Refinement Decisions

- Round 0 (RESEARCH): content fingerprint over `@sha` (pre-commit recording plus squash-land
  reachability); `add` refuses and never upserts; no `conflict` via `add`; current-checkout root.
- Round 1: probe checks for external claims → Non-Goal, follow-up task; the latest locator-bearing
  evidence is authoritative (re-confirm = re-stamp); staleness propagates to `needs_revalidation`
  (verified that it gates nothing today); wrapup 5.7 lists stale assumptions first.
- Plan amendment (2026-09-18): AC-013's literal corrected to `changed: assumptions.yaml` — the
  SPEC said "the form the other verbs print" and then named a different form; the verbs print the
  bare file name. `paths_to_mutate` gains `evidence_locator.py` (PLAN ADR-001).
- Plan round 2 (2026-09-18, after plan-validator): the new keys go on `gap` only — `status` stays
  frozen (PLAN-objective-gap-proposal ADR-001); a malformed stored locator keeps the record loaded
  and is reported (never makes a dependent objective broken); 5.7 shows at most two ids + new + no;
  `fresh` is measured over the first `k` non-empty lines at or after `A`; `k` joins the locator.
- Defaulted (not asked):
  - `--locator path:A-B` is CLI syntax and the verb computes the fingerprint, because a pasted
    snippet invites LLM paraphrase;
  - the 40-line span cap (RESEARCH Pitfall 5);
  - whitespace-only normalization, with no AST;
  - an unreadable file reads `missing`;
  - `--locator` requires `--text` on `add`, because evidence without text is invalid today.
