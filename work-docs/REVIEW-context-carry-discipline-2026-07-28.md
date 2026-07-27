---
type: review
task_slug: context-carry-discipline
reviewed_at: 2026-07-28
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: context-carry-discipline
  computed_at: 2026-07-28
---

# REVIEW — context-carry discipline

Two phases, both landed. Phase 1 committed the meter and re-took the baseline with it;
Phase 2 shipped the two rules to all four rendered variants plus this repo's own CLAUDE.md.

## Findings

### F1 — ADR-001 paid for itself on its first run

The sequencing decision (meter before instruction) existed to make the eventual before/after
comparison committed-code vs committed-code. It immediately found a real discrepancy:

| | committed | scratchpad |
|---|---:|---:|
| `write_after_read` duplicate chars | 877,409 | 877,409 |
| `grep/rg` | **10.8%** | **8.3%** |
| `pytest` | 3.5% | 2.3% |

The scratchpad computed each Bash kind's share *within Bash* entry-weighted, then multiplied
by Bash's **carry-weighted** total — two weightings multiplied together. The committed meter
divides by `total_chars` throughout. **The committed figure is correct and the lever is
bigger than the RESEARCH document claimed:** search + inspection is 16.0%, not 13.5%.

Had the instruction shipped first, that 2.5pp would have been indistinguishable from an
effect. The RESEARCH table is corrected; the discrepancy is recorded in the PLAN rather than
tuned away, as ADR-001 requires.

### F2 — three real gate gaps, all found by the mutation receipt

First run: 10 mutants, 4 survivors. Three were holes in passing tests:

- **M4** — `_PRECONDITION` accepted the bare token `Read`, which the rewrite bullet contains
  in its *explanation* ("requires a prior `Read`"). So the conditional clause could be
  deleted — turning the rule into the bare "prefer Edit", which PLAN ADR-004 establishes is
  **false** for 69% of Write traffic — while the gate stayed green. Fixed to the clause
  itself, one phrase per locale.
- **M5** — **a Korean render emitting English passed every assertion.** The required tokens
  (`rg`, `grep`, `Edit`, `Write`, `| head`) are identifiers, identical in both branches by
  design, so nothing distinguished them. Forcing the locale branch to `False` was silent.
  Fixed with an explicit both-directions language assertion.
- **M10** — dropping the tool_use INPUT half of the Bash accounting left the tool_result
  half, so both keys stayed present and every number silently halved. Fixed with a
  hand-derived character count from the fixture (26 + 13).

Second run: **10 / 10 killed, 0 survivors.**

### F3 — the mutant-that-doesn't-reach-the-artifact defect, third phase running

**M6** survived twice for two different reasons, neither of them a gate weakness:

1. First attempt replaced only the bullet's lead phrase, leaving every required token in the
   body. Identical in shape to `PLAN-token-economy-step-pruning` Phase 4's M6 and Phase 5's
   M1/M5.
2. Second attempt used the `{#`/`#}` comment trick that works on the `.j2` partial — but
   `CLAUDE.md` is **markdown, not Jinja**, so those are literal characters and deleted
   nothing.

Only a whole-section removal actually made the artifact lose the rules, and then
`test_this_repo_carries_its_own_rule` killed it. **A mutant must be verified to change the
artifact under assertion before its survival means anything**, and that check has now been
skipped in three consecutive phases.

### F4 — two test-construction errors, both caught by running rather than reading

- AC-006 was first written against `render()`. Preservation lives in `block_merge.merge`;
  `render()` writes a fresh tree and never merges. The test went red on user content the
  render path was never responsible for — **a red that says nothing about the product**.
- The section-slice regex terminated only at `<!-- @hm:user`, which is how the *rendered*
  variants end. This repo's hand-maintained CLAUDE.md is followed by another `##`, so the
  slice silently failed to match and AC-003 asserted nothing about its own subject.

### F5 — the locale mechanism was verified, not reasoned about

PLAN ADR-002 predicted that `ja` selects the `.en` file while `config.locale` stays `ja`,
so the in-partial branch is false and English renders. The PLAN required execute to confirm
this with a third-locale render rather than argue it. Six renders (2 presets × en/ko/ja) all
behave as predicted, and `test_the_unknown_locale_fallback_renders_the_english_rules` keeps
it that way.

Also verified rather than assumed: `synthesize.py:474` passes `{}` as the per-file context
for claude-md, so the branch key had to be `config.locale`, not a bare `locale` that does
not exist there.

## Grade

**A.** AC-001..006 green across six renders; 10/10 mutants killed; full suite `rc=0`; ruff,
ruff format, `mypy --strict` clean; snapshot delta exactly `../CLAUDE.md` with zero
machine-path leaks. Instruction size 1,012 chars (en) / 612 (ko) against the 2,000 cap.

**Two caveats, both structural rather than incidental:**

1. **Single-voter review.** No reviewer agents were dispatched — the session operates under
   a standing constraint against agent dispatch. Every finding above is mine about my own
   work, so all of it is `manual-only` by construction. As in the previous three phases,
   the findings that changed code (F2) came from the mutation receipt, not from reading.
2. **R1 is unmitigated and known.** Nothing here can detect whether the prose changes
   behaviour. That is the direct consequence of the prose-only shape the user chose over a
   prose+observability option, recorded in the SPEC's Accepted Risks. AC-004 is what makes
   it answerable later, and answering it is the follow-up below — not a conclusion this
   review is entitled to draw.

## Follow-ups

1. **Re-run `economics composition` once a comparable corpus has accumulated** and compare
   against the committed baseline (16.0% search+inspection, 3.8% duplication). This is the
   only thing that will say whether the work was worth its own bytes.
2. Lever 2 — resetting context before `verify`/`wrapup` ($390 of $697 carry) — still needs
   its own SPEC; it is an architectural decision, not a prompt change.
3. Re-derive `PLAN-token-economy-step-pruning` ADR-014's 119,000 ceiling (still open from
   Phase 4; current margin 40 chars).
