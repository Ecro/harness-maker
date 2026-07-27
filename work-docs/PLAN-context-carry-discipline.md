---
type: plan
task_slug: context-carry-discipline
spec: "[[SPEC-context-carry-discipline]]"
research_doc: "[[RESEARCH-context-carry-economics-2026-07-28]]"
status: draft
created: 2026-07-28
---

# PLAN — context-carry discipline

Ship two prose rules to every rendered harness, and commit the measurement that will later
say whether they worked. Small surface, one genuinely load-bearing sequencing decision.

## 🧭 Architecture Decisions

### ADR-001: the meter lands BEFORE the instruction, and re-takes the baseline
**Status:** Accepted.
**Context:** The RESEARCH baseline (13.5% search/inspection, 3.8% Write-after-Read) was
produced by four throwaway scripts in a scratchpad directory. AC-004 commits an equivalent
as `economics composition`. If the instruction ships first, the "before" number comes from
code that no longer exists and the "after" from committed code, and any disagreement
between the two implementations is indistinguishable from an effect.
**Decision:** Phase 1 ships the subcommand and **re-measures the current corpus with it**,
recording the committed-code baseline in this PLAN. Phase 2 ships the instruction. The
comparison is then committed-code vs committed-code.
**Consequences:** ✅ The one number this work will eventually be judged on is produced twice
by the same implementation. ⚠️ If the committed meter disagrees with the scratchpad figures,
**that discrepancy is a Phase 1 finding and must be reported, not reconciled by adjusting
the new code to match the old numbers.**
**Rejected:** Landing both in one commit (cheaper, but leaves the baseline un-reproducible).

### ADR-002: one shared partial, four includes — not four copies of the prose
**Status:** Accepted.
**Context:** `templates/claude-md/` has four files (Production/Side × en/ko). The rule text
is ~1,000 characters. Pasting it four times is a drift surface, and this repo has shipped
that failure before: the `communication_variant` work exists because a per-file convention
silently diverged.
**Decision:** `templates/agents/_partials/context_discipline.md.j2`, included by all four —
the same idiom `output_language.md.j2` already uses in these exact templates. Locale is a
`{% if config.locale == 'ko' %}` branch **inside** the partial, so en and ko sit adjacent
and a change to one is visibly a change to the other or visibly not.

> **Verified, not assumed:** `synthesize.py:474` passes `{}` as the per-file context for
> claude-md, so nothing is available from the call site. `config` reaches these templates as
> a renderer global — proven by `output_language.md.j2`, which reads `config.locale` and is
> already included by `Production.en.md.j2:23`. The branch key is therefore
> **`config.locale`**, not a bare `locale`, which does not exist here.
>
> Locale also selects the *file* (`_localized(stem, locale)`), so the two mechanisms must
> agree. They do, including for the documented unknown-locale fallback: `ja` selects the
> `.en` file, `config.locale` is `ja`, the `== 'ko'` branch is false, and the English text
> renders. Execute must confirm this with a third-locale render rather than reasoning about
> it.
**Consequences:** ✅ AC-001's four-variant assertion tests four *includes* of one source,
so the realistic failure it catches is a missing include, which is exactly the failure
mode. ⚠️ The partial is a fifth file in a directory named `agents/` that is not agent-only;
that misnomer predates this work and is not fixed here.
**Rejected:** Two partials (en/ko) — puts the translations in different files, which is how
they drift.

### ADR-003: bound the output, do not ban the tool
**Status:** Accepted.
**Context:** `rg`/`grep` output is 8.3% of carried context over 1,536 calls; file inspection
(`cat`/`head`/`ls`/`find`/`wc`) is 5.2% over 840. The obvious stronger rule is "use the Grep
tool, not `rg` in Bash" — the tool has `head_limit` built in.
**Decision:** The rule requires a **bound on output**, and recommends the Grep tool where it
fits, but does not forbid `rg`. Two reasons, both from the data: the measured problem is
unbounded *output*, not tool choice — a `rg` piped through `head` costs what a Grep call
costs; and `rg` in Bash composes with other commands in one call, which the tool cannot do,
so a ban would trade context bytes for extra round trips.
**Consequences:** ✅ The rule is about the thing that was measured. ⚠️ It is weaker than a
ban and depends on the reader applying a limit each time — which, under the prose-only
shape chosen for this work, is the whole bet.
**Rejected:** Banning `rg` in Bash (stronger, but unsupported by the measurement and a large
workflow opinion to ship to every user); a numeric cap on total output per call (not
expressible as prose an agent can follow at call time).

### ADR-004: the rewrite rule states its precondition, or it is false
**Status:** Accepted.
**Context:** 69% of `Write` bytes create new files. "Prefer Edit over Write" as a bare
instruction is wrong for the majority of Write traffic and would be correctly ignored.
**Decision:** The rule is conditional and says so: use `Edit` when the file is **already in
context from a Read**; `Write` is for new files and for rewrites where most of the content
actually changes. AC-002 asserts the precondition is present, so a future simplification to
the bare form fails the gate.
**Consequences:** ✅ The instruction is true as written. ⚠️ A conditional rule is more
tokens than an unconditional one; that is bought inside AC-005's 2,000-character cap.
**Rejected:** The bare "prefer Edit" (shorter, false).

