---
type: plan
task_slug: assumption-entry-and-evidence-locator
status: complete
created: 2026-09-18
tags: [harness-maker, plan, python, jinja2, intent-layer, assumptions, staleness]
spec: "[[SPEC-assumption-entry-and-evidence-locator]]"
research_doc: "[[RESEARCH-assumption-entry-and-evidence-locator]]"
interview_rounds: 2
adrs: 8
validator_outcome: MAJOR_REVISION_RESOLVED
second_opinion_results:
  - model: codex
    status: invoked
    reconciliation: ["dab153fb656d7d41 accepted (status gains assumptions map, ADR-005)", "e1822e467af1e2a5 accepted (parsed-datetime authority, ADR-004)", "5557e9ab98c79235 accepted (stored-locator invariants, ADR-004)", "09c3a79bc8407f50 accepted (OSError to missing/LocatorError, ADR-002)", "2f33982bc00d3709 accepted (staleness passed explicitly, no cache, ADR-004)", "af03d18b998c2713 accepted (lock-held deterministic test + resolve, P2)"]
summary: "assume add + content-fingerprint locator (new pure module), derived staleness, 5.7 option; allowance retired last"
spec_need_verdict: add
spec_need_target: assumption-entry-and-evidence-locator
---

# PLAN — Assumption entry point + evidence locator

## 🎯 Executive Summary

**TL;DR.**
- A new pure module, `evidence_locator.py`, parses `path:A-B`, normalizes text, fingerprints it
  and classifies a stored locator against the current file as
  `fresh | moved | changed | missing`.
- `world.py` gains `assume add` and `observe --locator`. All three assumption writers share a
  per-file RMW lock.
- `gap` (never `status`, whose payload stays frozen) reports `assumptions`, `stale_evidence`,
  `moved_evidence` and `needs_revalidation` from the latest locator-bearing evidence.
  `derive(..., staleness=)` ORs staleness in only when it is handed a map, so `status`, the
  autopilot gate and transitions do no cited-file I/O.
- A malformed stored locator keeps the record loaded and is reported.
- Wrapup 5.7's existing assumption block lists stale ids first and gains a "new" option.
- The skill gains the verb.
- Surface growth rides a `surface_allowance` that the last phase retires.

**What / why.** See [[SPEC-assumption-entry-and-evidence-locator]]. The assumption layer has no
entry point, and recorded knowledge cannot say when its code moved.

**Key decisions.**
- ADR-001: new pure module.
- ADR-002: content fingerprint with no VCS.
- ADR-003: per-file lock.
- ADR-004: latest-locator authority plus propagation.
- ADR-005: extend the existing 5.7 block.
- ADR-006: allowance, retired in P5.
- ADR-007: the new keys go on `gap` only; `status` stays frozen.
- ADR-008: a malformed stored locator is reported, never fatal.

**Impact.**
- `world.py`: about +120 lines.
- New module: about 120 lines.
- Two templates: ≤ 8 lines per wrapup variant, ≤ 6 skill lines.
- Wrapup round trips: +1 per variant.
- `plan`, `review` and `help` stay byte-identical.

## 📚 Prior Work

- [[RESEARCH-assumption-entry-and-evidence-locator]]:
  - `@sha` is broken, because wrapup 5.7 runs before the Step 6 commit and `task-land` squashes;
  - fiberplane/drift stores content fingerprints only;
  - the motivating incidents were mostly external claims (the probe is a Non-Goal).
- [[PLAN-outcome-measure]]: the template for this shape. It used a Phase 0 pin, one allowance
  phase and a terminal retire phase. Its lessons:
  - `surface_allowance` must be declared in the same commit as the growth;
  - `_CLAUDE_ROUND_TRIPS['wrapup']` needs attribution;
  - the autopilot-gate golden must be re-captured, with a `rebases` entry;
  - snapshots are regenerated in the worktree (memory `project_snapshot_regen_in_worktree_is_correct`).
- `[wiki:gotcha] one-rendered-command-size-has-four-normative-sites`: `_ATOMIC_RATCHET`,
  `surface_baseline.json`, `_CLAUDE_ROUND_TRIPS` and the wrapup line pin.
- `[wiki:architecture] two-roots-versioned-state-vs-operational-events`: `.claude/world/` and
  locator paths resolve at the CURRENT checkout root. The lock file lives under base-agnostic
  `.claude/observability/`, which is already how `_rmw_lock` works.
- Memory `project_surface_allowance_expires_at_wrapup`: a terminal retire phase is owned here (P5).
- The prior invariance pins (`test_{objective_gap_proposal,playbook_alignment,outcome_measure}_invariance`)
  are pinned at 0.56.0 and skip at 0.57.1, so they do not constrain this task. This task ships its
  own pin (AC-012).

## 🎙️ Interview Transcript

