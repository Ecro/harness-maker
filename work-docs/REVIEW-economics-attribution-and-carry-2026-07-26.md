---
type: review
task_slug: economics-attribution-and-carry
status: CHANGES_REQUESTED
human_review_needed: true
created: 2026-07-26
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
second_opinion_results:
  - model: codex
    status: invoked
    findings: 9
  - model: antigravity
    status: invoked
    findings: 7
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/presets.py
    - src/harness_maker/templates/harness-yaml/Production.yaml.j2
    - src/harness_maker/templates/harness-yaml/Side.yaml.j2
    - src/harness_maker/command_registry.py
  scenario_misses: []
  task_slug: economics-attribution-and-carry
  computed_at: 2026-07-26T00:00:00Z
---

# REVIEW — economics-attribution-and-carry

Voter pool **N = 4**: `code-reviewer`, `security-reviewer` (Claude, 2-pass redacted)
plus `codex` and `antigravity` as full cross-model voters (ADR-006, K = 2).

## 🎯 Round 1 Summary

| | count |
|---|---|
| consensus-passed **P0** | 1 |
| consensus-passed **P1** | 4 |
| weak-consensus | 1 |
| manual-only P0/P1 | 8 |
| manual-only P2/P3 | 6 |
| drift | 4 (all P2) |

**Grade: D** (1 consensus-passed P0). Threshold is **A** → auto-fix loop entered.

`human_review_needed: true` — eight `manual-only` P0/P1 findings exist, including
one **P0 from antigravity** that describes the same defect as a consensus-passed P1
but at a different severity tier, so the filter could not merge them (Step 4c).

### A note on the consensus filter's tier rule

Step 4a admits candidates only within one severity tier. On this diff that rule split
**four** cross-model agreements that clearly describe one defect each:

| defect | voices | outcome |
|---|---|---|
| `_build_spans` session truncation | CR P1, CX P1, **AG P0** | P1 consensus + orphan P0 |
| `_extract_payload` brace counting | CX P2, **AG P1** | two manual-only |
| receipt path escape | SR P1, CX P1, **AG P2** | P1 consensus + orphan P2 |
| `_vault_slugs` over-broad | **SR P1**, CR P2 | two manual-only |

The rule is doing its job (it refuses to invent a middle severity), but the effect is
that agreement *about the defect* is discarded because the voices disagree about *how
bad it is*. Recorded here rather than worked around.

### One deliberate departure from the letter of the protocol

**F-01 is recorded as `consensus-passed` on a single reviewer voice**, because the
orchestrator **reproduced it by execution** before grading:

```
$ uv run python -m harness_maker.run_classify boundaries --root .
total_boundaries: 0 | pending: 0
$ uv run python -m harness_maker.economics report --root .   # same corpus
classification_boundaries: 392
```

A reproduction is stronger evidence than a second model's agreement, and letting a
demonstrably dead shipping path score as "does not affect the grade" would be the
wrong answer. The departure is stated rather than hidden.

## 🔍 Drift Findings

`drift_verdict.result: scope_violation`, four files changed that no PLAN phase's
scope names — **all four forced by work the PLAN does name.** These are inaccuracies
in the PLAN's Affected Components table, not scope over-reach:

| file | forced by | severity |
|---|---|---|
| `presets.py` | ADR-007's agent asset requires per-preset model routing (structural test enforces) | P2 |
| `templates/harness-yaml/{Side,Production}.yaml.j2` | ADR-011's config key requires the checkpoint-6 write half | P2 |
| `command_registry.py` | three new CLI entry points; command-surface parity gate enforces | P2 |

Reverse direction: `render.py` is listed in the table but was **not** changed — it did
not need to be (`synthesize._agent_files` drives the asset). Table over-listing, not an
incomplete phase.

**Why this matters beyond bookkeeping:** the same table's omission of the
`harness-yaml` templates is *how* the `economics.span_max_*` write-half defect shipped
in Phase 1. A reader who treats the table as exhaustive reproduces that bug.

## ✅ Consensus Findings

### F-01 · P0 · `src/harness_maker/run_classify.py:360` — `--root` is never resolved, so the shipped `boundaries` call finds nothing
*Voices: code-reviewer + orchestrator reproduction.*

