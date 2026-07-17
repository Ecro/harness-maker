---
type: research
task_slug: review-grade-criteria
status: complete
created: 2026-07-01
tags: [harness-maker, research, review-stage, grading, consensus, llm-judgment]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: []
summary: "Grade = deterministic P0/P1 lookup table on LLM-judged severity+consensus inputs; prompt-executed, no Python backstop"
---

# RESEARCH — /hm:review grade criteria & reliability

## 🎯 Recommended Direction

**The grade is NOT "just handed to the LLM," but it is not a pure rule engine either — it is a two-layer hybrid.** A **fully deterministic lookup table** maps two integer counts (`P0_count`, `P1_count` of *consensus-passed* findings) to a letter A–F. But every input to that table — severity classification, which findings "count" (consensus), and severity resolution on disagreement — is **LLM judgment against prose rubrics**. Crucially, even the deterministic table itself is **executed by the LLM at review time from the prompt; there is no Python that counts findings and emits a letter.** So the grade removes "gut-feeling letter grades" but inherits full LLM dependence on severity accuracy and correct counting.

Trust verdict: **moderately trustworthy with multiple, real guardrails — but with named single points of failure** (severity classification, single-reviewer mode, no deterministic count backstop). Details below.

## 🔍 Refinement Decisions

- Discovery lens: **Technical architecture / implementation** (internal harness-maker self-inspection; no `--deep`, no user-workflow/product lens needed — this is a mechanism question, not a roadmap question).

## 🛠️ Approaches Found

This section maps the *actual mechanism* (not competing options) across the two layers, since the user asked "how does it work + is it reliable."

### Layer 1 — Deterministic grade table (rule-based)

| Field | Content |
|-------|---------|
| Approach | Fixed lookup: `(P0_count, P1_count) → letter` |
| Where | `src/harness_maker/templates/stages/review.md.j2:340-363` ("Grade Computation") |
| Rule | Only **`consensus-passed`** findings counted. `P2/P3`, `weak-consensus`, `manual-only` do **not** lower the grade (`review.md.j2:347`) |
| Table | `0P0/0P1→A` · `0P0/1-2P1→B` · `0P0/≥3P1→C` · `1-2P0/*→D` · `≥3P0/*→F` (`review.md.j2:355-361`) |
| Gate | Order `A>B>C>D>F`; threshold met iff `grade ≥ grade_threshold` (default **A**), `models.py:914-918`, config surfaced in `harness-yaml/{Production,Side}.yaml.j2:65` |
| Evidence | Table is prose in the command template; **no Python implements it** — grep for a grade-computing function in `src/harness_maker/*.py` finds only `grade_threshold` storage (`models.py`, `synthesize.py:703`), never a P0/P1 counter → letter mapper |
| Trade-off | Deterministic *specification* removes letter-grade subjectivity, but *LLM-executed* → the model must correctly count consensus-passed P0/P1 and read the table; no runtime backstop verifies the arithmetic |
| Compatibility | Fits the project's "LLM judgment over rules, Python owns only rails" principle (CLAUDE.md §LLM 활용 원칙) |
| Risk | **low** for the mapping logic itself (5-row table), **medium** because it is unenforced by code |

### Layer 2 — LLM-judged inputs (the load-bearing layer)

| Field | Content |
|-------|---------|
| Approach | Reviewer LLMs assign severity + a consensus filter decides which findings count |
| Severity rubric | `agents/_partials/rubric.md.j2` — **P0**=correctness bug/security/data-loss/CI break; **P1**=incorrect under known inputs, missing tests for new behavior, contract violation; P2/P3=maintainability/nits. Prose rubric, **not pattern-matched** |
| Reasoning discipline | `agents/_partials/reasoning.md.j2` — every P0/P1 needs OBSERVE→TRACE→INFER→CONCLUDE; "if you cannot complete all four, the finding is not yet ready" (`reasoning.md.j2:13`) |
| Consensus filter | `review.md.j2:268-311` — surface match (`file` + `line±5` + **same severity tier**) is semi-mechanical; **reasoning alignment** (do CONCLUDE clauses name the same execution risk?) is LLM judgment |
| Tags | `consensus-passed` (counts) vs `weak-consensus` / `manual-only` (do NOT count) — `review.md.j2:305-311` |
| Severity resolution | On disagreement: all agree→agreed; 2 agree→majority; all differ→middle/P1 (`review.md.j2:297-303`) |
| Trade-off | Judgment against a rubric beats keyword matching for correctness, but the P0-vs-P1-vs-P2 boundary — which fully determines the grade — is unenforceable prose |
| Risk | **medium-high** — this is where grade variance actually lives |

### False-positive guardrails (why the LLM layer is more trustworthy than "just ask the LLM")

