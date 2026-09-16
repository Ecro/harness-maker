---
type: plan
task_slug: playbook-alignment
status: complete
created: 2026-09-16
tags: [harness-maker, plan, python, jinja2, intent-layer, playbook, deliverables, world-state]
spec: "[[SPEC-playbook-alignment]]"
research_doc: "[[RESEARCH-playbook-alignment]]"
interview_rounds: 4
adrs: 11
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "INTENT-<ID>.md becomes the objective record (frontmatter = machine fields, body = Playbook sections); new verb; three P2 fixes"
spec_need_verdict: add
spec_need_target: playbook-alignment
surface_allowance:
  chars: 67
  reason: "wrapup 5.7 names --claim for the supersedes relation on the existing observe line (SPEC S7 / AC-007); one line, no new call site, so no round_trips entry"
  delta_doc: BASELINE-DELTA-playbook-alignment.md
  commands:
    wrapup: 67
    hm-wrapup: 67
---

# PLAN — playbook-alignment

> **Revision 2 (2026-09-16, after the single plan-validator pass).** Every critical and major
> critique changed a decision or a phase; the record is in `## 🔍 Plan Validation`. The
> validator is not re-run (one-pass rule); its surviving findings are carried into execute's
> Phase A.5 and review.

## 🎯 Executive Summary

**TL;DR.** The objective record moves from `.claude/world/objectives/<ID>.yaml` to
`work-docs/INTENT-<ID>.md`. The YAML frontmatter is the record `world.py` already validates and
hashes; the markdown body carries the Playbook's five sections and is carried as opaque bytes that
no writer ever re-renders. A new `hm world objective new <ID>` verb writes the skeleton. `INTENT`
becomes a deliverable prefix. Three P2 defects the last review left (wrapup 5.7 `supersedes`
without `--claim`, `schema_version: "1.0"` validate/load mismatch, a value-less outcome row
crashing `last_value`) are fixed in the same files.

**What / why.** Anthropic's AI-Native SDLC Playbook makes a human-written `intent.md` the first
committed artifact of the chain; harness-maker had the machine half (hash, states, scope) in a
folder no human reads and no prose half at all. One file that is both the deliverable and the
record closes that without a mirror that drifts (RESEARCH Approach A) or a YAML nobody browses
(Approach C).

**Key decisions.** ADR-001 record location · ADR-002 frontmatter-only writers, opaque body ·
ADR-003 id and stem rule (one extraction function, four consumers) · ADR-004 `new` verb,
advisory body · ADR-005 rendered *commands* unchanged except wrapup 5.7 · ADR-006 legacy path
diagnosed · ADR-007 deliverable single source · ADR-008 P2 bundle and the exact allowance block ·
ADR-009 one byte-level frontmatter splitter in a new module · ADR-010 pre-change pin for AC-005 ·
ADR-011 ordered optional keys.

**Impact.** ~300 lines in `world.py`, a new ~80-line `frontmatter.py`, ~15 in `intent.py`,
~10 in `second_brain.py` (delegation), 3 in `worktree.py`, 1 in `.gitignore`, one template line
in `wrapup.md.j2`, skill verb list +1, fixtures moved, ~14 new tests. Rendered `plan`/`review`/
`help` byte-identical to a committed pin.

## 📚 Prior Work

- `[[SPEC-intent-world-model-objective-layer]]` / `[[PLAN-intent-world-model-objective-layer]]`
  (landed 2026-09-16, commit 3edcca62): the record, the hash, the gate, `DELIVERABLE_STATE_PATHS`
  (ADR-012 there), two roots (ADR-006 there), the accepted `surface_allowance` block shape (its
  frontmatter, "validator P-01"). This PLAN supersedes three of that SPEC's Constraints rows.
- `[[REVIEW-intent-world-model-objective-layer-2026-09-16]]` "Open items" — the three P2s bundled
  here (ids `5202e61acb247105`, `0eadd6c9f6e3b3ef`, `889c342883fae2a7`).
- `[wiki:architecture] two-roots-versioned-state-vs-operational-events` — INTENT files are
  versioned → checkout root; `approved_by` and gate events → base root.
- `[fail:design] git-identity-read-at-wrong-root-despite-spec-decision` — carry the two-roots row
  into every new function, not just the table.
- `[wiki:gotcha] one-rendered-command-size-has-four-normative-sites` — the wrapup line moves four
  frozen numbers; declare the allowance after the delta doc, in the accepted shape.
- `[fail:test] auto-fix-reordered-fixture-literals-without-testing-anything` — property ACs here
  exercise the subject's writer over generated bodies **and** disk fixtures, never a literal's order.
- `tests/structural/test_autopilot_gate_render.py` docstring — verify-before-recapture protocol.
- `[[RESEARCH-playbook-alignment]]` — approaches, pitfalls, Playbook citations.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Record location | Scope/Architecture | Where does the objective record live? | A mirror / **B frontmatter is the record** / C YAML prose fields | B | spec round 1 | ADR-001 |
| 2 | Id rule | Contract | Keep `[A-Z0-9-]+` with `INTENT-<ID>.md`? | **keep** / lowercase kebab | keep | spec round 1 | ADR-003 |
| 3 | Authoring | Contract | How is the first file created? | **`objective new` verb** / hand-write + template / both | verb | spec round 1 | ADR-004 |
| 4 | P2 bundle | Scope | Bundle the three review P2s? | **bundle** / two only / none | bundle | spec round 1 | ADR-008 |
| 5 | Link key | Contract | PLAN frontmatter key? | **`objective:` keep** / `intent:` rename | keep | spec round 2 | ADR-005 |
| 6 | Body rule | Contract | Enforce the five headings? | **advisory** / enforced | advisory | spec round 2 | ADR-004 |
| 7 | Migration | Risk | Converter for old YAML? | **none, diagnose** / `migrate` verb | none | spec round 2 | ADR-006 |
| 8 | Oracles | Testing | Oracle table as proposed? | **yes** / end | yes | spec round 2 | — |
| 9 | Step 3.0 | Phasing | Proceed with the brief's defaults? | **proceed** / one decision first ×2 / several | proceed | plan | ADR-002, ADR-007 |
| 10 | Parser | Architecture | Where is frontmatter split and bytes preserved? | **new `frontmatter.py` `split_frontmatter`** / world-local splitter / extend `second_brain` only | new module | validator follow-up | ADR-009 |
| 11 | AC-005 pin | Testing | Where is the pre-change baseline pinned? | **arm×command sha map in BASELINE-DELTA** / base commit SHA + git render | delta doc | validator follow-up | ADR-010 |
| 12 | Remaining 11 critiques | Risk | Revise all / accept some as risk / end | **A revise all** / B / end | A | validator follow-up | ADR-003, 005, 008, 011 + phases |