`main` passes `Path(ns.root)` unresolved; `economics.main` resolves (`economics.py:749`).
The rendered command is `run_classify boundaries --root .` (`metrics.md.j2`). With
`root = Path(".")`, `encode_project_dir` yields `"-"`, discovery matches no directory,
and `is_own_cwd` would reject every turn regardless. **Every unit test passes an
absolute `str(tmp_path)`, which is exactly why none of them saw it.**

Third instance in this task of *unit boundary green, shipped entry point wrong* — after
the `--stage` argument-order parse (Phase 2) and `_collect` never passing `spans` /
`inferred` (Phase 3).

**Fix:** resolve in `main`, and add a CLI test that `chdir`s into a tmp repo and passes
a literal `--root .`.

### F-02 · P1 · `src/harness_maker/stage_spans.py:169` — one global `current` span, so a peer session truncates yours
*Voices: code-reviewer P1 + codex P1 (antigravity filed the same defect at P0 — see manual-only M-01).*

`_build_spans` sorts all events globally and threads a single `current`, so any `start`
closes whatever span is open regardless of `session_id`. Session A's span ends the
moment session B starts one; A's Stop hook then refuses to write its own `end`
(`worktree.py` session-scoped `span-end`), so A's span is never reopened. Worse, when
`HM_SESSION_ID` is absent (documented WSL2 env-file failure) B's span carries
`session_id=None`, `_match` returns `degraded=True`, and **B's stage claims A's turns**.

Concurrent sessions are an explicitly supported workflow in this project, with three
prior contamination incidents on adjacent machinery.

**Fix:** partition events by `session_id` before chaining; keep session-less events in
their own chain. Add a two-session interleaved test.

### F-03 · P1 · `src/harness_maker/economics.py` — capped turns are resurrected by lower-precedence sources
*Voices: codex P1 + antigravity P1.*

`attribute_turns` leaves `stages[idx] = None` for a capped turn, so the turn is
indistinguishable from "no span claimed it". `find_boundaries` then opens a run over it
and `inferred`/`adjacency` can attribute it — while `capped_turns` still counts it. A
turn can therefore be reported as *both* capped and attributed, which contradicts
ADR-003's "turns past a cap stay unattributed" and its terminal-cap guarantee.

**Fix:** exclude capped indices from boundary detection and from the adjacency estimate,
forcing `source = "none"` for them.

### F-04 · P1 · `src/harness_maker/wrapup_receipt.py:217,245` — receipt-controlled paths are not confined to the repo
*Voices: security-reviewer P1 + codex P1 (antigravity filed it at P2 — M-05).*

`documents_updated` and `record_path` are free strings from an LLM reply, joined as
`base / rel` with no validation. `Path("/base") / "/etc/hostname"` is `/etc/hostname`;
`base / "../../x"` escapes upward. A delegate that appended no record can claim
`record_path: "/dev/null"` and reconciliation returns `ok`, after which the verify
template instructs the main loop to **adopt the receipt's `result`**.

**Fix:** reject absolute paths and `..` parts before joining, and require
`(base / rel).resolve().is_relative_to(base.resolve())`. Mirror
`SecondBrainFolder._reject_absolute_or_empty_path`.

### F-05 · P1 · `src/harness_maker/wrapup_receipt.py:243` — an empty verify receipt reconciles clean
*Voices: code-reviewer P1 + codex P1 (antigravity at P2 — M-06).*

The verify checks are conditional (`if receipt.record_path:`, `if failed and result ==
PASS`), and `stage` is an unvalidated free string that `parse_receipt` never compares
against the requested stage. A receipt of `{schema_version: 1, stage: "verify"}` with no
`checks`, no `record_path` and `result: ""` produces **zero mismatches** — promotion
arithmetic is 0 == 0 — so `ok` is True and the CLI exits 0. The verify template then
adopts an empty-string verdict and applies the stage's normal exit-code rules.

The module docstring already names this state as the thing it exists to prevent.

**Fix:** add `--stage` to the CLI and reject a stage mismatch; for `stage == "verify"`
emit mismatches for empty `result`, empty `checks`, and absent `record_path`.

## ⚠️ Weak Consensus

### W-01 · P2 · `src/harness_maker/economics_source.py:382` — `pending_user` state machine
*codex P2 + antigravity P2 — surfaces match, mechanisms diverge.*