Case A (SPEC approved, Open Questions empty). Step 3.0 answer: **proceed to phase decomposition**.
The brief's five defaults became ADR-001, ADR-003, ADR-005 and ADR-006, plus the SPEC amendment for
AC-013.

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 0.5 | Objective link | scope | Which objective does this task serve? | LOOP-OPT-IN / none | none | no outcome measures this; Step 4.9 draft skipped (no fitting outcome) | — |
| 3.0 | Readiness | scope | Proceed to decomposition or lock an architecture question first? | proceed / one / several | proceed | brief defaults accepted | ADR-001,003,005,006 |
| SPEC-R1 | Probe scope | scope | Include probe-backed checks? | non-goal / include | non-goal | (from /hm:spec) | — |
| SPEC-R1 | Authority | contract | Which evidence decides staleness? | latest / all | latest locator | (from /hm:spec) | ADR-004 |
| SPEC-R1 | Propagation | contract | Stale → needs_revalidation? | yes / no | yes | gates nothing today (verified) | ADR-004 |
| SPEC-R1 | 5.7 | contract | Stale ids first in 5.7? | yes / status-only | yes | (from /hm:spec) | ADR-005 |
| 2.1 | Payload | contract | Where do assumptions / stale_evidence go (status is frozen by objective-gap-proposal ADR-001)? | gap only / unfreeze status | gap only | status stays the free read path | ADR-007 |
| 2.2 | Malformed locator | failure | Stored locator fails its shape check | keep record + report / whole file invalid | keep + report | a typo must never gate autopilot via `link_invalid` | ADR-008 |
| 2.3 | Option cap | contract | AskUserQuestion allows at most 4 options | 2 ids + new + no / two-step question | 2 ids + new + no | other ids named in the question text for Other | ADR-005 |
| 2.4 | Validator batch | scope | Apply the other 14 validator critiques as suggested? | all / one by one | all | no re-validation (single-pass policy) | — |

## 📐 Architecture Decision Records

### ADR-001: locator logic is a new pure module, `evidence_locator.py`
**Status:** Accepted (2026-09-18, via /hm:plan brief default)

**Context.** `world.py` is 1,635 lines. The locator is a pure function of `(root, text)` and needs
property tests.

**Decision.** `src/harness_maker/evidence_locator.py` imports only the stdlib and owns:
- `parse_locator(spec: str) -> tuple[str, int, int]`;
- `normalize(lines) -> str` and `fingerprint(text) -> str`;
- `capture(root, spec) -> dict` (validate and build `{path, lines, fingerprint}`, raising
  `LocatorError(field, message)`);
- `classify(root, locator) -> Freshness` (`state` ∈ fresh/moved/changed/missing plus `line`);
- `validate_locator_shape(raw) -> str | None`, the error message for the validator.

`world.py` imports it. The module never imports `world`.

**Consequences.**
- ✅ Property tests hit one small surface; the mutation scope stays explicit (SPEC `paths_to_mutate` amended).
- ⚠️ One more module in the package. `LocatorError` is translated to `WorldError` at the boundary.

**Rejected alternatives.**
- Inline in `world.py`: grows an already-large file and couples property tests to the loader.

**Source:** brief ambiguity 1.

### ADR-002: staleness = content fingerprint against the current checkout; no VCS
**Status:** Accepted (2026-09-18, locked in SPEC/RESEARCH)

**Context.** Wrapup 5.7 records before the commit, and `task-land` deletes task-branch SHAs.

**Decision.**
- **Normalization** is exactly the SPEC Constraints row: per line `" ".join(line.split())`, drop
  empties, join with `"\n"`, then sha256 hex.
