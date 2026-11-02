---
type: spec
task_slug: hm-check-docs-only-reuse
status: approved
created: 2026-11-02
tags: [hm-check, reuse, verdict-record, wrapup-cost]
test_framework: pytest
interview_rounds: 3
summary: hm check --reuse keys only the gate results; DRI-declared inert globs (verified against an in-process read-set) let a docs-only delta or a HEAD move reuse the gate.
---

# SPEC — hm-check-docs-only-reuse

## Intent

`hm check --reuse` reruns the whole gate when anything in the tree or HEAD changed since the
last pass. In workdesk (2026-11-02) one wrapup ran its 33-minute serial pytest 3 times: for a
docs edit, a REVIEW-table fix and a rebase onto a docs-only main. Automatic test selection is
not viable there. 98% of gate time is in subprocess-spawning test files, and scoped fixtures
spawn `git`/`node`/`uv` (`work-docs/RESEARCH-hm-check-docs-only-reuse.md`, Measurement). So
the DRI declares which paths the gate cannot depend on, and `hm check` verifies what it can
observe.

## Outcomes

- On a `--reuse` hit, only the gate results are reused. Approval, AC, review, security and
  CVE are computed fresh, so a REVIEW-table fix reruns the review check in seconds rather
  than the gate.
- With `check.reuse_inert` declared, a delta whose every path is a modified, declared, non-code
  path reuses the gate. That includes a HEAD move (rebase, commit). The receipt names the rule,
  the delta and the globs that matched.
- A declared path that a pytest gate opened in-process during the recorded pass is *voided*:
  the full gate runs, and the line says which path and why.
- With no declaration, behaviour equals 0.65.2 apart from the section split.

## In-Scope Scenarios

- **S1 (normal, docs edit):** given a recorded pass and `reuse_inert: [CHANGELOG.md, work-docs/**]`,
  when CHANGELOG.md is edited and `hm check --slug s --reuse` runs, then no gate command runs,
  exit is 0, and the line carries `reused: true` and `reuse.rule: inert`.
- **S2 (normal, REVIEW fix):** given a recorded pass, when the REVIEW doc's findings change to
  an unresolved row, then the gate is reused, `review` fails and exit is non-zero. The gate
  record survives, so after the row is fixed the next `--reuse` exits 0 without running the gate.
- **S3 (edge, rebase):** given a declaration and a recorded pass, when HEAD moves and the tree
  delta is inert-only (or empty), then the gate is reused. Without a declaration, a HEAD move
  runs the gate.
- **S4 (failure, voided):** given a pytest gate whose test opens `work-docs/data.md` and a
  declaration covering it, when that file is edited, then the full gate runs and the line
  carries `reuse_miss.reason: voided` with the path.
- **S5 (failure, unsafe delta):** a code-suffix path, an added or removed path, an undeclared
  path, a config change, a missing or pre-0.66 record, or a pytest gate with no read-set: each
  runs the full gate.

## Non-Goals

- Automatic test selection (grep or read-set based) or partial pytest reruns. Rejected in
  RESEARCH Approaches A/B.
- Parallelising consumer gates (`-n auto`): the consumer's choice.
- Changing any stage template. Wrapup Step 1 already calls `--reuse` and reads the exit code.
- A harness-owned default inert list. Workdesk reads a `work-docs/RESEARCH-*` file in-process,
  so any default would be wrong somewhere.
- Observing subprocess reads.

## Constraints