- codex: an assistant line later discarded (no usage / foreign cwd / outside window)
  still clears the flag, so the next *retained* turn loses it.
- antigravity: a synthetic user line arriving after a human one overwrites the flag to
  `False`.

Both land on the same state machine; they disagree about which transition is wrong, and
the two readings imply opposite fixes. Kept for manual judgment — the codex reading is
arguably correct behaviour (an intervening assistant turn genuinely breaks adjacency),
while the antigravity reading is a real but rare ordering.

## 📝 Manual-Only Findings

| id | sev | file | summary |
|---|---|---|---|
| M-01 | P0 | `stage_spans.py:122` | *(antigravity)* Same defect as F-02, filed one tier higher |
| M-02 | P1 | `wrapup_receipt.py:166` | *(security-reviewer)* `_vault_slugs` rglobs the whole vault, bypassing `second_brain.folders`; `stem.split("-",1)[1]` turns a user's `my-notes.md` into slug `notes` |
| M-03 | P1 | `stage-delegate_body.md.j2:26` | *(security-reviewer)* No untrusted-data framing on the only **write-capable** new asset, while the same diff added it twice to the read-only `/hm:metrics` surface |
| M-04 | P1 | `wrapup.md.j2:78`, `verify.md.j2:347` | *(security-reviewer)* Receipt file path unspecified; sibling steps 5.1/5.6 in the same file mandate a fresh temp file outside the repo — a fixed name collides under concurrent fleet wrapups |
| M-05 | P1 | `wrapup_receipt.py:217` | *(code-reviewer)* `documents_updated` / `record_path` resolved against **base**, but the delegate writes in the **worktree** — the normal delegated path false-fails on every run |
| M-06 | P1 | `wrapup_receipt.py:104` | *(codex)* Mixed fenced + unfenced payloads: the fenced branch short-circuits, so the "refuse if more than one" promise does not hold |
| M-07 | P1 | `run_classify.py:180` | *(antigravity)* `turns[i-1]` may belong to a peer session, so a run's own preceding stage is not found under concurrency and a legitimate continuation is refused |
| M-08 | P1 | `wrapup_receipt.py:95` | *(antigravity)* Brace counting ignores string literals |
| M-09 | P2 | `run_classify.py:245` | *(code-reviewer)* A `continuation` inherits an **unbounded** run — no turn or duration cap, unlike both sibling attribution paths |
| M-10 | P2 | `wrapup_receipt.py:174` | *(code-reviewer)* Same as M-02 at a lower tier; suggests matching on `hm_source`/`project_id` frontmatter |
| M-11 | P2 | `wrapup_receipt.py:225` | *(codex)* Duplicate promoted/skip slugs inflate the arithmetic check |
| M-12 | P2 | `wrapup_receipt.py:107` | *(codex)* Same as M-08 at a lower tier |
| M-13 | P2 | `synthesize.py:144` | *(security-reviewer)* `stage-delegate` renders unconditionally although `delegation.stages` is documented as the rollback |
| M-14 | P3 | `economics.py:465` | *(codex)* Length-mismatched attribution sequences raise `IndexError` rather than a described error |

## 🤝 Disagreements

Four (tabulated in Round 1 Summary): the same defect filed at different severity tiers
by different voices. Per Step 4c these are **not** bridged — no middle severity is
synthesized. They surface through `human_review_needed`.

One substantive disagreement, W-01, where the mechanism itself is contested.

---

## Auto-Fix Loop

### Iteration 1 (Grade: D → not re-graded; see the note below)

Applied all 5 consensus-passed findings plus 9 `manual-only` ones the orchestrator
**verified against the code first** — a single-source finding stops being unverified
once it is reproduced, and leaving a confirmed defect unfixed to honour a tag would be
the wrong reading of the rule.