## 📐 Architecture Decision Records

### ADR-001: `work-docs/INTENT-<ID>.md` frontmatter is the objective record
**Status:** Accepted (2026-09-16, via /hm:spec interview)
**Context:** The Playbook's intent artifact is human-written markdown in the deliverable chain; harness-maker's record was hand-written YAML under `.claude/world/` with no prose and no chain placement.
**Decision:** The objective record is the YAML frontmatter of `work-docs/INTENT-<ID>.md`; the body is prose. `.claude/world/objectives/` is retired.
**Consequences:**
- ✅ One source of truth; the deliverable and the record are the same bytes; `hm world` verbs and the gate keep reading the same fields.
- ⚠️ `world.py` gains a frontmatter loader/writer; the previous SPEC's storage rows are superseded.
**Rejected alternatives:**
- A — YAML record + INTENT.md mirror with an import verb: a second source of truth of the exact class the last review rejected twice in this module.
- C — Playbook prose as YAML fields: stays in a folder no human reads; the withdrawal criterion would likely fire.
**Source:** Interview #1

### ADR-002: Writers rewrite the frontmatter only; the body is opaque bytes, refused when unknown
**Status:** Accepted (2026-09-16, via /hm:plan; revised after validator)
**Context:** Five writers mutate the record; git history is the Playbook's governance record. A writer that re-renders the prose, reorders keys, or writes an empty body on a miss destroys either the diff or the human's text.
**Decision:**
- The loader returns the body as **bytes** sliced from the original file after the closing fence (ADR-009); `World.bodies: dict[str, bytes]`.
- One `_dump_intent(path, record, body: bytes)`: `yaml.safe_dump(record_in_declared_order, sort_keys=False, allow_unicode=True)` between `---\n` fences, then the body bytes appended verbatim, written through `atomic_write` in binary mode (`newline` untouched). Every writer (`approve`, `transition`, `activate`, `close`, `edit_objective`, `new`) goes through it.
- Declared order = `_OBJECTIVE_REQUIRED` then `_OBJECTIVE_OPTIONAL` (ADR-011); a key outside both raises `WorldError` rather than being dropped.
- A writer whose id has no `bodies` entry raises `WorldError("body", …)`; it never writes an empty body.
**Consequences:**
- ✅ AC-002 holds by construction; a repeated no-op write is byte-identical; a hand-formatted frontmatter is normalised once, on the first write, and never again.
- ⚠️ `atomic_write` gains (or `world.py` uses) a bytes-mode path; verify `io_utils.atomic_write` signature in Phase 1 and add `atomic_write_bytes` if it only takes `str`.
**Rejected alternatives:**
- Re-parse and re-render the whole document — cannot preserve CRLF/trailing whitespace.
- `bodies.get(id, "")` on the write path — silent truncation of the operator's prose.
**Source:** Interview #9, #12

### ADR-003: Ids stay `[A-Z0-9-]+`; one `_id_from_stem` rule, four consumers
**Status:** Accepted (2026-09-16, via /hm:spec interview; revised after validator)
**Context:** The file stem is `INTENT-OBJ-7` while the id, the PLAN link, the gate lookup and every `hm world` argument use `OBJ-7`. Today `_validate_objective_raw` compares `id` to `path.stem`, `load_world` keys by `p.stem`, `validate_objective_record` synthesises the path, `_load_objective` looks the id up.
**Decision:** `_OBJECTIVE_ID_RE` unchanged. `objective_doc_path(root, id) = root/work-docs/INTENT-<id>.md` (the existing `intent_path(root)` → `.claude/intent.yaml` is untouched). `_id_from_stem(path) -> str | None` strips the `INTENT-` prefix and returns `None` for any other stem. All four consumers use it: `_validate_objective_raw` compares `id` to `_id_from_stem(path)`; `load_world` keys `objectives`/`broken` by it and records a stem without the prefix as `errors` (never as a record); `validate_objective_record` synthesises `objective_doc_path`; `_load_objective` is unchanged in shape. `world_fixture.objective_path` becomes `objective_doc_path`.
**Consequences:**
- ✅ Zero change to the gate, the templates, the golden and the boundary baseline; AC-001 gains three independent cases (good file loads under the bare id; `id` field disagreeing with the stem → broken; stem without prefix → `errors`, not loaded).
- ⚠️ INTENT stems look different from lowercase task-slug deliverables; documented.
**Rejected alternatives:**
- Lowercase kebab ids — moves four previous-task artifacts for cosmetics.
- `intent_path(root, id)` — collides with the live `.claude/intent.yaml` helper (world.py:126, called at 482 and 746).
**Source:** Interview #2, #12

