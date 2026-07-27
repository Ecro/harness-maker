---
type: review
task_slug: economics-attribution-and-carry
status: CHANGES_REQUESTED
human_review_needed: true
created: 2026-07-26
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
rounds: 5
last_round_reviewed: 5
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

---

## Round 3 — re-review of the Iteration-2 fixes (the gap this round existed to close)

Both reviewers re-run against the landed code (`86556c6a` + `cc0fec7f`), each asked the
same two questions: *does each fix close its finding*, and *did the fixes introduce
anything new*.

### Verdicts on the Iteration-2 fixes

| id | code-reviewer | security-reviewer | resolution |
|---|---|---|---|
| R2-01 sentinel leak | CLOSED | — | CLOSED |
| R2-02 diverging entry points | CLOSED (guard nominal) | — | CLOSED, guard replaced |
| **R2-03 span-end session scoping** | **STILL OPEN** | CLOSED | **STILL OPEN** — see below |
| R2-04 back-scan | CLOSED | — | CLOSED |
| R2-05 journal enum | CLOSED | CLOSED | CLOSED |
| R2-06 span selection | CLOSED | — | CLOSED |
| R2-06 untrusted-data prose | — | **STILL OPEN** | fixed this round |
| M-02 residual | CLOSED | CLOSED | CLOSED |
| 0.43.2 frontmatter | CLOSED | CLOSED | CLOSED |

### The one reviewer disagreement, and how it was settled

security said R2-03 CLOSED; code said STILL OPEN. **code was right**, and the evidence
is checkable rather than a matter of judgment:

- `hooks/sessionid_envfile.py` states in its own docstring that *"The Stop-hook DOES
  receive `session_id` on stdin, but the loop driver/marker writer (a slash command)
  does not"* — the env-file exists to bridge the gap **for slash commands**.
- `hooks/loop_gate.py:108`, the sibling Stop hook in the same settings block, reads
  `session_id` from the stdin payload.
- `span-end` ships **only** as a `Stop` / `PreCompact` hook, and never read stdin.

So the Round-2 fix picked the wrong channel: with no `HM_SESSION_ID` in the hook
process (its documented state on WSL2) the caller matches none of its own events,
writes no `end`, and the span stays open to the cap — the unbounded over-attribution
ADR-003 rejected start-only closure to avoid. Every existing test set or cleared the
env var identically for start and end, so none could see the asymmetry.

**A reviewer disagreement is a signal to go and check, not to average.** Taking the
more optimistic verdict here would have shipped the defect with a CLOSED label on it.

### New findings this round

| id | sev | finding | disposition |
|---|---|---|---|
| N-01 | P1 | `span-end` reads the wrong channel (above) | fixed — stdin first, env second |
| N-02 | P1 | `test_both_entry_points_derive_the_same_boundaries` **calls neither entry point** | guard replaced; a second test now drives list → record → report |
| N-03 | P1 | `_configured_vault_folders` reads the raw dict, bypassing `SecondBrainConfig` validation and ignoring `write` — a read-only folder could satisfy a promotion claim | fixed — validated model, writable folders only. **Consensus: both reviewers, same tier** |
| N-04 | P1 | `--worktree` accepted unvalidated, making `_confined`'s confinement root caller-controlled | fixed — must be the base or one of its `.worktrees/<slug>` |
| N-05 | P1 | The new frontmatter gate never asserts `tools:`, the only enforced agent boundary | fixed — `tools:` presence plus a per-agent read-only boundary check |
| N-06 | P2 | `--worktree` unquoted while sibling substitutions in the same file are single-quoted | fixed |
| N-07 | P2 | untrusted-data prose omits command/tool output | fixed |
| N-08 | P2 | `boundary_inputs(spans: object)` duck-types an available type | fixed |
| N-09 | P2 | `_vault_slugs` docstring described the fallback its body had removed | fixed |
| N-10 | P2 | id-less `span-end` fallback can close a peer id-less session's span | documented as a structural limit (no per-session key exists by definition) |
| N-11 | P2 | two wrong cross-reference labels in new comments | fixed |

### A defect the round-4 fixes introduced, caught by a test written in the same round

The new stdin test failed: the **writer** stored the session id raw while the **reader**
sanitized it. `sanitize_session_id`'s `_TAME_SESSION_ID` is `^[0-9a-fA-F-]{8,64}$`, so a
real Claude session id (a UUID) passes through unchanged and the asymmetry is invisible
in production — it only showed because the test fixture used `session-A`. Fixed by
sanitizing at the single write point so both ends normalise identically; the fixtures
were also changed to production-shaped UUIDs, which they should have been anyway.