| # | sev | finding | status |
|---|---|---|---|
| 1 | P0 | F-01 `--root` unresolved | Applied — reproduced before and after (0 → 393 boundaries) |
| 2 | P1 | F-02 global `current` span | Applied |
| 3 | P1 | F-03 capped turns resurrected | Applied — **and immediately broke `direct` attribution**; the edit consumed the `if turn.attribution_skill is not None:` line and ground-truth turns fell to `none`. Caught by the existing suite within one run. Fixed. |
| 4 | P1 | F-04 receipt path escape | Applied |
| 5 | P1 | F-05 empty verify receipt | Applied |
| 6–14 | P1–P3 | M-02/03/04/05/06/07/08/09/11/12/14 | Applied |
| — | P2 | M-13 | Resolved as a **documentation** fix — the asset renders unconditionally by design; the accurate statement is what the switch removes |

Also tightened `test_verify_delegation._receipt`, whose defaults (`checks=()`,
`record_path=None`) were the exact vacuous shape F-05 describes — so every test built
on it was measuring a receipt that could not fail for the reason it named.

Full suite green. Both reviewers re-run.

### Iteration 2 (re-review found 6 new findings, 2 of them self-inflicted)

The re-review was asked two questions, not one: *does each fix close its finding* **and**
*did the fixes introduce anything new*. The second question earned its place.

| id | sev | finding | source | status |
|---|---|---|---|---|
| R2-01 | P1 | `(capped)` sentinel read as a stage name → fabricated `by_stage["(capped)"]` row | **introduced by the F-03 fix** | Fixed — `capped` is its own argument, no sentinel |
| R2-02 | P1 | `boundaries` CLI and `economics report` derive different boundary UUIDs → recorded verdicts silently discarded | **introduced by the F-03 fix** (applied to one of two callers) | Fixed — one shared `boundary_inputs` helper |
| R2-03 | P1 | `span-end` reads the globally-last event, so a peer suppresses your close | pre-existing, **unmasked by F-02** (a peer's start used to close your span as a side effect) | Fixed — session-scoped selection |
| R2-04 | P1 | M-07 narrowed, not closed: the back-scan stopped at an unattributed peer-split fragment | incomplete fix | Fixed — scan continues past unattributed same-session turns, **but stops at a capped one** (skipping it would re-extend a span past its terminal cap — caught by a test of the R2-01 fix) |
| R2-05 | P1 | `_VAULT_NOTE_TYPES` omitted `journal`, so a truthful promotion reconciled as fabricated | **introduced by the M-02 fix** (hand-copied 5 of 6 enum values) | Fixed — derived from `SecondBrainNoteType` |
| R2-06 | P2 | A session-less span outranks an exact session match on list order | pre-existing | Fixed — exact-session-first two-pass selection |
| M-02 residual | P2 | Unconfigured `folders` fell back to walking the whole vault | incomplete fix | Fixed — no folders ⇒ no slugs |

The security re-review's verdict on M-05 is the one worth keeping: **"closed in the
library and open in the product."** `reconcile` gained `worktree_root` with two passing
unit tests and *no caller passed it*, so `doc_root` stayed at base — byte-identical to
the behaviour the parameter was added to fix. Both templates now pass `--worktree`, and
a render test pins it.

Full suite green (`rc=0`, verified from the log rather than the exit code).

## Review Iteration Summary

| Iteration | Grade | Fixes applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | **D** | — | 21 | — |
| 2 | not re-graded | 14 | — | 6 |
| 3 | not re-graded | 7 | — | 0 (no re-review) |

**Final grade: not claimed.** Every Round 1 consensus-passed P0/P1 is closed and
verified — F-01 by reproduction, the rest by the re-review — but the **Iteration 2
fixes were never put in front of a reviewer**. Claiming grade A here would assert a
verification that did not happen, which is the substitution this task has now caught
itself making four times.

**Status: CHANGES_REQUESTED**
**`human_review_needed`: true**

Why the flag is set, concretely:
1. Iteration 2's seven fixes are unreviewed. Two of Iteration 1's fixes introduced
   defects, so the prior for "a fix round is clean" is measurably poor.
2. Eight Round 1 `manual-only` P0/P1 findings existed, including antigravity's **P0**
   for the same defect the filter graded P1 — the tier rule kept them apart.
3. The delegated paths (`delegation.stages`) have never executed. Every guarantee about
   them is a render-grep plus a unit test, not an observation.

**What a human should look at first:** `stage_spans._build_spans` +
`worktree._cli_span_end` together — they are the pair the concurrency argument runs
through, they changed twice, and the second change was only needed because the first
removed an accidental compensation nobody had documented.