### ADR-004: `hm world objective new` writes the skeleton; the five body headings are advisory
**Status:** Accepted (2026-09-16, via /hm:spec interview)
**Context:** Hand-written frontmatter is the class of error that produces `broken` records; the Playbook expects prose to be corrected freely.
**Decision:** `new <ID> --title --hypothesis --scope (repeatable) --outcome [--non-scope (repeatable)]` writes a `proposed`, unapproved record with `created_at` UTC Z, `schema_version: 1`, and a body carrying `## Problem`, `## Proposed outcome`, `## Affected users and systems`, `## Constraints`, `## Open questions`. It refuses an existing file and an id outside the rule before touching the filesystem, and refuses an `--outcome` not in `intent.yaml`. The validator never inspects the body. The `intent-layer` skill's verb list gains one line.
**Consequences:**
- ✅ AC-006; the operator's first file always loads.
- ⚠️ One more name in `command_registry`'s `world` subcommand list; the skill render moves (ADR-005 names it).
**Rejected alternatives:**
- Hand-write with a documented template — changes plan Step 0.5 wording (rendered command) and keeps the typo class.
- Enforced headings — a hand-edited file becomes `broken` for prose reasons.
**Source:** Interview #3, #6

### ADR-005: Rendered *commands* are unchanged except the wrapup 5.7 line; the skill line is the one allowed asset change
**Status:** Accepted (2026-09-16, via /hm:spec interview; narrowed after validator)
**Context:** `_plan_link` reads `objective:`; the command ratchet covers `.claude/commands/hm/*.md`, not skills (previous PLAN ADR-010). The skill body must gain the `new` verb line (ADR-004).
**Decision:** No link-key rename. Of the rendered **commands**, only `wrapup` (and `hm-wrapup` on the Codex arm) moves, by the 5.7 line (ADR-008); `plan`, `review`, `help` are pinned byte-for-byte by AC-005 against the ADR-010 pin. The `intent-layer` skill body changes by exactly one verb line; `tests/unit/test_render_intent_layer.py` (AC-019 of the previous SPEC: `VERB_ARGUMENT_FORMS`) is updated to include the new form, and `tests/unit/test_synthesize_codex.py` / `test_codex_phase7.py` are unaffected — they count skills and check descriptions, not verb bodies (verified in Phase 2's first step; if either asserts body bytes, re-baseline it with an attribution note).
**Consequences:**
- ✅ AC-005 is a pure pin comparison; the previous task's AC-012 baseline stays valid.
- ⚠️ Playbook vocabulary lives only in the filename.
**Rejected alternatives:**
- `intent: INTENT-<ID>` — re-measurement of four artifacts for no behavioural gain.
**Source:** Interview #5, #12

### ADR-006: A file at the legacy path is diagnosed, never loaded; no converter
**Status:** Accepted (2026-09-16, via /hm:spec interview)
**Context:** The old layout shipped hours earlier; no real record exists outside fixtures.
**Decision:** `load_world` scans `.claude/world/objectives/*.yaml`; each hit adds one `world.errors` entry naming the file and `work-docs/INTENT-<stem>.md`, and is not loaded. `DELIVERABLE_STATE_PATHS` drops the directory.
**Consequences:**
- ✅ A stale file cannot silently become a second record; the message says where to move it.
- ⚠️ No automation for a migration nobody needs yet.
**Rejected alternatives:**
- `objective migrate` verb — code for zero users.
**Source:** Interview #7

### ADR-007: `INTENT` joins `DELIVERABLE_PREFIXES`; the previous SPEC's storage rows are superseded
**Status:** Accepted (2026-09-16, via /hm:plan brief default)
**Context:** Three derived sites (gitignore negation, `_DELIVERABLE_RE`, `derive_deliverable_globs`) and a structural test hang off the one tuple.
**Decision:** Add `INTENT` to the tuple and mirror `!work-docs/INTENT-*.md` in `.gitignore`; remove `.claude/world/objectives/` from `DELIVERABLE_STATE_PATHS`. Append a "Superseded by SPEC-playbook-alignment (2026-09-16)" note under the three rows of the previous SPEC rather than rewriting them.
**Consequences:**
- ✅ AC-004 is the existing structural contract extended by one prefix.
- ⚠️ The previous SPEC's AC-017 judgment subject (the fixtures) moves; that SPEC's next wrapup re-judges it — out of this task's gates.
**Rejected alternatives:**
- A separate `intent/` folder — its own ignore, sweep and manifest rows.
**Source:** Interview #9

### ADR-008: Bundle the three P2 fixes; declare the wrapup allowance in the accepted block shape, after the delta doc
**Status:** Accepted (2026-09-16, via /hm:spec interview; block shape fixed after validator)
**Context:** The three defects live in `world.py`, `intent.py` and `wrapup.md.j2`. `surface_allowance._parse` requires `chars` (positive int), `reason`, `delta_doc`, and integer maps for `commands` / `round_trips`; the previous PLAN records the accepted block verbatim.
**Decision:** Phase 4 fixes all three. The wrapup 5.7 change appends ` (add \`--claim "<new claim>"\` for \`supersedes\`)` to the existing observe line — same line, same `!`/`Bash(` call site, so `round_trips` is omitted (no new call) and `test_render_wrapup_delegation.py`'s line-count pin does not move. Then, in this order: measure → write `BASELINE-DELTA-playbook-alignment.md` → add to this PLAN's frontmatter exactly:
```yaml
surface_allowance:
  chars: <measured aggregate delta, positive int>
  reason: "wrapup 5.7 names --claim for the supersedes relation (SPEC S7 / AC-007); one line, no new call"
  delta_doc: BASELINE-DELTA-playbook-alignment.md
  commands:
    wrapup: <measured int>
    hm-wrapup: <measured int>
```
then regenerate snapshots in the worktree and re-capture the gate golden with a docstring entry (verify-before-recapture per ADR-010).
**Consequences:**
- ✅ The review's open items shrink by three; the allowance parses on the first try.
- ⚠️ Golden re-capture number four in two days; recorded in the golden's docstring list.
**Rejected alternatives:**
- Separate diet task — three round trips for thirty lines.
- Free-form `≤200` block — `_parse` rejects it (validator critical #4).
**Source:** Interview #4, #12

### ADR-009: One byte-level frontmatter splitter in a new `harness_maker/frontmatter.py`
**Status:** Accepted (2026-09-16, via /hm:plan validator follow-up)
**Context:** `second_brain.parse_frontmatter` opens on the literal `---\n`, closes on `\n---\n`, and returns `({}, text)` for missing, unterminated, invalid-YAML and non-mapping cases alike — none of which S1 can distinguish; `world.py` reads with `read_text`, which translates CRLF. Four parsers already exist (`second_brain`, `reconcile`, `provenance`, `autopilot_caps._FRONTMATTER_RE`).
**Decision:** New module `src/harness_maker/frontmatter.py` with
`split_frontmatter(data: bytes) -> Split(status: Literal["ok","missing","unterminated","invalid_yaml","non_mapping"], mapping: dict | None, body: bytes, error: str | None)`.
It tolerates a UTF-8 BOM and `\r?\n` fences, decodes the frontmatter text for YAML only, and returns `body` as the **original bytes** after the closing fence (byte-offset slice, never re-encoded). `second_brain.parse_frontmatter` becomes a thin wrapper preserving its `(dict, str)` contract for existing callers; `reconcile`, `provenance` and `autopilot_caps` are **not** migrated in this task (out of scope; noted as follow-up). `world._read_intent(path)` maps `missing`/`unterminated`/`invalid_yaml`/`non_mapping` to the S1 `file` error and an empty mapping to the ordinary required-key errors.
**Consequences:**
- ✅ S1's three cases and S2's CRLF case are decidable; the module is the convergence point the other three parsers can adopt later.
- ⚠️ A fifth implementation exists until the others migrate; a structural test asserts `world` imports only `frontmatter`, and `second_brain` delegates.
**Rejected alternatives:**
- World-local splitter — the fifth parser with no path to convergence.
- Extend `second_brain.parse_frontmatter` in place — `world` would import the vault module for a string utility.
**Source:** Interview #10

### ADR-010: AC-005 compares against a pre-change pin committed in the delta doc
**Status:** Accepted (2026-09-16, via /hm:plan validator follow-up)
**Context:** Phase 4 re-captures `autopilot_gate_golden.json`; a test that reads the re-captured golden cannot tell "wrapup alone moved" from "wrapup plus three others moved" — the regression class the golden's docstring records three times.
**Decision:** Phase 0 copies the current golden's per-arm `{command: sha256}` map for `plan`, `review`, `help` (all four arms) into a fenced JSON block in `work-docs/BASELINE-DELTA-playbook-alignment.md`, plus the 77-cell boundary baseline's sha256. `tests/structural/test_playbook_alignment_invariance.py` (AC-005) parses that block and asserts the live render of those three commands equals it per arm, and that the boundary fixture file's sha256 equals the pinned value. Phase 4 asserts, before re-capture, that the moved set against the *current* golden is exactly `{wrapup}` per arm, and writes that result into the delta doc and the golden docstring.
**Consequences:**
- ✅ AC-005 is discriminating after the re-capture; the pin is a committed deliverable.
- ⚠️ The pin goes stale at the next release's version bump (every command moves); the test compares command bodies with the `harness_maker_version:` frontmatter line normalised out, the same normalisation the gate test uses for `content_hash`.
**Rejected alternatives:**
- Base commit SHA + `git show` render — the test would depend on git history.
**Source:** Interview #11

### ADR-011: `_OBJECTIVE_OPTIONAL` becomes an ordered tuple; the set derives from it
**Status:** Accepted (2026-09-16, via /hm:plan validator follow-up)
**Context:** ADR-002 needs a declared key order; the module has `_OBJECTIVE_OPTIONAL: frozenset`.
**Decision:** `_OBJECTIVE_OPTIONAL: tuple[str, ...] = ("non_scope", "rejected", "depends_on", "approval", "revisit_when", "observed", "note", "closed_at")`; `_OBJECTIVE_KEYS = frozenset(_OBJECTIVE_REQUIRED) | frozenset(_OBJECTIVE_OPTIONAL)`. A Phase 1 test asserts the dump covers `_OBJECTIVE_KEYS` exactly and raises on an unknown key.
**Consequences:**
- ✅ One source for both membership and order.
- ⚠️ None.
**Rejected alternatives:**
- A second `_OBJECTIVE_OPTIONAL_ORDER` constant — the two-sources shape `DELIVERABLE_PREFIXES`'s comment exists to prevent.
**Source:** Interview #12

## 🏗️ Technical Design

**Current state.** `world.py`: `objectives_dir` / `objective_path` → `.claude/world/objectives/<ID>.yaml`; `intent_path(root)` → `.claude/intent.yaml` (keep); `load_world` globs the dir, validates via `_validate_objective_raw` (compares `id` to `path.stem`), stores raw mappings keyed by `p.stem`; writers `approve` (~823), `transition` (~855), `edit_objective` (~899), `activate`/`close` call `_dump_yaml(objective_path(...), rec)`; `_read_yaml` uses `read_text`. `worktree.DELIVERABLE_STATE_PATHS` lists the dir; `_DELIVERABLE_RE` derives from `DELIVERABLE_PREFIXES`. `intent.schema_version_error` parses a string major; `load_intent` does `int(raw["schema_version"])`. `load_world` keeps every `values` row whose `outcome_id` exists. `wrapup.md.j2` 5.7 observe line has no `--claim`. `pyproject.toml:69` pins `hypothesis>=6.100`; existing property tests register a `ci` profile per module (`tests/unit/test_stage_span_end_fields.py`).

**Affected components.** New `src/harness_maker/frontmatter.py`; `world.py`; `intent.py`; `second_brain.py` (delegation only); `worktree.py` (two tuples); `command_registry.py` (`world` names +`new`); `templates/skills/intent-layer/SKILL.md.j2` (+1 verb line); `templates/stages/wrapup.md.j2` (5.7 line); `.gitignore` (+1 negation); `tests/unit/world_fixture.py`; `tests/fixtures/objective_scope_drift/*/` (rename); `specs/SPEC-intent-world-model-objective-layer.md` (supersede notes); `tests/unit/test_render_intent_layer.py` (verb forms); snapshots + gate golden (re-capture, attributed); `work-docs/BASELINE-DELTA-playbook-alignment.md` (new, pin + delta).

**Dependencies.** `yaml`, `hypothesis` (pinned), `io_utils.atomic_write` (bytes mode — verify in Phase 1).

**Architecture / data flow.**
```
new ─▶ _dump_intent(objective_doc_path(root,id), skeleton_record, FIVE_HEADINGS_BODY)
load_world ─▶ for work-docs/INTENT-*.md:
                 id = _id_from_stem(p)  (None → errors, skip)
                 split = frontmatter.split_frontmatter(p.read_bytes())
                 status != ok → broken[id] = [file error]        (S1 case 3)
                 ok → errs = _validate_objective_raw(p, split.mapping, …)   (empty mapping → required-key errors)
                      errs → broken[id] ; else objectives[id] = mapping, bodies[id] = split.body
             for .claude/world/objectives/*.yaml → errors += legacy(path, INTENT target)   (S10)
writer ─▶ _load_objective → mutate mapping → body = bodies[id] (KeyError → WorldError("body")) → _dump_intent
derive / approval_hash ─▶ unchanged (mapping only)
```

**Design decisions.** ADR-001…011 above.

**API changes.** New CLI verb `hm world objective new`. `objective_path` → `objective_doc_path` (module-private callers plus `world_fixture`). `World` gains `bodies: dict[str, bytes]`. New public module `harness_maker.frontmatter`. No change to existing `hm world` argument forms or the hash payload.

## 📝 Implementation Plan

### Phase 0 — Pin the pre-change goldens
- `depends_on: []` · `parallel_group: serial-0` · `merge_hazards: none`
- Scope in: confirm `tests/structural/test_autopilot_gate_render.py` and `tests/unit/test_autopilot_caps_objective_gate.py` pass on the untouched branch; write `work-docs/BASELINE-DELTA-playbook-alignment.md` with (a) a fenced JSON block `{"arms": {<arm>: {"plan": sha, "review": sha, "help": sha}}, "boundary_baseline_sha256": sha}` copied from the current golden and the 77-cell fixture (ADR-010), (b) the current `wrapup`/`hm-wrapup` chars and round-trips from `surface_baseline.json`, (c) the measurement procedure (`_gen_autopilot_caps_baseline.py`-style: render, sha256, per arm). Scope out: any source change.
- Exit: `uv run pytest -q tests/structural/test_autopilot_gate_render.py tests/unit/test_autopilot_caps_objective_gate.py` green; `uv run python -c "import json,hashlib;…"` recomputes the pinned map from the golden and matches the delta doc block.
- Risk: low · Rollback: n/a (one new document)

### Phase 1 — `frontmatter.py`, loader and writers move to INTENT-<ID>.md
- `depends_on: [0]` · `parallel_group: serial-1` · `merge_hazards: src/harness_maker/world.py, src/harness_maker/second_brain.py, tests/unit/world_fixture.py`
- Scope in: new `frontmatter.py` (`split_frontmatter`, ADR-009) + `second_brain.parse_frontmatter` delegation; `world.py` — `objective_doc_path`, `_id_from_stem`, `_read_intent`, `_dump_intent` (bytes; `atomic_write` bytes path verified or `atomic_write_bytes` added in `io_utils`), `World.bodies`, `_OBJECTIVE_OPTIONAL` tuple (ADR-011), `load_world` over `INTENT-*.md` + legacy scan (ADR-006), every writer through `_dump_intent` with the missing-body raise (ADR-002), the four `_id_from_stem` consumers (ADR-003); `world_fixture.build_root` writes INTENT files with a fixed body, `objective_path` → `objective_doc_path`; move `tests/fixtures/objective_scope_drift/*/OBJ-7.yaml` → `INTENT-OBJ-7.md` (frontmatter + short body); add the test-file table to `SPEC-playbook-alignment.md` before the first test write (spec_gate hook); tests: AC-001 (three independent cases + differential), AC-002 (Hypothesis `ci` profile registered per module as in `test_stage_span_end_fields.py`, over generated bodies **and** a CRLF+BOM fixture read from disk through every writer, comparing `read_bytes()`), AC-003 (Hypothesis), AC-010, the ADR-011 key-coverage test, the ADR-002 missing-body test, `test_frontmatter_split.py` (five statuses, CRLF, BOM, byte-exact body). Scope out: the verb, deliverable tuples, templates, `tests/integration/test_intent_layer_lifecycle.py` (Phase 5).
- Exit: `uv run pytest -q tests/unit/test_frontmatter_split.py tests/unit/test_world_*.py tests/unit/test_autopilot_caps_objective_gate.py tests/unit/test_second_brain*.py` green; `uv run mypy --strict src/harness_maker/world.py src/harness_maker/frontmatter.py src/harness_maker/second_brain.py` clean; `uv run python -c "import harness_maker.world, harness_maker.second_brain"` (no cycle); a structural assertion that `world.py` does not import `second_brain`.
- Risk: medium (every world test's fixture moves) · Rollback: `git checkout -- src/harness_maker/world.py src/harness_maker/second_brain.py tests/unit/world_fixture.py tests/fixtures/objective_scope_drift && git rm -q src/harness_maker/frontmatter.py tests/unit/test_frontmatter_split.py`

### Phase 2 — `objective new` verb, skill line, registry
- `depends_on: [1]` · `parallel_group: serial-2` · `merge_hazards: src/harness_maker/world.py (CLI section), src/harness_maker/command_registry.py, templates/skills/intent-layer/SKILL.md.j2, tests/unit/test_render_intent_layer.py`
- Scope in: first step — `rg -n "intent-layer" tests/unit/test_synthesize_codex.py tests/unit/test_codex_phase7.py` to confirm neither asserts skill body bytes (record the result in the phase note; if one does, re-baseline it with attribution); `new` subparser + `new()` writer (ADR-004); `command_registry` `world` names +`new`; SKILL.md.j2 verb list +1 line (description unchanged, ≤200 chars); `test_render_intent_layer.py` `VERB_ARGUMENT_FORMS` += the `new` form; test for AC-006 (skeleton loads unbroken; duplicate id refused with bytes unchanged; bad id refused; unknown outcome refused). Scope out: help pages.
- Exit: `uv run pytest -q tests/unit/test_world_objectives.py tests/unit/test_render_intent_layer.py tests/unit/test_synthesize_codex.py tests/unit/test_codex_phase7.py tests/structural/test_cli_surfaces_are_driven.py` green.
- Risk: low · Rollback: `git checkout -- src/harness_maker/command_registry.py src/harness_maker/templates/skills/intent-layer/SKILL.md.j2 tests/unit/test_render_intent_layer.py` and drop the `new` block from `world.py` (Phase 1 tree)

### Phase 3 — Deliverable single source
- `depends_on: [1]` · `parallel_group: serial-3` · `merge_hazards: src/harness_maker/worktree.py, .gitignore, tests/structural/test_deliverable_single_source.py`
- Scope in: `DELIVERABLE_PREFIXES += "INTENT"`, `DELIVERABLE_STATE_PATHS -= objectives/`, `.gitignore` `!work-docs/INTENT-*.md` in the negation block, extend `test_deliverable_single_source.py` and the `derive_deliverable_globs` test for AC-004; supersede notes under the three rows of `specs/SPEC-intent-world-model-objective-layer.md` (ADR-007). Scope out: `_HARNESS_CHURN_PREFIXES`.
- Exit: `uv run pytest -q tests/structural/test_deliverable_single_source.py tests/unit/test_wrapup_land*.py tests/unit/test_worktree_*deliverable*.py` green; `git check-ignore -v --no-index work-docs/INTENT-OBJ-7.md` prints nothing (the path need not exist).
- Risk: low · Rollback: `git checkout -- src/harness_maker/worktree.py .gitignore tests/structural/test_deliverable_single_source.py specs/SPEC-intent-world-model-objective-layer.md`

### Phase 4 — P2 bundle and the wrapup line
- `depends_on: [1]` · `parallel_group: serial-4` · `merge_hazards: src/harness_maker/templates/stages/wrapup.md.j2, tests/snapshot/*.expected.yaml, tests/structural/autopilot_gate_golden.json, this PLAN's frontmatter, work-docs/BASELINE-DELTA-playbook-alignment.md`
- Scope in, in this order: (1) `intent.py` — one `_major_of(raw) -> int | None` used by both `schema_version_error` and `load_intent` (AC-008); (2) `load_world` — build `values` only from rows `validate_outcomes` accepted, keep the error entries (AC-009); (3) `wrapup.md.j2` 5.7 — append the `--claim` clause to the observe line, same line (AC-007 render test); (4) verify-before-recapture: compute the moved set per arm against the **current** golden, assert it is exactly `{wrapup}`, record in the delta doc and the golden docstring; (5) measure `wrapup`/`hm-wrapup` chars, fill `BASELINE-DELTA-playbook-alignment.md`, then add the ADR-008 `surface_allowance` block to this PLAN's frontmatter with the measured ints; (6) `regenerate.py` snapshots in the worktree; re-capture the gate golden. Scope out: `world.observe` (unchanged).
- Exit: `uv run pytest -q tests/unit/test_intent_*.py tests/unit/test_world_outcomes.py tests/unit/test_world_status_and_revisit.py tests/unit/test_render_intent_layer.py tests/snapshot tests/structural/test_autopilot_gate_render.py tests/structural/test_surface_baseline.py tests/structural/test_roundtrip_budget.py tests/unit/test_render_wrapup_delegation.py tests/structural/test_step_sensitivity_registry.py` green.
- Risk: medium (four frozen numbers) · Rollback, in order: restore the Phase-0 state of the golden (`git checkout -- tests/structural/autopilot_gate_golden.json tests/structural/test_autopilot_gate_render.py`), `git checkout -- tests/snapshot/`, delete the `surface_allowance` block from this PLAN's frontmatter, `git checkout -- src/harness_maker/templates/stages/wrapup.md.j2 src/harness_maker/intent.py`, revert step (2) in `world.py`

### Phase 5 — Invariance, lifecycle and documentation
- `depends_on: [2, 3, 4]` · `parallel_group: serial-5` · `merge_hazards: none`
- Scope in: `tests/structural/test_playbook_alignment_invariance.py` (AC-005 per ADR-010: live `plan`/`review`/`help` per arm equal the pinned map with the version line normalised; boundary fixture sha256 equals the pin); `tests/integration/test_intent_layer_lifecycle.py` rewritten to author via `objective new`, approve, activate, run wrapup's staging manifest and `task-land`, and find `work-docs/INTENT-<ID>.md` on the landed base; `spec_machine mark-tested` for every AC; CHANGELOG `[Unreleased]` entry; CLAUDE.md: one sentence under the intent-layer mention if one exists (else none). Scope out: TECH_SPEC; migrating the other three frontmatter parsers (follow-up).
- Exit: `uv run pytest -q` green; `uv run ruff check src tests` / `uv run ruff format --check src tests` / `uv run mypy --strict src tests` clean; `hm spec_machine check --all` ok; `hm spec_machine find-unbound` exit 0.
- Risk: low · Rollback: `git checkout -- tests/integration/test_intent_layer_lifecycle.py CHANGELOG.md CLAUDE.md && git rm -q tests/structural/test_playbook_alignment_invariance.py`

### Phase status (execute, 2026-09-16)

| Phase | Status | Notes |
|---|---|---|
| 0 | DONE | pin (arms × plan/review/help + boundary sha + `harness_maker_version`) in the delta doc |
| 1 | DONE | A.5 2 rounds (round 1: `reopen` writer + `target` case missing); `frontmatter.py`, `_id_from_stem`, `_dump_intent`/`_write_record`, `World.bodies`, fixtures → INTENT; `validate_objective` reads INTENT too (found by AC-016's existing test) |
| 2 | DONE | A.5 2 rounds (round 1: refusal tests asserted stderr; `main()` emits via stdout); `new_objective` + `new` subparser + registry + skill line; `test_synthesize_codex`/`test_codex_phase7` count skills only — no re-baseline needed |
| 3 | DONE | A.5 1 round; `INTENT` unkeyed in `derive_deliverable_globs` (INTENT is objective-id-keyed); supersede notes on 3 rows of the previous SPEC |
| 4 | DONE | A.5 2 rounds (round 1: `--claim` block-wide check; `GOOD` row lacked `definition_hash`); see D.5 below; **crossing**: both baselines re-frozen at main (main was already red — previous task's allowance expired), then this task's +67 declared |
| 5 | DONE | AC-005 pin test, lifecycle via `objective new`, bindings, CHANGELOG |

#### Phase 4 — the full suite's four extra gates (found at Phase D, fixed in place)

`test_baseline_delta_attribution` (every moved key of the re-frozen baseline needs a named
row, the ADR-010 / `ratchet-rebaselined-by-its-own-subject` framing and the aggregate's
direction) → delta doc §2.1; `test_command_size_budget[wrapup]` (`_ATOMIC_RATCHET["wrapup"]`
42452 → 44654, re-based to the landed figure with an attribution comment); 
`test_instruction_preservation` (the pre-`--claim` observe line leaves the instruction baseline
→ `_ALLOWED_REMOVALS["playbook-alignment"]`, both wrapup arms);
`test_new_gates_file_a_mutation_receipt` (receipt for the AC-005 gate: deleting
`plan.md.j2:91` — the Step 0.5 heading — turns it red).

#### T1 mutation gate (Phase D)

`hm spec_mutation gate --tier 1` again checked ZERO mutants (mutmut 2.5.1, same broken run the
previous task recorded) and warned that a mutated source might be left on disk; the world /
intent / frontmatter suites were re-run afterwards and passed, so the sources are clean. Known
gap carried forward; the property ACs (AC-002/003, Hypothesis over generated bodies and disk
fixtures) and the differential AC-001 are the static substitute.

#### Phase 4 — D.5 newly-reachable windows

1. `intent.py` `_major_of`: window = string `schema_version` with a dotted minor (`"1.0"`) reaching `load_intent`; test `test_ac_008_schema_version_string_loads_when_it_validates[1.0-True]`; absent case (key missing) still refused by `schema_version_error` (`[2.0-False]` and the existing AC-016 tests pin the refusals).
2. `load_world` values filter: window = a `values` row with a validator error at index *i* while sibling rows are valid; test `test_ac_009_malformed_value_row_is_reported_not_raised` (len == 1 rejects whole-list drop); absent case (no errors) unchanged — `test_ac_018_*` latest-value tests still pass.
3. wrapup 5.7 line: window = the `supersedes` answer path in the rendered command; test `test_ac_007_wrapup_supersedes_carries_claim[claude|codex]` on the call line itself; absent case (`confirms`/`contradicts`) unchanged — the clause is bracketed as conditional.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/autopilot_caps.py` — the gate reads `objective:` and `load_world`; no edit (ADR-005)
- `src/harness_maker/templates/stages/plan.md.j2` — Step 0.5 wording is pinned by ADR-010
- `src/harness_maker/templates/stages/review.md.j2` — Step 3.3 wording is pinned by ADR-010
- `src/harness_maker/templates/commands/hm/help.en.md.j2`
- `src/harness_maker/templates/commands/hm/help.ko.md.j2`
- `tests/fixtures/autopilot_caps_baseline.json` — pre-change 77-cell baseline; AC-005 pins its sha256
- `tests/structural/surface_baseline.json` — frozen; the wrapup delta is declared via allowance, never by regenerating
- `src/harness_maker/reconcile.py` — its frontmatter parser is not migrated in this task
- `src/harness_maker/provenance.py` — same
- Advisory: the approval hash payload `{hypothesis, non_scope, outcome_id, scope, target}` and `canonical_json` are unchanged
- Advisory: `hm world` argument forms for every existing verb are unchanged; `new` is additive
- Advisory: `second_brain.parse_frontmatter`'s `(dict, str)` return contract is unchanged for its existing callers

## 🧪 Testing Strategy

- **Unit (pytest):** `test_frontmatter_split.py` (five statuses, CRLF, BOM, byte-exact body); AC-001 (three independent cases + the differential error-list equality); AC-006; AC-008; AC-009; AC-010; ADR-011 key coverage; ADR-002 missing-body raise.
- **Property (Hypothesis, `ci` profile registered in each module — `derandomize=True`, `database=None`, as `tests/unit/test_stage_span_end_fields.py` does):** AC-002 body preservation across writers over generated bodies, plus the disk CRLF+BOM fixture through every writer compared by `read_bytes()`; AC-003 hash scope across body edits and hashed-field edits.
- **Structural:** AC-004 single source; AC-005 pin comparison (ADR-010); `world` does not import `second_brain`.
- **Render:** AC-007 wrapup 5.7 block (`--claim` present for `supersedes`, two answer-gated markers, no-branch, observe verb form).
- **Integration (Phase 5 only):** lifecycle via `objective new` → approve → activate → wrapup manifest → `task-land` → INTENT file on base.
- **Manual:** none.
- **spec_gate hook:** every new test file is named in `SPEC-playbook-alignment.md`'s test-file table before it is written (Phase 1 first step).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A hand-formatted frontmatter is normalised into a noisy first diff | high | low | ADR-002/011 fixed order; `new` writes the canonical form so the common path has no diff |
| `atomic_write` has no bytes mode | medium | low | Phase 1 first step checks `io_utils.atomic_write`; add `atomic_write_bytes` beside it (same temp+replace shape) |
| Four frozen surface numbers move on the wrapup line | high | medium | ADR-008 order and exact block; verify-before-recapture (ADR-010) |
| Previous SPEC's AC-017 judgment goes stale when fixtures move | certain | low | ADR-007 note; not a gate for this slug |
| `second_brain` delegation changes a vault caller's behaviour on CRLF notes | low | low | wrapper decodes body to `str` exactly as before for LF files; `test_second_brain*.py` in Phase 1 exit |
| The pinned map in the delta doc is edited by hand | low | medium | Phase 0 exit recomputes it from the golden; AC-005 fails loudly on mismatch |
| `worktree` single-source test fails until `.gitignore` mirrored | certain | low | Phase 3 does both in one edit |

## ✅ Success Criteria

- [x] AC-001 INTENT frontmatter loads under the on-disk rules (`test_ac_001_intent_frontmatter_loads_under_the_disk_rules`)
- [x] AC-002 every writer preserves the body bytes (`test_ac_002_every_writer_preserves_the_body_bytes`)
- [x] AC-003 prose edits keep approval valid; hashed edits break it (`test_ac_003_prose_edits_keep_approval_hashed_edits_break_it`)
- [x] AC-004 INTENT deliverable single source; objectives dir no longer a state path (`test_ac_004_intent_is_a_deliverable_and_objectives_dir_is_not_a_state_path`)
- [x] AC-005 plan/review/help bytes and boundary baseline equal the Phase-0 pin (`test_ac_005_plan_review_help_bytes_and_boundary_baseline_unchanged`)
- [x] AC-006 `objective new` writes a loadable skeleton (`test_ac_006_objective_new_writes_a_loadable_skeleton`)
- [x] AC-007 wrapup supersedes carries claim (`test_ac_007_wrapup_supersedes_carries_claim`)
- [x] AC-008 schema_version string loads when it validates (`test_ac_008_schema_version_string_loads_when_it_validates`)
- [x] AC-009 malformed value row reported not raised (`test_ac_009_malformed_value_row_is_reported_not_raised`)
- [x] AC-010 legacy path diagnosed (`test_ac_010_legacy_objective_path_is_diagnosed`)
- [x] Full suite, ruff, format, mypy strict clean; `spec_machine check --all` ok; every AC bound

## 🔍 Plan Validation

**Pass 1 (single pass by rule — no re-run): MAJOR_REVISION** — 4 critical, 6 major, 4 minor.
Codex second opinion: `invoked`, 8 findings; the validator accepted 7 and refuted 1
(`d7b204e0acf8c99a`, check-ignore exit code: the repo's own `.gitignore` convention says the
verbose form must print nothing; the tracked-file blind spot is carried as the `--no-index` minor).

| # | Sev | Critique | Resolution |
|---|---|---|---|
| 1 | critical | Stem rule: `INTENT-OBJ-7` ≠ `OBJ-7`; four consumers missing; differential AC-001 blind | A — ADR-003 rewritten: `_id_from_stem`, four named consumers, three independent AC-001 cases (Interview #12) |
| 2 | critical | `read_text` destroys CRLF; shared parser is LF-only; preservation is a precondition | A — ADR-009 new `frontmatter.py` bytes splitter; ADR-002 bytes body; disk CRLF+BOM fixture in AC-002 (Interview #10) |
| 3 | critical | AC-005 baseline overwritten before verification | A — ADR-010 pin in the delta doc; Phase 4 verify-before-recapture; AC-005 reads the pin (Interview #11) |
| 4 | critical | `surface_allowance` block shape invalid | A — ADR-008 carries the exact accepted block; `round_trips` omitted with the reason stated |
| 5 | major | `_OBJECTIVE_OPTIONAL_ORDER` does not exist | A — ADR-011 ordered tuple, set derived, key-coverage test |
| 6 | major | Writer may write an empty body on a `bodies` miss | A — ADR-002: raise `WorldError("body")`; named Phase 1 test |
| 7 | major | `intent_path` name collision | A — `objective_doc_path`; `intent_path(root)` untouched (ADR-003) |
| 8 | major | ADR-005 absolute vs skill line | A — ADR-005 narrowed to rendered commands; skill line named; Phase 2 first step checks which tests assert bytes |
| 9 | major | Lifecycle test cannot be green in Phase 1 | A — moved to Phase 5 scope and exit |
| 10 | major | Shared parser cannot distinguish S1's three cases | A — ADR-009 status enum; `_read_intent` mapping stated in the data flow |
| 11 | minor | `validator_outcome: APPROVED` asserted before validation | A — now `MAJOR_REVISION_RESOLVED` (user chose A for every critique) |
| 12 | minor | Hypothesis profile per module; dependency question already answered | A — Testing Strategy names the profile pattern; `pyproject.toml:69` cited |
| 13 | minor | check-ignore tracked-file blind spot | A — `--no-index` in Phase 3 exit |
| 14 | minor | Rollback lines are labels | A — every phase's rollback is a command sequence; Phase 4's is ordered |

Rounds planned by `plan_rounds plan`: 14, skipped 0; answered in one batched round (Interview
#10–#12) because eleven critiques had no defensible alternative to "revise". Outcome recorded as
`MAJOR_REVISION_RESOLVED` — a human chose A for each; the terminal findings are the ones above,
carried into execute as known risks. Ledger: `plan-validator` pass 1, `--terminal`.