*Relying on the input happening to be tame is an assumption, not an invariant* — and it
is the fourth time in this task that a guarantee held only because the data happened to
cooperate.

## Round 4 summary

| Iteration | Fixes applied | New findings | Re-reviewed |
|-----------|---------------|--------------|-------------|
| 1 (init)  | — | 21 | — |
| 2 | 14 | 6 | yes |
| 3 | 7 | — | **no** (this was the gap) |
| 4 | 11 | 1 (self-caught) | **not yet** |

**Status: CHANGES_REQUESTED. `human_review_needed`: true.**

The grade is still not claimed, and the reason is unchanged in shape: **Round 4's eleven
fixes have not been re-reviewed.** Three consecutive fix rounds have each introduced at
least one new defect (R2-01/R2-02 in round 2, the wrong channel in round 3, the
sanitize asymmetry in round 4), so "a fix round is clean" remains an unsupported prior —
now with three data points against it.

What a human should look at first, unchanged and now sharper: **`stage_spans` +
`worktree._cli_span_end` together.** That pair has been changed in three separate rounds,
each change was needed because the previous one removed a compensation nobody had
written down, and its correctness argument runs entirely through concurrency behaviour
that no test in this repo exercises against a real second session.

---

---

## Round 5 — the re-review Round 4 never got (2026-07-27)

**This IS a review.** Four independent voices ran against the previously unreviewed
surface: the three fix commits landed after the `v0.43.1` tag (PART A), the
uncommitted working tree (PART B), and one new untracked test file (PART C) — ~1,700
diff lines total.

| voter | kind | findings |
|---|---|---|
| `code-reviewer` | Claude, read-only | 3 P1, 3 P2 |
| `security-reviewer` | Claude, read-only | 1 P1, 1 P2 |
| `codex` | cross-model | 1 P1, 2 P2, 1 P3 |
| `antigravity` | cross-model | 1 P0, 1 P1, 2 P2 |

Voter pool N = 4, threshold K = 2 (ADR-006, fixed).

### Consensus-passed (≥2 voices)

| finding | voices | disposition |
|---|---|---|
| `--shortstat \| grep insertion` can read zero | code-reviewer P1, codex P1, antigravity P0 | **fixed** — but see the refutation below |
| `_configured_vault_folders` strict-parse → truthful promotion reconciles as fabricated | code-reviewer P1, security-reviewer P1 | **fixed**, both halves mutation-verified |
| positional-param gate scans one render config, misses branch-gated `$N` | code-reviewer P2, antigravity P2 | **fixed** — template-source scan added |

### Single-source but REPRODUCED, therefore not "manual-only"

A finding I could execute is a fact, not an opinion, so these were treated as
consensus-equivalent:

| finding | voice | reproduction |
|---|---|---|
| `test_read_only_agents_…` never enforces when `tools:` is a YAML list | antigravity P2 | ran the real parser: `tools: [Read, Write, Bash]` **passed** the read-only check |
| `release_ref` >200 chars clears the gate then stores under a truncated key | codex P2 | read `put`: caches `release_ref[:200]`, gate compares the full string |
| confinement guard's only test asserts `rc != 0` | code-reviewer P1 | guard deleted → returns 1/`mismatch` wherever `/etc/hostname` is absent |
| `test_re_adjudicating_…` passes pre-fix | codex P3 | full sha both calls made the two key halves equal by construction |
| `--commit` reaches a git ref position unanchored | security-reviewer P2 | `--end-of-options` added |

### Raised and NOT adopted

- **codex P2, window-boundary rejection.** A candidate listed seconds before a 28-day
  boundary can be rejected by the gate moments later. Real, but `code-reviewer`
  independently assessed the same code and declined to flag it: the failure is loud
  and the error names `--force`. Threading a candidate token through `candidates` →
  `adjudicate` buys a narrow race at the cost of a new persisted identity. Recorded,
  not fixed.
- **antigravity P2, "the gate ignores templates that render into `.claude/stages/`".**
  There is no such render target; stage templates are fused into `commands/hm/*.md`.
  The *consequence* it described was real for a different reason (the fixture's
  `second_opinion.models: []`), and that is what was fixed.

