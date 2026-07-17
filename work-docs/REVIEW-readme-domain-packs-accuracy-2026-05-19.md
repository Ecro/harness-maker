---
type: review
task_slug: readme-domain-packs-accuracy
status: APPROVED
created: 2026-05-19
reviewers_invoked: [orchestrator-manual]
consensus_method: single-source (docs-only override)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: readme-domain-packs-accuracy
  computed_at: 2026-05-19T14:30:00+09:00
---

## 🎯 Round 1 Summary

- **Grade:** A
- **Fixes pending:** 0
- **Manual items:** 0
- **Status:** APPROVED → ready for `/hm:wrapup`

**Why no multi-reviewer fan-out.** The diff is two prose bullets (4-line numstat) in `README.md`. `/hm:review`'s own "When to Run" section skips docs-only / single-file changes by default. User invoked it explicitly ("기존 했던 작업 리뷰부터"), so a focused manual review ran instead of code/security/perf/concurrency/ux agents. The cost of spinning up 5 redacted+verified reviewer passes for two README bullets is strictly worse than a careful manual read against the shipped code.

## 🔍 Drift Findings

PLAN scope (Phase 1) declared: `README.md` lines 143 and 358 only. Actual staged diff:

```
 README.md | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)
```

Exactly the two lines named in the PLAN. No other file modified. **Drift = clean.**

## ✅ Consensus Findings

**None.** Every load-bearing factual claim in the new wording was verified against shipped code:

| Claim in new wording | Shipped reality | Evidence |
|---|---|---|
| `--add-domain python` inlines a standards block | python pack inlined via Jinja `{% include %}` | `src/harness_maker/templates/agents/_standards/python.md.j2` exists |
| Into **5** reviewer agents (code, security, performance, concurrency, ux) | Exactly 5 templates have the inline loop, names match | `grep -l "for d in config.project.domains" src/harness_maker/templates/agents/*.j2` returns 5 files; names match the bullet's enumeration verbatim |
| `python` is the only pre-filled sample today | `_SHIPPED_DOMAIN_SAMPLES = frozenset({"python"})` | `src/harness_maker/cli.py:37` |
| `--add-domain <other>` scaffolds a blank stub at `.claude/agents/_standards/<name>.md` | `add_domain()` writes the rendered `_template.md.j2` to that exact path | `src/harness_maker/add_domain.py:135-141` |
| Stubs are user-fillable without forking | Stub template is empty; users edit in place; the inline loop uses `ignore missing` for unknown names | `src/harness_maker/templates/agents/_standards/_template.md.j2` + 5 reviewer body templates |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### M-1 (P3, stylistic — non-blocking)

**File:** `README.md:143` and `README.md:358`
**Observation:** Both new bullets use the temporal hedge "today" / "Today":
- Line 143: "`python` ships as the only sample **today**"
- Line 358: "**Today** `python` is the only pre-filled sample"

**Risk:** Implies impermanence — a reader can infer "the team plans to ship node/rust soon" even though no such commitment exists in the repo. If the project's intent is genuinely "we may ship more packs", keep "today". If the intent is "this is the steady-state design and adding more is the user's job, not ours", swap to "currently" or drop the hedge entirely (`python` is the only pre-filled sample; other domain names scaffold blank stubs…).

**Severity:** P3 — does not change correctness; pure tone/expectation-setting. Manual call by the user.

**Suggestion (if user agrees with "drop the hedge" framing):**
- Line 143: `…inlines a stack-specific standards block into the 5 reviewer agents (code, security, performance, concurrency, ux). \`python\` is the only sample that ships pre-filled; \`--add-domain <other>\` scaffolds a blank user-side stub…`
- Line 358: `…\`python\` is the only pre-filled sample; other domain names scaffold blank user-side stubs that teams fill in without forking harness-maker.`

Not promoted to a fix because it's a single-source observation on a tone choice. The original wording is also defensible.

## 🤝 Disagreements

None — single-orchestrator review.

## 🚨 Orthogonal Concern (out of this PLAN's scope, but surfaced for awareness)

**Subject:** Commit `7f00ace` ("fix: model-routing review fixes…") that landed on `main` HEAD during the `execute` worktree finalize.

**Why surfaced here despite being out of scope:**
- This REVIEW is the first stage with the leverage to halt before `/hm:wrapup`.
- The user has already opened this as a separate concern in conversation and is mid-decision on layered fixes (L1–L4 in the prior turn).
- The README change being reviewed sits on top of `7f00ace` — if user decides to `git reset --soft HEAD~1` to unwind `7f00ace`, the README staged change must survive that operation.

**Verification on safety of unwind:**
- README change is **staged** (in index), not part of `7f00ace`.
- `git reset --soft HEAD~1` moves HEAD back but leaves both `7f00ace`'s contents *and* the staged README change in the index. The README staged hunk is preserved; the model-routing changes would join it in the index.
- So unwinding `7f00ace` is non-destructive to this PLAN's deliverable. The other workflow's user just needs to re-stage / re-commit through its own wrapup path.

**Not auto-applied.** This belongs in a separate `/hm:plan` for the multi-session safety layers — not this REVIEW's auto-fix loop.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 0         | —   |

- Final grade: **A**
- Iterations used: 1 / 3
- Status: **APPROVED**
- `human_review_needed`: **false** (M-1 is P3 stylistic, non-blocking; user can act on it or not)