- **Reading.** Text is read with `read_text(encoding="utf-8")`, and `splitlines()` handles CRLF.
- **Classification:**
  - `fresh` if the first `k` non-empty normalized lines at or after line `A` hash to `fingerprint`
    (a blank line inserted inside the span is whitespace, not a change — validator minor);
  - else `moved` if some other window of `k` consecutive non-empty normalized lines hashes equal
    (first match; report the original 1-based line of the window's first line);
  - else `changed`;
  - `missing` if the path is absent, is not a file, escapes the root, is not UTF-8, or reading
    it raises any `OSError` (permission, deleted between the check and the read), or
    `Path.resolve` raises `RuntimeError` (a symlink loop on 3.12). `classify` never raises on file
    state. `capture` turns the same conditions into
    `LocatorError("locator", …)` (codex 09c3a79b).
- **Moved matching.** The stored record has no text, only the fingerprint. The comparison is
  therefore done by hashing each sliding window of `k` consecutive normalized non-empty lines of
  the current file, where `k` is the count of non-empty normalized lines captured at record time.
  **`k` is stored in the locator**, which is therefore `{path, lines, fingerprint, k}`. Without it,
  `moved` cannot be decided from a hash, and guessing the window size could match a
  different-sized run.
- **Refused at capture:** absolute paths, `..`, anything resolving outside the root, a missing
  file, non-UTF-8, `A < 1`, `A > B`, `B` past EOF, a span over 40 lines, and an empty normalized
  span.

**Consequences.**
- ✅ Git-free, worktree-neutral, deterministic.
- ⚠️ `k` adds a fourth locator key (the SPEC S3 shape lists three). This is recorded as a SPEC
  amendment in P1.
- ⚠️ The moved search is O(file lines) per locator. Fine: assumptions number in the tens.

**Rejected alternatives.**
- `path:line@sha` + `git diff`: stale on arrival.
- Storing the snippet text: duplicates code into YAML, and the text itself goes stale.
- Whole-file hash: noisy.

**Source:** SPEC Constraints; RESEARCH Approaches 2a–2d.

### ADR-003: `_rmw_lock` is keyed by target file stem; all assumption writers take it
**Status:** Accepted (2026-09-18, via /hm:plan brief default)

**Context.** `observe` and `resolve` write `assumptions.yaml` unlocked, and `add` is a third
writer. `_rmw_lock` hardcodes `.hm-world-outcomes.lock`.

**Decision.** The lock path becomes `<world>/../observability/.hm-world-<path.stem>.lock`.
- For `outcomes.yaml` this is exactly the existing name, so there is zero rename.
- `add`, `observe` and `resolve` each wrap load → mutate → dump in `_rmw_lock(assumptions_path(root))`.
- The error message changes from the hardcoded `outcomes.yaml is locked …` to
  `f"{path.name} is locked by another writer ({lock_path})"`. This is byte-identical for outcomes
  and asserted for assumptions (validator minor).

**Consequences.**
- ✅ Outcomes behaviour is byte-identical; the gitignore and churn prefix `.claude/observability/`
  already cover the new lock file.
- ⚠️ `_load_assumptions_doc` must be called inside the lock. Moving the read changes no output.

**Rejected alternatives.**
- One directory-wide lock: needless contention between outcomes and assumptions, plus a rename.

**Source:** brief ambiguity 2; SPEC S7.

### ADR-004: authority = the latest locator-bearing evidence; staleness is derived and propagates
**Status:** Accepted (2026-09-18, via /hm:spec round 1)

**Decision.**
- **Authoritative entry.** For each assumption, pick the evidence entry with a `locator` that has
  the greatest `observed_at`, compared as **parsed aware datetimes**, never as strings.
  `normalise_timestamp` omits `.ffffff` when it is zero, so `"…:00Z" > "…:00.500000Z"` as strings
  (codex e1822e46). Ties → last in list. An entry whose stored `observed_at` does not parse as an
  aware ISO-8601 timestamp is ignored for authority rather than raising. `status` must not crash on
  a hand-edited file; the validator already reports the field.
- **Payload.** Only `gap` gains keys (ADR-007): `assumptions: {id: status}`,
  `stale_evidence: {id: "changed"|"missing"}`, `moved_evidence: {id: <line>}` and
  `needs_revalidation: [objective ids]`, all sorted by id. `gap_report` copies keys **explicitly**
  (it does not spread `status`), so each new key is an explicit line there.
- **`derive(world, oid, *, staleness=None)`.** `needs_revalidation` = any dependency in `conflict`,
  or, **only when a staleness map is passed**, any dependency in a stale state. With
  `staleness=None` (status, the autopilot gate, `transition`) there is no cited-file I/O and the
  return value is exactly the pre-change one. Terminal objectives stay `False`.
- **Classification cost.** `World` is an unhashable mutable dataclass, so there is no
  `functools.cache` (codex 2f33982b). `staleness(world) -> dict[str, Freshness]` is a plain
  function that only `gap_report` calls, **once** per report, passing the map to every `derive`.
  There is no cross-call cache.
- **`validate_assumptions`.** An evidence entry's `locator` must pass `validate_locator_shape`,
  which enforces every file-independent invariant capture enforces (codex 5557e9ab):
  - keys exactly `{path, lines, fingerprint, k}`;
  - `path` a non-empty relative POSIX string with no `..` segment and not absolute;
  - `lines` a list of two `int`s (with `bool` excluded explicitly);
  - `1 ≤ A ≤ B`, `B − A + 1 ≤ 40`;
  - `fingerprint` lowercase hex64;
  - `k` an `int` (not `bool`) with `1 ≤ k ≤ B − A + 1`.

  A shape failure does **not** invalidate the file (ADR-008): `validate_assumptions` does not
  report it. `load_world` collects it separately and appends it to `world.errors` as
  `assumptions.yaml:assumptions[i].evidence[j].locator: …`, so it surfaces in `broken_references`.
  The entry is then treated as locator-less. The same applies to a locator-bearing entry whose
  `observed_at` is not an aware ISO-8601 **string** (an unquoted YAML timestamp loads as
  `datetime`; it is treated as unparseable, reported, and never crashed on — validator minor).
  File existence is **not** a validation rule: a file deleted after recording is `missing` at read
  time, never an invalid world.

**Consequences.**
- ✅ Re-confirming via `observe --locator` is the re-stamp. History stays immutable.
- ⚠️ The SPEC-intent-world-model-objective-layer line 249 derivation widens, but only on the
  `gap` path (SPEC S6). The gate caller (`autopilot_caps.py:317`) reads `approval_valid` with no
  staleness map, so it is unchanged and does no extra I/O.

**Rejected alternatives.**
- All locators: a stale entry could never be cleared without mutating history.

**Source:** SPEC-R1.

### ADR-005: wrapup 5.7 extends the existing assumption block; the stale list comes from the existing status read
**Status:** Accepted (2026-09-18, via /hm:spec round 1 + brief default)

**Decision.** Inside `<!-- @hm:answer-gated:assumption -->`, in both `is_codex` branches:
- **Options (≤ 4, the AskUserQuestion cap):**
  - at most two assumption ids from `hm world gap --json` (`assumptions`), stale ids first, each
    stale one labelled **"(cited code changed)"**;
  - **"new — record an assumption"**;
  - **"no"**.

  Any remaining ids are named in the question text, for the operator to type via Other. The gap
  read is the one the same step's outcome-measure block already makes, run once for both. It is
  inline prose, not a new `!` line.
- **On an id,** the existing `observe` line gains the optional `[--locator <path:A-B>]`.
- **On "new,"** one `assume add <id> --claim … --status <known|assumed|unknown> [--text … --observed-at … --locator …]`
  line is run once with the arguments the operator confirmed.
- **The `Otherwise: write nothing` line is unchanged.**

**The id list comes from `gap` (codex dab153fb; ADR-007).** Today no payload lists assumption ids:
`status` only has `conflicts`. The existing 5.7 prose ("one option per assumption id (from the status
output)") therefore has nothing to enumerate, a latent defect this task fixes. The fix goes on `gap`,
because `status` is frozen.

**Test literals, fixed now (validator minor).** `STALE_LABEL='(cited code changed)'`,
`NEW_LABEL='new — record an assumption'` and `ADD_CMD='hm world assume add <id> --claim'`. The
AC-010 test is written before the P4 template edit, and a payload test asserts that a locator-less
`assumed` record appears in `gap["assumptions"]`.

No new question, and no new status call. There is one new command line, so round trips go +1 per
variant. The `intent-layer` skill verbs block gains the `add` form and `[--locator]` on `observe`.

**Consequences.**
- ✅ The smallest surface that makes the layer enterable.
- ⚠️ The block's "If the answer is yes" line now has two command forms (observe or add). The SPEC
  marker contract (question → yes-line → command → otherwise-line) holds, with both commands
  between yes and otherwise.

**Rejected alternatives.**
- A fourth question: more surface and question fatigue.

**Source:** SPEC S8; brief ambiguity 4.

### ADR-006: surface growth via `surface_allowance`, pinned in P0 and retired in P5
**Status:** Accepted (2026-09-18, precedent PLAN-outcome-measure ADR-007)

**Decision.**
- **P0** writes `work-docs/BASELINE-DELTA-assumption-entry-and-evidence-locator.md` §1. It holds a
  fenced JSON pin of per-arm sha256 for `plan`/`review`/`help`/`wrapup` plus `wrapup_len` and
  `harness_maker_version`, using the same recipe as `test_outcome_measure_invariance._live_arms`,
  before any template edit.
- **P4** declares `surface_allowance{chars, commands{wrapup, hm-wrapup}, round_trips{wrapup, hm-wrapup: 1}, delta_doc, reason}`
  in THIS PLAN's frontmatter in the same commit as the template edit. It also bumps
  `_CLAUDE_ROUND_TRIPS['wrapup']` by 1 with attribution and re-captures the autopilot-gate golden
  (with a `rebases` entry).
- **P5:**
  - re-freezes `surface_baseline.json` and `instruction_baseline.json` from the worktree;
  - moves `_ATOMIC_RATCHET['wrapup']` only if outside its band;
  - (the `test_render_wrapup_delegation` line pin moves in P4, together with the template);
  - writes §3 attribution;
  - deletes the allowance;
  - re-pins wrapup in §1.
- **New test** `tests/structural/test_assumption_entry_invariance.py` (AC-012), modelled on
  `test_outcome_measure_invariance.py`: plan/review/help are byte-identical to the pin, wrapup grows
  ≤ the allowance while it is declared and is byte-identical after retirement, and the test skips
  loudly on a version bump.

**Rejected alternatives.**
- Regenerating the baselines up front: destroys the ratchet (wiki gotcha).

**Source:** SPEC Surface row.

### ADR-007: new keys on `gap` only; the `status` freeze is honored
**Status:** Accepted (2026-09-18, via /hm:plan round 2)

**Context.**
- PLAN-objective-gap-proposal ADR-001 froze the `status` payload.
- `tests/unit/test_world_gap.py:156-170` pins the key set.
- The `world.py:820` docstring states it.

**Decision.**
- `assumptions`, `stale_evidence`, `moved_evidence` and `needs_revalidation` are added to
  `gap_report` only.
- `status_report`, `_status_payload`, the key-set pin and the docstring are untouched.
- Wrapup 5.7's assumption block reads `gap`.

**Consequences.**
- ✅ `status` stays the free read path: no cited-file I/O on plan Step 0.5 or skill status calls.
- ✅ No earlier ADR is overridden.
- ⚠️ Staleness is visible only on `gap`, which is on-demand.

**Rejected alternatives.**
- Unfreeze `status`: it would override a locked ADR and add file reads to the hot read path.

**Source:** Interview 2.1; validator critical.

### ADR-008: a malformed stored locator is reported, never fatal
**Status:** Accepted (2026-09-18, via /hm:plan round 2)

**Context.** Today any assumption validation error drops the whole file. Every `depends_on` then
dangles, the objective becomes `broken`, and the autopilot gate returns `link_invalid`
(`world.py:576-583`, `511-515`; `autopilot_caps.py:311-312`). With exact-key locator checks, one
hand-edit or a future key could gate autopilot.

**Decision.**
- Locator shape failures, and unparseable `observed_at` on locator-bearing entries, are collected
  **outside** `validate_assumptions`.
- They are reported in `broken_references` via `world.errors`, and the entry is treated as
  locator-less.
- All other assumption validation keeps its all-or-nothing behavior.

**Consequences.**
- ✅ The Non-Goal "no gate reads staleness data" holds structurally.
- ⚠️ Two error channels for one file (record rules vs locator rules). This is documented in the
  loader docstring.

**Rejected alternatives.**
- Whole-file invalid: simpler, but lets locator data gate autopilot.

**Source:** Interview 2.2; validator major.

## 🏗️ Technical Design

**Current state.**
- `hm world assume {observe, resolve}` both need an existing record.
- Evidence is `{text, observed_at, relation}`, and unknown keys inside evidence are **not**
  rejected today (only record-level keys are).
- `needs_revalidation` is derived from `conflict` only.
- 5.7's assumption block offers the ids plus "no".

**Affected components.**
- **`src/harness_maker/evidence_locator.py`** (new).
- **`src/harness_maker/world.py`:**
  - `add_assumption()`;
  - `observe(..., locator=None)`;
  - lock around the `observe`/`resolve`/`add` RMW;
  - locator/`observed_at` problems collected in `load_world`, outside `validate_assumptions`
    (ADR-008);
  - `staleness(world)`;
  - `gap_report` keys (ADR-007; `_status_payload` untouched);
  - `derive(..., staleness=None)`;
  - `_parser` (`add` subparser, `--locator` on observe);
  - `main` dispatch.
- **`src/harness_maker/command_registry.py`:** `"add"` in the `world` verb set (command-surface gate
  reads `add_parser` literals).
- **Templates:**
  - `src/harness_maker/templates/stages/wrapup.md.j2` §5.7 assumption block;
  - `src/harness_maker/templates/skills/intent-layer/SKILL.md.j2` verbs block.
- **Tests:**
  - `tests/unit/test_world_assume_add.py`;
  - `tests/unit/test_world_evidence_locator.py`;
  - `tests/integration/test_world_assume_concurrency.py`;
  - `tests/unit/test_render_intent_layer_assume_add.py`;
  - `tests/structural/test_assumption_entry_invariance.py`;
  - ratchet files.
- **Docs:** CHANGELOG, `docs/HOW-IT-WORKS*` intent-layer section (if present), and the SPEC
  amendment (`k`).

**CLI shape.**
```
hm world assume add <id> --claim C --status {known,assumed,unknown}
                         [--text T --observed-at TS] [--locator path:A-B] [--json]
hm world assume observe <id> --relation R --text T --observed-at TS [--claim C] [--locator path:A-B] [--json]
```
- Refusal layers (validator major, AC-002 channel):
  - `--status conflict` → argparse `choices`, exit 2, **stderr**;
  - an existing id, an empty claim, an id outside `[a-z0-9_]+`, a naive timestamp, `--locator`
    without `--text`, and `--text` without `--observed-at` (or the reverse) → `WorldError`,
    exit 1, `{"error": …}` on **stdout** via `_emit`.

  The AC-002 test asserts on `stdout + stderr` (SPEC machine predicate amended).
- Output is `changed: assumptions.yaml` (`_emit`).

**Data flow (status).**
`load_world` (collects locator problems into `world.errors`) → `gap_report` → `staleness(world)`,
computed once. For each assumption, the latest valid locator is passed to
`evidence_locator.classify(world.root, loc)`, and the results are split into `stale_evidence` and
`moved_evidence`. `derive(world, oid, staleness=map)` builds `needs_revalidation`. `status_report`
never calls `staleness`.

## 📝 Implementation Plan

### Phase 0 — Pin the pre-change surface, confirm main is green
- `depends_on`: [] · `parallel_group`: serial-0 · `merge_hazards`: none
- **Scope (in):**
  - run `uv run pytest tests/structural/test_surface_baseline.py tests/structural/test_command_size_budget.py tests/structural/test_roundtrip_budget.py`
    from the worktree (inherited state must be green);
  - write the BASELINE-DELTA §1 pin (ADR-006) using the `test_outcome_measure_invariance._live_arms`
    recipe;
  - §2 "inherited fold: none" (or the measured fold);
  - §3 placeholder.
- **Scope (out):** src, templates.
- **Exit:** the pin exists with 4 arms × 4 commands (hex64) + `wrapup_len` + version; the structural
  suites above are green.
- **Risk:** low · **Rollback:** none (docs only).

### Phase 1 — `evidence_locator` module (AC-003 fingerprint half, AC-004)
- `depends_on`: [0] · `parallel_group`: serial-1 · `merge_hazards`: `specs/SPEC-…machine.yaml` (the `k` amendment)
- **Scope (in):**
  - `src/harness_maker/evidence_locator.py` per ADR-001/002;
  - `tests/unit/test_world_evidence_locator.py`:
    - AC-004 hypothesis property, with a whitespace perturbation and a token edit;
    - a pure-function capture/classify table using the hand-computed `EXPECTED_FP` literal,
      including a `PermissionError` injected via monkeypatched `Path.read_text` (→ `missing` /
      `LocatorError`);
    - a `validate_locator_shape` table (bool lines, `k > span`, `..`, absolute, over 40);
  - the SPEC amendments (`k`, freshness row, gap-only, malformed-locator rule, AC-002/008/010/012
    predicates) were made during plan round 2; P1 only re-runs `spec_machine check`.
- **Scope (out):** world.py.
- **Exit:** `uv run pytest tests/unit/test_world_evidence_locator.py -k "ac_004 or capture or classify"`
  green; `mypy --strict src/harness_maker/evidence_locator.py` clean; `spec_machine check --all` ok.
- **Risk:** low · **Rollback:** Phase 0.

### Phase 2 — `assume add`, `observe --locator`, lock, validation, registry (AC-001/002/003/008/009/013)
- `depends_on`: [1] · `parallel_group`: serial-2 · `merge_hazards`: `src/harness_maker/world.py`, `src/harness_maker/command_registry.py`
- **Scope (in):**
  - `world.add_assumption`;
  - `observe(..., locator=None)` capturing through `evidence_locator.capture(root, spec)` (with
    `LocatorError` → `WorldError`);
  - `_rmw_lock` keyed by stem (ADR-003), wrapping all three writers;
  - the `validate_assumptions` locator check;
  - parser + dispatch;
  - `command_registry` `"add"`;
  - tests `test_world_assume_add.py` (AC-001/002/013) and the AC-003/009 rows in
    `test_world_evidence_locator.py`;
  - `tests/integration/test_world_assume_concurrency.py` (AC-008), with two layers (codex af03d18b):
    - **(a) Deterministic (validator major).** The test holds `_rmw_lock(assumptions_path)`.
      flock conflicts across separate open descriptions, even within one process. It then runs
      the writer on a thread (`add`, then `observe`, then `resolve` on a `conflict` record), with
      `world.time.sleep` monkeypatched to set an `Event` on the first contended retry. It waits on
      that Event (a positive "blocked" signal, not a timer), asserts the bytes are unchanged,
      releases, joins, and asserts the write landed. An unlocked writer never sets the Event and
      writes immediately, so it fails.
    - **(b) Stress.** Two subprocesses released by a shared start barrier file, ≥ 20 iterations:
      `add`/`add` must keep both ids; `add`/`observe` must keep both the new id **and** the new
      evidence row (count +1).
- **Scope (out):** status/derive, templates.
- **Exit:** `uv run pytest tests/unit/test_world_assume_add.py tests/unit/test_world_evidence_locator.py tests/integration/test_world_assume_concurrency.py tests/unit/test_world_assumptions.py tests/unit/test_world_outcomes.py tests/unit/test_world_outcome_measure.py tests/unit/test_command_surface_gate.py`
  green; `mypy --strict` and `ruff` clean on the touched files.
- **Risk:** medium (the lock refactor touches the outcomes writer; mitigated by
  `test_world_outcomes.py` + `test_world_outcome_measure.py` in the exit set) · **Rollback:** Phase 1.

### Phase 3 — Derived staleness in status + propagation (AC-005/006/007)
- `depends_on`: [2] · `parallel_group`: serial-3 · `merge_hazards`: `src/harness_maker/world.py`
- **Scope (in):**
  - `staleness(world)`, computed once per `gap` report and passed explicitly;
  - `gap_report`: explicit `assumptions` / `stale_evidence` / `moved_evidence` /
    `needs_revalidation` lines (ADR-007);
  - `derive(..., staleness=None)`;
  - `load_world` collects locator problems (ADR-008);
  - `status_report` is untouched, and the `test_world_gap.py:156-170` key-set pin stays as-is;
  - tests AC-005/006/007, including the authority rows: fractional vs whole seconds, `+09:00` vs
    `Z`, a tie, and an unparseable stored `observed_at` (ignored, no crash);
  - confirm `gap` writes nothing (byte snapshot of `.claude/world/`) and `status`'s key set is
    unchanged.
- **Scope (out):** templates.
- **Exit:** `uv run pytest tests/unit/test_world_evidence_locator.py tests/unit/test_world_status_and_revisit.py tests/unit/test_world_gap.py tests/unit/test_world_objectives.py tests/unit/test_autopilot_caps_objective_gate.py`
  green; mypy/ruff clean.
- **Risk:** medium (the `gap` payload gains keys; the `status` key set is pinned by an existing
  test) · **Rollback:** Phase 2.

### Phase 4 — Wrapup 5.7 + skill prose, allowance (AC-010/011)
- `depends_on`: [3] · `parallel_group`: serial-4 · `merge_hazards`: `wrapup.md.j2`, `SKILL.md.j2`, `tests/structural/test_instruction_preservation.py`, `tests/unit/test_render_wrapup_delegation.py`, `tests/structural/surface_baseline.json`, `tests/structural/test_roundtrip_budget.py`, autopilot-gate golden, `tests/snapshot/**`, this PLAN's frontmatter
- **Scope (in):**
  - edit the 5.7 assumption block per ADR-005 (both `is_codex` branches, ≤ 8 lines each);
  - skill verbs block (+`add` form, `[--locator]`);
  - measure the wrapup delta per arm;
  - declare `surface_allowance` (with the required `reason` key) in the same commit;
  - add `_ALLOWED_REMOVALS["assumption-entry-and-evidence-locator"]` in
    `tests/structural/test_instruction_preservation.py`, holding the exact pre-change observe line
    (canonicalized form) for `wrapup@task-driven` and `wrapup@spec-driven`, following the
    playbook-alignment precedent at :222-225;
  - update the `tests/unit/test_render_wrapup_delegation.py` body-line pin, which moves with the
    template;
  - `_CLAUDE_ROUND_TRIPS['wrapup']` +1 with attribution;
  - re-capture the autopilot-gate golden (verify wrapup is the only moved command) + `rebases` entry;
  - regenerate snapshots in the worktree (`tests/snapshot/regenerate.py`);
  - `tests/unit/test_render_intent_layer_assume_add.py` (AC-010/011), with the literals from ADR-005
    written **before** the template edit;
  - `tests/structural/test_assumption_entry_invariance.py` (AC-012 in its in-flight form).
- **Scope (out):** plan/review/help templates.
- **Exit:** `uv run pytest tests/unit/test_render_intent_layer_assume_add.py tests/unit/test_render_intent_layer.py tests/unit/test_render_wrapup_delegation.py tests/structural tests/snapshot`
  green.
- **Risk:** medium (the four normative size sites; the golden re-capture must show only wrapup
  moved) · **Rollback:** Phase 3.

### Phase 5 — Docs, CHANGELOG, retire the allowance (AC-012)
- `depends_on`: [4] · `parallel_group`: serial-5 · `merge_hazards`: `tests/structural/surface_baseline.json`, `tests/structural/instruction_baseline.json`, `tests/structural/test_command_size_budget.py`, `tests/unit/test_render_wrapup_delegation.py`, this PLAN's frontmatter, BASELINE-DELTA doc
- **Scope (in):**
  - CHANGELOG `Unreleased` entry;
  - HOW-IT-WORKS intent-layer paragraph (if the section exists);
  - re-freeze both baselines from the worktree;
  - `_ATOMIC_RATCHET['wrapup']` only if outside its band;
  - (the wrapup line pin already moved in P4);
  - BASELINE-DELTA §3 attribution + wrapup re-pin in §1;
  - delete `surface_allowance`.
- **Scope (out):** src.
- **Exit:** `uv run pytest tests/structural` green with zero allowances; full suite green
  (background, per memory `feedback_pytest_background`); `uv run mypy --strict src tests` clean.
- **Risk:** medium · **Rollback:** Phase 4.

### Phase status

| Phase | Status |
|---|---|
| 0 | done — pin written at base 43c7ded0; inherited ratchets green (54 passed) |
| 1 | done — `evidence_locator` 44 tests GREEN (property incl. dev profile); A.5 FAIL round 1 (single positive `shape_error` control, magic value) → PASS round 2; `spec_mutation gate` again collected zero mutants (known `mutation-gate-timeout-leaves-source-mutated-on-disk`; sources verified unmodified) |
| 2 | done — `assume add`, `observe --locator`, stem-keyed lock on all three writers, registry `add`; A.4 caught one false-RED (absent-file refusal passed pre-impl via argparse) → fixed; A.5 PASS round 1; exit suite 156 passed |
| 3 | done — `staleness()`, `derive(staleness=)`, gap keys, locator problems → `broken_references`; A.5 PASS round 1; exit suite 1001 passed |
| 4 | done — templates + allowance (+548/+555, round trips +1); golden re-captured (wrapup only), `_ALLOWED_REMOVALS`, line pins, roundtrip table, snapshots; A.5 PASS round 1; mutation receipt filed for the new structural gate (deleting `plan.md.j2:13` turns AC-012 red — observed) |
| 5 | done — CHANGELOG, HOW-IT-WORKS §7.13; both baselines re-frozen from the worktree; allowance deleted; wrapup re-pinned; §3/§3.1 attribution |

**Implementation notes (deviations recorded, not silent):**
- ADR-001 named `parse_locator` / `normalize` / `validate_locator_shape`; the shipped module exposes
  `capture` (parses and validates), `fingerprint`, `classify` and `shape_error`. Same
  responsibilities, fewer public names; parsing and normalization are private helpers.
- The mutation receipt row lives in the BASE `.claude/observability/mutation-receipts.jsonl`
  (the writer's root, by design) — `/hm:wrapup` must commit it, or a fresh clone fails
  `test_every_new_structural_gate_has_a_mutation_receipt` (the 0.57.0 failure).
- `intent-layer-ops` landed on main (b48bcec4) during review preflight, touching `world.py`
  (`gap_report` gained `withdrawal`), wrapup 5.7 (+1 sentence) and every shared baseline. This
  branch was rebased onto it before round 1 (WIP commit → `git rebase main` → conflicts resolved
  by keeping both sides → `git reset --soft main`), then the golden, snapshots and both baselines
  were re-derived on top of it; the growth attributed here is unchanged (+548 / +555).
  `mission-context-loop` is still in flight on the old base.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/stages/plan.md.j2` — pinned byte-identical (AC-012)
- `src/harness_maker/templates/stages/review.md.j2` — pinned byte-identical (AC-012)
- `src/harness_maker/intent.py` — the intent schema is untouched; locators live only in assumption evidence
- `src/harness_maker/autopilot_caps.py` — the objective gate's `derive` call stays approval-only, with no staleness map and no cited-file I/O (SPEC Non-Goal)
- Advisory: the SPEC-intent-world-model-objective-layer wrapup marker contract (question → `If the answer is "yes":` → command(s) → `Otherwise: write nothing`) keeps its order and literals
- Advisory: `outcomes.yaml` lock file name and outcome write behaviour stay byte-identical
- Advisory: `hm world status`'s payload keys and values are unchanged (PLAN-objective-gap-proposal ADR-001; ADR-007)

## 🧪 Testing Strategy

- **Unit:**
  - pure locator functions (a table plus a hypothesis property);
  - world verbs via `world_fixture` in `tmp_path`;
  - validation rows;
  - derived status;
  - render tests for both variants.
- **Integration:** AC-008 races two `python -m harness_maker.world` subprocesses on one tmp
  checkout, repeated.
- **Structural:** own invariance pin + the four ratchets + the golden + snapshots.
- **Manual:** none required. Optional dogfood after land: `hm world assume add` one real
  assumption in this repo, with a locator, then edit the cited line and see `status` flag it (not
  automatic here; a released plugin is needed for the rendered harness — memory
  `project_rendered_harness_pins_released_plugin`).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The lock refactor changes outcome writes | low | high | same lock name for outcomes (ADR-003); outcomes + measure suites in the P2 exit |
| `gap` gets slow on many locators | low | low | one classification per assumption per report; no subprocess; `status` does none |
| A malformed or future-version locator gates autopilot | medium | high | ADR-008: reported in `broken_references`, the record stays loaded; AC-009 asserts the dependent objective is not `broken` |
| An unexpected classify exception escapes the autopilot gate | low | high | the gate's `derive` gets no staleness map, so classify is never called there (Contract Boundaries); classify catches `OSError` + `RuntimeError` |
| The golden re-capture hides an unintended move in another command | medium | medium | diff the re-captured golden per command; only wrapup may move (P4) |
| The allowance is left behind after land | medium | medium | P5 owns retirement; the AC-012 test fails while an allowance is declared at close |
| A wrong-cause claim in docs about external-claim coverage | medium | low | the CHANGELOG states the limitation verbatim from SPEC Non-Goals |
| Hypothesis flakiness from the generator alphabet | low | low | bounded alphabet; `@settings(deadline=None)` like the existing property tests |

## ✅ Success Criteria

- [x] AC-001 add creates the record
- [x] AC-002 refusals write nothing
- [x] AC-003 locator validated and fingerprinted
- [x] AC-004 whitespace-invariant, token-sensitive fingerprint (property)
- [x] AC-005 fresh/moved/changed/missing derived on `gap`, no write, `status` keys unchanged
- [x] AC-006 latest locator authoritative; re-confirm clears
- [x] AC-007 propagation to non-terminal objectives only
- [x] AC-008 concurrent writers keep both rows
- [x] AC-009 v1 file loads; malformed locator named
- [x] AC-010 wrapup 5.7 stale-first + "new" + add command
- [x] AC-011 skill lists add and `--locator`
- [x] AC-012 surface pinned and allowance retired
- [x] AC-013 `changed: assumptions.yaml`

## 🔍 Plan Validation

**Cross-model (codex, invoked, 64 s):** 6 findings, all accepted and applied before the validator
dispatch. The validator confirmed all 6 as real. Two of the applied fixes were incomplete: the
status freeze (dab153fb) and the lock test (af03d18b). Both were completed in round 2 (ADR-007,
P2 (a)).

**plan-validator pass 1 (run-id `aeel-20260918-1`, 434 s): MAJOR_REVISION** — 1 critical, 8 major,
8 minor. `plan_rounds plan` queued all 17 (0 skipped). Resolution:
- 3 real decisions were asked in round 2: payload (→ ADR-007), malformed locator (→ ADR-008),
  option cap (→ ADR-005).
- The remaining 14 were factual corrections, applied as suggested on the operator's answer
  (Interview 2.4).

| # | Sev | Critique | Resolution |
|---|---|---|---|
| 1 | critical | the `status` payload is frozen (objective-gap-proposal ADR-001; `test_world_gap.py:160`); `gap_report` copies keys by name | ADR-007: `gap` only, with explicit copies; `status` untouched |
| 2 | major | phantom `objective_gate.py`; `autopilot_caps.py` calls `derive` unguarded | Contract Boundaries corrected; `derive(staleness=None)` does no I/O; gate test added to the P3 exit |
| 3 | major | the instruction-preservation allow-list is missing for the edited observe line | P4 `_ALLOWED_REMOVALS` entry |
| 4 | major | the machine AC-012 test id / predicate mismatch | machine.yaml amended (structural test, phase-aware predicate) |
| 5 | major | the AC-002 oracle reads stderr, but `WorldError` goes to stdout | refusal layers named; predicate uses stdout+stderr |
| 6 | major | the 1 s lock test is not discriminating | positive contention Event via patched `sleep` |
| 7 | major | the P2 exit misses the outcomes lock test | `test_world_outcome_measure.py` added |
| 8 | major | the 4-option AskUserQuestion cap | ≤ 2 ids + new + no; the rest named in the question text |
| 9 | major | a malformed locator invalidates the file and gates autopilot | ADR-008 |
| 10 | minor | "cached per World" wording | removed (3 sites) |
| 11 | minor | the validator does not parse `observed_at` | ignored entries reported in `broken_references`; non-str tolerated |
| 12 | minor | allowance `reason` key | added to the ADR-006 shape |
| 13 | minor | the wrapup line pin moves in P4 | moved to P4 + exit |
| 14 | minor | a blank line inside the span → moved | fresh = first `k` non-empty lines at/after `A` (SPEC Freshness row) |
| 15 | minor | the AC-008 add/observe arm checks ids only | evidence count +1 asserted |
| 16 | minor | the lock message hardcodes `outcomes.yaml` | `{path.name}` (byte-identical for outcomes) |
| 17 | minor | AC-010 literals are not fixed | named in ADR-005; the test is written before the template |

**No pass 2 or terminal re-validation** (operator policy: plan-validator runs once; revisions are
not re-validated). This revision has not been independently re-read, so `/hm:execute` A.5 and
`/hm:review` carry the residual risk that a round-2 edit introduced a new defect. Loop outcome:
n/a (single pass).