### ADR-005: `composition` reuses the economics transcript reader, and takes a `--root`
**Status:** Accepted.
**Context:** Four scratchpad scripts each re-implemented transcript iteration.
`harness_maker.economics` already owns a reader with a `--transcripts-dir` override for
testing, and `doctor` proves it is exercised.
**Decision:** `composition` is a subcommand of `economics`, sharing that reader and its
override. It reads local transcripts only — the zero-network contract is unchanged.
**Consequences:** ✅ One reader, one place for path/format drift. ✅ AC-004's fixture arm is
possible because the override already exists. ⚠️ `economics.py` grows; it is already ~2k
lines and tier-2 for mutation.
**Rejected:** A standalone `scripts/` file (this repo is Python-module-only, no loose scripts).

### ADR-006: AC-002's required tokens are pinned HERE, before the text is written
**Status:** Accepted.
**Context:** AC-002 says each rule must name its tools and a concrete bound. If the token
list is chosen during execute, it will be chosen by reading the text just written — the
assertion then cannot fail, which is precisely the defect
`PLAN-token-economy-step-pruning` ADR-021 recorded twice in three phases (an assertion green
before the change it gates).
**Decision:** The required tokens are fixed now, and the rule text must be written to satisfy
them rather than the reverse:

| arm | must contain |
|---|---|
| search rule — tools | `rg`, `grep`, and at least two of `cat` / `head` / `ls` / `find` |
| search rule — bound | a literal `head` **pipe form** (`\| head`) or `head_limit`, **and** a numeral |
| rewrite rule — alternative | `Edit` and `Write` |
| rewrite rule — precondition | a phrase naming the prior read (`already read` / `already in context` / `Read`) |

**Consequences:** ✅ The gate is falsifiable: the mandated mutant (replace the rule body with
an exhortation, keep the heading) drops every token and fails. ⚠️ The token list constrains
phrasing, including the Korean branch, which must carry the same literals — they are
identifiers and command names, so this is consistent with the repo's "code and identifiers
stay English" rule.
**Rejected:** Deriving the tokens from the written text at execute time (unfalsifiable);
a judgment AC with a rubric (an independent-reviewer dispatch per wrapup for a four-token
check).

## 📝 Implementation Plan

### Phase 1 — `economics composition` + re-measured baseline

- `depends_on`: `[]`
- `parallel_group`: `meter`
- `merge_hazards`: touches `economics.py` only; no template surface, so it cannot conflict
  with Phase 2.
- **Scope (in):** `economics composition` subcommand (by-category share, by-Bash-kind share,
  Write-after-Read duplication); a transcript fixture under `tests/fixtures/` with a
  hand-counted duplicate figure; AC-004's test; the re-measured baseline recorded in this PLAN.
- **Scope (out):** any CLAUDE.md or template change; any change to `report`/`stages`/`doctor`.
- **Exit criterion:** AC-004 green including the non-vacuity arm (the fixture's duplicate
  count is computed, not merely well-shaped); the subcommand run against the live corpus and
  its numbers written into this PLAN next to the scratchpad figures, **with any discrepancy
  reported rather than reconciled** (ADR-001).
- **Risk:** `low` — read-only, additive subcommand.
- **Rollback:** revert this phase's own commit.

#### Phase 1 baseline — committed meter vs scratchpad (ADR-001's discrepancy check)

`economics composition --root /home/noel/harness-maker`, 2026-07-28. Corpus 23,345,929
chars against the scratchpad's 23,041,855 — **+1.3%, because this session added turns
between the two runs**, which bounds how far any figure may legitimately have moved.

| | committed | scratchpad | |
|---|---:|---:|---|
| `write_after_read` duplicate chars | **877,409** | **877,409** | exact |
| ...as share of all context | **3.8%** | **3.8%** | exact |
| ...calls | 66 of 413 | 66 of 407 | +6 Writes this session |
| `tool_call_input` | 37.4% | 38.2% | within corpus drift |
| `tool_result` | 29.4% | 30.9% | within corpus drift |
| `slash-command-body` | 18.2% | 17.6% | within corpus drift |
| **`grep/rg`** | **10.8%** | **8.3%** | **discrepancy** |
| **`pytest`** | **3.5%** | **2.3%** | **discrepancy** |
| `harness_maker CLI` | 4.3% | 3.7% | discrepancy |
| `assistant_text` | 5.5% | 4.1% | weighting, below |
| `system-reminder` | 2.7% | 1.6% | weighting, below |

**The discrepancy is in the scratchpad arithmetic, not the committed code — reported rather
than reconciled, per ADR-001.** Two distinct causes:

1. **Mixed weighting in the per-Bash-kind figures.** The scratchpad computed each kind's
   share *within Bash* entry-weighted (`grep/rg` = 29.7% of Bash) and multiplied it by
   Bash's **carry-weighted** total (27.9%) to reach "8.3% of all context" — two numbers
   computed under different weightings, multiplied together. The committed meter divides by
   `total_chars` throughout. **The committed figure is the correct one, and lever 1 is
   bigger than the RESEARCH document claimed, not smaller.**
2. **Residency weighting, deliberately absent.** `assistant_text` and `system-reminder` had
   carry ratios of 0.75 and 0.59 — they enter late or are short-lived, so carry-weighted
   sits below entry-weighted. `context_composition` implements entry weighting only, with
   the reason in its module docstring (the two agreed within ±5% on every category). These
   two rows are that documented choice surfacing, not an error.

**Consequence:** the RESEARCH document's per-Bash-kind table is corrected to the committed
figures. Search + inspection is **16.0%** of carried context (10.8% + 5.2%), not 13.5%. The
ranking is unchanged. Had the instruction shipped first, this 2.5pp would have been
indistinguishable from an effect — which is the whole of ADR-001's argument, arriving on the
first run.

### Phase 2 — the two rules

- `depends_on`: `[1]`
- `parallel_group`: `serial-render`
- `merge_hazards`: adds a partial and edits four `templates/claude-md/*.j2` plus this repo's
  `CLAUDE.md`. Re-renders every harness's CLAUDE.md, so snapshot fixtures move.
- **Scope (in):** `templates/agents/_partials/context_discipline.md.j2` (en + ko branches);
  four `{% include %}` lines; this repo's own `CLAUDE.md`; AC-001/002/003/005/006 tests;
  regenerated snapshot fixtures.
- **Scope (out):** reviewer agent bodies; stage templates; `harness.yaml` schema (no flag —
  the user chose unconditional ship); any hook.
- **Exit criterion:** AC-001/002/003/005/006 green; the snapshot delta is **exactly** the
  CLAUDE.md entries and nothing else; the rendered section measured under 2,000 chars in all
  four variants; `@hm:user:*` content preserved on a re-render over an existing file.
- **Risk:** `low-medium` — the risk is not breakage but writing an instruction that reads
  well and changes nothing, which no test in this plan can detect.
- **Rollback:** revert this phase's own commit.

## 🧪 Testing Strategy

- **Render** — `tests/render/` (it owns the install-ref pin) for AC-001/002/005.
- **Unit** — `tests/unit/` for AC-004's subcommand against the fixture.
- **Structural** — AC-003's assertion on the repo's own CLAUDE.md; AC-006 extends the
  existing block-merge test.
- **Mutation (ADR-010 of the prior plan, carried forward)** — per AC, delete the code and
  name the test that dies, in the commit message. Two mutants are mandatory because they are
  the ones this plan can plausibly get wrong: **(a)** replace the rule text with an
  exhortation that keeps the heading — must fail AC-002 while still passing AC-001;
  **(b)** drop one of the four `{% include %}` lines — must fail AC-001 for that variant only.
- **Determinism** — `freeze_time` + the install-ref pin, per the existing conventions.

## ⚠️ Risks & Mitigation

| # | risk | likelihood | impact | mitigation |
|---|---|---|---|---|
| R1 | **The instruction reads well and changes nothing.** The prose-only shape cannot detect this. | **high** | medium | Not mitigated by any test here — only by re-running `economics composition` later (SPEC AC-004, ADR-001). Stated in the SPEC's Accepted Risks rather than hidden. |
| R2 | The criterion degrades to "a section exists" | medium | high | AC-002's tool + bound + precondition arms, plus mutant (a) |
| R3 | A variant silently misses the rule | medium | medium | AC-001 asserts all four; mutant (b) |
| R4 | The instruction's own cost exceeds its benefit | low | medium | AC-005's 2,000-char cap, set before the text was written |
| R5 | The committed meter disagrees with the scratchpad baseline | medium | medium | ADR-001 makes the discrepancy a reportable Phase 1 finding, not something to tune away |
| R6 | Shipping one operator's habit to every user | **certain** | low-medium | Stated in the SPEC's Open Questions; the evidence base is narrower than the blast radius and this is recorded, not argued away |
| R7 | Snapshot regeneration inside a worktree bakes machine paths | medium | high | `[fail:test] snapshot-regen-inside-worktree` count:13; `tests/render/conftest.py` pin + audit which entries changed |

## ❓ Open Questions

- **Should the ko text be validated for semantic equivalence, and by whom?** AC-001 checks
  presence, not meaning; a machine cannot check the translation. Current answer: the en and
  ko branches live adjacent in one partial (ADR-002) so divergence is visible in review. If
  that proves insufficient, a judgment AC with a rubric is the next step — deliberately not
  added up front, since a judgment AC costs an independent reviewer dispatch per wrapup.