| Constraint | Value | Why |
|---|---|---|
| test framework | pytest (+ hypothesis for the property AC) | project standard |
| absent declaration | `check.reuse_inert` absent → `[]` → reuse only on an identical key (today's rule) | absent-case must be explicit |
| never inert | a path that `is_code_or_test` accepts (a `CODE_SUFFIXES` suffix or a `tests`/`test` part), or a runner config (`pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini`, at any depth), is never inert, even when a glob matches | a code edit must always gate; pytest reads its ini before a `-p` plugin's hook exists |
| delta kinds | *modified* = a content sha256 on both sides. A delta path with no digest on one side, or with `absent`/`link:`/`unreadable:` on either side, is added/removed and forces the full gate | presence checks, symlinks and unhashable files are invisible to the read-set |
| glob dialect | own translator: case-sensitive, anchored at the repo root, `*` and `?` never cross `/`, `**` spans any depth (zero or more segments), no negation or dir-only rules | DRI decision, round 3; Python 3.12 lacks `PurePath.full_match` |
| malformed declaration | `hm check` reads the raw config. A `check.reuse_inert` that is not a list of str reads as no declaration, and `--reuse` reports `bad-declaration` | a bare string iterated as characters would make `*` match everything |
| read-set paths | each `open` path is resolved with `os.path.realpath` against the cwd at event time, then kept only if inside the resolved root; integer fds are skipped | relative opens, `chdir` and symlinks must still record |
| read-set processes | every pytest process (controller and each xdist worker) writes its own read-set file and the parent merges them. An xdist run whose worker files are missing counts as no read-set | the voiding check must survive `-n auto` |
| HEAD | may differ from the record only when the declaration is non-empty and the tree delta is inert-only | DRI decision, round 1: declaring is accepting HEAD independence |
| non-pytest gates | reused under the same rule | DRI decision, round 1 |
| read-set | in-repo paths opened in-process (`open` audit event) by every pytest gate, one union set | DRI decision, round 1; attribution is not needed without selection |
| missing read-set | a gate list with a pytest gate but no read-set → no inert reuse | fail-closed |
| record lifetime | written after a fresh gate run when the gate section is ok AND no digest is `unreadable:*` AND HEAD did not move during the run AND the tree did not change during the run. Unlinked when the gate section fails or the tree changed during the run. A non-gate section failure leaves it. Not rewritten on a reuse hit | a review failure must not cost the next gate (S2); keeps 0.65.2's fail-closed write conditions |
| config in key | the parsed harness config stays in the key; changing the declaration misses once | the declaration is itself an input |
| Python only, `mypy --strict`, ruff | — | CLAUDE.md |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | `harness.yaml` gains `check: {reuse_inert: list[str]}` as a `HarnessConfig` field with an `InterviewAnswers` mirror; its globs use the dialect in Constraints | schema/file format/storage layout | users write it, and `/hm:make` must preserve it. A ≤0.65.2 harness-maker (`extra="forbid"`) rejects a harness.yaml carrying `check:`, so a declaration requires ≥0.66 everywhere that file is read |
| IRR-002 | verdict record `hm/check-verdict.json` becomes `{slug, options, head, fingerprint, harness_maker_version, files, read_set, gates, at}`. `fingerprint` hashes the gate list, degraded reason and config, no longer the files. `files` is path → digest, `read_set` is a list or null (`partial` noted by an `unobserved` list), `gates` is the gate section body, `line` is the whole verdict line when it exited 0 (else null). The record means "the gate section passed", not "the verdict passed". `harness_maker_version` stays in the key, so a ≤0.65.2 record (no `files`) is a `legacy-record` miss and a 0.66 record is never honoured by 0.65.2 | schema/file format/storage layout | later versions must parse it; cross-version misreads are prevented by the version key |
| IRR-003 | `--reuse` output. A reused line carries `reused: true`. Under `rule: identical` (same key, HEAD and tree, and a recorded exit-0 `line`) the whole 0.65.2 line is reprinted. Otherwise, including `rule: inert` and an identical key whose recorded verdict did not pass, `reused: true` means *the gate section was reused and every other section ran fresh*. Either way the line carries `reuse: {rule, delta, inert, read_set, unobserved}` with `read_set` ∈ `checked \| partial \| absent` and `unobserved` = the gate commands not observed. A fresh run under `--reuse` carries `reuse_miss: {reason, paths}`. Reasons, by precedence: `no-record`, `legacy-record`, `bad-declaration`, `key`, `code`, `added-removed`, `undeclared`, `head`, `voided`, `no-read-set` | public API/CLI contract | wrapup and scripts read it; changes the meaning of p3's `reused: true` |

## Acceptance Criteria

### AC-001: a non-identical reuse hit reuses only the gate section

On a hit that is not an identical reprint, `approval`, `ac`, `review`, `security` and `cve` are computed fresh, and only `gates`
comes from the record. A non-gate section failure leaves the gate record in place. Golden table
in the machine.yaml (S2).

### AC-002: inert-delta reuse follows the rule table

Over the golden table (S1, S3, S5), whether the gate runs and the `reuse.rule` value
(`identical` or `inert`) match the table exactly.

### AC-003: a reuse never accepts an unsafe delta (property)

For any recorded snapshot, declaration, delta (modify/add/remove/sentinel over random paths,
code, test, runner-config and doc paths), HEAD-moved flag, read-set (list or null) and
has-pytest-gate flag: `reused` implies one of two things. Either the key is identical, HEAD is
the same and the delta is empty. Or the declaration is non-empty, every delta path is
sha→sha modified, matches a declared glob and is not never-inert, no delta path is in the
read-set, and the read-set is non-null whenever a pytest gate exists. `run()` must route its
decision through the function this property tests.

### AC-004: a declared path read in-process voids the declaration

A pytest gate that opens a declared path records it in `read_set`. The open may be absolute,
relative, after a `chdir`, through a symlink, or in an xdist worker. Editing that path runs the
full gate with `reuse_miss: {reason: voided, paths: [...]}`. A gate list with a pytest gate
and a null read-set never reuses on an inert delta (S4, S5).

### AC-005: the line names the rule

A reused line carries `reused: true` and `reuse: {rule, delta, inert, read_set, unobserved}`. An identical hit with a recorded exit-0 line reprints that whole line (0.65.2 behaviour). Every other hit recomputes all sections except `gates`.
`read_set` is `checked` (every gate is pytest and observed), `partial` (some gate commands are
unobserved, listed in `unobserved`) or `absent` (no pytest gate). A fresh run under `--reuse`
carries `reuse_miss: {reason, paths}`, with the first matching reason in IRR-003's precedence.

### AC-006: `check.reuse_inert` is a typed, preserved config key

`HarnessConfig` accepts `check: {reuse_inert: [str, ...]}`. An absent key reads as `[]`. A
non-list or non-str entry is rejected. A load → dump round trip keeps the key, and so does the
`/hm:make` update path (`InterviewAnswers` mirror). Through `hm check` on a raw config, a
malformed value reads as no declaration with miss reason `bad-declaration`.

## Verification

| scenario | mode | test |
|---|---|---|
| S2 | unit (CLI on a temp git repo) | `tests/unit/test_hm_check_inert_reuse.py::test_ac_001_section_split` |
| S1, S3, S5 | unit (CLI on a temp git repo) | `tests/unit/test_hm_check_inert_reuse.py::test_ac_002_rule_table` |
| S5 | unit (property, hypothesis, pure function) | `tests/unit/test_hm_check_inert_reuse.py::test_ac_003_never_unsafe` |
| S4 | unit (real pytest gate in a temp repo) | `tests/unit/test_hm_check_inert_reuse.py::test_ac_004_voided` |
| S1, S4 | unit | `tests/unit/test_hm_check_inert_reuse.py::test_ac_005_receipt` |
| — | unit | `tests/unit/test_hm_check_inert_reuse.py::test_ac_006_config` |
| S1–S3 in workdesk | manual, after release | declare `[CHANGELOG.md, work-docs/PLAN-*.md, work-docs/REVIEW-*.md]`; the next wrapup's docs edit and REVIEW fix reuse; record the wall time of a hit (the fresh `ac` section still runs its AC tests) |

## Open Questions

None.

## Refinement Decisions

- 2026-11-02 round 1 (DRI): intent none. HEAD may move only under a non-empty declaration with
  an inert-only delta. Keep the in-process read-set check. Non-pytest gates reuse under the same
  rule.
- 2026-11-02 round 2 (DRI): the declaration lives in `harness.yaml` `check.reuse_inert`. Oracle
  design approved, and SPEC approved.
- Default: the record is not rewritten on a reuse hit. The next delta is computed against
  the last *fresh* pass, which is cumulative and still correct.
- Default: the read-set is one union set of in-repo paths opened by the pytest gate run.
  Directory listings are not recorded, because adds and removes already force the full gate.
- Default: the gate record keeps `slug` and `options` in its key, as today (record per slug).
- Default: `reuse_miss` is only emitted when `--reuse` was asked.
- 2026-11-02 round 3 (DRI), after the spec-validator's MAJOR_REVISION (4 critical, 6 warning,
  3 suggestion): glob dialect = own minimal translator. All critiques were applied and the
  revision re-approved. The defaults it added: modified = sha→sha only, so sentinels are
  added/removed. The read-set is merged across xdist workers, and missing worker files mean
  no read-set. A malformed declaration is `bad-declaration`. Read-set paths are realpath'd
  against the event-time cwd. `tests/` and runner configs are never inert. 0.65.2's
  unreadable/HEAD-unmoved write conditions stay. Reason precedence is fixed. `read_set` gains
  `partial`/`unobserved`. AC-003 covers a null read-set and requires `run()` to use the
  tested function. The workdesk row records hit wall time. IRR-001/002/003 were rewritten to
  the full shapes, including ≤0.65.2's rejection of `check:` and the new meaning of
  `reused: true`.
- 2026-11-02 execute (DRI): an identical-key hit with a recorded exit-0 line reprints the whole line as in 0.65.2 (no AC-test rerun on the common case; SPEC-hm-cost-p3 AC-002 stays valid). IRR-002 gains `line`, IRR-003 and AC-001/AC-005 say so. A record carrying a non-zero `exit` is treated as no record.
- 2026-11-02 execute (DRI): AC-001 row 4 was unsatisfiable (the approval stamp lives in `specs/`, an undeclared path). Its declaration is now `['work-docs/**', 'specs/**']`, so removing the stamp is an inert delta and approval is recomputed fresh.
- 2026-11-02 execute (agent): the new `check` axis is classified as internal in `tests/structural/test_make_fastpath_contract.py` (`_INTERNAL_AXES`). It is empty by default and never an onboarding question.