- **2-pass redaction** (`review.md.j2:169-244`) — Pass 1 sees the diff with PR title/description **redacted** to neutralize metadata anchoring; Pass 2 restores context and is authoritative (Pass-1-only findings are dropped, "CP10 contract").
- **Pass 1.5 `code-verifier`** (`review.md.j2:195-214`) — a dedicated reduce-only agent makes KEEP/DROP/DEMOTE calls to cut false positives *before* they can inflate P0/P1 counts.
- **Consensus requirement** — a single reviewer's finding is `manual-only` and **does not move the grade**; only findings ≥2 sources corroborate (or the k-of-3 Codex ring, `review.md.j2:246-266`) reach `consensus-passed`.
- **Only P0/P1 count** — noise at P2/P3 cannot tank a grade, so over-reporting low-severity items is grade-neutral.

## ⚠️ Pitfalls

1. **Severity classification is the single load-bearing judgment and it is fully LLM.** The entire grade pivots on P0-vs-P1-vs-P2. A reviewer that systematically under-rates severity ships an inflated grade; over-rating hard-blocks good diffs. The rubric (`rubric.md.j2`) is prose with no enforcement. This is the biggest reliability dependency.
2. **The count→letter step has no Python backstop.** Confirmed by grep: nothing in `src/` counts consensus-passed P0/P1 and emits a letter — the LLM does it from the table in the prompt. Low-complexity, but unverified at runtime (contrast with the project's own atomic-write / schema rails that Python *does* own).
3. **Single-reviewer configs degrade sharply.** When only one reviewer is enabled, the 2-pass redaction *and* Pass 1.5 verifier are **skipped** (`review.md.j2:217-221` "single reviewer — skip Pass 1 + Pass 1.5"), and `consensus-passed` becomes trivially satisfiable by that one voice. The grade then reflects one unchecked LLM opinion.
4. **In autoloop mode a low grade does not hard-block.** `review.md.j2:448` — D/F yields `CHANGES_REQUESTED` + `human_review_needed=true` but **proceeds to wrapup** (does not halt the loop). The grade is a surfaced flag, not a merge gate, inside `/hm:loop`. (Interactive/gated runs stop at the Grade Gate, `review.md.j2:365-378`.)
5. **[INFER] Possible internal tension between Step 4a and Step 4c.** Step 4a candidacy requires the **same severity tier** ("do not bridge tiers", `review.md.j2:276`), yet Step 4c is titled "Severity resolution (when consensus has differing severities)" (`review.md.j2:297`). If cross-tier findings can never become candidates, it is unclear when 4c's differing-severity path fires (perhaps only in ≥3-voter/Codex-relaxation rings). Two reviewers who spot the same bug but split P0/P1 may fail surface match → both demote to `manual-only` → **neither counts toward the grade**, silently improving it. Needs confirmation (see Open Questions).

## ❓ Open Questions

1. Is the Step 4a "same severity tier" gate vs Step 4c "differing severities" resolution a real contradiction, and does it let split-severity duplicates escape the grade as `manual-only`? (Pitfall 5 — needs a fixture trace, not just prose reading.)
2. Should the deterministic count→letter step get a Python backstop (`harness_maker.review_grade.compute(p0, p1) -> str`) that the command calls, so the arithmetic is enforced rather than LLM-executed? Trade-off: adds a rail vs. the project's "LLM owns judgment" bias — but *counting* is not judgment.
3. What is the recommended minimum reviewer count for a trustworthy grade, and should the harness warn when a single-reviewer config disables both redaction and the verifier?
4. Is there empirical grade-variance data (same diff, repeated reviews) anywhere in telemetry to quantify how reproducible the grade actually is?

## 📚 Sources

- Internal code only (no external libraries relevant):
  - `src/harness_maker/templates/stages/review.md.j2` (grade table, consensus filter, grade gate, auto-fix loop)
  - `src/harness_maker/templates/agents/_partials/rubric.md.j2` (severity definitions)
  - `src/harness_maker/templates/agents/_partials/reasoning.md.j2` (OBSERVE→TRACE→INFER→CONCLUDE discipline)
  - `src/harness_maker/templates/agents/_partials/finding_schema.md.j2` (finding severity field)
  - `src/harness_maker/templates/agents/consensus-arbiter_body.md.j2` (consensus tagging contract)
  - `src/harness_maker/models.py:914-918` (`grade_threshold` config, default "A")
  - `src/harness_maker/synthesize.py:703`, `harness-yaml/{Production,Side}.yaml.j2:65` (config plumbing)

## 🔗 Related Internal Docs

- [[project_review_grade_gate]] — memory: review = fix→re-review loop to grade-A gate (neuroTerm Phase 6 model); supersedes the old "D/F just proceed" policy.
