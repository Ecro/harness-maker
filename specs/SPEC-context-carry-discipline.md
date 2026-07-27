---
type: spec
slug: context-carry-discipline
status: draft
test_framework: pytest
research_doc: "[[RESEARCH-context-carry-economics-2026-07-28]]"
created: 2026-07-28
---

# SPEC — context-carry discipline

## 🎯 Intent

Cut carried context by instructing the **main loop** to stop putting two specific kinds of
avoidable bytes into it: unbounded search/inspection output, and file bodies the context
already holds.

Aimed at the main loop deliberately. It is **87.9% of spend at 70.0% carry**; the reviewer
subagents that `PLAN-token-economy-step-pruning` Phase 3 instructed are 12.1% at 35.2%, and
`Read` — the traffic that phase bounded — is 7.8% of carried context. The measurement is in
`work-docs/RESEARCH-context-carry-economics-2026-07-28.md`; every number below comes from
23.0M chars of local transcript, carry-weighted.

## 📈 Outcomes

| what | measured today | target |
|---|---:|---|
| `grep`/`rg` + file-inspection output | **13.5%** of carried context, 2,376 calls | materially lower |
| `Write` bodies duplicating an earlier `Read` | **3.8%**, 66 of 407 calls | ~0 — it is pure waste |
| the instruction's own carried cost | 0 | **bounded and stated** |

No percentage target is committed. The honest position is that a prose instruction's effect
on behaviour is not predictable in advance, so a number here would be invented. What IS
committed is that the same measurement is re-runnable, so the effect becomes knowable
afterwards rather than never.

## 📋 In-Scope Scenarios

**S1 — the rules render into every harness.** Given a render at any preset × locale
(Production/Side × en/ko), when `CLAUDE.md` is produced, then it contains a context-discipline
section naming both rules.

**S2 — the rules are actionable, not exhortations.** Given the rendered section, when it is
read, then each rule names the concrete tools it governs and a concrete limit or alternative
— not "be mindful of context".

**S3 — harness-maker carries its own rule.** Given this repo's hand-maintained `CLAUDE.md`
(not rendered from the templates), when the change lands, then it carries the same two rules.
The measurement came from this repo; it is the first place the rule must apply.

**S4 — the measurement is re-runnable.** Given a project with Claude Code transcripts, when
`python -m harness_maker.economics composition` is run, then it reports the carried-context
share by category and by Bash command kind, and the Write-after-Read duplication rate — the
same numbers the RESEARCH document reports, from committed code rather than a scratchpad script.

**S5 — the instruction pays for itself in principle.** Given the rendered section, when its
size is measured, then it is ≤ 2,000 characters per CLAUDE.md. Phase 3 spent 3,765 characters
of instruction against an unmeasured runtime saving; this SPEC states its own cost up front.

**S6 — user content survives.** Given a CLAUDE.md with content inside `@hm:user:*` markers,
when the harness is re-rendered with this change, then that content is preserved.

## 🚫 Non-Goals

- **Enforcement.** No PreToolUse hook, no denial, no counting. Chosen explicitly by the user
  over a prose+observability option. See Accepted Risks.
- **Reviewer agent bodies.** `Read` is 7.8% of carried context and the reviewers are the
  cheap population; re-instructing them is not where the bytes are.
- **Lever 2 — resetting context before `verify`/`wrapup`** ($390 of $697 carry). It needs an
  architectural decision about session/compaction boundaries and gets its own SPEC.
- **Lever 3 — slash-command bodies** (17.6%). `PLAN-token-economy-step-pruning` Phase 4 is
  the evidence for how hard that is to move; the ratchet already exists.
- **Retiring the `Write` tool or discouraging it generally.** 69% of `Write` bytes create new
  files, which is irreducible.

## ⚙️ Constraints

- Context lint: CLAUDE.md ≤ 200 lines (Side) / 500 lines (Production). Current rendered
  template is 31 lines, so budget is not scarce — S5's cap is about carried cost, not the lint.
- English is the default locale; the `ko` variants must be semantically equivalent, not a
  looser paraphrase.
- `templates/claude-md/*.j2` renders into user projects. Per the domain-content-ownership
  rule, this is harness operating discipline (ours), not domain standards (the user's) — the
  distinction is why it is admissible to ship at all.
- No new runtime machinery. The `composition` subcommand reads local transcripts only, on
  the existing zero-network contract.

## ⚠️ Accepted Risks

**The chosen shape is prose-only, which is the shape whose effect Phase 3 could not
measure.** Recorded, not re-litigated: the user was shown that comparison and chose it. The
consequence is that the instruction's cost is certain and its benefit is not, in advance.

S4 is what keeps this from being unfalsifiable. It does not make the instruction enforced;
it makes the outcome *observable afterwards* by committing the measurement. Without S4 this
SPEC would ship a cost with no path to ever learning whether it bought anything, and that is
the failure mode this whole line of work exists to stop repeating.

## ✅ Verification Criteria

### AC-001: the rules render into every preset and locale

**Given** a render at each of Production/Side × en/ko
**When** `CLAUDE.md` is produced
**Then** it contains a context-discipline section naming **both** rules — bounded search
output, and Edit-over-rewrite for a file already in context
**And** the check is over all four variants, not one, so a ko-only or Side-only omission fails

### AC-002: each rule names a tool and a concrete limit or alternative

**Given** the rendered section
**When** its text is read
**Then** the search rule names the governing tools and a concrete output bound, and the
rewrite rule names `Edit` as the alternative to a full-file `Write` of an already-read file
**And** an exhortation with no tool and no bound ("be mindful of context") does not satisfy it

### AC-003: harness-maker carries its own rule

**Given** this repo's hand-maintained `CLAUDE.md`, which is NOT rendered from the templates
**When** the change lands
**Then** it carries the same two rules

### AC-004: the composition measurement is committed and re-runnable

**Given** a directory of Claude Code transcripts
**When** `python -m harness_maker.economics composition` runs against it
**Then** it reports carried-context share by category and by Bash command kind, and the
Write-after-Read duplication rate
**And** it does so from committed code, so the before/after comparison this SPEC depends on
is repeatable rather than a scratchpad artifact that no longer exists

### AC-005: the instruction states and bounds its own cost

**Given** each rendered `CLAUDE.md`
**When** the context-discipline section is measured
**Then** it is ≤ 2,000 characters

### AC-006: user content survives the re-render

**Given** a `CLAUDE.md` with content inside `@hm:user:project-rules` or `@hm:user:extensions`
**When** the harness is re-rendered with this change
**Then** that content is preserved verbatim

## ❓ Open Questions

- **Does the prose change behaviour at all?** Unknowable before shipping, and answerable
  after via S4. Re-run `economics composition` once a comparable volume of sessions has
  accumulated and compare the two shares against 13.5% / 3.8%.
- **Does it generalise beyond this repo?** The 23.0M-char corpus is one project with one
  operator. Shipping to all harnesses is the user's decision; the evidence base is narrower
  than the blast radius, and that is stated rather than hidden.