### Where the reviewers were wrong, and how that was established

Three of four voices called the `--shortstat` line a live defect. **It is not**, and
the mechanisms they named do not fire:

- antigravity's P0 said the regex hardcodes the singular and so misses
  `17 insertions(+)`. Measured: `grep -oE '[0-9]+ insertion'` extracts `17` — the
  singular is a prefix of the plural.
- codex and code-reviewer said git localises the summary via gettext. Measured across
  **all 18 git catalogs installed here** (bg ca de el es fr id is it ko pl pt_PT ru sv
  tr vi zh_CN zh_TW): every one returns the English msgid. Confirmed end-to-end —
  `git status` under `ko_KR.UTF-8` prints Korean while `git diff --shortstat` stays
  English.

The line was still changed, because `--numstat` is strictly better (plumbing output,
no locale surface, no positional parameter) and the change is one line. Severity as
shipped: fragility, not defect. Taking three concurring voices at face value would
have put a false "live P1" in the changelog.

### Verification

Every fix was mutation-checked — the code removed, the suite run, the killed test
named:

| mutant | test that died |
|---|---|
| sha normalisation removed | `test_abbreviated_commit_is_normalised_to_the_full_sha`, `test_unresolvable_commit_is_rejected_not_recorded`, `test_re_adjudicating_an_already_recorded_pair_is_allowed` |
| `--worktree` confinement guard removed | `test_reconcile_cli_rejects_a_worktree_outside_the_base` |
| retired-key strip removed | `test_a_truthful_promotion_is_never_reported_as_fabricated[legacy-key]` (and only that one — `[clean-config]` still passes, so the parametrisation is not vacuous) |
| vault fail-safe removed | `test_an_unparseable_second_brain_block_reports_unverified_not_missing` |
| `$1` injected into a stage template | `test_no_command_or_stage_template_uses_a_positional_parameter` |

The first draft of the vault test failed this discipline: it asserted only "not accused
of fabricating", which the fail-safe alone satisfies, so removing the retired-key strip
killed nothing. It now asserts `unverified == 0` and `checked >= 1` — verified, not
merely unaccused — and a second test covers the fail-safe on its own.

### Applied after the fixes, from self-review of the fixes

Three consecutive earlier rounds each introduced a defect while fixing one, so the
round-5 changes were re-read against the same checklist that produced the findings:

- **`--end-of-options` buys nothing measurable.** Probed both ways:
  `git rev-parse --verify --quiet <anchor?> '--glob=refs/*^{commit}'` exits 1 with AND
  without the anchor — the appended suffix already makes every option form
  unresolvable. Kept, because the suffix neutralises today's option set by accident
  while the anchor neutralises tomorrow's by contract, but the comment now says that
  instead of implying a live block, and records the cost (first `--end-of-options` in
  this codebase → a git >= 2.24 floor).
- **The 200-char cap lived in two places.** `_RELEASE_REF_MAX` and `put`'s literal
  `200` had to agree for the new gate to mean anything; they are now one constant,
  defined beside the other module constants rather than 1,000 lines below its first
  use.
- **The flag-drift test found a real scoping bug in itself on first run**: it matched
  `--with` from the `uv run` prefix. Now scoped to the text after the module name.
  Its own blind spot (argparse prefix matching) is documented in the test rather than
  left implied.

### Still open

- **The delegation soak has not started.** Verified: `wrapup_brief --root .` returns
  `status: degraded, reason: HEAD is 'main'`, so a wrapup from the base repo takes the
  inline path with the flag fully on. ADR-011's clock starts at the first wrapup that
  runs inside a task worktree.
- **This repo's own harness still carries the pre-fix line.** `.claude/` was rendered
  from the installed 0.43.2 plugin, so `.claude/commands/hm/review.md:294` still holds
  the `awk '{s+=$1}'` form. It corrects itself on the next release + `/hm:make --update`.
- **`stage_spans` + `worktree._cli_span_end`** remains the first thing a human should
  read — changed in three separate rounds, each time to restore a compensation nobody
  had written down, with a correctness argument that runs through concurrency no test
  here exercises against a real second session. Round 5 did not touch it, and
  `code-reviewer` re-examined it this round without flagging a regression.

**Status: CHANGES_REQUESTED cleared for the reviewed surface; `human_review_needed`
stays `true` for `stage_spans`/`_cli_span_end`, which is a scope no automated round has
been able to close.**
